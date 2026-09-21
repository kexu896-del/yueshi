from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import (
    APP_VERSION,
    DIAGNOSTICS_FILE,
    FORM_DICTIONARY_VERSION,
    catalog_rule_for,
    INSPECT_ALLOWED,
    DINGDONG_HOME,
    FORBIDDEN_BUTTON_TEXTS,
    FORBIDDEN_URL_HINTS,
    LOG_DIR,
    OUTPUT_DIR,
    PROFILE_DIR,
    QUERY_FILE,
    RESULT_FILE,
    SELECTORS,
)
from models import (
    DiagnosticsLog,
    PriceQueryBatch,
    PriceResultBatch,
    QueryDiagnostics,
    QueryResult,
    SuggestedPurchase,
)
from network_capture import (
    ResponseCollector,
    extract_any_names,
    extract_candidates_from_json,
)
from page_fallback import extract_candidates_from_dom


def load_query(path: Path) -> PriceQueryBatch:
    with path.open("r", encoding="utf-8") as f:
        batch = PriceQueryBatch.model_validate(json.load(f))
    # round58：精简清单展开——空字段从本地目录规则快照补齐；清单已填字段优先。
    for item in batch.items:
        item.apply_catalog_rules(catalog_rule_for(item.ingredient_id))
    return batch


def resolve_query_file(path: Path) -> Path:
    """定位查价清单，不依赖固定文件名。

    优先级：显式参数/拖入路径 > 目录中 price-query.json >
    目录中任何「含 request_id + items 的 JSON」（兼容解压后文件名乱码）。
    """
    if path.exists():
        return path
    if path != QUERY_FILE:
        return path
    if QUERY_FILE.exists():
        return QUERY_FILE
    try:
        for candidate in sorted(QUERY_FILE.parent.glob("*.json")):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and data.get("items") and data.get("request_id"):
                print(f"已自动识别查价清单：{candidate.name}")
                return candidate
    except OSError:
        pass
    return path


def _atomic_write_json(payload_json: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload_json, encoding="utf-8")
    temporary.replace(path)


def export_selfcheck(result_path: Path, request_id: str) -> dict:
    """round58 助手端导出门禁 E01–E06。

    2026-09-18：新增 E06 = 批次级 observed_at 非空（P02 契约缺口修复的助手侧保险），
    完成页"格式校验通过"展示以 E01–E06 全通过为准，属界面层。
    普通用户不需要理解根级字段；自检失败时界面只提示"结果文件格式不完整，
    请回到查价助手重新保存"，字段明细仅出现在导出诊断中。
    返回 {"E01": bool, ..., "E06": bool, "missing": [...]}。
    """
    out = {"E01": False, "E02": False, "E03": False, "E04": False,
           "E05": False, "E06": False, "missing": []}
    try:
        data = json.loads(Path(result_path).read_text(encoding="utf-8"))
    except Exception:
        out["missing"].append("file_unreadable")
        return out
    out["E01"] = data.get("schema_version") == PriceResultBatch.model_fields["schema_version"].default
    if not out["E01"]:
        out["missing"].append("schema_version")
    out["E02"] = data.get("provider") == "dingdong_web"
    if not out["E02"]:
        out["missing"].append("provider")
    out["E03"] = bool(request_id) and data.get("request_id") == request_id
    if not out["E03"]:
        out["missing"].append("request_id")
    results = data.get("results")
    out["E04"] = isinstance(results, list) and (
        len(results) > 0 or data.get("status") in ("partial", "failed"))
    if not out["E04"]:
        out["missing"].append("results")
    try:  # E05：保存后回读并通过同一份模型校验
        PriceResultBatch.model_validate(data)
        out["E05"] = True
    except Exception:
        out["missing"].append("schema_revalidate")
    # E06：批次级 observed_at 非空（缺则提示重新保存）
    out["E06"] = bool(data.get("observed_at"))
    if not out["E06"]:
        out["missing"].append("observed_at")
    return out


def save_result(result: PriceResultBatch, path: Path) -> None:
    """原子输出：先写 tmp，回读校验通过才替换正式文件。
    v2.0 结果瘦身（命名统一与查价质量方案 §八）：
    空字段与等于默认值的重复元数据（provider/data_source/空数组）
    一律省略，正式结果只保留月食采购需要的字段。"""
    text = result.model_dump_json(
        indent=2, exclude_none=True, exclude_defaults=True)
    # round54 根级必填兜底：exclude_defaults 会把取默认值的
    # schema_version/provider 一并裁掉，回读前显式补回——
    # 月食侧规则为「缺 schema_version/provider/request_id 即 price_result_invalid」，
    # 助手导出必须保证三字段恒在。
    payload = json.loads(text)
    payload["schema_version"] = result.schema_version
    payload["provider"] = result.provider
    payload["request_id"] = result.request_id
    # 2026-09-18：三个根级字段恒在（exclude_defaults 会裁掉空数组/默认值）——
    # run_warnings 固定 []；observed_at 与 provider_version 缺省时补空值防 None。
    payload["run_warnings"] = list(result.run_warnings or [])
    payload["observed_at"] = (
        result.observed_at.isoformat() if result.observed_at else None)
    payload["provider_version"] = result.provider_version
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    # 替换前回读校验，确保写出的不是半成品。
    PriceResultBatch.model_validate(json.loads(text))
    _atomic_write_json(text, path)


