# -*- coding: utf-8 -*-
# round 54 回归：两阶段流程 / 渲染门禁 M10 / 采购表 7 列与购买备注 /
# provider_product_name 防泄漏 / menu-map PDF 移除 / 结果校验强化与迁移器。
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RR = read("references/runtime-rules.md")
PF = read("workflows/planning-flow.md")
PP = read("references/price-provider-policy.md")
OP = read("references/output-policy.md")
VS = read("references/visual-spec.md")
Q = read("references/questionnaire.md")
RP = read("scripts/render_plan.py")
PRINT = read("styles/print.css")
SCREEN = read("styles/screen.css")


def test_docs_two_stage_flow():
    for src, name in ((SK, "SKILL"), (RR, "runtime-rules"), (PF, "planning-flow"),
                      (PP, "price-provider-policy"), (OP, "output-policy")):
        assert "awaiting_price_result" in src, f"{name} 缺 awaiting_price_result"
    assert "price_workflow_state" in RR and "opt_out_after_query" in RR
    assert "menu_snapshot_hash" in PF and "nutrition_snapshot_hash" in PF
    assert "局部重算" in PF
    # SKILL：清单交付后暂停，不得同时输出最终 PDF
    assert "禁止生成 PDF、Word" in SK and "G12" in SK and "G13" in SK  # G12/G13 入口级门禁


def test_docs_validation_hardening():
    assert "price_result_invalid" in PP and "禁止人工静默绕过" in PP and "G13" in PP
    assert "migration_log" in PP and "price_result_migrator.py" in PP
    assert "conditional_accept" in PP and "purchase_note" in PP or "购买备注" in PP


def test_questionnaire_ab_format():
    # round58：逐计划周期必显选答（不再有"不填默认 B"）
    assert "A. 使用「月食叮咚查价助手」" in Q
    assert "按当地公开参考价格估算" in Q
    assert "必显选答" in Q and "不填默认 B" not in Q


def test_output_policy_gates_and_table():
    for m in ("M01", "M05", "M06", "M10"):
        assert m in OP, f"output-policy 缺 {m}"
    assert "购买备注" in OP and "provider_product_name" in OP
    # round56：映射组件恢复为格式差异化（round55 全移除口径已撤销）
    assert "render_meal_usage_map" in RP and "menu-map" in RP
    assert "menu-map-print-note" not in PRINT and "menu-map-extra" not in PRINT


def test_render_gates_in_renderer():
    assert "check_provider_name_leak" in RP
    assert "provider-product-name" in RP and "（叮咚：" in RP
    assert "购买备注" in RP  # 7 列表头
    ro = read("scripts/render_output.py")
    assert "awaiting_price_result" in ro and "M10" in ro


def test_m10_gate_blocks_render():
    with tempfile.TemporaryDirectory() as td:
        plan = {"plan": {"date_range": "x", "subtitle": "x", "stats": {}},
                "price_workflow_state": "awaiting_price_result"}
        fp = os.path.join(td, "plan.json")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(plan))
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "render_output.py"),
                            "--input", fp, "--format", "md",
                            "--output", os.path.join(td, "o.md")],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "M10" in (r.stderr + r.stdout)


