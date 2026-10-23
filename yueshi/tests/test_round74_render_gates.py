# -*- coding: utf-8 -*-
"""round74（2026-09-21）：渲染门禁与入口归一。

断言：
- 门禁唯一实现在 scripts/render_gates.py（render_plan 仅 re-export 旧名）；
- 跨格式辅助在 scripts/common/render_shared.py（公开名 + 旧别名兼容）；
- enforce(plan, fmt)：四入口统一执行（必填键/版本/泄漏/价格/流转/PDF 提示条数）；
- validate_user_text：Markdown/Word 产物文字门禁（新增覆盖）；
- render_pdf 不再丢弃 validate_html 错误（未过门禁不打印）；
- render_plan 只生成 HTML：--format pdf 显式拒绝（rc=2）并指路；
- G12 仍由 render_output 总控拦截。
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import render_gates as rg  # noqa: E402
import render_plan as rp  # noqa: E402
import render_shared as rs  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def _plan(**over):
    plan = {
        "plan": {"date_range": "2026-09-21 至 2026-09-27", "stats": {}},
        "plan_meta": {"plan_schema_version": "1", "skill_version": "yueshi-1.4.3",
                      "runtime_rules_version": "1", "nutrition_rules_version": "1",
                      "output_policy_version": "1", "recipe_manifest_version": "1",
                      "effective_parameters_version": "1", "price_data_version": "1.2"},
        "profile": {},
        "shopping": {"items": [{"ingredient": "虾", "category": "肉蛋水产与豆制品",
                                "required_quantity": "300g", "acceptable_package": "300g/袋",
                                "reference_price": "26元/袋", "price_basis": "category_estimate",
                                "substitutes": [], "leftover_action": "0 剩余"}]},
        "prep": {"leftover_verification": [
            {"ingredient": "虾", "purchase_vs_use": "1:1", "result": "0 剩余"},
            {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
            {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
        "days": [{"label": "周一 9/21", "window": "进食 07:30–19:30",
                  "meals": [{"time": "07:30", "name": "早餐", "dishes": "燕麦碗", "status": "自炊"}]}],
        "wisdom": {"paragraphs": ["本周按节奏安排。"]},
        "execution_tips": ["铁剂与钙片间隔两小时"],
        "disclaimer": "本计划为一般性健康饮食建议。",
    }
    plan.update(over)
    return plan


def _expect_exit(fn, needle, label):
    try:
        fn()
    except SystemExit as e:
        check(needle in str(e), "%s：报错信息缺 %r（实际 %r）" % (label, needle, str(e)[:120]))
        return
    fails.append("%s：未触发 SystemExit" % label)


def _run(script, args, plan=None):
    with tempfile.TemporaryDirectory() as td:
        cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script)] + args
        if plan is not None:
            ip = os.path.join(td, "plan.json")
            with open(ip, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False)
            cmd = [c.replace("{plan}", ip).replace("{td}", td) for c in cmd]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=120)
        return r, td


# ---------- 1) 模块归属与 re-export ----------
for name in ("enforce", "validate_user_text", "validate_html", "check_plan_meta",
             "compute_rules_bundle_hash", "compute_pipeline_bundle_hash"):
    check(hasattr(rg, name), "render_gates 缺 %s" % name)
check(rp.validate_html is rg.validate_html and rp.enforce is rg.enforce,
      "render_plan 必须 re-export render_gates 门禁（旧调用面兼容）")
for name in ("display_price", "window_no_fasting", "normalize_provider_name",
             "clean", "load_cafeteria_templates", "CATEGORY_ORDER"):
    check(hasattr(rs, name), "render_shared 缺 %s" % name)
check(rp._display_price.__name__ == "display_price"
      and rp._window_no_fasting.__name__ == "window_no_fasting",
      "render_plan 旧下划线别名应指向 render_shared 公开实现")
check(rp._display_price({"reference_price": "26元/袋", "price_basis": "category_estimate"})
      == "约26元/袋", "render_plan 价格渲染行为异常")

# ---------- 2) validate_user_text（md/docx 新增覆盖） ----------
check(rg.validate_user_text("正常的一周饮食计划。") == [], "干净文本不应报错")
check(any("试跑" in e for e in rg.validate_user_text("本周试跑版本。")), "内部表达未被拦截")
check(any("周期协议" in e for e in rg.validate_user_text("# 周期协议\n正文")), "标题内部术语未被拦截")
check(any("三餐自行解决" in e for e in rg.validate_user_text("三餐自行解决")), "非做饭日违禁文案未被拦截")
check(any("{{" in e for e in rg.validate_user_text("x{{y")) or any("占位符" in e for e in rg.validate_user_text("x{{y")),
      "占位符未被拦截")

# ---------- 3) enforce：四入口统一的计划级门禁 ----------
rg.enforce(_plan(), "html")
rg.enforce(_plan(), "pdf")
rg.enforce(_plan(), "md")
rg.enforce(_plan(), "docx")
p = _plan(); del p["disclaimer"]
_expect_exit(lambda: rg.enforce(p, "html"), "缺字段", "缺必填键")
p = _plan(); p["plan_meta"] = {}
_expect_exit(lambda: rg.enforce(p, "html"), "plan_meta", "缺 plan_meta")
p = _plan(); p["days"][0]["meals"][0]["provider_product_name"] = "叮咚虾"
_expect_exit(lambda: rg.enforce(p, "html"), "字段泄漏门禁", "菜谱层商品名泄漏")
p = _plan(); p["shopping"]["items"][0]["reference_price"] = ""
_expect_exit(lambda: rg.enforce(p, "html"), "价格硬门禁", "缺参考价")
p = _plan(); p["prep"]["leftover_verification"] = p["prep"]["leftover_verification"][:2]
_expect_exit(lambda: rg.enforce(p, "html"), "流转核验", "流转核验不足 3 项")
p = _plan(execution_tips=["提示%d" % i for i in range(6)])
_expect_exit(lambda: rg.enforce(p, "pdf"), "5 条", "PDF 提示超过 5 条")
rg.enforce(p, "html")  # HTML 不受 PDF 条数限制

# ---------- 4) 入口集成（subprocess） ----------
# 4.1 Markdown：文字门禁新增覆盖
r, td = _run("render_markdown.py", ["--input", "{plan}", "--output", os.path.join("{td}", "o.md")],
             _plan(execution_tips=["试跑一下"]))
check(r.returncode == 3 and "渲染门禁未通过" in r.stderr, "md 未拦截内部表达（rc=%s）" % r.returncode)
# 4.2 Word：同一门禁（转换前拦截）
r, td = _run("render_docx.py", ["--input", "{plan}", "--output", os.path.join("{td}", "o.docx")],
             _plan(wisdom={"paragraphs": ["试跑阶段说明。"]}))
check(r.returncode == 3 and "渲染门禁未通过" in r.stderr, "docx 未拦截内部表达（rc=%s）" % r.returncode)
# 4.3 PDF：validate_html 错误必须显式失败（不再丢弃）
r, td = _run("render_pdf.py", ["--input", "{plan}", "--output", os.path.join("{td}", "o.pdf")],
             _plan(execution_tips=["试跑提示"]))
check(r.returncode == 3 and "渲染门禁未通过" in r.stderr,
      "PDF 仍吞校验错误（rc=%s, err=%s）" % (r.returncode, r.stderr[:80]))
# 4.4 render_plan 只产 HTML：--format pdf 显式拒绝并指路
r, td = _run("render_plan.py", ["--input", "{plan}", "--format", "pdf",
                                "--output", os.path.join("{td}", "o.pdf")], _plan())
check(r.returncode == 2 and "只生成 HTML" in r.stderr, "render_plan --format pdf 未显式拒绝（rc=%s）" % r.returncode)
# 4.5 正常路径：HTML/Markdown 均成功
r, td = _run("render_plan.py", ["--input", "{plan}", "--output", os.path.join("{td}", "o.html")], _plan())
check(r.returncode == 0, "render_plan html 正常路径失败：%s" % r.stderr[:100])
r, td = _run("render_markdown.py", ["--input", "{plan}", "--output", os.path.join("{td}", "o.md")], _plan())
check(r.returncode == 0, "render_markdown 正常路径失败：%s" % r.stderr[:100])

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round74 渲染门禁与入口归一全部通过")
