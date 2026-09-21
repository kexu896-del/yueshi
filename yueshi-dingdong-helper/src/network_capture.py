from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Response

from config import (
    MAX_RESPONSE_PREVIEW_CHARS,
    NETWORK_LOG_FILE,
    PRICE_FIELD_UNITS,
    PRODUCT_RESPONSE_URL_HINTS,
    RESTRICTIVE_FORMS,
    detect_forms,
    detect_conditional_accept,
    conditional_accept_note,
)
from normalizer import normalize_text, parse_package, parse_price
from models import ProductCandidate, PriceQueryItem
from semantics import evaluate_candidate


SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "cookies",
    "mobile",
    "phone",
    "telephone",
    "sms_code",
    "verification_code",
    "address_detail",
}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                result[key] = "[REDACTED]"
            else:
                result[key] = redact(child)
        return result

    if isinstance(value, list):
        return [redact(item) for item in value[:30]]

    return value


def appears_product_related(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in PRODUCT_RESPONSE_URL_HINTS)


def write_inspection_record(
    response: Response,
    body: Any,
    output_file: Path = NETWORK_LOG_FILE,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "observed_at": datetime.now().astimezone().isoformat(),
        "url": response.url,
        "status": response.status,
        "content_type": response.headers.get("content-type"),
        "preview": redact(body),
    }

    serialized = json.dumps(record, ensure_ascii=False)
    if len(serialized) > MAX_RESPONSE_PREVIEW_CHARS:
        serialized = serialized[:MAX_RESPONSE_PREVIEW_CHARS] + "...[TRUNCATED]"

    with output_file.open("a", encoding="utf-8") as f:
        f.write(serialized + "\n")


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def first_value(obj: dict, candidate_keys: tuple[str, ...]) -> Any:
    return first_value_with_key(obj, candidate_keys)[1]


def first_value_with_key(
    obj: dict,
    candidate_keys: tuple[str, ...],
) -> tuple[str | None, Any]:
    """返回 (命中的候选字段名, 值)，供价格单位门禁按字段名查单位。"""
    key_map = {str(k).lower(): k for k in obj}

    for candidate in candidate_keys:
        original_key = key_map.get(candidate.lower())
        if original_key is not None:
            value = obj.get(original_key)
            if value not in (None, "", [], {}):
                return candidate, value

    return None, None


def is_eligible_sku(candidate: ProductCandidate) -> bool:
    """正式 SKU 门槛：有 id + 商品名 + 可确认当前价 + 可解析规格 + 至少一种库存证据。
    聚合面板/联想项（无价格或无库存证据）不得进入正式候选，不占 max_candidates。"""
    return all((
        candidate.product_id,
        candidate.product_name,
        candidate.listed_price_yuan is not None,
        candidate.reference_grams is not None
        or candidate.reference_milliliters is not None,
        # P06：售罄不得作为正式采购候选；unknown 无库存证据同样不合格。
        candidate.availability == "available",
    ))


_NEGATION_PREFIXES = ("免", "无", "不含", "未", "去")


def _is_hard_excluded(name: str, hard_excludes: list[str]) -> bool:
    """硬排除词命中商品名即拒绝，但跳过否定前缀场景：
    「免腌制」「无添加」「不含防腐剂」「未腌制」不应被「腌制/添加」等词误伤。"""
    for term in hard_excludes:
        start = 0
        while True:
            idx = name.find(term, start)
            if idx < 0:
                break
            prefix = name[max(0, idx - 2):idx]
            if not any(prefix.endswith(neg) for neg in _NEGATION_PREFIXES):
                return True
            start = idx + 1
    return False


def _append_dropped(dropped: list[dict[str, str]], name: str, reason: str) -> None:
    """诊断 dropped 列表按 (name, reason) 去重，同一 SKU 不重复记录。"""
    if len(dropped) >= 10:
        return
    if any(d.get("name") == name and d.get("reason") == reason for d in dropped):
        return
    dropped.append({"name": name, "reason": reason})


