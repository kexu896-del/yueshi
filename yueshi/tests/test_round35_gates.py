# -*- coding: utf-8 -*-
# round 35 回归：gate_result 分类修正 / 逐项失败等级 + fatal_after_retry /
# 餐次完整性拆分 MEAL_DATA_MISSING vs MEAL_RENDER_FIELD_DROPPED /
# 术语门禁限定可见字段 / meal_plan_mode 统一 / 黑名单扩充 /
# 周期阶段参数措辞 / 排版令牌四格式映射 / 维护地图标注 / 哈希覆盖 safety-rules
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
RR = read("references/runtime-rules.md")
MM = read("developer/maintenance-map.md")
RP = read("scripts/render_plan.py")


def _plan(**kw):
    plan = {"plan": {"date_range": "2026-09-01 至 2026-09-07",
                     "subtitle": kw.get("subtitle", "能量期 · 减重目标"), "stats": {}},
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
                                 "status": "自备 · 免煮"},
                                {"time": "12:00", "name": "午餐", "meal_source": "cafeteria",
                                 "order_template": "balanced_standard",
                                 "status": kw.get("lunch_status", "外食 · 区间估算")}]}],
            "wisdom": {"paragraphs": ["段一", "段二", "段三"]},
            "execution_tips": ["动作一", "动作二"],
            "disclaimer": "本计划为一般性健康饮食建议。"}
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


def test_gate_classification_fixed():
    # 用户餐次/输出格式不明确属于可追问补齐，不得归入 fatal
    assert "可通过一次追问补齐" in SK
    assert "fatal：安全筛查未完成" not in SK
    assert "用户餐次不明确" not in SK
    # 安全筛查未完成须区分缺信息与路由不可执行
    assert "安全路由无法执行" in SK and "user_input_required" in SK


def test_gate_items_have_failure_levels():
    for tag in ("[fatal]", "[user_input_required]", "[auto_fix]"):
        assert tag in SK, tag
    assert "auto_fix_retry_exhausted" in SK  # round36：fatal_after_retry 改为 fatal_reason
    assert "最多两轮" in SK


def test_meal_content_gate_split():
    assert "MEAL_DATA_MISSING" in OP and "MEAL_RENDER_FIELD_DROPPED" in OP
    assert "不重新计算菜单" in OP
    assert "business_data" in OP and "rendered_output" in OP
    # 业务字段缺失 → MEAL_DATA_MISSING
    rc, out = _render(_plan(lunch_status=""))
    assert rc != 0 and "MEAL_DATA_MISSING" in out
    rc, out = _render(_plan())
    assert rc == 0


def test_terminology_gate_scoped_to_visible_fields():
    assert "visible_text_fields" in SK and "visible_text_fields" in OP
    assert "cover.title" in OP and "meals[].display_content" in OP
    assert "disclaimer.display_text" in OP
    assert "禁止对整个 plan.json" in SK or "避免误报" in OP


def test_meal_plan_mode_unified():
    assert "meal_plan_mode" in SK and "meal_plan_mode" in RR and "meal_plan_mode" in OP
    assert "meal_type" in RR
    assert "不得同时存在 breakfast_mode / meal_mode / recipe_mode" in RR or \
           "不同时存在 breakfast_mode / meal_mode / recipe_mode" in SK


def test_banned_terms_expanded():
    for t in ("accepted_batch", "locked_basket", "provisional_locked_basket",
              "plan.json", "gate_result", "low confidence", "runtime-rules", "nutrition-routing"):
        assert t in RP, t
    # 显示转换表
    assert "已确认食材" in OP and "本周食材" in OP and "区间估算" in OP
    # 副标题出现扩充后的内部词 → 渲染失败
    rc, out = _render(_plan(subtitle="locked_basket 已生成"))
    assert rc != 0


def test_cycle_wording_user_friendly():
    assert "周期阶段参数满足" in SK
    assert "周期协议参数满足" not in SK


def test_typography_tokens_four_formats():
    assert "typography_tokens:" in OP
    assert "Yueshi Body" in OP and "Yueshi List" in OP and "Yueshi Disclaimer" in OP
    assert "DOCX" in OP and "Markdown" in OP
    assert "不得直接搬" in OP or "不照搬 CSS 数值" in OP


def test_maintenance_map_marks_render_plan_not_router():
    assert "render_plan.py is not an output router" in MM
    assert "render_output.py" in MM


def test_rules_bundle_hash_covers_safety_rules():
    assert "references/safety-rules.md" in RP
    assert "safety-rules" in OP.split("rules_bundle_hash")[1][:200] or "safety-rules" in OP


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
