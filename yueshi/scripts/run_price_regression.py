#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定查价回归（round67 最终验收，2026-09-18）

六类食材：无糖酸奶 / 全麦面包 / 豆腐 / 猪里脊 / 南瓜 / 带鱼
验证：大品类召回 + 商品语义门禁三态 + 只从 accepted 生成最终采购。

用法：
  python scripts/run_price_regression.py --result price-result.json [--query price-query.json] \
      --out-dir <目录> [--source live|fixture]
产物：
  price-query-regression.json / price-result-regression.json
  price-semantic-gate-report.json / price-regression-summary.md
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))

from common.product_semantics import evaluate_candidate, load_profiles  # noqa: E402
import purchase_selector as ps  # noqa: E402

REGRESSION_ITEMS = [
    ("无糖酸奶", 550), ("全麦面包", 40), ("豆腐", 150),
    ("猪里脊", 300), ("南瓜", 330), ("带鱼", 200),
]


def build_query(profiles):
    items = []
    for iid, grams in REGRESSION_ITEMS:
        p = profiles.get(iid) or {}
        item = {"ingredient_id": iid, "query": (p.get("display_name") or iid),
                "required_grams": grams}
        if p.get("display_name"):
            item["display_name"] = p["display_name"]
        if p.get("search_scope"):
            item["search_scope"] = p["search_scope"]
        if p.get("acceptance_profile"):
            item["acceptance_profile"] = p["acceptance_profile"]
        if p.get("uncertainty_policy"):
            item["uncertainty_policy"] = p["uncertainty_policy"]
        items.append(item)
    return {"request_id": "2026-09-18-regression", "catalog_version": "1.6.0",
            "form_dictionary_version": "1.4.0", "items": items}


def _decision_of(candidate, profile, revalidate=False):
    d = candidate.get("candidate_decision")
    if not revalidate and d in ("accepted", "rejected", "review_required"):
        return d, candidate.get("evidence") or {}, list(candidate.get("rejection_reasons") or [])
    return evaluate_candidate(candidate.get("product_name", ""), profile)


def run_regression(result, query, out_dir, source="fixture", revalidate=False):
    profiles = load_profiles()
    q = query or build_query(profiles)
    q_items = {it["ingredient_id"]: it for it in q.get("items", [])}
    selection = ps.select_batch(result, q, profiles, revalidate=revalidate)

    gate_items = []
    counts = {"accepted": 0, "rejected": 0, "review_required": 0}
    for item in result.get("results", []):
        iid = item.get("ingredient_id")
        if iid not in q_items:
            continue
        profile = (profiles.get(iid) or {}).get("acceptance_profile")
        cands = []
        for c in item.get("candidates", []):
            d, ev, rs = _decision_of(c, profile, revalidate)
            counts[d] = counts.get(d, 0) + 1
            cands.append({"product_name": c.get("product_name"),
                          "decision": d, "evidence": ev, "rejection_reasons": rs,
                          "eligible_for_purchase": bool(c.get("eligible_for_purchase"))})
        sel = selection["items"].get(iid, {})
        gate_items.append({
            "ingredient_id": iid,
            "search_category": (q_items[iid].get("search_scope") or {}).get("category_query"),
            "candidates_recalled": len(cands),
            "accepted": sum(1 for c in cands if c["decision"] == "accepted"),
            "rejected": sum(1 for c in cands if c["decision"] == "rejected"),
            "review_required": sum(1 for c in cands if c["decision"] == "review_required"),
            "final_selection": (sel.get("final_selection") or {}).get("product_name"),
            "final_selection_reason": sel.get("change_reasons") or [],
            "candidates": cands,
        })

    # 最终采购有效性：final_selection 必须来自 accepted 或为空（估算回退）
    invalid = 0
    for gi in gate_items:
        iid = gi["ingredient_id"]
        sel = selection["items"].get(iid, {})
        final = (sel.get("final_selection") or {}).get("product_name")
        if final:
            match = next((c for c in gi["candidates"] if c["product_name"] == final), None)
            if not match or match["decision"] != "accepted":
                invalid += 1
    summary = {
        "ingredient_count": len(gate_items),
        "accepted_count": counts["accepted"],
        "rejected_count": counts["rejected"],
        "review_required_count": counts["review_required"],
        "final_purchase_count": selection["summary"]["selected"],
        "fallback_to_estimate_count": selection["summary"]["fallback_to_estimate"],
        "invalid_final_purchase_count": invalid,
    }

    os.makedirs(out_dir, exist_ok=True)
    json.dump(q, open(os.path.join(out_dir, "price-query-regression.json"), "w",
                      encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(result, open(os.path.join(out_dir, "price-result-regression.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    report = {"request_id": q.get("request_id"), "source": source,
              "summary": summary, "items": gate_items}
    json.dump(report, open(os.path.join(out_dir, "price-semantic-gate-report.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)

    lines = ["# 固定查价回归总结（六类食材）", "",
             "> 数据源：%s · request_id：%s" % (source, q.get("request_id")), "",
             "## 汇总", "",
             "| 指标 | 值 |", "|---|---|",
             "| 食材数 | %d |" % summary["ingredient_count"],
             "| accepted 候选 | %d |" % summary["accepted_count"],
             "| rejected 候选 | %d |" % summary["rejected_count"],
             "| review_required 候选 | %d |" % summary["review_required_count"],
             "| 最终采购 | %d |" % summary["final_purchase_count"],
             "| 参考估价回退 | %d |" % summary["fallback_to_estimate_count"],
             "| 无效最终采购 | %d |" % summary["invalid_final_purchase_count"],
             "", "## 逐项结果", "",
             "| 食材 | 品类召回 | 候选 | accepted | rejected | review | 最终采购 | 差异原因 |",
             "|---|---|---|---|---|---|---|---|"]
    for gi in gate_items:
        lines.append("| %s | %s | %d | %d | %d | %d | %s | %s |" % (
            gi["ingredient_id"], gi["search_category"], gi["candidates_recalled"],
            gi["accepted"], gi["rejected"], gi["review_required"],
            gi["final_selection"] or "（参考估价）",
            "、".join(gi["final_selection_reason"]) or "—"))
    lines += ["", "## 判定", "",
              ("PASS：最终采购只从 accepted 产生，无无效采购。"
               if invalid == 0 else "FAIL：存在 %d 项无效最终采购。" % invalid)]
    open(os.path.join(out_dir, "price-regression-summary.md"), "w",
         encoding="utf-8").write("\n".join(lines) + "\n")
    return summary, report


def main() -> int:
    ap = argparse.ArgumentParser(description="固定查价回归（六类食材）")
    ap.add_argument("--result", required=True)
    ap.add_argument("--query", default=None)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--source", choices=["live", "fixture"], default="fixture")
    ap.add_argument("--revalidate", action="store_true",
                    help="忽略结果内已有判定，用当前门禁重评（旧结果复评）")
    args = ap.parse_args()
    result = json.load(open(args.result, encoding="utf-8"))
    query = json.load(open(args.query, encoding="utf-8")) if args.query else None
    summary, _ = run_regression(result, query, args.out_dir, source=args.source,
                                revalidate=args.revalidate)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["invalid_final_purchase_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
