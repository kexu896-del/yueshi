# -*- coding: utf-8 -*-
# round 36 定版回归：plan_meta 契约声明 build_id/rules_bundle_hash +
# fatal_after_retry 归入 fatal_reason 枚举 + 定版 18 项回归清单映射核验
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
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
                                 "order_template": "balanced_standard", "status": "外食 · 区间估算"}]}],
            "wisdom": {"paragraphs": ["段一", "段二", "段三"]},
            "execution_tips": ["动作一", "动作二"],
            "disclaimer": "本计划为一般性健康饮食建议。"}
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


def test_plan_meta_contract_declares_build_id_and_hash():
    # 契约字段列表必须声明门禁实际使用的字段，不能只列 8 个明细版本
    for f in ("build_id", "plan_schema_version", "rules_bundle_hash"):
        assert f in SK and f in OP, f
    # 哈希覆盖六文件在文档中声明
    seg = OP[OP.index("plan_meta 构建标识"):]
    for f in ("safety-rules", "runtime-rules", "nutrition-routing",
              "output-policy", "effective-parameters", "recipe-manifest"):
        assert f in seg, f


def test_gate_status_three_values_with_fatal_reason():
    # 状态只有三类；fatal_after_retry 不作为第四状态出现
    assert "fatal_after_retry" not in SK
    assert "fatal_reason" in SK
    for r in ("core_rule_file_missing", "safety_route_unresolvable", "plan_schema_mismatch",
              "rules_bundle_mismatch", "corrupted_plan_json", "auto_fix_retry_exhausted",
              "renderer_retry_exhausted"):
        assert r in SK, r
    assert "status 升级为 `fatal`" in SK


def test_hash_gate_still_enforced():
    rc, out = _render(_plan(bad_hash=True))
    assert rc != 0 and "rules_bundle_hash" in out
    rc, out = _render(_plan())
    assert rc == 0


# ---- 定版 18 项回归清单（映射到既有测试文件；此处做存在性核验）----
def test_release_checklist_coverage():
    checklist_tests = {
        1: "test_ranker_empty_fingerprint.py",          # 空指纹不崩溃
        2: "test_protein_reference_not_cap.py",         # book_reference 非硬上限
        3: "test_nutrition_gate_before_render.py",      # 碳水超限冻结前修正
        4: "test_accepted_batch_semantics.py",          # 都可以吃→accepted_batch
        5: "test_accepted_batch_items.py",              # accepted_batch 不静默消失
        8: "test_cafeteria_template.py",                # 食堂午餐完整点餐结构
        10: "test_render_gates.py",                     # 每采购项有价格
        15: "test_html_self_contained.py",              # 离开目录样式完整
        16: "test_pdf_layout.py",                       # PDF 布局门禁
        17: "test_output_router.py",                    # 四格式同一 plan.json
    }
    for n, f in checklist_tests.items():
        assert os.path.exists(os.path.join(BASE, "tests", f)), f"{n}: {f}"
    # 6/7 餐次契约、9 一锅出、11 术语、12 字号、13 免责声明、14 当日建议、18 哈希
    for f in ("test_round31_finalization.py", "test_round33_output_polish.py",
              "test_round34_gates.py", "test_round35_gates.py"):
        assert os.path.exists(os.path.join(BASE, "tests", f)), f


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
