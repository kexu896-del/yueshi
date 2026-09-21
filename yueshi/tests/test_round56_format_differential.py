# -*- coding: utf-8 -*-
# round 56 验收：格式差异化展示「对应菜单及用量」——
# HTML 可折叠完整版 / Markdown 分组列表 / Word 附录（经 Markdown 链路）/
# PDF full/summary/hidden 三模式与 auto 评估日志；G12/G13 与商品名边界不回退。
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RR = read("references/runtime-rules.md")
PF = read("workflows/planning-flow.md")
OP = read("references/output-policy.md")
VS = read("references/visual-spec.md")
RP = read("scripts/render_plan.py")
RMD = read("scripts/render_markdown.py")
RPDF = read("scripts/render_pdf.py")


def _plan(items, output_options=None):
    plan = {"plan": {"date_range": "2026-09-01 至 2026-09-07", "subtitle": "s",
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
                      "meals": [{"time": "12:00", "name": "午餐", "dishes": "青椒猪里脊",
                                 "grams": "猪里脊120g", "status": "自炊"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}
    if output_options:
        plan["output_options"] = output_options
    return plan


def _item(**extra):
    return dict(ingredient="猪里脊", category="肉蛋水产与豆制品",
                required_quantity="240g", acceptable_package="250g/盒",
                reference_price="18元/盒", price_basis="direct_public_price",
                substitutes=["鸡胸肉"], leftover_action="0 剩余",
                meal_allocation="9月2日晚餐 青椒猪里脊120g、9月3日晚餐 咖喱饭120g",
                **extra)


def _render_html(plan, fmt="html"):
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "plan.json")
        op = os.path.join(td, "o.html")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False))
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_plan.py"),
                            "--input", fp, "--format", fmt, "--output", op],
                           capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and os.path.exists(op):
            out += io.open(op, encoding="utf-8").read()
        return r.returncode, out


def test_docs_differential_policy():
    assert "格式差异化" in OP and "shopping_meal_usage_map" in OP
    assert "output_options" in OP
    assert "PDF：固定 hidden" in OP or "PDF：固定不展示" in OP or "PDF 固定 hidden" in OP
    assert "不再支持 auto/full/summary" in OP  # PDF 试排逻辑已删除
    assert "见网页版展开" in OP  # 以禁止形式出现
    assert "差异化渲染" in RR and "不得跳过暂停直落最终渲染" in RR
    assert "格式差异化" in PF
    assert "PDF 固定不展示" in VS
    # SKILL 摘要指向 output-policy，G12/G13 完整定义只在入口级门禁清单
    assert "PDF 不展示" in SK
    assert "G12. [user_input_required]" in SK and "G13. [user_input_required]" in SK


def test_version_bumped():
    assert "version: yueshi-1.4.3" in SK


def test_html_full_collapsible():
    rc, html = _render_html(_plan([_item()]))
    assert rc == 0
    assert "<details class='menu-map'>" in html
    assert "9月2日晚餐 青椒猪里脊120g" in html
    assert "见网页版展开" not in html
    # 映射模块不含叮咚商品名
    rc, html2 = _render_html(_plan([_item(provider_product_name="新鲜猪大里脊")]))
    assert rc == 0 and html2.count("新鲜猪大里脊") == 1  # 仅采购清单第二行一处


def test_pdf_modes():
    detail = "9月2日晚餐 青椒猪里脊120g"
    # 默认即 hidden：PDF 不生成映射表标题、表头、残留行或空容器
    rc, out = _render_html(_plan([_item()]), fmt="pdf")
    assert rc == 0 and "<table class='menu-map-table'" not in out \
        and "<div class='menu-map" not in out and detail not in out
    assert "auto →" not in out  # 不再有评估/降级日志
    # 显式 hidden 合法
    rc, out = _render_html(_plan([_item()], {"meal_usage_map": {"pdf": "hidden"}}), fmt="pdf")
    assert rc == 0 and detail not in out
    # PDF 配 full/summary/auto 即渲染失败（固定 hidden）
    for bad in ("full", "summary", "auto"):
        rc, out = _render_html(_plan([_item()], {"meal_usage_map": {"pdf": bad}}), fmt="pdf")
        assert rc != 0 and "PDF 固定 hidden" in out, bad
    # 非法取值即失败
    rc, out = _render_html(_plan([_item()], {"meal_usage_map": {"pdf": "weird"}}), fmt="pdf")
    assert rc != 0
    # render_pdf.py 走 fmt="pdf"
    assert 'render_document(plan, fmt="pdf")' in RPDF
    # 打印样式不再含映射表规则
    pr = read("styles/print.css")
    assert "menu-map" not in pr


def test_markdown_grouped():
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "plan.json")
        op = os.path.join(td, "o.md")
        io.open(fp, "w", encoding="utf-8").write(json.dumps(_plan([_item()]), ensure_ascii=False))
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_markdown.py"),
                            "--input", fp, "--output", op], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        md = io.open(op, encoding="utf-8").read()
    assert "## 食材对应菜单及用量" in md
    assert "### 猪里脊，共 240g" in md
    assert "- 9月2日晚餐 青椒猪里脊120g" in md
    assert "- 9月3日晚餐 咖喱饭120g" in md


def test_no_regression_gates():
    # G12/G13 不回退
    assert "awaiting_price_result" in SK and "request_id" in SK
    # 采购表 7 列与双行商品名不回退
    assert "购买备注" in RP and "provider-product-name" in RP
    # 模式降级说明在渲染器（只重跑渲染层）
    assert "render_meal_usage_map" in RP and "_meal_map_mode" in RP


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
    print("round56:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