def save_diagnostics(log: DiagnosticsLog, path: Path = DIAGNOSTICS_FILE) -> None:
    text = log.model_dump_json(indent=2)
    DiagnosticsLog.model_validate(json.loads(text))
    _atomic_write_json(text, path)


class ReadOnlyViolation(RuntimeError):
    """只读门禁触发：检测到交易链路 URL 或受控点击目标为禁止动作。"""


def audit_current_url(page: Page) -> None:
    """URL 审计：命中购物车/结算/支付/下单/领券链路即中止。"""
    lowered = page.url.lower()
    for hint in FORBIDDEN_URL_HINTS:
        if hint in lowered:
            raise ReadOnlyViolation(
                f"只读门禁：当前 URL 命中禁止片段 {hint!r}，已中止运行。"
            )


def guarded_click(locator) -> None:
    """
    本程序唯一允许的点击入口（搜索入口）。
    点击前审计按钮文本，命中禁止动作即拒绝。
    """
    try:
        text = locator.inner_text().strip()
    except Exception:
        text = ""

    for forbidden in FORBIDDEN_BUTTON_TEXTS:
        if forbidden in text:
            raise ReadOnlyViolation(
                f"只读门禁：拒绝点击含禁止文本 {forbidden!r} 的按钮。"
            )

    locator.click()


def find_first(page: Page, selectors: list[str]):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue

    return None


def user_confirms_login_and_delivery(page: Page) -> tuple[bool, bool]:
    """v1.3 定稿：助手不读取、不保存、不验证具体收货地址。
    用户在叮咚网页内自行确认；这里只记录「用户已确认当前配送会话」。
    返回 (登录确认, 配送会话确认)。"""
    print()
    print("浏览器已打开叮咚网页。")
    print("请在浏览器中自行完成以下操作：")
    print("1. 手机号和验证码登录")
    print("2. 在叮咚网页里确认当前收货地址（程序不读取具体地址）")
    print("3. 确认网页能够展示商品和价格")
    print()
    input("完成后回到此窗口，按 Enter 继续；输入 Ctrl+C 可取消。")

    answer = input("你是否已亲自确认登录成功且收货地址正确？[y/N] ")
    confirmed = answer.strip().lower() == "y"

    return confirmed, confirmed


def enter_search(page: Page, query: str) -> bool:
    """
    选择器是占位回退逻辑。
    接口字段如有变动，按实际页面结构收紧。
    """
    search_entry = find_first(page, SELECTORS["search_entry"])
    if search_entry is None:
        return False

    try:
        tag_name = search_entry.evaluate("(el) => el.tagName.toLowerCase()")

        if tag_name != "input":
            guarded_click(search_entry)
            page.wait_for_timeout(500)

        search_input = find_first(page, SELECTORS["search_input"])
        if search_input is None:
            return False

        search_input.fill(query)
        search_input.press("Enter")
        return True

    except Exception:
        return False


SEARCH_RESULT_HINTS = ("searchProduct",)


def _wait_for_search_response(collector: ResponseCollector, page: Page,
                              timeout_s: float = 5.0) -> bool:
    """等待真实搜索结果响应（searchProduct）进入采集器；未出现返回 False。
    用于替代固定等待时长，避免把推荐流（有名无价）误当搜索结果。"""
    steps = max(1, int(timeout_s * 4))
    for _ in range(steps):
        if any(any(h in url for h in SEARCH_RESULT_HINTS)
               for url, _payload in collector.payloads):
            return True
        page.wait_for_timeout(250)
    return False