def test_migrator(tmp_doc=None):
    mig = os.path.join(BASE, "scripts", "price_result_migrator.py")
    with tempfile.TemporaryDirectory() as td:
        # 缺根级必填 → price_result_invalid，非零退出
        bad = os.path.join(td, "bad.json")
        io.open(bad, "w", encoding="utf-8").write(json.dumps(
            {"schema_version": "1.1", "results": []}))
        r = subprocess.run([sys.executable, mig, "--input", bad,
                            "--output", os.path.join(td, "o.json")],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "price_result_invalid" in r.stderr
        # 旧版 → 1.2，写入 migration_log
        old = os.path.join(td, "old.json")
        io.open(old, "w", encoding="utf-8").write(json.dumps({
            "schema_version": "1.1", "provider": "dingdong_web",
            "request_id": "req-9",
            "started_at": "2026-08-30T10:00:00+08:00",
            "completed_at": "2026-08-30T10:05:00+08:00",
            "delivery_context_confirmed_by_user": True,
            "results": [
                {"ingredient_id": "鸡蛋", "query": "鸡蛋", "status": "success",
                 "candidates": [{"ingredient_id": "鸡蛋", "query": "鸡蛋",
                                 "product_name": "x", "observed_at": None,
                                 "product_url": None}]}]}))
        out = os.path.join(td, "new.json")
        r = subprocess.run([sys.executable, mig, "--input", old, "--output", out],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        doc = json.load(io.open(out, encoding="utf-8"))
        assert doc["schema_version"] == "1.2"
        log = doc["migration_log"]
        # round55 G13 定稿字段
        assert log["source_schema_version"] == "1.1"
        assert log["target_schema_version"] == "1.2"
        assert log["migrator_version"] and log["revalidation_passed"] is True
        assert log["migrated_at"] and "fields_added" in log
        cand = doc["results"][0]["candidates"][0]
        assert "observed_at" not in cand and "product_url" not in cand


def test_schemas_and_catalog_sync():
    rs = read("schemas/price-result.schema.json")
    assert "conditional_accept" in rs and "purchase_note" in rs
    cat = json.loads(read("data/ingredient-catalog.json"))
    assert cat["catalog_version"] == "1.6.0"
    qp = cat["items"]["鸡蛋"]["query_profile"]
    assert "shell_egg" in qp["allowed_forms"]
    assert "pancake" in qp["excluded_states"]
    fd = json.loads(read("data/product-form-dictionary.json"))
    assert fd["form_dictionary_version"] == "1.4.0"
    assert "conditional_accept" in fd


def _plan_with_shopping(item_extra):
    plan = {"plan": {"date_range": "2026-09-01 至 2026-09-07", "subtitle": "s",
                     "stats": {}},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "x",
                          "runtime_rules_version": "x", "nutrition_rules_version": "x",
                          "output_policy_version": "x", "recipe_manifest_version": "x",
                          "effective_parameters_version": "x", "price_data_version": "x"},
            "profile": {},
            "shopping": {"items": [dict(
                ingredient="牛肉", category="肉蛋水产与豆制品",
                required_quantity="400g", acceptable_package="500g/袋",
                reference_price="35元/袋", price_basis="direct_public_price",
                substitutes=[], leftover_action="0 剩余", **item_extra)]},
            "prep": {"leftover_verification": [
                {"ingredient": "牛肉", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周二 9/1", "window": "进食 07:30–19:30",
                      "meals": [{"time": "12:00", "name": "午餐", "dishes": "炖牛肉",
                                 "grams": "牛肉100g", "status": "自炊"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}
    return plan


def _render(plan):
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "plan.json")
        op = os.path.join(td, "o.html")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False))
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "render_plan.py"),
                            "--input", fp, "--format", "html",
                            "--output", op],
                           capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and os.path.exists(op):
            out += io.open(op, encoding="utf-8").read()
        return r.returncode, out


def test_shopping_table_note_and_double_line():
    rc, out = _render(_plan_with_shopping({
        "provider_product_name": "调味牛肉片500g",
        "purchase_note": "附独立调味包，可不用"}))
    assert rc == 0
    assert "购买备注" in out and "附独立调味包，可不用" in out
    assert "provider-product-name" in out and "（叮咚：调味牛肉片500g）" in out


def test_provider_name_leak_gate():
    plan = _plan_with_shopping({"provider_product_name": "调味牛肉片500g"})
    plan["days"][0]["meals"][0]["dishes"] = "调味牛肉片500g 炖土豆"
    rc, out = _render(plan)
    assert rc != 0 and "字段泄漏门禁" in out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = []
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            fails.append(fn.__name__)
            print("FAIL", fn.__name__, e)
    print("round54:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
