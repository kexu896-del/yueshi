#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月食采购选择层（round67，2026-09-18）

职责（references/price-provider-policy.md §7/§12）：
- 查价助手负责找（候选证据），商品语义门禁负责判（accepted/rejected/review_required），
  本选择层负责选：**最终采购建议只从 accepted 候选中生成**；
- 助手的 eligible_for_purchase / suggested_purchase 不再视为最终结论；
- 记录助手候选与最终商品的选择差异（selection_change_reason_codes），禁止静默替换；
- 无 accepted 候选 → 返回 fallback_to_estimate（由上游按参考价估算或替换同功能食材）。

用法：
  python scripts/purchase_selector.py --result price-result.json [--query price-query.json] \
      [--out final-selection.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))

from common.product_semantics import evaluate_candidate, load_profiles  # noqa: E402
from price_provider_router import ordinary_payable_price  # noqa: E402

CHANGE_REASON_CODES = (
    "smaller_package", "lower_waste", "product_form_correction",
    "species_conflict_rejected", "prepared_food_rejected",
    "ordinary_price_preferred", "better_required_amount_fit",
    "fallback_to_estimate",
)


def _decision_for(candidate, profile, revalidate=False):
    """新助手输出 candidate_decision；旧结果回退到语义门禁/eligible 字段。
    revalidate=True 时忽略结果内已有判定，用本地当前门禁重评（用于旧结果复评）。"""
    decision = candidate.get("candidate_decision")
    if not revalidate and decision in ("accepted", "rejected", "review_required"):
        return decision, candidate.get("evidence") or {}, list(candidate.get("rejection_reasons") or [])
    if profile:
        return evaluate_candidate(candidate.get("product_name", ""), profile)
    # 无概念档案：保守回退（旧字段只作参考，形态被拒或未标合格 → review_required）
    if candidate.get("form_match") == "rejected" or candidate.get("eligible_for_purchase") is False:
        return "rejected", {}, ["product_form_correction"]
    if candidate.get("eligible_for_purchase") is True:
        return "accepted", {
            "identity": {"status": "matched", "note": "legacy_eligible"},
            "composition": {"status": "unknown"},
            "processing": {"status": "unknown"},
            "attribute_evidence": {},
        }, []
    return "review_required", {}, ["insufficient_identity_evidence"]