def _search_once(
    page: Page,
    collector: ResponseCollector,
    query_item,
    term: str,
) -> tuple[list, dict[str, int], list[str], list[dict[str, str]], list[str]]:
    """执行一次搜索并提取候选。
    返回 (合格候选, 累计诊断计数, 页面出现的商品名, 被剔除候选, 原始字段名)。
    收尾防护（方案 §四）：任何 goto 前先确认页面还活着。"""
    collector.clear()

    if page.is_closed():
        raise BrowserSessionLost("搜索前页面已关闭")

    if not enter_search(page, term):
        # 第二次起搜索框结构可能变化：回首页重置后再试一次。
        if page.is_closed():
            raise BrowserSessionLost("搜索重试前页面已关闭")
        try:
            page.goto(DINGDONG_HOME, wait_until="domcontentloaded",
                      timeout=20000)
            page.wait_for_timeout(800)
        except PlaywrightTimeoutError:
            pass

        if page.is_closed():
            raise BrowserSessionLost("搜索重试后页面已关闭")
        if not enter_search(page, term):
            return [], {}, [], [], []

    try:
        # 这里只等待页面和网络进入相对稳定状态。
        page.wait_for_timeout(800)
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except PlaywrightTimeoutError:
        pass

    # round67.1（2026-09-18 实测修复）：平台搜索首击偶发不触发、且 searchProduct
    # 响应可能数秒后才到达；固定 1800ms 会抓到推荐流（有名无价）而误判"未查到"。
    # 改为等待真实搜索结果响应，未出现则重试 Enter（最多 2 次）。
    fired = _wait_for_search_response(collector, page, timeout_s=4.0)
    for _ in range(2):
        if fired:
            break
        try:
            retry_input = find_first(page, SELECTORS["search_input"])
            if retry_input is not None:
                retry_input.press("Enter")
        except Exception:
            pass
        fired = _wait_for_search_response(collector, page, timeout_s=5.0)
    if fired:
        page.wait_for_timeout(400)  # 等响应体处理完

    candidates = []
    stats = {
        "json_node_examined_count": 0,
        "relevant_count": 0,
        "excluded_count": 0,
        "unpriced_count": 0,
        "unavailable_count": 0,
    }
    seen_names: list[str] = []
    dropped: list[dict[str, str]] = []
    raw_fields: list[str] = []

    for response_url, payload in collector.payloads:
        extracted, payload_stats, payload_dropped, payload_fields = (
            extract_candidates_from_json(
                payload=payload,
                query_item=query_item,
                source_url=response_url,
                matched_query=term,
            )
        )
        candidates.extend(extracted)
        for key, value in payload_stats.items():
            stats[key] = stats.get(key, 0) + value
        for d in payload_dropped:
            if len(dropped) < 10 and d not in dropped:
                dropped.append(d)
        for k in payload_fields:
            if k not in raw_fields:
                raw_fields.append(k)
        for n in extract_any_names(payload):
            if n not in seen_names:
                seen_names.append(n)

    # 网络解析不足时，回退到 DOM（DOM 无 product_id，仅供诊断）。
    if not candidates:
        dom_candidates, dom_stats = extract_candidates_from_dom(
            page=page,
            query_item=query_item,
            matched_query=term,
        )
        candidates.extend(dom_candidates)
        for key, value in dom_stats.items():
            stats[key] = stats.get(key, 0) + value

    return candidates, stats, seen_names, dropped, raw_fields


# 效率门禁（v1.3）：主词取得至少 3 个合格候选即停止，不再搜索别名。
ELIGIBLE_STOP_COUNT = 3


