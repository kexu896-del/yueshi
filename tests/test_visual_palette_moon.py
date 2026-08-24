#!/usr/bin/env python3
# round24：视觉语言恢复（奶油底/紫绿/黑标题/真实月相轨道）防回退
import json, os, subprocess, sys, tempfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1) 配色硬性元素回到 visual-spec 权威值
css = open(os.path.join(ROOT, "styles", "screen.css"), encoding="utf-8").read()
for token in ["#faf8f0", "#a08ac9", "#7fa283", "#fff8df", "#2f2b23", "#111111"]:
    assert token in css, f"screen.css 缺少 {token}"
assert ".moon-track" in css, "缺月相轨道样式"
pcss = open(os.path.join(ROOT, "styles", "print.css"), encoding="utf-8").read()
assert "#111111" in pcss and "cover-title" in pcss, "打印端标题强制黑缺失"

# 2) 月相算法：2026-08-26 前后为满月；无满月周不得出现"满月"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("rp", os.path.join(ROOT, "scripts", "render_plan.py"))
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
illum, waxing, name = rp.moon_phase(date(2026, 8, 26))
assert name == "满月" and illum > 0.95, (illum, name)
illum2, waxing2, name2 = rp.moon_phase(date(2026, 8, 3))
assert name2 != "满月", name2
_, wax_new, _ = rp.moon_phase(date(2026, 8, 13))   # 新月后不久 → 盈
assert wax_new is True

# 3) 端到端：渲染含 moon-track、每日相位名、无满月周不写满月
plan = {"plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "2026-08-01 至 2026-08-07", "subtitle": "t",
                 "include_recipe_steps": False, "stats": {"天数": "7"}},
        "profile": {"目标": "维持"},
        "shopping": {"items": [{"ingredient": "鸡蛋", "required_quantity": "10枚", "reference_price": "约8元/10枚",
                                "acceptable_package": "10枚/盒",
                                "substitutes": [], "leftover_action": ""}]},
        "days": [{"label": f"周{c}", "window": "w",
                  "meals": [{"time": "19:00", "status": "在家", "name": "晚餐",
                             "dishes": "x", "grams": ""}],
                  "nutrition_line": "n", "advice": ""} for c in "一二三四五六日"],
        "disclaimer": "d"}
td = tempfile.mkdtemp()
pj = os.path.join(td, "p.json"); out = os.path.join(td, "o.html")
json.dump(plan, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "render_plan.py"),
                    "--input", pj, "--output", out], capture_output=True, text=True, cwd=ROOT)
assert r.returncode == 0, r.stderr
html = open(out, encoding="utf-8").read()
assert "moon-track" in html and html.count('class="moon-cell"') == 7
assert "满月" not in html, "2026-08-01 当周无满月，不得出现满月字样"

print("PASS")
