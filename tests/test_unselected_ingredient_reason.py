#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""未入选食材回归：不进采购数据行；去向说明含真实原因；aggregator 排除逻辑。"""
import io, json, os, subprocess, sys, tempfile

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []
sa = io.open(os.path.join(base, "scripts", "shopping_aggregator.py"), encoding="utf-8").read()
if "--selection-report" not in sa:
    fails.append("aggregator 缺 --selection-report")
if 'menu_status") == "not_selected"' not in sa:
    fails.append("aggregator 缺未入选排除逻辑")
osch = io.open(os.path.join(base, "references", "output-schema.md"), encoding="utf-8").read()
if "不得出现在正式采购表数据行" not in osch:
    fails.append("output-schema 缺采购排除规则")
if "原因只能来自 ranker 日志" not in io.open(os.path.join(base, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md")) + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md")):
    fails.append("SKILL 未规定原因必须来自 ranker 日志")
# 端到端：构造菜单 CSV 含蛤蜊行 + selection report 未入选 → 被移除且无金额行
tmp = tempfile.mkdtemp()
menu = os.path.join(tmp, "menu.csv")
open(menu, "w", encoding="utf-8").write(
    "date,meal,dish,food,grams,unit,storage,kind,category\n"
    "2026-08-22,晚餐,蛤蜊蒸蛋,蛤蜊,150,g,冷藏,fresh,水产\n"
    "2026-08-22,晚餐,蛤蜊蒸蛋,鸡蛋,100,g,冷藏,fresh,蛋\n")
sr = os.path.join(tmp, "sr.jsonl")
open(sr, "w", encoding="utf-8").write(json.dumps(
    {"ingredient": "蛤蜊", "preselection_decision": "accepted_batch", "menu_status": "not_selected",
     "candidate_count": 1, "top_candidate": "蛤蜊蒸蛋", "rejected_at": "constraint_gate",
     "reason_codes": ["insufficient_quantity"], "can_swap": True, "swap_target_meal": "周日晚餐"},
    ensure_ascii=False) + "\n")
r = subprocess.run([sys.executable, os.path.join(base, "scripts", "shopping_aggregator.py"),
                    "--menu", menu, "--selection-report", sr], capture_output=True, text=True)
if r.returncode != 0:
    fails.append("aggregator 运行失败: " + r.stderr[:200])
if "蛤蜊" in r.stdout and "已从采购表移除" not in r.stdout:
    fails.append("未入选蛤蜊未被移除或无提示")
if "已从采购表移除" not in r.stdout:
    fails.append("缺移除提示")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
