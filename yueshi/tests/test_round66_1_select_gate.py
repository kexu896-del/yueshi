# -*- coding: utf-8 -*-
"""round66.1（2026-09-18）：预选确认强制交互（SELECT-001）回归。

断言：
- 本周已删除（week_only_dislikes）的食材不得进入候选清单（layers/numbered）；
- 锁定留痕 selection_mode：applied（有选择）/ bypassed（明确"都可以"）/ provisional（未回复）；
- 未确认锁定时 stderr 输出 SELECT-001 告警；
- planning-flow.md 与 rule-index.md 含 SELECT-001 与"不得自行整批接受"。
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "ingredient_preselector.py")
fails = []


def run(args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, "-X", "utf8", SCRIPT] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


with tempfile.TemporaryDirectory() as td:
    basket = {"weekly_basket": {
        "proteins": ["鸡蛋", "鸡腿"],
        "vegetables": ["黄瓜", "菠菜", "生菜"],
        "carbohydrates": ["南瓜"],
        "flavor_bases": ["酱香"],
        "fat_extras": ["全脂牛奶"]}}
    bp = os.path.join(td, "basket.json")
    json.dump(basket, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
    prefs = {"week_only_dislikes": ["黄瓜"],
             "preference_status": {"黄瓜": "dislike_this_week"},
             "permanent_dislikes": [], "history_4w": {}, "current_week": 38}
    pp = os.path.join(td, "prefs.json")
    json.dump(prefs, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
    cp = os.path.join(td, "cands.json")
    r = run(["--build-candidates", "--basket", bp, "--month", "9",
             "--preferences", pp, "--export-json", cp])
    if r.returncode != 0:
        fails.append("build-candidates 运行失败: %s" % (r.stderr[-200:] if r.stderr else ""))
    else:
        c = json.load(open(cp, encoding="utf-8"))
        names = {e["normalized_name"] for lst in c["layers"].values() for e in lst}
        if "黄瓜" in names:
            fails.append("本周已删除食材仍出现在候选清单")
        dropped = dict(c.get("dropped_before_selection", []))
        if "黄瓜" not in dropped or "已删除" not in dropped.get("黄瓜", ""):
            fails.append("预筛选移除未记录本周已删除原因")

    # 未确认锁定 → provisional + 告警
    r = run(["--lock-basket", "--candidates", cp])
    try:
        b = json.loads(r.stdout)["locked_basket"]
        if b.get("selection_mode") != "provisional":
            fails.append("未确认锁定 selection_mode 应为 provisional，实为 %r" % b.get("selection_mode"))
    except Exception as e:
        fails.append("未确认锁定输出不可解析: %r" % e)
    if "SELECT-001" not in (r.stderr or ""):
        fails.append("未确认锁定未输出 SELECT-001 告警")

    # 明确"都可以" → bypassed（带偏好文件时也不得误记为 applied）
    r = run(["--lock-basket", "--candidates", cp, "--preferences", pp, "--user-reviewed"])
    try:
        b = json.loads(r.stdout)["locked_basket"]
        if b.get("selection_mode") != "bypassed":
            fails.append("明确都可以锁定 selection_mode 应为 bypassed，实为 %r" % b.get("selection_mode"))
        if "黄瓜" in b.get("vegetables", []):
            fails.append("偏好文件中本周已删除项未从锁定篮子剔除")
    except Exception as e:
        fails.append("bypass 锁定输出不可解析: %r" % e)

    # 用户选择 → applied，删除项不进篮子
    sp = os.path.join(td, "sel.json")
    json.dump({"remove": ["菠菜"]}, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    r = run(["--lock-basket", "--candidates", cp, "--selection", sp,
             "--preferences", pp, "--user-reviewed"])
    try:
        b = json.loads(r.stdout)["locked_basket"]
        if b.get("selection_mode") != "applied":
            fails.append("有选择锁定 selection_mode 应为 applied，实为 %r" % b.get("selection_mode"))
        if "菠菜" in b.get("vegetables", []):
            fails.append("用户删除项未从锁定篮子移除")
    except Exception as e:
        fails.append("applied 锁定输出不可解析: %r" % e)

# 文档门禁
pf = open(os.path.join(ROOT, "workflows", "planning-flow.md"), encoding="utf-8").read()
if "SELECT-001" not in pf or "不得自行整批接受" not in pf:
    fails.append("planning-flow 缺 SELECT-001 强制交互规则")
ri = open(os.path.join(ROOT, "references", "rule-index.md"), encoding="utf-8").read()
if "SELECT-001" not in ri:
    fails.append("rule-index 缺 SELECT-001")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round66.1 预选确认强制交互（SELECT-001）全部通过")
