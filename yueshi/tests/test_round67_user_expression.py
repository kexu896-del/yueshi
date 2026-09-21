# -*- coding: utf-8 -*-
"""round67（2026-09-18）：用户表达层与运行可靠性回归。

断言：
- 模式显示映射：hormone_balance → 平衡激素模式、keto_biologic → 酮生物模式；全仓无"均衡激素模式"；
- 用户文案转换器：可选加餐/蛋白/预算/估价均为生活化文案，不含内部词；
- 渲染门禁：用户可见文字出现"热量补偿/主餐口径/试跑"等内部表达即失败；
- PDF 每日营养只展示生活化摘要（nutrition_summary.user_line），不展示计算口径；
- PDF 执行提醒超过 5 条即失败；
- render_pdf 传目录路径必须显式失败（rc=2），不得静默"成功"；
- README 关键八项为有序子列表。
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import render_plan as rp  # noqa: E402
import visible_messages as vm  # noqa: E402

fails = []

# 1) 模式显示映射
rules = vm.load_mode_display()
hb = vm.mode_display("hormone_balance", rules)
kb = vm.mode_display("keto_biologic", rules)
if not hb or hb["display_name"] != "平衡激素模式":
    fails.append("hormone_balance 显示名应为 平衡激素模式")
if not kb or kb["display_name"] != "酮生物模式":
    fails.append("keto_biologic 显示名应为 酮生物模式")
if vm.mode_display("unknown_mode", rules) is not None:
    fails.append("未知模式不得猜测显示名")

# 全仓不得出现"均衡激素模式"（本测试文件与 mode-display 的禁用词表除外）
for r, ds, fs in os.walk(ROOT):
    if any(s in r for s in ("book-extraction", "__pycache__", ".pytest_cache")):
        continue
    for f in fs:
        if not f.endswith((".md", ".py", ".json")):
            continue
        if f in ("test_round67_user_expression.py", "test_round67_final_acceptance.py",
                 "mode-display.json", "CHANGELOG.md"):
            continue
        p = os.path.join(r, f)
        if "均衡激素模式" in open(p, encoding="utf-8", errors="ignore").read():
            fails.append("仍存在旧称：%s" % p.replace(ROOT, ""))

# 2) 转换器文案
snack = vm.snack_line("calorie_floor_adjustment")
if "饿" not in snack or "热量补偿" in snack or "自动" in snack:
    fails.append("可选加餐文案不合格：%s" % snack)
pl = vm.protein_line("above_target_tolerance")
if "饥饿" not in pl or "above_target_tolerance" in pl:
    fails.append("蛋白文案不合格：%s" % pl)
budget = vm.budget_summary(150, 157.5, 183.57)
if "预算目标为 150" not in budget or "可接受范围约至 157.5" not in budget or "高约 26.07" not in budget:
    fails.append("预算摘要不合格：%s" % budget)
if "5%" in budget or "线" in budget:
    fails.append("预算摘要不得出现内部比例口径：%s" % budget)
note = vm.estimate_note()
if any(w in note for w in ("candidates_filtered", "查价失败", "过滤")):
    fails.append("估价说明含内部词：%s" % note)

# 3) 渲染门禁：内部表达
plan = json.loads(open(os.path.join(ROOT, "data/golden/golden-sample-plan.json"),
                       encoding="utf-8").read())
html = rp.render_document(plan, fmt="html")
errs = rp.validate_html(html, plan)
if errs:
    fails.append("golden 样例渲染校验不应失败：%s" % errs[:2])
bad = html.replace("本周执行要点", "热量补偿加餐说明", 1)
errs2 = rp.validate_html(bad, plan)
if not any("内部表达" in e for e in errs2):
    fails.append("内部表达（热量补偿）未被渲染门禁拦截")

# 4) PDF 每日营养：用 nutrition_summary，不展示计算口径
day = plan["days"][0]
day["nutrition_line"] = "净碳水约 92g（主餐口径，补偿加餐不计上限）"
day["nutrition_summary"] = {"status": "within_plan", "user_line": "今日营养：整体符合本周安排。"}
html_pdf = rp.render_days([day], False, fmt="pdf")
if "主餐口径" in html_pdf or "不计上限" in html_pdf:
    fails.append("PDF 每日营养仍展示计算口径")
if "今日营养：整体符合本周安排。" not in html_pdf:
    fails.append("PDF 每日营养未使用 user_line")
html_md = rp.render_days([day], False, fmt="html")
if "主餐口径" not in html_md:
    fails.append("HTML 每日营养应保留参考估算行")

# 5) PDF 执行提醒 >5 条失败
plan6 = json.loads(json.dumps(plan))
plan6["execution_tips"] = ["提醒%d" % i for i in range(6)]
try:
    rp.render_document(plan6, fmt="pdf")
    fails.append("PDF 执行提醒 6 条未被拦截")
except SystemExit as e:
    if "5 条" not in str(e):
        fails.append("PDF 提醒超限报错信息不含 5 条：%s" % e)

# 6) render_pdf 传目录必须显式失败
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
r = subprocess.run([sys.executable, "-X", "utf8",
                    os.path.join(ROOT, "scripts", "render_pdf.py"),
                    "--input", os.path.join(ROOT, "data/golden/golden-sample-plan.json"),
                    "--output", os.path.join(ROOT, "tests")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
if r.returncode != 2 or "必须是文件路径" not in (r.stderr or ""):
    fails.append("render_pdf 传目录未显式失败（rc=%s）" % r.returncode)

# 7) README 关键八项有序子列表
readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
for needle in ("1. **基本情况**", "6. **预算库存**", "8. **输出格式**"):
    if needle not in readme:
        fails.append("README 关键八项缺：%s" % needle)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round67 用户表达层与运行可靠性全部通过")
