# -*- coding: utf-8 -*-
# round 31 定版回归：CHANGELOG 收口 / 早餐三态 / 一锅出白名单 / 价格三层 /
# 食堂模板字段 / SKILL 拆分 / 四渲染器 / 页数与字号底线
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
CORPUS = SK + read("references/runtime-rules.md") + read("references/nutrition-routing.md") + read("references/output-policy.md")


def test_changelog_and_inline_notes_removed():
    assert os.path.exists(os.path.join(BASE, "CHANGELOG.md"))
    assert "2026-08-21" in read("CHANGELOG.md")
    assert "用户指示 2026-08-21" not in SK
    assert "用户指示取消" not in read("scripts/macros_calculator.py")


def test_parameter_report_single_path():
    assert "references/parameter-build-report.md" not in CORPUS
    assert "book-extraction/nutrition-audit/parameter-build-report.md" in CORPUS


def test_breakfast_mode_three_states():
    for kw in ("breakfast_mode", "planned", "guidance_only", "excluded", "不计入采购清单"):
        assert kw in CORPUS, kw


def test_one_pot_whitelist_rules():
    for kw in ("true_one_pot", "synchronized_one_cooker", "one_hot_dish_plus_ready_staple",
               "one_hot_dish_plus_no_cook_side", "two_independent_hot_dishes",
               "two_dishes_one_soup", "multi_pan"):
        assert kw in CORPUS, kw
    src = read("scripts/recipe_ranker.py")
    assert "ONE_POT_ALLOWED_STRUCTURES" in src and "ONE_POT_DENIED_STRUCTURES" in src


def test_one_pot_rule_behavior():
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    from recipe_ranker import apply_one_pot_rule
    cands = [
        {"name": "焖饭", "meal_structure": "true_one_pot"},
        {"name": "两菜一汤", "meal_structure": "two_dishes_one_soup"},
        {"name": "多锅", "cookware_count": 2, "dish_count": 2},
        {"name": "热菜+面包", "meal_structure": "one_hot_dish_plus_ready_staple"},
    ]
    out = apply_one_pot_rule(cands, True, log=[])
    names = [c["name"] for c in out]
    assert "两菜一汤" not in names and "多锅" not in names
    assert "焖饭" in names and "热菜+面包" in names


def test_price_three_layers():
    for kw in ("price_basis", "direct_public_price", "category_estimate", "historical_estimate",
               "冻结前将该食材替换"):
        assert kw in CORPUS, kw
    src = read("scripts/render_plan.py")
    assert "ESTIMATE_PRICE_BASIS" in src and "_display_price" in src
    est = json.load(open(os.path.join(BASE, "data/price-estimates.json"), encoding="utf-8"))
    for f in ("city", "as_of", "unit_standard", "method", "version"):
        assert f in est["meta"], f
    assert all("price_basis" in it for it in est["items"].values())


def test_display_price_prefix():
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    from render_plan import _display_price
    assert _display_price({"reference_price": "26元/袋", "price_basis": "category_estimate"}) == "约26元/袋"
    assert _display_price({"reference_price": "约26元/袋", "price_basis": "historical_estimate"}) == "约26元/袋"
    assert _display_price({"reference_price": "¥5–8/500g", "price_basis": "direct_public_price"}) == "¥5–8/500g"
    assert _display_price({"reference_price": "¥5/500g"}) == "¥5/500g"


def test_preselection_closed_loop():
    assert "不得" in CORPUS and "被当作跳过预选" in CORPUS
    assert "accepted_batch" in CORPUS and "点名食材可见原因" in CORPUS
    assert "原因只能来自 ranker 日志" in CORPUS


def test_protein_four_fields():
    for kw in ("safety_floor_g", "individual_target_g", "book_reference_g", "medical_limit_g",
               "protein_tolerance_pct"):
        assert kw in CORPUS, kw


def test_nutrition_autofix_before_freeze():
    assert "禁止渲染完成后再人工" in CORPUS
    assert "冻结 plan.json" in CORPUS