def collect_one_query(
    page: Page,
    collector: ResponseCollector,
    query_item,
) -> tuple[QueryResult, QueryDiagnostics]:
    """逐级召回：主词合格 SKU ≥3 即停止，不足再顺序尝试别名（最多 3 个词）。
    返回 (正式结果, 诊断)；诊断只进 logs/price-diagnostics.json。"""
    search_terms = query_item.effective_search_terms()
    attempted: list[str] = []
    all_candidates = []
    total_stats = {
        "json_node_examined_count": 0,
        "relevant_count": 0,
        "excluded_count": 0,
        "unpriced_count": 0,
        "unavailable_count": 0,
    }
    seen_names: list[str] = []
    dropped: list[dict[str, str]] = []
    raw_fields: list[str] = []
    matched_query: str | None = None
    search_input_missing = False

    for tier, term in enumerate(search_terms):
        attempted.append(term)
        candidates, stats, names, term_dropped, term_fields = _search_once(
            page, collector, query_item, term,
        )

        if not stats and not candidates and not names:
            search_input_missing = True

        for key in total_stats:
            total_stats[key] += stats.get(key, 0)
        for n in names:
            if n not in seen_names:
                seen_names.append(n)
        for d in term_dropped:
            if len(dropped) < 10 and d not in dropped:
                dropped.append(d)
        for k in term_fields:
            if k not in raw_fields:
                raw_fields.append(k)

        if candidates:
            all_candidates.extend(candidates)
            if matched_query is None:
                matched_query = term

        # 效率门禁：合格 SKU ≥3 即提前停止，不耗尽全部搜索词。
        if len(all_candidates) >= ELIGIBLE_STOP_COUNT:
            break

    def _diagnostics() -> QueryDiagnostics:
        return QueryDiagnostics(
            ingredient_id=query_item.ingredient_id,
            attempted_queries=attempted,
            matched_query=matched_query,
            counts=total_stats,
            raw_field_names=raw_fields,
            dropped=dropped,
        )

    if search_input_missing and not attempted:
        return QueryResult(
            ingredient_id=query_item.ingredient_id,
            query=query_item.query,
            status="parse_failed",
            attempted_queries=attempted,
            warnings=["SEARCH_INPUT_NOT_FOUND"],
        ), _diagnostics()

    # 去重：按 product_id；无 id 回退按名称+规格+价格。
    unique = {}
    for candidate in all_candidates:
        key = candidate.product_id or (
            f"{candidate.product_name}|{candidate.package_text}"
            f"|{candidate.listed_price_yuan}"
        )
        unique.setdefault(key, candidate)

    # round67.1：截断前按语义三态排序（accepted 优先），
    # 避免推荐流（review_required 证据）挤占名额把真实商品截断掉。
    _decision_rank = {"accepted": 0, "review_required": 1, "rejected": 2, None: 3}
    final_candidates = sorted(unique.values(), key=lambda c: (
        _decision_rank.get(c.candidate_decision, 3),
        0 if c.eligible_for_purchase else 1,
    ))[: min(query_item.max_candidates, 3)]

    # round67：没有 accepted 候选（只剩 rejected/review_required 证据）时不得标 success，
    # 按 candidates_filtered 返回并保留证据，供月食选择层回退参考估价。
    has_accepted = any(
        (c.candidate_decision == "accepted")
        or (c.candidate_decision is None and c.eligible_for_purchase)
        for c in final_candidates)
    if final_candidates and not has_accepted:
        return QueryResult(
            ingredient_id=query_item.ingredient_id,
            query=query_item.query,
            status="candidates_filtered",
            attempted_queries=attempted,
            matched_query=None,
            match_strategy="none",
            candidates=final_candidates,
            warnings=["NO_ACCEPTED_CANDIDATE", "REASON:仅剩 rejected/review_required 候选"],
        ), _diagnostics()

    if not final_candidates:
        # 分阶段诊断状态：定位“抓不到”的真正原因。
        if total_stats["json_node_examined_count"] == 0:
            status = "search_empty"
            reason = "接口未捕获或页面无结果"
        elif total_stats["relevant_count"] == 0:
            status = "candidates_filtered"
            reason = "有返回但全部相关/排除词过滤"
        elif total_stats["unpriced_count"] >= total_stats["relevant_count"] > 0:
            status = "candidates_unpriced"
            reason = "相关候选均无价格"
        elif (total_stats["unavailable_count"] > 0
              and total_stats["unavailable_count"]
              >= total_stats["relevant_count"] - total_stats["unpriced_count"]):
            status = "candidates_unavailable"
            reason = "相关候选均售罄或无库存证据"
        else:
            status = "no_match"
            reason = "无合格 SKU（缺 id/价/规格/库存证据）"

        warnings = ["NO_RELIABLE_PRODUCT_CANDIDATE", f"REASON:{reason}"]
        if seen_names:
            warnings.append("SEEN:" + ";".join(seen_names[:8])[:300])

        return QueryResult(
            ingredient_id=query_item.ingredient_id,
            query=query_item.query,
            status=status,
            attempted_queries=attempted,
            matched_query=None,
            match_strategy="none",
            warnings=warnings,
        ), _diagnostics()

    match_strategy = "primary" if matched_query == query_item.query else "alias_tier"

    _enrich_candidates(final_candidates)
    # v1.7：诊断 dropped 中被后续召回/恢复价格的商品打 recovered 标记，
    # 避免维护者把「先无价后有价」误判为漏采。
    final_names = {c.product_name for c in final_candidates}
    for d in dropped:
        if d.get("name") in final_names:
            d["recovered"] = "true"

    suggestion = _suggest_purchase(query_item, final_candidates)
    # v2.0：建议采用宽泛同类候选时必须明示，不得冒充精确命中。
    substitution_notice = None
    if suggestion is not None and suggestion.match_quality == "category_fallback":
        substitution_notice = (
            f"建议商品「{suggestion.product_name}」为同类候选，"
            f"非「{query_item.query}」精确命中；"
            "月食侧请确认菜单允许同类替代。"
        )

    return QueryResult(
        ingredient_id=query_item.ingredient_id,
        query=query_item.query,
        status="success",
        attempted_queries=attempted,
        matched_query=matched_query,
        match_strategy=match_strategy,
        candidates=final_candidates,
        suggested_purchase=suggestion,
        substitution_notice=substitution_notice,
        dictionary_suggestions=_dictionary_suggestions(
            query_item, final_candidates, dropped),
    ), _diagnostics()


def _enrich_candidates(candidates) -> None:
    """v1.7：为候选补充 元/100g 单价（仅当克重与价格都可确认）。"""
    for c in candidates:
        if c.listed_price_yuan is not None and c.reference_grams:
            c.unit_price_yuan_per_100g = round(
                c.listed_price_yuan / c.reference_grams * 100, 2)


def _suggest_purchase(query_item, candidates):
    """v1.7：满足 required_grams 的最低总价组合（单一 SKU、整份购买）。
    无 required_grams 或无可用候选时返回 None。

    v2.0 推荐门槛（通用食材库方案 §五，匹配质量先于价格）：
    - 宽泛同类（category_fallback）只在清单允许同类替代、
      且没有 exact/alias 候选时才可进入建议；
    - 设置 allowed_forms 时，建议只在形态正向匹配（form_match=exact）
      的候选中挑选；形态无法确认的候选不自动推荐；
    - 价格只在同一门槛等级内比较。"""
    required = query_item.required_grams
    if not required:
        return None
    pool = [c for c in candidates
            if c.match_quality in ("exact", "alias")]
    if not pool and query_item.category_substitution_allowed:
        pool = [c for c in candidates
                if c.match_quality == "category_fallback"]
    if query_item.allowed_forms:
        form_matched = [c for c in pool if c.form_match == "exact"]
        if form_matched:
            pool = form_matched
        else:
            pool = []
    best = None
    for c in pool:
        if not (c.eligible_for_purchase and c.listed_price_yuan
                and c.reference_grams):
            continue
        packages = math.ceil(required / c.reference_grams)
        total = round(packages * c.listed_price_yuan, 2)
        suggestion = SuggestedPurchase(
            product_id=c.product_id,
            product_name=c.product_name,
            packages=packages,
            total_grams=round(packages * c.reference_grams, 1),
            total_price_yuan=total,
            unit_price_yuan_per_100g=c.unit_price_yuan_per_100g,
            total_count_text=_total_count_text(c.count_text, packages),
            package_text=c.package_text,
            match_quality=c.match_quality,
            purchase_note=c.purchase_note,
        )
        if best is None or total < best.total_price_yuan:
            best = suggestion
    return best


