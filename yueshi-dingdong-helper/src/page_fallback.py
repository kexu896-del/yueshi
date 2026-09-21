from __future__ import annotations

from datetime import datetime

from playwright.sync_api import Locator, Page

from config import SELECTORS
from models import ProductCandidate, PriceQueryItem
from normalizer import normalize_text, parse_package, parse_price
from network_capture import is_eligible_sku


def first_existing(root: Page | Locator, selectors: list[str]) -> Locator | None:
    for selector in selectors:
        locator = root.locator(selector)
        try:
            if locator.count() > 0:
                return locator
        except Exception:
            continue

    return None


def first_text(root: Locator, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            locator = root.locator(selector)
            if locator.count() > 0:
                text = normalize_text(locator.first.inner_text())
                if text:
                    return text
        except Exception:
            continue

    return None


def extract_candidates_from_dom(
    page: Page,
    query_item: PriceQueryItem,
    matched_query: str | None = None,
) -> tuple[list[ProductCandidate], dict[str, int]]:
    stats = {
        "sku_record_count": 0,
        "relevant_count": 0,
        "excluded_count": 0,
        "unpriced_count": 0,
        "unavailable_count": 0,
    }
    card_locator = first_existing(page, SELECTORS["product_card"])
    if card_locator is None:
        return [], stats

    candidates: list[ProductCandidate] = []
    positive_terms = query_item.effective_positive_terms()
    hard_excludes = query_item.effective_hard_excludes()
    card_count = min(card_locator.count(), query_item.max_candidates * 3)

    for index in range(card_count):
        card = card_locator.nth(index)

        name = first_text(card, SELECTORS["product_name"])
        if not name:
            continue

        stats["sku_record_count"] += 1

        if any(term in name for term in hard_excludes):
            stats["excluded_count"] += 1
            continue

        if positive_terms and not any(term in name for term in positive_terms):
            continue

        stats["relevant_count"] += 1

        package_text = first_text(card, SELECTORS["package_text"])
        price_text = first_text(card, SELECTORS["price"])

        package = parse_package(package_text)
        if package.reference_grams is None and package.reference_milliliters is None:
            name_package = parse_package(name)
            if (name_package.reference_grams is not None
                    or name_package.reference_milliliters is not None):
                if package_text is None:
                    package_text = name
                package = name_package

        # DOM 价格来自页面展示文本，单位是元。
        price = parse_price(price_text, unit="yuan")

        availability = "available"
        for selector in SELECTORS["sold_out"]:
            try:
                if card.locator(selector).count() > 0:
                    availability = "sold_out"
                    break
            except Exception:
                pass

        warnings = list(package.warnings)
        if price is None:
            warnings.append("PRICE_UNRESOLVED")
            stats["unpriced_count"] += 1
        if availability == "sold_out":
            stats["unavailable_count"] += 1

        candidate = ProductCandidate(
            ingredient_id=query_item.ingredient_id,
            query=query_item.query,
            matched_query=matched_query,
            product_name=name,
            package_text=package.package_text,
            reference_grams=package.reference_grams,
            reference_milliliters=package.reference_milliliters,
            package_count=package.package_count,
            listed_price_yuan=price,
            price_type="regular" if price is not None else "unknown",
            availability=availability,
            # 只保留 URL 主体，去掉可能含个人信息的查询参数。
            product_url=page.url.split("?", 1)[0],
            observed_at=datetime.now().astimezone(),
            data_source="page_dom",
            parse_warnings=warnings,
        )
        # DOM 候选没有 product_id，按 SKU 门槛不进入正式候选（仅供侦察）。
        candidate.eligible_for_purchase = is_eligible_sku(candidate)
        if not candidate.eligible_for_purchase:
            continue

        candidates.append(candidate)

        if len(candidates) >= query_item.max_candidates:
            break

    return candidates, stats
