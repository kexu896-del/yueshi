#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品变更日志（round65）：记录 provider_suggestion → final_selection 的每次变更。

每条记录：
  {ingredient_id, provider_suggestion, final_selection, selection_changed,
   selection_change_reason_codes, change_category}

reason codes（枚举）：
  smaller_package / lower_waste / product_form_correction / prepared_food_rejected /
  non_member_price_required / better_required_amount_fit / fallback_to_estimate

change_category 统计口径（纠错与包装优化分开）：
  correction            —— product_form_correction / prepared_food_rejected /
                           non_member_price_required / fallback_to_estimate
  packaging_optimization—— smaller_package / lower_waste / better_required_amount_fit
"""
import json, os

REASON_CODES = {
    "smaller_package", "lower_waste", "product_form_correction",
    "prepared_food_rejected", "non_member_price_required",
    "better_required_amount_fit", "fallback_to_estimate",
}
CATEGORY_BY_REASON = {
    "product_form_correction": "correction",
    "prepared_food_rejected": "correction",
    "non_member_price_required": "correction",
    "fallback_to_estimate": "correction",
    "smaller_package": "packaging_optimization",
    "lower_waste": "packaging_optimization",
    "better_required_amount_fit": "packaging_optimization",
}


def log_change(ingredient_id, provider_suggestion, final_selection, reason_codes):
    """构造一条变更记录；reason_codes 必须在枚举内，否则 ValueError。"""
    codes = list(reason_codes or [])
    bad = [c for c in codes if c not in REASON_CODES]
    if bad:
        raise ValueError("未知 selection_change_reason_codes: %s" % bad)
    changed = bool(codes) or (provider_suggestion != final_selection)
    cats = sorted({CATEGORY_BY_REASON[c] for c in codes})
    return {
        "ingredient_id": ingredient_id,
        "provider_suggestion": provider_suggestion,
        "final_selection": final_selection,
        "selection_changed": changed,
        "selection_change_reason_codes": codes,
        "change_category": cats[0] if len(cats) == 1 else cats or None,
    }


def summarize(records):
    """汇总统计：纠错与包装优化分开计数。"""
    stats = {"total": len(records), "changed": 0,
             "correction": 0, "packaging_optimization": 0,
             "by_reason": {}}
    for r in records:
        if not r.get("selection_changed"):
            continue
        stats["changed"] += 1
        for c in r.get("selection_change_reason_codes") or []:
            stats["by_reason"][c] = stats["by_reason"].get(c, 0) + 1
            cat = CATEGORY_BY_REASON.get(c)
            if cat:
                stats[cat] += 1
    return stats


def append_jsonl(path, record):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