def _package_total(candidate, required_grams):
    price = ordinary_payable_price(candidate)
    if price is None:
        return None
    grams = candidate.get("reference_grams")
    if not grams or grams <= 0:
        return float(price), 1
    n = max(1, int((required_grams + grams - 1) // grams)) if required_grams else 1
    return float(price) * n, n


def select_item(item, query_item, profile, revalidate=False):
    """单食材选择：返回 {status, final_selection, provider_suggestion, change_reasons, rejected}。"""
    required = (query_item or {}).get("required_grams") or 0
    evaluated = []
    for cand in item.get("candidates", []):
        decision, evidence, reasons = _decision_for(cand, profile, revalidate)
        evaluated.append({"candidate": cand, "decision": decision,
                          "evidence": evidence, "reasons": reasons})

    accepted = [e for e in evaluated if e["decision"] == "accepted"]
    rejected = [e for e in evaluated if e["decision"] == "rejected"]
    review = [e for e in evaluated if e["decision"] == "review_required"]

    if not accepted:
        return {
            "status": "fallback_to_estimate",
            "final_selection": None,
            "provider_suggestion": item.get("suggested_purchase"),
            "change_reasons": ["fallback_to_estimate"],
            "review_required": [e["candidate"].get("product_name") for e in review],
            "rejected": [{"product_name": e["candidate"].get("product_name"),
                          "reasons": e["reasons"]} for e in rejected],
        }

    def rank(e):
        cost = _package_total(e["candidate"], required)
        total = cost[0] if cost else float("inf")
        unit = e["candidate"].get("unit_price_yuan_per_100g")
        return (total, unit if unit is not None else float("inf"),
                -(e["candidate"].get("reference_grams") or 0))

    accepted.sort(key=rank)
    chosen = accepted[0]["candidate"]
    chosen_cost = _package_total(chosen, required)

    suggestion = item.get("suggested_purchase")
    reasons = []
    if suggestion and suggestion.get("product_name") != chosen.get("product_name"):
        suggested_name = suggestion.get("product_name")
        suggested_entry = next((e for e in evaluated
                                if e["candidate"].get("product_name") == suggested_name), None)
        if suggested_entry and suggested_entry["decision"] == "rejected":
            rs = suggested_entry["reasons"]
            if "species_conflict" in rs:
                reasons.append("species_conflict_rejected")
            if "prepared_dish" in rs:
                reasons.append("prepared_food_rejected")
            if any(x in rs for x in ("composite_food", "snack_product", "wrong_processing_state",
                                     "requirement_not_verified", "category_conflict")):
                reasons.append("product_form_correction")
        chosen_price = ordinary_payable_price(chosen)
        sug_price = ordinary_payable_price(next(
            (e["candidate"] for e in evaluated
             if e["candidate"].get("product_name") == suggested_name), {}))
        if chosen_price is not None and sug_price is not None and chosen_price < sug_price:
            reasons.append("ordinary_price_preferred")
        if not reasons:
            reasons.append("better_required_amount_fit")
    final = {
        "product_id": chosen.get("product_id"),
        "product_name": chosen.get("product_name"),
        "package_text": chosen.get("package_text"),
        "reference_grams": chosen.get("reference_grams"),
        "price_yuan": ordinary_payable_price(chosen),
        "unit_price_yuan_per_100g": chosen.get("unit_price_yuan_per_100g"),
        "packages": chosen_cost[1] if chosen_cost else None,
        "selected_by": "yueshi_purchase_selector",
        "decision": "accepted",
    }
    # round68：证据层级透传（title_claim 附用户可见提示，不得表述为配料表已验证）
    ev = accepted[0].get("evidence") or {}
    if ev.get("evidence_level"):
        final["evidence_level"] = ev["evidence_level"]
        if ev["evidence_level"] == "title_claim":
            final["user_visible_note"] = "按商品页面标注筛选，购买时请查看配料表确认"
    return {
        "status": "selected",
        "final_selection": final,
        "provider_suggestion": suggestion,
        "change_reasons": reasons,
        "review_required": [e["candidate"].get("product_name") for e in review],
        "rejected": [{"product_name": e["candidate"].get("product_name"),
                      "reasons": e["reasons"]} for e in rejected],
    }


def select_batch(result, query=None, profiles=None, revalidate=False):
    profiles = profiles if profiles is not None else load_profiles()
    query_items = {}
    for it in (query or {}).get("items", []):
        query_items[it.get("ingredient_id")] = it
    out = {
        "request_id": result.get("request_id"),
        "selector_version": "1.0.0",
        "items": {},
        "summary": {"selected": 0, "fallback_to_estimate": 0,
                    "changed_from_provider_suggestion": 0,
                    "rejected_candidates": 0, "review_required_candidates": 0},
    }
    for item in result.get("results", []):
        iid = item.get("ingredient_id")
        profile = profiles.get(iid)
        r = select_item(item, query_items.get(iid), profile, revalidate)
        out["items"][iid] = r
        if r["status"] == "selected":
            out["summary"]["selected"] += 1
            if r["change_reasons"]:
                out["summary"]["changed_from_provider_suggestion"] += 1
        else:
            out["summary"]["fallback_to_estimate"] += 1
        out["summary"]["rejected_candidates"] += len(r.get("rejected") or [])
        out["summary"]["review_required_candidates"] += len(r.get("review_required") or [])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="月食采购选择层（只从 accepted 候选中选）")
    ap.add_argument("--result", required=True, help="price-result.json")
    ap.add_argument("--query", default=None, help="price-query.json（需求量/概念档案）")
    ap.add_argument("--out", default=None, help="输出 final-selection.json")
    args = ap.parse_args()
    result = json.load(open(args.result, encoding="utf-8"))
    query = json.load(open(args.query, encoding="utf-8")) if args.query else None
    selection = select_batch(result, query)
    text = json.dumps(selection, ensure_ascii=False, indent=1)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print("final-selection 已写入：%s" % args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