_COUNT_TEXT_RE = re.compile(r"(\d+)\s*(枚|件|只|条|盒|袋|瓶)")


def _total_count_text(count_text: str | None, packages: int) -> str | None:
    """盒数 × 单件枚数 → 总枚数原文（如 2 盒 × 12枚 = 24枚）。
    重量与枚数不一致或解析缺失时不估算，返回 None。"""
    if not count_text:
        return None
    hit = _COUNT_TEXT_RE.search(count_text)
    if not hit:
        return None
    return f"{int(hit.group(1)) * packages}{hit.group(2)}"


def _dictionary_suggestions(query_item, candidates, dropped) -> list[dict]:
    """v2.0 字典建议闭环（通用食材库方案 §七）：
    助手只生成建议，不自动回写主库；需人工确认后入库并提升 catalog_version。

    - new_alias：同一非主词稳定命中 ≥2 个合格商品，建议审核为别名；
    - parent_category_query：命中词来自 search_scope（大品类召回词，如「酸奶」「面包」），
      不是食材等价别名，只建议登记为父品类搜索词（round68）；
    - negation_exception：否定前缀商品被硬排除词误伤，建议审核豁免规则。"""
    suggestions: list[dict] = []
    scope_terms = set()
    scope = getattr(query_item, "search_scope", None) or {}
    for key in ("category_query", "fallback_category_query"):
        if scope.get(key):
            scope_terms.add(scope[key])
    term_hits: dict[str, list[str]] = {}
    for c in candidates:
        if not c.match_reason or not c.match_reason.startswith("term:"):
            continue
        term = c.match_reason[5:]
        if term == query_item.query or term in query_item.aliases:
            continue
        term_hits.setdefault(term, [])
        if c.product_name not in term_hits[term]:
            term_hits[term].append(c.product_name)
    for term, names in sorted(term_hits.items()):
        if len(names) >= 2:
            is_parent = term in scope_terms
            suggestions.append({
                "ingredient_id": query_item.ingredient_id,
                "type": ("parent_category_query" if is_parent else "new_alias"),
                "relation_type": ("parent_category" if is_parent else "synonym_candidate"),
                "usage": ("search_recall_only" if is_parent else "requires_review"),
                "value": term,
                "evidence_count": len(names),
                "example_products": names[:3],
            })
    for d in dropped:
        name = d.get("name", "")
        if (d.get("reason") == "hard_excluded"
                and any(neg in name for neg in ("免", "无", "不含", "未", "去"))):
            suggestions.append({
                "ingredient_id": query_item.ingredient_id,
                "type": "negation_exception",
                "value": name,
                "evidence_count": 1,
                "example_products": [name],
            })
    return suggestions


def _diff_price_changes(previous: dict, results, per_query_diag=()) -> list[dict]:
    """v1.7：与上一次同 request_id 的结果对比，输出价格变化清单。
    previous 为上一次结果文件反序列化后的 dict。
    v1.8：统一以 ingredient_id 为稳定连接键，display_query 仅供显示。
    v2.0：每条变化带 change_reason——只有同一 product_id 连续观察到
    不同价格才标 up/down；「本次未选入」不得表述为下架。"""
    old_prices = {}   # (ingredient_id, product_id) -> (name, query, price)
    for r in previous.get("results", []):
        for c in r.get("candidates", []):
            pid = c.get("product_id")
            price = c.get("listed_price_yuan")
            if pid and price is not None:
                old_prices[(r.get("ingredient_id"), pid)] = (
                    c.get("product_name"), r.get("query"), price)
    # 本次被规则过滤 / 售罄的商品名（按食材分组），用于区分 removed 原因。
    dropped_names: dict[str, set[str]] = {}
    soldout_names: dict[str, set[str]] = {}
    for diag in per_query_diag:
        bucket = dropped_names.setdefault(diag.ingredient_id, set())
        for d in diag.dropped:
            reason = d.get("reason", "")
            if "availability_sold_out" in reason:
                soldout_names.setdefault(
                    diag.ingredient_id, set()).add(d.get("name", ""))
            else:
                bucket.add(d.get("name", ""))
    changes: list[dict] = []
    seen = set()
    for r in results:
        for c in r.candidates:
            if not c.product_id or c.listed_price_yuan is None:
                continue
            key = (r.ingredient_id, c.product_id)
            seen.add(key)
            old = old_prices.get(key)
            if old is None:
                changes.append({
                    "ingredient_id": r.ingredient_id,
                    "display_query": r.query,
                    "product_name": c.product_name,
                    "change": "new", "change_reason": "newly_observed",
                    "new_price": c.listed_price_yuan,
                })
            elif abs(c.listed_price_yuan - old[2]) > 1e-9:
                changes.append({
                    "ingredient_id": r.ingredient_id,
                    "display_query": r.query,
                    "product_name": c.product_name,
                    "change": ("down" if c.listed_price_yuan < old[2]
                               else "up"),
                    "change_reason": "price_update",
                    "old_price": old[2], "new_price": c.listed_price_yuan,
                })
    for (ingredient_id, pid), (name, query, price) in old_prices.items():
        if (ingredient_id, pid) not in seen:
            # removed ≠ 下架：能定位到本次证据的，如实标注原因。
            if name in soldout_names.get(ingredient_id, set()):
                reason = "unavailable"
            elif name in dropped_names.get(ingredient_id, set()):
                reason = "filtered_by_rule"
            else:
                reason = "no_longer_in_top_candidates"
            changes.append({
                "ingredient_id": ingredient_id,
                "display_query": query,
                "product_name": name,
                "change": "removed", "change_reason": reason,
                "old_price": price,
            })
    return changes


