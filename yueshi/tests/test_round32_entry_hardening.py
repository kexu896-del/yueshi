# -*- coding: utf-8 -*-
# round 32 入口加固回归：渲染器命名 / plan_meta 版本门禁 / 规则优先级 / 失败关闭 / 触发收窄
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
CORPUS = SK + read("references/runtime-rules.md") + read("references/nutrition-routing.md") + read("references/output-policy.md")


def test_renderer_naming_unique():
    # 渲染器语义唯一：总控与格式渲染器分离
    for f in ("scripts/render_plan.py", "scripts/render_html.py", "scripts/render_pdf.py",
              "scripts/render_markdown.py", "scripts/render_docx.py", "scripts/render_output.py"):
        assert os.path.exists(os.path.join(BASE, f)), f
    assert "render_output.py" in SK and "总控路由" in SK
    assert "Chromium 打印一次" in SK


def test_plan_meta_gate():
    src = read("scripts/render_plan.py")
    assert "PLAN_SCHEMA_VERSION" in src and "check_plan_meta" in src
    for f in ("plan_schema_version", "skill_version", "recipe_manifest_version",
              "effective_parameters_version", "price_data_version"):
        assert f in src and f in CORPUS, f
    # 缺 plan_meta 必须失败关闭
    plan = {"plan": {"date_range": "x", "stats": {}}, "profile": {}, "shopping": {"items": []},
            "days": [], "disclaimer": "d"}
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "p.json")
        json.dump(plan, open(ip, "w", encoding="utf-8"))
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_markdown.py"),
                            "--input", ip, "--output", os.path.join(td, "o.md")],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "plan_meta" in (r.stderr + r.stdout)


def test_rule_conflict_priority():
    assert "规则冲突裁决" in SK  # round34 起改为按领域裁决
    assert "safety-rules.md" in SK and "以对应详细规则文件为准" in SK
    assert "不参与用户计划决策" in SK  # maintenance-map 角色
    assert "不是运行规则" in SK        # CHANGELOG 角色


def test_rule_file_fail_closed():
    assert "规则文件完整性门禁" in SK and "失败关闭" in SK
    assert "不使用模型记忆补写缺失规则" in SK
    assert "本次仅提供一般建议" in SK  # round34 起降级输出边界收紧


def test_cycle_wording_softened():
    assert "方可进入计划计算" in CORPUS
    assert "更保守的安全参数" in SK or "采用更保守值" in CORPUS
    assert "即按书直接执行" not in CORPUS, "旧的强口径残留"


def test_price_integrity_bridge():
    assert "价格完整性不等于允许编造价格" in SK and "价格完整性不等于允许编造价格" in read("references/runtime-rules.md")
    assert "冻结前将该食材替换为可合理定价的同功能食材" in CORPUS


def test_questionnaire_summary_and_single_round():
    assert "关键八项" in SK and "连续 7 天" in SK
    assert "合并在同一轮动态追问" in SK and "不得逐餐连续追问" in SK


def test_description_narrowed():
    desc = SK.split("---")[1]
    assert "不自动启动完整 15 步" in desc or "不自动启动完整15步" in desc
    assert "桥本" not in desc and "抗炎" not in desc and "五运六气" not in desc


def test_theory_not_decision_factor():
    assert "理论展示不得反向影响菜单" in SK
    assert "8. 理论展示" not in SK


def test_supplement_wording():
    assert "不主动推荐补充剂" in SK
    assert "补充剂只作“可考虑”" not in SK


def test_entry_final_gate():
    assert "入口级最终门禁" in SK
    # round43：G03 拆分为 G03a/G03b，关键词同步为新表述
    for kw in ("安全筛查", "locked_basket", "营养校验通过",
               "用户必填信息、餐次、做法和格式明确"):
        assert kw in SK, kw


def test_render_pdf_and_output_functional():
    plan = {"plan": {"date_range": "2026-08-23 至 2026-08-29", "stats": {}},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24",
                          "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24",
                          "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08",
                          "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
            "profile": {},
            "shopping": {"items": [{"ingredient": "虾", "category": "肉蛋水产与豆制品",
                                    "required_quantity": "300g", "acceptable_package": "300g/袋",
                                    "reference_price": "26元/袋", "price_basis": "category_estimate",
                                    "substitutes": [], "leftover_action": "0 剩余"}]},
            "prep": {"leftover_verification": [
                {"ingredient": "虾", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周六 8/23", "window": "进食 07:30–19:30",
                      "meals": [{"time": "07:30", "name": "早餐", "dishes": "燕麦碗", "status": "自炊"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "plan.json")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_output.py"),
                            "--input", ip, "--format", "md,docx", "--output", td],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert os.path.exists(os.path.join(td, "plan.md")) and os.path.exists(os.path.join(td, "plan.docx"))


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
    print("round32:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
