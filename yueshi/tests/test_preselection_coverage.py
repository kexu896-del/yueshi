#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预选闭环回归：ranker 支持三档语义、补偿搜索与追溯报告。"""
import io, json, os, subprocess, sys, tempfile

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rr = os.path.join(base, "scripts", "recipe_ranker.py")
fails = []
tmp = tempfile.mkdtemp()
sr = os.path.join(tmp, "sr.jsonl")
r = subprocess.run([sys.executable, rr, "--basket", "鸡腿,鸡蛋,菠菜", "--mode", "hormone",
                    "--accepted", "蛤蜊", "--wanted", "牛肉", "--selection-report", sr, "--limit", "5"],
                   capture_output=True, text=True)
if r.returncode != 0:
    fails.append("ranker 运行失败: " + r.stderr[:200])
else:
    recs = [json.loads(l) for l in open(sr, encoding="utf-8")]
    by_ing = {x["ingredient"]: x for x in recs}
    # 用例4：蛤蜊标记为 accepted_batch
    if by_ing.get("蛤蜊", {}).get("preselection_decision") != "accepted_batch":
        fails.append("蛤蜊未标记 accepted_batch")
    if by_ing.get("牛肉", {}).get("preselection_decision") != "explicitly_wanted":
        fails.append("牛肉未标记 explicitly_wanted")
    # 用例6：未入选须有真实原因码
    REASONS = {"no_production_recipe", "recipe_fingerprint_missing", "safety_or_medical_conflict",
               "allergen_conflict", "time_limit", "equipment_mismatch", "package_waste",
               "budget_pressure", "nutrition_conflict", "duplicate_protein", "low_diversity_gain",
               "lower_rank_after_constraints", "insufficient_quantity", "schedule_mismatch"}
    for x in recs:
        if x["menu_status"] == "not_selected":
            if not x["reason_codes"] or not set(x["reason_codes"]) <= REASONS:
                fails.append(f"{x['ingredient']} 原因码非法: {x['reason_codes']}")
            if "candidate_count" not in x or "rejected_at" not in x:
                fails.append(f"{x['ingredient']} 追溯字段不全")
        if x["menu_status"] == "compensation_candidate" and not x.get("can_swap"):
            fails.append(f"{x['ingredient']} 补偿候选未标 can_swap")
# SKILL/规则文本
sk = io.open(os.path.join(base, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md")) + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))
for kw in ["accepted_batch", "explicitly_wanted", "merely_allowed", "补偿搜索", "reason_code"]:
    if kw not in sk:
        fails.append(f"SKILL 缺: {kw}")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
