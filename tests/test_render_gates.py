#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染门禁回归：render_plan.py 固定组件渲染 + 完整性门禁 + steps 开关。
收口轮口径升级：CSS 已内联，占位符/组件计数按 class 属性判定，不按裸字符串。"""
import json, os, subprocess, sys, tempfile

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
script = os.path.join(base, "scripts", "render_plan.py")
fails = []

def sample(include_steps):
    day = {"label": "周一", "window": "进食 08:00-19:00",
           "meals": [{"time": "12:00", "status": "外食 · 区间估算", "name": "午餐", "dishes": "x",
                      "recipe_instruction": {"steps": ["a", "b", "c", "d"]}}],
           "nutrition_line": "净碳水 60g", "advice": ""}
    return {"plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "2026-08-22 至 2026-08-28", "include_recipe_steps": include_steps,
                     "stats": {"阶段": "能量期"}},
            "profile": {"性别": "女"},
            "shopping": {"items": [{"ingredient": "紫甘蓝", "required_quantity": "300g",
                                    "acceptable_package": "500g", "reference_price": "¥6",
                                    "substitutes": [], "leftover_action": ""}]},
            "days": [dict(day, label=f"周{i}") for i in "一二三四五六日"],
            "disclaimer": "免责"}

tmp = tempfile.mkdtemp()
# 用例10：选不需要做法 → 无做法小节
p = os.path.join(tmp, "a.json"); o = os.path.join(tmp, "a.html")
json.dump(sample(False), open(p, "w", encoding="utf-8"))
r = subprocess.run([sys.executable, script, "--input", p, "--output", o], capture_output=True, text=True)
h = open(o, encoding="utf-8").read()
if r.returncode != 0:
    fails.append("渲染失败: " + r.stderr[:150])
if 'class="recipe-steps"' in h:
    fails.append("include_recipe_steps=false 时仍渲染做法")
# 用例11：选需要 → 渲染做法
json.dump(sample(True), open(p, "w", encoding="utf-8"))
r = subprocess.run([sys.executable, script, "--input", p, "--output", o], capture_output=True, text=True)
h = open(o, encoding="utf-8").read()
if 'class="recipe-steps"' not in h:
    fails.append("include_recipe_steps=true 时未渲染做法")
# 用例17：无占位符、一个 main 一个 cover
for pat in ["{{", "}}", "PLACEHOLDER", "undefined", "[object Object]"]:
    if pat in h:
        fails.append(f"残留: {pat}")
if h.count("<main>") != 1 or h.count('class="cover-hero"') != 1:
    fails.append("main/cover 数量错误")
# 用例18：午餐时间与状态分字段
if 'class="meal-time">12:00<' not in h or 'class="meal-status">外食 · 区间估算<' not in h:
    fails.append("午餐字段未分行")
# 缺字段立即停止
bad = {"plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {}}
p2 = os.path.join(tmp, "bad.json")
json.dump(bad, open(p2, "w", encoding="utf-8"))
r = subprocess.run([sys.executable, script, "--input", p2, "--output", o], capture_output=True, text=True)
if r.returncode == 0:
    fails.append("缺字段未停止")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