def _system_browser_exe() -> str | None:
    """按常见安装路径直接查找系统 Chrome / Edge 可执行文件。
    不依赖 Playwright 的 channel 注册表探测（实测在部分机器上会漏判）。"""
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pfx = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    lad = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(pf) / "Google/Chrome/Application/chrome.exe",
        Path(pfx) / "Google/Chrome/Application/chrome.exe",
        Path(lad) / "Google/Chrome/Application/chrome.exe",
        Path(pf) / "Microsoft/Edge/Application/msedge.exe",
        Path(pfx) / "Microsoft/Edge/Application/msedge.exe",
        # 企业电脑常见：无管理员权限时 Edge 装在每用户目录。
        Path(lad) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for exe in candidates:
        if exe.exists():
            return str(exe)
    # 兜底：让系统 PATH 自己找（覆盖绿色版/自定义安装位置）。
    for name in ("chrome.exe", "chrome", "msedge.exe", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


# 浏览器启动诊断（脱敏：只记类型与沙箱状态，不记路径/用户名）。
_LAST_BROWSER_INFO: dict = {"source": "unknown", "sandbox_enabled": "unknown"}


def last_browser_info() -> dict:
    return dict(_LAST_BROWSER_INFO)


def _launch_persistent(playwright, **kwargs):
    """浏览器解析顺序：系统 Chrome/Edge 可执行文件 → channel 探测
    → 内置 Chromium（打包时可选携带）。全部失败给出人话错误。
    安全门禁（发布要求）：显式启用浏览器沙箱，绝不传 --no-sandbox。"""
    kwargs.setdefault("chromium_sandbox", True)
    global _LAST_BROWSER_INFO
    exe = _system_browser_exe()
    if exe:
        try:
            context = playwright.chromium.launch_persistent_context(
                executable_path=exe, **kwargs)
            _LAST_BROWSER_INFO = {
                "source": ("edge_system" if "edge" in exe.lower()
                           else "chrome_system"),
                "sandbox_enabled": True,
            }
            return context
        except Exception:
            pass
    for channel in ("chrome", "msedge"):
        try:
            context = playwright.chromium.launch_persistent_context(
                channel=channel, **kwargs)
            _LAST_BROWSER_INFO = {
                "source": f"channel_{channel}", "sandbox_enabled": True}
            return context
        except Exception:
            continue
    try:
        context = playwright.chromium.launch_persistent_context(**kwargs)
        _LAST_BROWSER_INFO = {
            "source": "bundled_chromium", "sandbox_enabled": True}
        return context
    except Exception as exc:
        raise RuntimeError(
            "未找到可用的浏览器：请安装 Microsoft Edge 或 Chrome 后重试。"
        ) from exc


def open_browser_session(inspect_mode: bool = False):
    """打开浏览器会话（复用本机登录态）。
    供窗口模式使用：登录和查价共用同一窗口，避免二次打开。
    调用方负责 close_browser_session。必须在同一线程内使用返回的对象。"""
    playwright = sync_playwright().start()
    context = _launch_persistent(
        playwright,
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={"width": 430, "height": 900},
        device_scale_factor=1,
        locale="zh-CN",
        slow_mo=80,
    )
    pages = context.pages
    page = pages[0] if pages else context.new_page()
    collector = ResponseCollector(inspect_mode=inspect_mode)
    page.on("response", collector.handle_response)
    page.goto(DINGDONG_HOME, wait_until="domcontentloaded", timeout=30000)
    audit_current_url(page)
    return playwright, context, page, collector


def close_browser_session(session) -> None:
    """唯一关闭入口（方案 §四：所有关闭动作集中到一个控制器）。
    先移除监听器，再关 context / 停 playwright；全程吞错。"""
    playwright, context = session[0], session[1]
    page = session[2] if len(session) > 2 else None
    collector = session[3] if len(session) > 3 else None
    if page is not None and collector is not None:
        try:
            page.remove_listener("response", collector.handle_response)
        except Exception:
            pass
    try:
        context.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass


class QueryCancelled(Exception):
    """用户在界面点击取消：中止剩余查询。"""


class BrowserSessionLost(RuntimeError):
    """查询途中浏览器窗口/页面被关闭或崩溃：剩余查询无法继续。"""


LOGIN_HINT_SELECTORS = ["text=请登录", "text=立即登录", "text=登录/注册",
                        "text=登录"]


def session_needs_login(page: Page) -> bool:
    """启发式判断叮咚会话是否失效：首页出现登录入口即视为需要登录。"""
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass
    for selector in LOGIN_HINT_SELECTORS:
        try:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return True
        except Exception:
            continue
    return False


def execute_batch(page, collector, batch, progress_callback=None):
    """逐项查询并审计，返回 (结果列表, 诊断列表)。支持取消。"""
    results = []
    per_query_diag: list[QueryDiagnostics] = []
    for index, query_item in enumerate(batch.items, start=1):
        print(f"[{index}/{len(batch.items)}] 正在查询：{query_item.query}")
        if progress_callback is not None:
            try:
                progress_callback(index, len(batch.items), query_item.query)
            except QueryCancelled:
                raise
            except Exception:
                pass
        try:
            if page.is_closed():
                raise BrowserSessionLost(
                    f"查询「{query_item.query}」前页面已关闭")
            result, diag = collect_one_query(
                page=page, collector=collector, query_item=query_item)
            audit_current_url(page)
        except QueryCancelled:
            raise
        except PlaywrightError as exc:
            # 浏览器被用户关掉、页面崩溃或会话断开：转换成人话错误，
            # 由界面层提示「重新点开始查询」而不是抛底层堆栈。
            raise BrowserSessionLost(
                f"查询「{query_item.query}」时浏览器连接中断") from exc
        results.append(result)
        per_query_diag.append(diag)
    return results, per_query_diag


RUN_SUMMARY_FILE = LOG_DIR / "run-summary.json"


def _search_stage(result, diag) -> str:
    """round67 精简诊断阶段（§14.5）：不猜测，按结果状态与三态计数映射。"""
    counts = {"accepted": 0, "rejected": 0, "review_required": 0}
    for c in result.candidates:
        if c.candidate_decision in counts:
            counts[c.candidate_decision] += 1
    if result.status == "success":
        return "accepted_candidates_found"
    if result.status == "candidates_filtered":
        if counts["review_required"] > 0 and counts["accepted"] == 0:
            return "review_required_only"
        return "all_rejected"
    if result.status == "search_empty":
        return "search_not_triggered"
    if result.status in ("candidates_unpriced", "candidates_unavailable"):
        return "candidates_recalled"
    return "no_results"


def write_run_summary(batch, results, per_query_diag, completed_at) -> None:
    """窗口模式精简诊断：逐项状态 + 三态计数（不含原始响应/敏感字段）。"""
    diag_by_id = {d.ingredient_id: d for d in per_query_diag}
    items = []
    for r in results:
        counts = {"accepted": 0, "rejected": 0, "review_required": 0}
        for c in r.candidates:
            if c.candidate_decision in counts:
                counts[c.candidate_decision] += 1
        d = diag_by_id.get(r.ingredient_id)
        items.append({
            "ingredient_id": r.ingredient_id,
            "status": r.status,
            "search_stage": _search_stage(r, d),
            "attempted_queries": list(getattr(d, "attempted_queries", []) or []) if d else [],
            "decisions": counts,
        })
    doc = {
        "request_id": batch.request_id,
        "completed_at": completed_at.isoformat(),
        "query_count": len(items),
        "items": items,
    }
    _atomic_write_json(json.dumps(doc, ensure_ascii=False, indent=1), RUN_SUMMARY_FILE)


def finish_and_save(batch, results, per_query_diag, started_at,
                    login_confirmed, delivery_confirmed, output_file,
                    inspect_mode: bool = False,
                    write_diagnostics: bool = True,
                    search_response_count: int = 0,
                    cache_hit_count: int = 0) -> None:
    """组装正式结果并原子写出；诊断日志默认写（CLI），
    窗口模式传 False——诊断仅在用户主动导出时生成。"""
    completed_at = datetime.now().astimezone()

    # v1.7：同一 request_id 重复查询时，与上次结果对比价格变化。
    price_changes: list[dict] = []
    if output_file.exists():
        try:
            previous = json.loads(output_file.read_text(encoding="utf-8"))
            if previous.get("request_id") == batch.request_id:
                price_changes = _diff_price_changes(
                    previous, results, per_query_diag)
        except Exception:
            pass  # 旧文件损坏或结构不符：跳过 diff，不影响本次写出

    result_batch = PriceResultBatch(
        request_id=batch.request_id,
        started_at=started_at,
        completed_at=completed_at,
        observed_at=completed_at,  # 2026-09-18：批次级观察时间
        provider_version=APP_VERSION,
        login_confirmed_by_user=login_confirmed,
        delivery_context_confirmed_by_user=delivery_confirmed,
        results=results,
        run_warnings=[],
        price_changes=price_changes,
        catalog_version=batch.catalog_version,
        form_dictionary_version=(
            batch.form_dictionary_version or FORM_DICTIONARY_VERSION),
    )
    save_result(result_batch, output_file)
    print(f"结果已写入：{output_file}")

    # round67：窗口模式也写精简诊断（逐项状态与三态计数，不含原始响应），
    # 便于失败时一眼定位「搜索未触发 / 全被过滤 / 仅剩待复核」。
    try:
        write_run_summary(batch, results, per_query_diag, completed_at)
    except Exception:
        pass

    if not write_diagnostics:
        return

    save_diagnostics(DiagnosticsLog(
        request_id=batch.request_id,
        completed_at=completed_at,
        # v2.0：实时接口响应计数来自采集器本身，不再用遍历节点数冒充。
        search_response_count=search_response_count,
        cache_hit_count=cache_hit_count,
        recovered_record_count=sum(
            1 for d in per_query_diag for item in d.dropped
            if item.get("recovered") == "true"),
        unique_sku_count=sum(len(r.candidates) for r in results),
        eligible_sku_count=sum(
            1 for r in results for c in r.candidates
            if c.eligible_for_purchase),
        filtered_count=sum(
            d.counts.get("excluded_count", 0) for d in per_query_diag),
        parse_warnings=sorted({
            w for r in results for c in r.candidates
            for w in c.parse_warnings
        }),
        per_query=per_query_diag,
        extras={
            "inspect_mode": inspect_mode,
            "query_count": len(batch.items),
            "successful_query_count": sum(
                1 for item in results if item.status == "success"),
        },
    ))


def run(
    query_file: Path,
    output_file: Path | None = None,
    inspect_mode: bool = False,
    confirm_callback=None,
    progress_callback=None,
    login_only: bool = False,
) -> int:
    """
    confirm_callback：可选，替换命令行确认流程（供窗口模式使用）。
    签名 confirm_callback(page) -> (login_confirmed, delivery_context_confirmed)。
    progress_callback：可选，进度回调 progress_callback(index, total, query_text)，
    用于界面显示"正在查询 北豆腐 (3/10)"；登录等待不计入。
    login_only：True 时只打开浏览器让用户登录并确认地址，随后关闭返回（不查价）。
    v1.3：助手不读取具体收货地址，只记录用户已确认当前配送会话。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    query_file = resolve_query_file(query_file)
    # 输出写到输入文件旁，不要求用户理解 output 目录。
    if output_file is None:
        output_file = query_file.parent / "月食-叮咚价格结果.json"
    if login_only and not query_file.exists():
        # 仅登录流程允许清单缺失。
        batch = PriceQueryBatch(request_id="login-only", items=[])
    else:
        batch = load_query(query_file)
    started_at = datetime.now().astimezone()

    with sync_playwright() as playwright:
        context = _launch_persistent(
            playwright,
            user_data_dir=str(PROFILE_DIR),
            headless=False,

            # 移动网页视口，不等于控制手机 App。
            viewport={"width": 430, "height": 900},
            device_scale_factor=1,
            locale="zh-CN",

            # 调试阶段可保留少量 slow_mo。
            slow_mo=80,
        )

        pages = context.pages
        page = pages[0] if pages else context.new_page()

        collector = ResponseCollector(inspect_mode=inspect_mode)
        page.on("response", collector.handle_response)

        page.goto(
            DINGDONG_HOME,
            wait_until="domcontentloaded",
            timeout=30000,
        )
        audit_current_url(page)

        confirm = confirm_callback or user_confirms_login_and_delivery
        login_confirmed, delivery_confirmed = confirm(page)

        if not login_confirmed:
            print("未确认登录，本次不执行查询。")
            context.close()
            return 2

        if login_only:
            # 仅登录：会话已写入浏览器用户数据目录，下次查价直接复用。
            context.close()
            return 0

        results, per_query_diag = execute_batch(
            page, collector, batch, progress_callback)

        finish_and_save(
            batch, results, per_query_diag, started_at,
            login_confirmed, delivery_confirmed, output_file,
            inspect_mode=inspect_mode,
            search_response_count=collector.search_response_count,
            cache_hit_count=collector.cache_hit_count)

        if inspect_mode:
            print("开发者日志已写入 logs/。")

        context.close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="月食叮咚只读价格查询助手"
    )
    parser.add_argument(
        "--query",
        type=Path,
        default=QUERY_FILE,
        help="价格查询 JSON 文件",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULT_FILE,
        help="价格结果 JSON 文件",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="记录脱敏后的候选 JSON 响应，供首次适配",
    )

    args = parser.parse_args()

    if args.inspect and not INSPECT_ALLOWED:
        print("当前为正式版本，开发者模式未启用。")
        return 1

    try:
        return run(
            query_file=args.query,
            output_file=args.output,
            inspect_mode=args.inspect and INSPECT_ALLOWED,
        )
    except ReadOnlyViolation as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("\n用户取消。")
        return 130
    except Exception as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