def test_four_renderers_exist():
    for f in ("scripts/render_plan.py", "scripts/render_html.py",
              "scripts/render_markdown.py", "scripts/render_docx.py"):
        assert os.path.exists(os.path.join(BASE, f)), f


def test_page_and_font_floors():
    op = read("references/output-policy.md")
    assert "≤9 页" in op and "≥9pt" in op and "≥8.5pt" in op and "≥1.25" in op
    assert "删重复说明" in op  # 压缩顺序


def test_cafeteria_template_fields():
    d = json.load(open(os.path.join(BASE, "data/cafeteria-meal-templates.json"), encoding="utf-8"))
    for tid, t in d["templates"].items():
        for f in ("template_id", "version", "estimate_basis"):
            assert f in t, (tid, f)
        assert "confidence" in t["nutrition_estimate"]


def test_skill_split():
    for f in ("references/runtime-rules.md", "references/nutrition-routing.md",
              "references/output-policy.md", "developer/maintenance-map.md"):
        assert os.path.exists(os.path.join(BASE, f)), f
    assert len(SK.splitlines()) < 150, "SKILL.md 应保持入口级精简"
    assert "固定执行顺序（15 步）" in SK


def _minimal_plan():
    return {
        "plan": {"date_range": "2026-08-23 至 2026-08-29", "subtitle": "平衡激素", "stats": {"天数": "7 天"}},
        "plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24",
                      "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24",
                      "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08",
                      "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
        "profile": {},
        "stage_overview": {"current": "经前一周", "strategy": "温和",
                           "weeks": [{"time": "本周", "stage": "经前一周", "plan": "温和"}]},
        "shopping": {"items": [
            {"ingredient": "虾", "category": "肉蛋水产与豆制品", "required_quantity": "300g",
             "acceptable_package": "300g/袋", "reference_price": "26元/袋",
             "price_basis": "category_estimate", "substitutes": ["鳕鱼"], "leftover_action": "0 剩余",
             "meal_allocation": "周六午150g · 周三晚150g"},
        ], "total": "约 ¥26（估算口径）", "price_note": "参考价为估算"},
        "prep": {"purchase_day": {"label": "周六", "tasks": ["买虾"]},
                 "leftover_verification": [
                     {"ingredient": "虾", "purchase_vs_use": "300g vs 300g", "result": "0 剩余"},
                     {"ingredient": "菠菜", "purchase_vs_use": "300g vs 300g", "result": "0 剩余"},
                     {"ingredient": "豆腐", "purchase_vs_use": "400g vs 400g", "result": "0 剩余"}]},
        "days": [{"label": "周六 8/23", "window": "进食 07:30–19:30",
                  "meals": [{"time": "07:30", "name": "早餐", "dishes": "燕麦酸奶碗", "status": "自炊"}],
                  "nutrition_line": "净碳水约100g"}],
        "wisdom": {"paragraphs": ["段一", "段二", "段三"]},
        "execution_tips": ["提示一"],
        "disclaimer": "本计划为一般性健康饮食建议，不构成医疗诊断。",
    }


def test_markdown_renderer_functional():
    plan = _minimal_plan()
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "plan.json"), os.path.join(td, "plan.md")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_markdown.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        md = open(op, encoding="utf-8").read()
        assert "## 采购清单" in md and "## 七天菜单" in md and "约26元/袋" in md
        assert "食养之理与执行说明" in md and "禁食" not in md.split("## 七天菜单")[1].split("## 食养")[0]


def test_docx_renderer_functional():
    plan = _minimal_plan()
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "plan.json"), os.path.join(td, "plan.docx")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_docx.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert os.path.getsize(op) > 1000


if __name__ == "__main__":
    fails = []
    for name, fn in sorted([(k, v) for k, v in globals().items()
                            if k.startswith("test_") and callable(v)]):
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            fails.append(name)
            print(f"FAIL {name}: {e}")
    print("round31:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
