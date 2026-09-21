"""price-result.json 校验器（P01–P08 门禁 + price_result_hash 计算）。

职责（契约见 references/price-provider-policy.md）：
- 结构校验：price-result.json 必须符合 schemas/price-result.schema.json（契约版本 price_data_version = 1.2）；
- 批次匹配：request_id 必须与本次采购需求一致（P08）；
- 单项门禁：P02 必需字段 / P03 规格可解析 / P04 单位确认 / P05 价格类型不混写 /
  P06 售罄剔除 / P07 相关性与排除词；
- 哈希：对规范化字节计算 sha256，写入 plan.json 的 price_snapshot_meta.result_hash。

结果文件损坏 / Schema 不符 / 哈希不匹配 → provider_status = invalid_result，
拒绝结果但不判菜单损坏（不记 corrupted_plan_json）。

用法：
    python3 scripts/price_result_validator.py RESULT_JSON [--request-id ID] [--query QUERY_JSON]
退出码：0 全部通过；2 存在候选级/单项级拒绝（批次仍可用）；3 结果文件整体无效。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RESULT_SCHEMA = os.path.join(BASE, "schemas", "price-result.schema.json")
QUERY_SCHEMA = os.path.join(BASE, "schemas", "price-query.schema.json")

PRICE_DATA_VERSION = "1.2"

# 严重解析警告：命中即不得标 direct_public_price（policy §5.10）
SEVERE_PARSE_WARNINGS = {
    "PRICE_UNIT_UNCONFIRMED",
    "PRICE_UNRESOLVED",
    "PACKAGE_WEIGHT_UNRESOLVED",
}


def compute_price_result_hash(result_path: str) -> str:
    """对 price-result.json 规范化字节计算 sha256（排序键 + 紧凑分隔符）。"""
    with open(result_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_structure(result: dict) -> list[str]:
    """draft-07 结构校验；jsonschema 不可用时做最小必需字段检查。"""
    schema = _load_json(RESULT_SCHEMA)
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
                for e in validator.iter_errors(result)]
    except ImportError:  # pragma: no cover - 环境回退
        errors = []
        for field in schema["required"]:
            if field not in result:
                errors.append(f"<root>: 缺必需字段 {field}")
        return errors


def check_candidate_gates(candidate: dict, query_item: dict | None,
                          delivery_context_confirmed: bool = False,
                          batch_observed_at: str | None = None) -> list[str]:
    """候选级 P02–P07 检查；返回违例代码列表（空 = 通过）。

    delivery_context_confirmed：批次级「用户已确认当前配送会话」
    （delivery_context_confirmed_by_user，policy §5 条件 6）。
    v1.2 起不再读取具体地址。

    batch_observed_at：批次级观察时间（2026-09-18 修复 P02 契约缺口）。
    v2.0 结果瘦身允许候选省略 observed_at，统一用批次时间；
    判定口径 = 候选级 observed_at 或批次级 observed_at 至少一个存在。
    """
    violations: list[str] = []

    # round67：语义门禁明确 rejected 的候选是证据而非正式候选，不再逐项报 P02–P07；
    # 选择层只从 accepted 中选（scripts/purchase_selector.py）。
    if candidate.get("candidate_decision") == "rejected":
        return violations

    # P02：direct_public_price 必需字段（provider / observed_at / 配送会话已确认）
    if not (candidate.get("observed_at") or batch_observed_at):
        violations.append("P02_MISSING_OBSERVED_AT")
    if not delivery_context_confirmed:
        violations.append("P02_DELIVERY_CONTEXT_UNCONFIRMED")

    # P03：包装计算候选必须有可解析规格
    warnings = set(candidate.get("parse_warnings") or [])
    if candidate.get("reference_grams") is None and candidate.get("reference_milliliters") is None:
        violations.append("P03_PACKAGE_UNRESOLVED")

    # P04：价格单位必须显式确认（Provider 端已拒绝未登记单位的数值价格）
    if "PRICE_UNIT_UNCONFIRMED" in warnings:
        violations.append("P04_PRICE_UNIT_UNCONFIRMED")
    if candidate.get("listed_price_yuan") is None and "PRICE_UNRESOLVED" in warnings:
        violations.append("P04_PRICE_UNRESOLVED")

    # P05：普通价/活动价/会员价不得混写 —— price_type 必须与唯一非空价一致
    price_type = candidate.get("price_type", "unknown")
    typed = {
        "regular": candidate.get("regular_price_yuan"),
        "promotion": candidate.get("promotion_price_yuan"),
        "member": candidate.get("member_price_yuan"),
    }
    if price_type in typed and typed[price_type] is None and candidate.get("listed_price_yuan") is None:
        violations.append("P05_PRICE_TYPE_MISMATCH")

    # P06：售罄商品不得作为正式采购候选；正式候选须满足 eligible SKU 门槛
    if candidate.get("availability") == "sold_out":
        violations.append("P06_SOLD_OUT")
    elif (candidate.get("availability") == "available"
          and candidate.get("eligible_for_purchase") is False):
        violations.append("P06_NOT_ELIGIBLE_SKU")

    # P07：相关性与排除词（对照查询文件的 positive_terms / hard_excluded_terms，
    # 兼容旧字段 aliases / excluded_terms）
    if query_item:
        name = candidate.get("product_name") or ""
        terms = ([query_item.get("query", "")]
                 + list(query_item.get("positive_terms") or query_item.get("aliases") or []))
        if terms and not any(t and t in name for t in terms):
            violations.append("P07_IRRELEVANT_PRODUCT")
        excludes = (query_item.get("hard_excluded_terms")
                    or query_item.get("excluded_terms") or [])
        if any(t and t in name for t in excludes):
            violations.append("P07_EXCLUDED_TERM")

    # policy §5.10：严重解析警告 → 不得标 direct_public_price
    if warnings & SEVERE_PARSE_WARNINGS:
        violations.append("P05_SEVERE_PARSE_WARNING")

    # P09（round65，规则 ID：FORM-001）：商品形态门——与 helper / 合并层共用
    # data/ingredient-catalog.json + data/product-form-dictionary.json；
    # 命中排除形态或限制形态不在 allowed_forms 内的商品不得作为采购候选。
    if query_item and query_item.get("ingredient_id"):
        try:
            from product_forms import match_product
        except ImportError:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
            from product_forms import match_product
        fm = match_product(query_item["ingredient_id"],
                           candidate.get("product_name") or "")
        candidate["form_match"] = fm["verdict"]
        if fm["verdict"] == "rejected":
            candidate["eligible_for_purchase"] = False
            violations.append("P09_FORM_" + (fm["reason_code"] or "rejected").upper())

    return violations


def validate_result(result_path: str, request_id: str | None = None,
                    query_path: str | None = None) -> dict:
    """整批校验。返回 {provider_status, rejected, candidate_violations, result_hash?}。"""
    try:
        result = _load_json(result_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"provider_status": "invalid_result",
                "errors": [f"结果文件不可读或 JSON 损坏: {exc}"],
                "rejected": True}

    errors = validate_structure(result)
    if errors:
        return {"provider_status": "invalid_result", "errors": errors, "rejected": True}

    # P08：request_id 必须匹配本次采购需求
    if request_id and result.get("request_id") != request_id:
        return {"provider_status": "invalid_result",
                "errors": [f"P08 request_id 不匹配: {result.get('request_id')!r} != {request_id!r}"],
                "rejected": True}

    query_items: dict[str, dict] = {}
    if query_path:
        try:
            query = _load_json(query_path)
            q_errors = []
            try:
                import jsonschema
                q_errors = [e.message for e in
                            jsonschema.Draft7Validator(_load_json(QUERY_SCHEMA)).iter_errors(query)]
            except ImportError:
                pass
            if q_errors:
                return {"provider_status": "invalid_result",
                        "errors": [f"查询文件不符合 price-query Schema: {m}" for m in q_errors],
                        "rejected": True}
            query_items = {item["ingredient_id"]: item for item in query.get("items", [])}
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            return {"provider_status": "invalid_result",
                    "errors": [f"查询文件不可读: {exc}"], "rejected": True}

    # §5 条件 6：批次级配送会话确认（round48 起不再读取具体地址）
    delivery_context_confirmed = result.get("delivery_context_confirmed_by_user") is True
    # 2026-09-18：批次级观察时间（根级 observed_at 优先，回退 completed_at）
    batch_observed_at = result.get("observed_at") or result.get("completed_at")

    candidate_violations: dict[str, list[str]] = {}
    success_count = 0
    for item in result.get("results", []):
        if item.get("status") == "success":
            success_count += 1
        for cand in item.get("candidates", []):
            v = check_candidate_gates(cand, query_items.get(item.get("ingredient_id")),
                                      delivery_context_confirmed=delivery_context_confirmed,
                                      batch_observed_at=batch_observed_at)
            if v:
                key = f"{item.get('ingredient_id')}::{cand.get('product_name')}"
                candidate_violations[key] = v

    statuses = {item.get("status") for item in result.get("results", [])}
    if statuses and statuses <= {"login_required", "address_unconfirmed"}:
        provider_status = "user_action_required"
    elif success_count == 0 and statuses:
        provider_status = "unavailable"
    elif success_count and len(statuses) > 1:
        provider_status = "partial"
    else:
        provider_status = "success" if success_count else "unavailable"

    return {
        "provider_status": provider_status,
        "errors": [],
        "rejected": False,
        "candidate_violations": candidate_violations,
        "result_hash": compute_price_result_hash(result_path),
        "price_data_version": PRICE_DATA_VERSION,
        "delivery_context_confirmed_by_user": delivery_context_confirmed,
        "batch_observed_at": batch_observed_at,
        "provider_version": result.get("provider_version"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="price-result.json P01–P08 校验与哈希")
    parser.add_argument("result", help="price-result.json 路径")
    parser.add_argument("--request-id", default=None, help="期望的 request_id（P08）")
    parser.add_argument("--query", default=None, help="price-query.json 路径（P07 对照）")
    args = parser.parse_args()

    report = validate_result(args.result, request_id=args.request_id,
                             query_path=args.query)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["rejected"]:
        return 3
    if report.get("candidate_violations"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
