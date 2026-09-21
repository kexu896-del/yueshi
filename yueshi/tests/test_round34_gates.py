# -*- coding: utf-8 -*-
# round 34 回归：术语门禁入入口 / 排版令牌 / 餐次完整性与状态契约 /
# 免责声明独立 / 领域裁决 / gate_result 三分类 / rules_bundle_hash / wisdom 子区块
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
PRINT = read("styles/print.css")
RP = read("scripts/render_plan.py")


def _plan(**kw):
    plan = {"plan": {"date_range": "2026-09-01 至 2026-09-07",
                     "subtitle": kw.get("subtitle", "能量期 · 减重目标 · 月经期转卵泡期"), "stats": {}},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "x", "runtime_rules_version": "x",
                          "nutrition_rules_version": "x", "output_policy_version": "x",
                          "recipe_manifest_version": "x", "effective_parameters_version": "x",
                          "price_data_version": "x"},
            "profile": {},
            "shopping": {"items": [{"ingredient": "虾", "category": "肉蛋水产与豆制品",
                                    "required_quantity": "300g", "acceptable_package": "300g/袋",
                                    "reference_price": "26元/袋", "price_basis": "category_estimate",
                                    "substitutes": [], "leftover_action": "0 剩余"}]},
            "prep": {"leftover_verification": [
                {"ingredient": "虾", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周二 9/1", "window": "进食 07:30–19:30",
                      "meals": [{"time": "07:30", "name": "早餐", "dishes": "蒸玉米150g · 酸奶150g",
                                 "status": kw.get("bstatus", "自备 · 免煮"),
                                 **({"grams": "玉米150g"} if kw.get("bgrams") else {})},
                                {"time": "12:00", "name": "午餐", "meal_source": "cafeteria",
                                 "order_template": "balanced_standard", "status": "外食 · 区间估算"}]}],
            "wisdom": {"paragraphs": ["段一", "段二", "段三"]},
            "execution_tips": ["动作一", "动作二"],
            "disclaimer": "本计划为一般性健康饮食建议。"}
    if kw.get("tips_with_disclaimer"):
        plan["execution_tips"].append(plan["disclaimer"])
    if kw.get("bad_hash"):
        plan["plan_meta"]["rules_bundle_hash"] = "deadbeef"
    return plan


def _render(plan):
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "p.json"), os.path.join(td, "o.html")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_html.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        if r.returncode == 0:
            return 0, open(op, encoding="utf-8").read()
        return r.returncode, r.stderr + r.stdout


def test_no_internal_terms_in_visible_headings():
    assert "用户可见术语门禁" in SK and "reason_code" in SK
    assert "阶段适配" in SK  # 显示转换表
    rc, out = _render(_plan(subtitle="经前一周（周期协议）"))
    assert rc != 0
    rc, out = _render(_plan())
    assert rc == 0


def test_wisdom_body_and_list_same_font_size():
    assert "#why p, #why ul, #why li { font-size: 10.5pt" in PRINT
    assert "typography_tokens:" in OP and "pt: 10.5" in OP and "line_height: 1.6" in OP
    assert "渲染器不得各自解释字号" in OP or "不得各自解释字号" in OP


def test_cafeteria_display_content_not_empty():
    rc, out = _render(_plan())
    assert rc == 0 and "荤菜半份 + 素菜2份 + 米饭半碗 + 清汤" in out
    assert "无 display 内容" in RP


def test_planned_meal_not_labeled_self_managed():
    rc, out = _render(_plan(bstatus="自行处理", bgrams=True))
    assert rc != 0
    assert "planned" in SK and "不得显示“自行处理”" in SK or "不得显示\"自行处理\"" in SK


def test_guidance_only_contract():
    for kw in ("guidance_only", "不进入采购清单", "excluded", "不进入营养合计"):
        assert kw in SK, kw


def test_day_advice_stays_with_day_card():
    assert ".day-advice { break-before: avoid" in PRINT


def test_disclaimer_is_separate_component():
    rc, out = _render(_plan(tips_with_disclaimer=True))
    assert rc != 0 and "免责声明混入执行提示" in out
    rc, out = _render(_plan())
    assert rc == 0 and 'class="document-footer disclaimer"' in out
    assert "独立区块" in SK or "独立组件" in SK


def test_domain_based_conflict_resolution():
    assert "按领域" in SK and "output-policy 不得删除 runtime-rules" in SK
    assert "6. SKILL.md 中的摘要" not in SK  # 旧的线性优先级已移除


def test_gate_result_three_way():
    assert "gate_result" in SK and "auto_fix" in SK and "user_input_required" in SK and "fatal" in SK


def test_rules_bundle_hash():
    assert "rules_bundle_hash" in OP and "compute_rules_bundle_hash" in RP
    assert "build_id" in OP
    rc, out = _render(_plan(bad_hash=True))
    assert rc != 0 and "rules_bundle_hash" in out


def test_wisdom_subblocks():
    assert "本周怎么安排" in OP and "本周执行要点" in OP
    assert ".wisdom-subheading" in PRINT and "wisdom-subheading" in RP
    rc, out = _render(_plan())
    assert rc == 0 and "本周怎么安排" in out and "本周执行要点" in out


def test_description_user_language():
    desc = SK.split("---")[1]
    assert "周期协议" not in desc and "周期阶段适配" in desc
    assert "周期断食主线" not in SK


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
    print("round34:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
