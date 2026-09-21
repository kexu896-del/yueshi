#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""食堂模板回归：统一配置存在且口径正确；渲染器从配置读取完整点餐结构与区间估算。"""
import io, json, os, subprocess, sys, tempfile

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []
cfg = json.load(io.open(os.path.join(base, "data", "cafeteria-meal-templates.json"), encoding="utf-8"))
tpl = cfg["templates"]["balanced_standard"]
if tpl["display"] != "荤菜半份 + 素菜2份 + 米饭半碗 + 清汤":
    fails.append("点餐结构不符: " + tpl["display"])
est = tpl["nutrition_estimate"]
if (est["net_carbs_g"], est["protein_g"], est["fat_g"], est["confidence"]) != (32, 18, 14, "low"):
    fails.append("营养估算口径不符")
if "不保证精确" not in tpl.get("display_note", ""):
    fails.append("缺'不保证精确'提示")
# 渲染器读取配置而非硬编码
rp = io.open(os.path.join(base, "scripts", "render_plan.py"), encoding="utf-8").read()
if "cafeteria-meal-templates.json" not in rp:
    fails.append("render_plan 未读取统一配置")
if "荤菜半份" in rp:
    fails.append("渲染器硬编码点餐结构")
# 端到端渲染
plan = {"plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "x", "include_recipe_steps": False, "stats": {}},
        "profile": {}, "shopping": {"items": []},
        "days": [{"label": f"周{x}", "meals": [{"time": "12:00", "status": "外食 · 区间估算",
                  "name": "午餐", "meal_source": "cafeteria", "order_template": "balanced_standard"}],
                  "nutrition_line": "全天合计含食堂估算：净碳水约 90g · 蛋白约 70g"} for x in "一二三四五六日"],
        "disclaimer": "x"}
tmp = tempfile.mkdtemp()
p, o = os.path.join(tmp, "p.json"), os.path.join(tmp, "p.html")
json.dump(plan, open(p, "w", encoding="utf-8"))
r = subprocess.run([sys.executable, os.path.join(base, "scripts", "render_plan.py"),
                    "--input", p, "--output", o], capture_output=True, text=True)
h = open(o, encoding="utf-8").read()
if r.returncode != 0:
    fails.append("渲染失败: " + r.stderr[:150])
for s in ["荤菜半份 + 素菜2份 + 米饭半碗 + 清汤", "净碳水约32g", "蛋白质约18g", "脂肪约14g", "大致区间，不保证精确"]:
    if s not in h:
        fails.append(f"渲染缺: {s}")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