def extract_candidates_from_json(
    payload: Any,
    query_item: PriceQueryItem,
    source_url: str,
    matched_query: str | None = None,
) -> tuple[list[ProductCandidate], dict[str, int], list[dict[str, str]], list[str]]:
    """
    已按 2026-08-26 真实 search/searchProduct 响应确认字段映射：
    名称 = name；当前价 = price（字符串，元）；原价 = origin_price；
    会员价 = vip_price；规格 = net_weight + net_weight_unit（缺失回退商品名解析）；
    库存 = today_stockout（布尔）/ stock_number、station_stock（数值）。

    返回 (正式候选, 分阶段诊断计数, 被剔除候选[{name,reason}], 原始字段名)。
    诊断数据只进 logs/price-diagnostics.json，不进正式结果。
    语义过滤：positive_terms 命中其一即相关；hard_excluded_terms 命中即硬拒绝。
    """
    stats = {
        # v2.0 改名（原 sku_record_count 名不副实）：遍历到的 JSON 商品节点数。
        "json_node_examined_count": 0,
        "relevant_count": 0,
        "excluded_count": 0,
        "unpriced_count": 0,
        "unavailable_count": 0,
    }
    candidates: list[ProductCandidate] = []
    dropped: list[dict[str, str]] = []
    raw_fields: list[str] = []
    positive_terms = query_item.effective_positive_terms()
    hard_excludes = query_item.effective_hard_excludes()
    # v2.0 匹配质量分层：exact（精确词）> alias（审核别名）> broad（宽泛上位词）。
    exact_set = {query_item.query, *query_item.exact_terms}
    alias_set = set(query_item.aliases)
    # v2.0 形态门禁（词典识别，替代 v1.9 纯关键词包含）：
    # excluded_forms 命中即拒；allowed_forms 设置后，识别出的限制性形态
    # 不在允许清单内同样拒绝（鸡腿块不能冒充整腿进入候选）。
    excluded_form_set = set(query_item.excluded_forms)
    allowed_form_set = set(query_item.allowed_forms)
    seen_pids: set[str] = set()   # 进入解析即按 product_id 去重
    count_re = re.compile(r"\d+\s*(?:枚|件|只|条|盒|袋|瓶)")

    for obj in walk_dicts(payload):
        name = first_value(obj, ("name", "product_name", "title"))

        if not isinstance(name, str):
            continue

        name = normalize_text(name)
        if not name:
            continue

        stats["json_node_examined_count"] += 1

        # 同一 SKU 重复出现（多接口/多节点）只处理一次。
        pid_raw = first_value(
            obj,
            ("product_id", "productid", "goods_id", "goodsid",
             "item_id", "itemid", "sku_id", "skuid", "id"),
        )
        if pid_raw is not None:
            pid_str = str(pid_raw)
            if pid_str in seen_pids:
                continue
            seen_pids.add(pid_str)

        # 硬排除词（熟食/预制/腌制/水饺等）优先拒绝；否定前缀（免/无/不含）不误伤。
        if _is_hard_excluded(name, hard_excludes):
            stats["excluded_count"] += 1
            _append_dropped(dropped, name, "hard_excluded")
            continue

        # 形态识别（v2.0 词典）：排除形态命中即拒；allowed_forms 设置后，
        # 识别出的限制性形态不在允许清单内同样拒（鸡腿块 ≠ 整腿）。
        detected_forms = detect_forms(name)
        if excluded_form_set and any(f in excluded_form_set
                                     for f in detected_forms):
            stats["excluded_count"] += 1
            _append_dropped(dropped, name, "excluded_form")
            continue
        if allowed_form_set:
            disallowed = [f for f in detected_forms
                          if f in RESTRICTIVE_FORMS
                          and f not in allowed_form_set]
            if disallowed:
                stats["excluded_count"] += 1
                _append_dropped(dropped, name,
                                f"form_not_allowed:{'|'.join(disallowed)}")
                continue

        # 语义相关：命中任一 positive term；记录命中词供类别审计。
        # round67：有 acceptance_profile 时，名称命中只作召回参考——
        # 大品类召回（如「酸奶」搜出「裸酸奶」「0蔗糖酸奶」）不得因未逐字命中而丢弃，
        # 相关性由语义门禁三态判断。
        profile = getattr(query_item, "acceptance_profile", None)
        matched_term = next(
            (t for t in positive_terms if t in name), None)
        if positive_terms and matched_term is None and not profile:
            continue

        stats["relevant_count"] += 1

        net_weight = first_value(obj, ("net_weight",))
        net_weight_unit = first_value(obj, ("net_weight_unit",))
        if net_weight not in (None, ""):
            package_text = f"{net_weight}{normalize_text(net_weight_unit) or ''}"
        else:
            package_text = normalize_text(
                first_value(obj, ("spec", "specification", "package_text"))
            ) or None

        package = parse_package(package_text)
        if package.reference_grams is None and package.reference_milliliters is None:
            # 回退：从商品名解析规格（叮咚商品名普遍带“400g/份”等字样）。
            name_package = parse_package(name)
            if (name_package.reference_grams is not None
                    or name_package.reference_milliliters is not None):
                if package_text is None:
                    package_text = name
                package = name_package

        price_field, price_raw = first_value_with_key(
            obj,
            (
                "price",
                "sale_price",
                "sell_price",
                "current_price",
                "real_price",
                "final_price",
            ),
        )
        # 价格单位门禁：仅使用 PRICE_FIELD_UNITS 中显式登记的单位。
        price_unit = (
            PRICE_FIELD_UNITS.get(price_field.lower())
            if price_field
            else None
        )
        price = parse_price(price_raw, unit=price_unit)

        # 已确认字段：origin_price = 划线原价，vip_price = 会员价（均为元）。
        origin_price = parse_price(
            first_value(obj, ("origin_price",)), unit="yuan")
        member_price = parse_price(
            first_value(obj, ("vip_price",)), unit="yuan")
        if member_price is not None and member_price == price:
            member_price = None

        # 价格分类（v1.2 修正）：
        # vip 字段明确存在且低于当前价 → member；
        # 当前价低于原价 → promotion（当前价记为促销价，原价记常规价）；
        # 否则 regular。
        regular_price = origin_price
        promotion_price = None
        if price is None:
            price_type = "unknown"
        elif member_price is not None and member_price < price:
            price_type = "member"
        elif origin_price is not None and price < origin_price:
            price_type = "promotion"
            promotion_price = price
        else:
            price_type = "regular"
            if regular_price is None:
                regular_price = price

        product_id = first_value(
            obj,
            (
                "product_id",
                "productid",
                "goods_id",
                "goodsid",
                "item_id",
                "itemid",
                "sku_id",
                "skuid",
                "id",
            ),
        )

        # 库存字段已确认：today_stockout 布尔=今日售罄；stock_number / station_stock
        # 数值为站点库存。语义不符时不猜，保持 unknown。
        stock_raw = first_value(
            obj,
            (
                "stock_number",
                "station_stock",
                "today_stockout",
                "stock",
            ),
        )
        availability = "unknown"
        if stock_raw is not None and not isinstance(stock_raw, (dict, list)):
            lowered_keys = {str(k).lower(): k for k in obj}
            today_stockout = obj.get(lowered_keys.get("today_stockout", ""))
            if today_stockout in (True, 1, "1", "true"):
                availability = "sold_out"
            elif isinstance(stock_raw, bool):
                availability = "unknown"
            elif isinstance(stock_raw, (int, float)):
                availability = "available" if stock_raw > 0 else "sold_out"
            elif isinstance(stock_raw, str):
                stock_text = stock_raw.lower()
                if any(x in stock_text for x in ("售罄", "无货", "sold_out")):
                    availability = "sold_out"
                elif any(x in stock_text for x in ("有货", "available", "on_sale")):
                    availability = "available"

        warnings = list(package.warnings)
        if (
            isinstance(price_raw, (int, float))
            and price_field
            and price_unit is None
        ):
            # 数值型价格字段未在 PRICE_FIELD_UNITS 登记，不允许猜测单位。
            warnings.append("PRICE_UNIT_UNCONFIRMED")
        if price is None:
            warnings.append("PRICE_UNRESOLVED")
            stats["unpriced_count"] += 1
        if availability == "unknown":
            warnings.append("AVAILABILITY_UNRESOLVED")
        elif availability == "sold_out":
            stats["unavailable_count"] += 1

        count_hit = count_re.search(name) or (
            count_re.search(package_text) if package_text else None)

        # v2.0 匹配质量：宽泛上位词命中不得冒充精确命中。
        if matched_term in exact_set:
            match_quality = "exact"
        elif matched_term in alias_set:
            match_quality = "alias"
        elif matched_term is not None:
            match_quality = "category_fallback"
        elif profile:
            # round67：大品类召回命中（名称未逐字含查询词），由验收档案决定三态。
            match_quality = "category_fallback"
        else:
            match_quality = "low_confidence"
        # 形态匹配结论：设置 allowed_forms 时，识别形态正向命中才算 exact；
        # 未识别到形态为 acceptable（可保留但不参与自动建议）。
        if allowed_form_set and any(f in allowed_form_set
                                    for f in detected_forms):
            form_match = "exact"
        else:
            form_match = "acceptable"

        candidate = ProductCandidate(
            ingredient_id=query_item.ingredient_id,
            query=query_item.query,
            matched_query=matched_query,
            product_id=str(product_id) if product_id is not None else None,
            product_name=name,
            package_text=package.package_text,
            reference_grams=package.reference_grams,
            reference_milliliters=package.reference_milliliters,
            package_count=package.package_count,
            listed_price_yuan=price,
            regular_price_yuan=regular_price,
            promotion_price_yuan=promotion_price,
            member_price_yuan=member_price,
            price_type=price_type,
            availability=availability,
            # v2.0 结果瘦身：搜索接口 URL 打不开具体商品，不进正式结果。
            product_url=None,
            # 抓取时间统一使用批次 completed_at。
            observed_at=None,
            data_source="network_response",
            parse_warnings=warnings,
            match_reason=(f"term:{matched_term}" if matched_term else None),
            count_text=count_hit.group(0) if count_hit else None,
            match_quality=match_quality,
            product_form=("|".join(detected_forms) if detected_forms else None),
            form_match=form_match,
            # round54：本体合格但附独立调味包 → 条件接受 + 购买备注
            conditional_accept=detect_conditional_accept(name),
            purchase_note=conditional_accept_note(name) or None,
        )
        candidate.eligible_for_purchase = is_eligible_sku(candidate)

        # round67：有验收档案时执行商品语义三态（名称命中只用于召回）。
        # rejected / review_required 均保留为候选证据（不进建议购买），
        # 由月食选择层记录差异并只从 accepted 中选。
        profile = getattr(query_item, "acceptance_profile", None)
        if profile:
            decision, evidence, reasons = evaluate_candidate(candidate.product_name, profile)
            candidate.candidate_decision = decision
            candidate.evidence = evidence
            candidate.rejection_reasons = reasons
            if decision == "rejected":
                stats["excluded_count"] += 1
                _append_dropped(dropped, name,
                                "semantic:" + ("|".join(reasons) or "rejected"))
                candidate.eligible_for_purchase = False
            elif decision == "review_required":
                candidate.eligible_for_purchase = False

        for k in sorted(map(str, obj.keys())):
            if k not in raw_fields:
                raw_fields.append(k)

        # 聚合面板/无价节点不进入正式候选，不占名额（仅诊断日志可见）；
        # round67：有语义三态的候选（accepted/rejected/review_required）保留为证据。
        if not candidate.eligible_for_purchase and candidate.candidate_decision is None:
            reasons = []
            if not candidate.product_id:
                reasons.append("no_id")
            if candidate.listed_price_yuan is None:
                reasons.append("unpriced")
            if (candidate.reference_grams is None
                    and candidate.reference_milliliters is None):
                reasons.append("spec_unresolved")
            if candidate.availability != "available":
                reasons.append(f"availability_{candidate.availability}")
            _append_dropped(dropped, name, ",".join(reasons) or "not_eligible")
            continue

        candidates.append(candidate)

    # 去重：优先按 product_id；无 id 候选不进入正式结果（eligible 门槛已挡）。
    unique: dict[str, ProductCandidate] = {}
    for candidate in candidates:
        key = candidate.product_id or (
            f"{candidate.product_name}|{candidate.package_text}"
            f"|{candidate.listed_price_yuan}"
        )
        unique.setdefault(key, candidate)

    ordered = list(unique.values())
    # v2.0 排序原则（通用食材库方案 §二）：先匹配质量（exact > alias >
    # category_fallback > low_confidence），再形态匹配，价格只在同等级内比较。
    # round67：语义三态优先（accepted > review_required > rejected），
    # 保证最终截断时 accepted 候选优先保留。
    quality_rank = {"exact": 0, "alias": 1, "category_fallback": 2,
                    "low_confidence": 3, None: 4}
    form_rank = {"exact": 0, "acceptable": 1, "rejected": 2, None: 3}
    decision_rank = {"accepted": 0, "review_required": 1, "rejected": 2, None: 3}
    ordered.sort(key=lambda c: (
        decision_rank.get(c.candidate_decision, 3),
        quality_rank.get(c.match_quality, 4),
        form_rank.get(c.form_match, 3),
    ))
    return ordered, stats, dropped, raw_fields


