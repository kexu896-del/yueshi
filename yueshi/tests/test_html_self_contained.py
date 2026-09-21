#!/usr/bin/env python3
# 收口轮 六：交付 HTML 单文件自包含——无相对 CSS 路径，离开项目目录仍完整
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "scripts", "render_plan.py")

plan = {
    "plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "08-22 至 08-28", "subtitle": "自包含测试",
             "include_recipe_steps": False, "stats": {"天数": "7 天", "模式": "平衡激素", "进食窗口": "07:30–19:30", "预算": "约 ¥231"},
             "moon_phases": list(range(7))},
    "profile": {"目标": "维持"},
    "shopping": {"items": [{"ingredient": "鸡蛋", "required_quantity": "10枚",
                            "acceptable_package": "10枚/盒", "reference_price": "¥12",
                            "substitutes": ["鸭蛋"], "leftover_action": "冷藏"}],
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
# 1) 无 <link> 样式引用、无相对 css 路径
assert "<link" not in html, "存在 <link> 引用"
assert not re.search(r"href=['\"]styles/", html), "存在相对样式路径"
# 2) 样式已内联且两份都在（screen + print）
assert html.count("<style") >= 2, "内联样式块不足"
assert "@media print" in html or "media='print'" in html, "打印样式未内联"
# 3) SVG 内联（月相）
assert "<svg" in html, "SVG 未内联"
# 4) 复制到孤立目录仍完整（无外部依赖标签）
import shutil
iso = os.path.join(td, "iso")
os.makedirs(iso)
shutil.copy(out, os.path.join(iso, "plan.html"))
iso_html = open(os.path.join(iso, "plan.html"), encoding="utf-8").read()
assert not re.search(r"<(?:link|script)[^>]+(?:href|src)=", iso_html), "存在外部资源标签"

print("PASS")
