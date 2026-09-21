#!/usr/bin/env python3
# 收口轮 六：旧版核心视觉组件快照（恢复视觉语言，不恢复旧交互）
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(__file__) if "__file__" in dir() else os.getcwd())
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "scripts", "render_plan.py")

plan = {
    "plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "08-22 至 08-28", "subtitle": "视觉快照",
             "include_recipe_steps": False,
             "stats": {"天数": "7 天", "模式": "平衡激素", "进食窗口": "07:30–19:30", "预算": "约 ¥231"},
             "moon_phases": list(range(7))},
    "profile": {"目标": "维持"},
    "shopping": {"items": [{"ingredient": "鸡蛋", "required_quantity": "10枚",
                            "acceptable_package": "10枚/盒", "reference_price": "¥12",
                            "substitutes": [], "leftover_action": ""}],
                 "total": "¥12", "has_unpriced": False},
    "days": [{"label": f"周{c}", "window": "08:00-20:00",
              "meals": [{"time": "19:00", "status": "在家", "name": "晚餐",
                         "dishes": "番茄炒蛋", "grams": "鸡蛋2枚"}],
              "nutrition_line": "净碳水50g", "advice": "早睡"} for c in "一二三四五六日"],
    "disclaimer": "仅供参考",
}

td = tempfile.mkdtemp()
pj = os.path.join(td, "plan.json")
out = os.path.join(td, "plan.html")
json.dump(plan, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
r = subprocess.run([sys.executable, RENDER, "--input", pj, "--output", out],
                   capture_output=True, text=True, cwd=ROOT)
assert r.returncode == 0, r.stderr
html = open(out, encoding="utf-8").read()

# 1) 核心组件在场：hero / 大号日期 / 状态四宫格 / 圆角日卡 / 营养合计底条 / 建议卡 / 月相
assert 'class="cover-hero"' in html
assert 'class="cover-date-range"' in html
assert html.count('class="cover-stat"') == 4, "状态四宫格缺失"
assert html.count('class="day-card"') == 7
assert 'class="day-total"' in html, "营养合计底条缺失"
assert 'class="day-advice"' in html, "建议卡缺失"
assert html.count('class="moon-phase"') == 7

# 2) 屏幕样式含：章节自动编号、柔和分区底色、圆角、四宫格网格
css = open(os.path.join(ROOT, "styles", "screen.css"), encoding="utf-8").read()
for needle in ["counter-increment: section", "decimal-leading-zero",
               "grid-template-columns: repeat(4", "border-radius", ".day-total"]:
    assert needle in css, f"screen.css 缺少视觉规则: {needle}"

# 3) 旧交互未恢复：checkbox / localStorage / 渠道拆单
assert "checkbox" not in html and "localStorage" not in html, "旧交互残留"

print("PASS")