def extract_any_names(payload: Any, limit: int = 8) -> list[str]:
    """诊断用：不做相关性过滤，收集响应里出现的商品名。

    用于 no_match 时回答“页面实际返回了什么”，只进 warnings 日志。
    """
    names: list[str] = []
    for obj in walk_dicts(payload):
        name = first_value(obj, ("name", "product_name", "title"))
        if isinstance(name, str):
            text = normalize_text(name)
            if text and text not in names:
                names.append(text)
                if len(names) >= limit:
                    break
    return names


class ResponseCollector:
    def __init__(self, inspect_mode: bool = False):
        self.inspect_mode = inspect_mode
        self.payloads: list[tuple[str, Any]] = []
        # v2.0 诊断口径修正：被接受的主搜索接口实时响应个数，
        # 其中命中浏览器缓存（Service Worker）的单独计数。
        self.search_response_count = 0
        self.cache_hit_count = 0

    # 只解析商品搜索接口，其余页面响应不存（v1.8 诊断瘦身：
    # 实测粗放宽进来 2024 个原始对象、唯一 SKU 仅 9）。
    MAX_FALLBACK_PAYLOADS = 4

    def handle_response(self, response: Response) -> None:
        try:
            url = response.url.lower()
            is_search_api = "searchproduct" in url
            if not is_search_api and not (
                    appears_product_related(response.url)
                    and len(self.payloads) < self.MAX_FALLBACK_PAYLOADS):
                return
            content_type = response.headers.get("content-type", "").lower()
            if "json" not in content_type:
                return

            payload = response.json()

            if is_search_api:
                # 实时接口查询被接受才累加；缓存命中单独统计（方案 §六）。
                self.search_response_count += 1
                try:
                    if response.from_service_worker:
                        self.cache_hit_count += 1
                except Exception:
                    pass

            if self.inspect_mode and appears_product_related(response.url):
                write_inspection_record(response, payload)

            self.payloads.append((response.url, payload))

        except Exception:
            # 页面中会有大量与任务无关的响应，单个解析失败不应终止整个查询。
            return

    def clear(self) -> None:
        self.payloads.clear()
