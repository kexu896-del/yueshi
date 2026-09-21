"""外部价格 Provider 路由器（纯函数，不启动浏览器）。

实现 references/price-provider-policy.md 的运行时部分：
- price_provider_priority 回退链（§2）；
- provider_status → 既有门禁三类（auto_fix / user_input_required / fatal）映射（§4）；
- provider 与 price_basis 分离赋值（§2.1、§5）；
- price_snapshot_meta 构建（§6）。

Skill 只通过本模块消费 price-result.json；浏览器与页面细节由外部助手管理。
"""
from __future__ import annotations

# §2 价格来源优先级（高 → 低）
PRICE_PROVIDER_PRIORITY = (
    "dingdong_web_direct",
    "other_public_direct",
    "category_estimate",
    "historical_estimate",
)

# §2.1 provider（数据来源）枚举 —— 与 price_basis（证据等级）分离
PROVIDERS = (
    "dingdong_web",
    "public_market_page",
    "historical_cache",
    "category_model",
)

PRICE_BASIS_LEVELS = (
    "direct_public_price",
    "direct_public_price_limited",
    "category_estimate",
    "historical_estimate",
)

# §4 Provider 状态枚举
PROVIDER_STATUSES = (
    "success",
    "partial",
    "user_action_required",
    "unavailable",
    "invalid_result",
)

# §5.10 严重解析警告：命中即不得标 direct_public_price
SEVERE_PARSE_WARNINGS = frozenset({
    "PRICE_UNIT_UNCONFIRMED",
    "PRICE_UNRESOLVED",
    "PACKAGE_WEIGHT_UNRESOLVED",
})

DIRECT_PRICE_REQUIRED_FIELDS = (
    "product_name",
    "package_text",
    "listed_price_yuan",
    "observed_at",
    "availability",
    "provider",
    "data_source",
)


def map_provider_status(provider_status: str, user_requires_live_price: bool = False) -> dict:
    """§4：Provider 状态映射进既有三类门禁，不扩大 fatal_reason 枚举。

    返回 {"gate_result": ..., "fallback": ...}：
    - user_action_required：用户明确要求叮咚实时价 → user_input_required；否则允许降级；
    - unavailable / invalid_result：降级到后备价格层，永不判 fatal；
    - invalid_result 不得记为 corrupted_plan_json。
    """
    if provider_status not in PROVIDER_STATUSES:
        raise ValueError(f"未知 provider_status: {provider_status!r}")

    if provider_status == "user_action_required":
        if user_requires_live_price:
            return {"gate_result": "user_input_required", "fallback": None,
                    "reason": "验证码/地址/会话需用户操作，且用户明确要求实时叮咚价格"}
        return {"gate_result": "auto_fix", "fallback": "category_estimate",
                "reason": "用户未强制实时价，允许降级到后备价格层"}

    if provider_status == "unavailable":
        return {"gate_result": "auto_fix", "fallback": "category_estimate",
                "reason": "Provider 页面不可读，不判 fatal，走后备价格层"}

    if provider_status == "invalid_result":
        return {"gate_result": "auto_fix", "fallback": "category_estimate",
                "reason": "抓价结果无效，拒绝该结果且不污染 plan.json；不判菜单损坏"}

    # success / partial：可用部分正常进入价格层
    return {"gate_result": "auto_fix" if provider_status == "partial" else "success",
            "fallback": "category_estimate" if provider_status == "partial" else None,
            "reason": "无结果食材按回退链降级" if provider_status == "partial" else ""}


def assign_price_basis(candidate: dict, address_confirmed: bool) -> str:
    """§5：按收紧条件判定候选的证据等级。

    - 全部必需字段齐备、可换算规格、eligible SKU 门槛通过（eligible_for_purchase=true）、
      配送会话已经用户确认（delivery_context_confirmed_by_user）、无严重警告 → direct_public_price；
    - 有价格但规格解析失败 / eligible 未通过 → direct_public_price_limited（不得进入包装组合求解）；
    - 配送会话未经用户确认 → 至多 direct_public_price_limited，展示文案只能写
      "页面参考价，配送会话未完成确认"，不纳入正式预算锁定。

    address_confirmed 参数应传入批次级 delivery_context_confirmed_by_user
    （用户已在叮咚网页确认当前配送会话；v1.2 起不再读取具体地址）。
    """
    warnings = set(candidate.get("parse_warnings") or [])
    has_convertible = (
        candidate.get("reference_grams") is not None
        or candidate.get("reference_milliliters") is not None
    )
    complete = all(candidate.get(f) is not None for f in DIRECT_PRICE_REQUIRED_FIELDS)
    # eligible SKU 门槛（§7 P06）：契约 1.1 候选显式给出 eligible_for_purchase；
    # 缺省时按五要素推算（product_id + 名称 + 价格 + 可换算规格 + 可售）
    eligible = candidate.get("eligible_for_purchase")
    if eligible is None:
        eligible = bool(
            candidate.get("product_id")
            and candidate.get("product_name")
            and candidate.get("listed_price_yuan") is not None
            and has_convertible
            and candidate.get("availability") == "available"
        )
    sellable = candidate.get("availability") == "available" and eligible

    if complete and sellable and not (warnings & SEVERE_PARSE_WARNINGS):
        if has_convertible and address_confirmed:
            return "direct_public_price"
        return "direct_public_price_limited"

    if candidate.get("listed_price_yuan") is not None:
        return "direct_public_price_limited"

    raise ValueError("候选无可用价格，应走回退链而非赋值 price_basis")


def ordinary_payable_price(candidate: dict) -> float | None:
    """§5：预算按普通应付价；会员价/活动价不得默认当作预算价。"""
    if candidate.get("regular_price_yuan") is not None:
        return candidate["regular_price_yuan"]
    if candidate.get("price_type") == "regular" and candidate.get("listed_price_yuan") is not None:
        return candidate["listed_price_yuan"]
    return None


def build_price_snapshot_meta(result_batch: dict, result_hash: str,
                              provider_version: str) -> dict:
    """§6：构建 plan.json 的 price_snapshot_meta 块（契约 1.2 配送会话确认）。"""
    return {
        "provider": result_batch.get("provider", "dingdong_web"),
        # 2026-09-18：调用方未传时回退读取结果根级 provider_version（助手侧新增）
        "provider_version": provider_version or result_batch.get("provider_version"),
        "result_schema_version": result_batch.get("schema_version", "1.2"),
        "delivery_context_confirmed_by_user": result_batch.get(
            "delivery_context_confirmed_by_user", False),
        # 2026-09-18：批次级 observed_at 优先，回退 completed_at
        "observed_at": result_batch.get("observed_at") or result_batch.get("completed_at"),
        "source_mode": "live",
        "request_id": result_batch.get("request_id"),
        "result_hash": result_hash,
    }
