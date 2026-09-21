# -*- coding: utf-8 -*-
# round 55 验收：最终修订方案十项清单——
# 唯一正式查价清单生成点 / G12 / G13 / 商品名边界 / menu-map 全格式移除 /
# 迁移日志格式 / 快照哈希 / 购买备注与剩余去向分开 / 列顺序。
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RR = read("references/runtime-rules.md")
PF = read("workflows/planning-flow.md")
PP = read("references/price-provider-policy.md")
OP = read("references/output-policy.md")
Q = read("references/questionnaire.md")
RP = read("scripts/render_plan.py")
RM = read("scripts/render_markdown.py")
RO = read("scripts/render_output.py")
PRINT = read("styles/print.css")
SCREEN = read("styles/screen.css")


def test_single_formal_query_file():
    # 修正一：预选不生成草稿；唯一正式清单在步骤 13（菜单+营养+新购需求后）
    for src, name in ((RR, "runtime-rules"), (Q, "questionnaire"),
                      (SK, "SKILL"), (PP, "policy"), (PF, "planning-flow")):
        assert "预选锁定后" not in src.replace("预选阶段只登记", ""), f"{name} 仍有预选生成草稿口径"
        assert "查价清单草稿" not in src, f"{name} 仍提查价清单草稿"
    assert "唯一正式" in RR and "唯一正式" in PF
    assert "最终 ingredient_id 和 request_id" in PF or "最终 ingredient_id 与 request_id" in PF


def test_g12_gate():
    for src, name in ((SK, "SKILL"), (OP, "output-policy"), (RR, "runtime-rules")):
        assert "G12" in src, f"{name} 缺 G12"
    assert "拒绝渲染是正常等待状态" in OP or "属正常等待" in OP
    assert "不属于 fatal" in OP or "不判 fatal" in RR
    assert "G12" in RO  # 渲染总控执行
    # G12 实际拦截
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "plan.json")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(
            {"plan": {"date_range": "x", "subtitle": "x", "stats": {}},
             "price_workflow_state": "awaiting_price_result"}))
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_output.py"),
                            "--input", fp, "--format", "pdf",
                            "--output", os.path.join(td, "o.pdf")],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "G12" in (r.stderr + r.stdout)


def test_g13_gate():
    for src, name in ((SK, "SKILL"), (OP, "output-policy"), (PP, "policy")):
        assert "G13" in src, f"{name} 缺 G13"
    assert "request_id` 必须与本次查价清单一致" in PP or "request_id 必须与本次查价清单一致" in PP
    assert "禁止人工静默绕过" in PP
    # 迁移日志 G13 字段
    for f in ("source_schema_version", "target_schema_version", "fields_added",
              "migrator_version", "revalidation_passed"):
        assert f in PP, f"policy 缺 migration_log 字段 {f}"
    assert "只有在旧文件来源可唯一确认时才可补齐" in PP
    assert "不能直接填最新版" in PP
    assert "不进入用户 PDF" in PP
    # schema 允许 migration_log 根级字段
    rs = json.loads(read("schemas/price-result.schema.json"))
    assert "migration_log" in rs["properties"]


def _base_plan(items):
    return {"plan": {"date_range": "2026-09-01 至 2026-09-07", "subtitle": "s",
                     "stats": {}},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "x",
                          "runtime_rules_version": "x", "nutrition_rules_version": "x",
                          "output_policy_version": "x", "recipe_manifest_version": "x",
                          "effective_parameters_version": "x", "price_data_version": "x"},
            "profile": {},
            "shopping": {"items": items},
            "prep": {"leftover_verification": [
                {"ingredient": "猪里脊", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周二 9/1", "window": "进食 07:30–19:30",
                      "meals": [{"time": "12:00", "name": "午餐", "dishes": "炒猪里脊",
                                 "grams": "猪里脊100g", "status": "自炊"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}


def _render(script, plan, fmt_arg=None):
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "plan.json")
        op = os.path.join(td, "o.out")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False))
        cmd = [sys.executable, os.path.join(BASE, "scripts", script),
               "--input", fp, "--output", op]
        if fmt_arg:
            cmd += ["--format", fmt_arg]
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and os.path.exists(op):
            out += io.open(op, encoding="utf-8").read()
        return r.returncode, out


def _item(**extra):
    return dict(ingredient="猪里脊", category="肉蛋水产与豆制品",
                required_quantity="400g", acceptable_package="500g/袋",
                reference_price="35元/袋", price_basis="direct_public_price",
                substitutes=["鸡胸肉"], leftover_action="0 剩余", **extra)


def test_menu_map_differential_formats():
    # round56：撤销全格式移除——HTML 可折叠完整版、Markdown 分组列表、
    # PDF 完整展开（试验期 full）；任何格式无"见网页版展开"截断。
    plan = _base_plan([_item(meal_allocation="周一午100g")])
    rc, html = _render("render_plan.py", plan, "html")
    assert rc == 0 and "对应菜单及用量" in html and "<details class='menu-map'>" in html
    assert "周一午100g" in html and "见网页版展开" not in html
    rc, md = _render("render_markdown.py", plan)
    assert rc == 0 and "## 食材对应菜单及用量" in md and "周一午100g" in md
    assert "### 猪里脊，共 400g" in md
    assert "render_meal_usage_map" in RP
    assert "menu-map" not in PRINT  # PDF 固定 hidden，无打印规则
    assert "menu-map" in SCREEN  # HTML 折叠组件样式保留


def test_shopping_columns_and_separation():
    # 列顺序：食材/需要量/建议购买规格/参考价/购买备注/替代/剩余去向
    hdr = "<th>食材</th><th>需要量</th><th>建议购买规格</th><th>参考价</th><th>购买备注</th><th>替代</th><th>剩余去向</th>"
    assert hdr in RP
    plan = _base_plan([_item(provider_product_name="新鲜猪大里脊（去筋膜）",
                             purchase_note="去筋膜")])
    rc, html = _render("render_plan.py", plan, "html")
    assert rc == 0
    assert "去筋膜" in html
    # 嵌套括号转逗号
    assert "（叮咚：新鲜猪大里脊，去筋膜）" in html
    # Markdown 同口径：含购买备注列与叮咚注记
    rc, md = _render("render_markdown.py", plan)
    assert rc == 0 and "| 购买备注 |" in md and "（叮咚：新鲜猪大里脊，去筋膜）" in md


def test_snapshot_hashes_and_hash_sourcing():
    for h in ("menu_snapshot_hash", "nutrition_snapshot_hash", "shopping_demand_hash"):
        assert h in PF, f"planning-flow 缺 {h}"
    assert "只有 ingredient_id 发生替换时" in PF
    assert "price_result_hash" in PF and "price_result_hash" in PP


def test_provider_name_boundary_docs():
    assert "复热说明" in OP  # 商品名不得进入复热说明
    assert "购买备注与剩余去向分开" in OP
    assert "附调味包可不用" in OP and "不得写入剩余去向" in OP
    # 渲染器值级门禁：复热说明也不含商品名
    plan = _base_plan([_item(provider_product_name="新鲜猪大里脊")])
    plan["days"][0]["meals"][0]["reheat_note"] = "新鲜猪大里脊 微波 2 分钟"
    rc, out = _render("render_plan.py", plan, "html")
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
    print("round55:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
