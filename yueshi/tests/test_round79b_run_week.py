# -*- coding: utf-8 -*-
"""round79b（2026-09-21）：周计划一键收尾编排（run_week.py）。

断言：
- 目标校验通过 → rc 0，报告 step=targets rc=0；
- 目标矩阵破损 → fail-fast rc 3，报告 ok=false 且错误写 stderr；
- 完整链路（目标 + 渲染）→ rc 0，产物 HTML 存在；
- plan 缺失 → rc 2。
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_WEEK = os.path.join(ROOT, "scripts", "run_week.py")
COMPILER = os.path.join(ROOT, "scripts", "daily_target_compiler.py")

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def _env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=_env(), timeout=timeout)


def _minimal_plan():
    return {
        "plan": {"date_range": "2026-09-21 至 2026-09-27", "stats": {}},
        "plan_meta": {
            "plan_schema_version": "1", "skill_version": "yueshi-1.4.3",
            "runtime_rules_version": "1", "nutrition_rules_version": "1",
            "output_policy_version": "1", "recipe_manifest_version": "1",
            "effective_parameters_version": "1", "price_data_version": "1.2"},
        "profile": {},
        "shopping": {"items": [{
            "ingredient": "虾", "category": "肉蛋水产与豆制品",
            "required_quantity": "300g", "acceptable_package": "300g/袋",
            "reference_price": "26元/袋", "price_basis": "category_estimate",
            "substitutes": [], "leftover_action": "0 剩余"}]},
        "prep": {"leftover_verification": [
            {"ingredient": "虾", "purchase_vs_use": "1:1", "result": "0 剩余"},
            {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
            {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
        "days": [{"label": "周一 9/21", "window": "进食 07:30–19:30",
                  "meals": [{"time": "07:30", "name": "早餐",
                             "dishes": "燕麦碗", "status": "自炊"}]}],
        "wisdom": {"paragraphs": ["本周按节奏安排。"]},
        "execution_tips": ["铁剂与钙片间隔两小时"],
        "disclaimer": "本计划为一般性健康饮食建议。",
    }


with tempfile.TemporaryDirectory() as td:
    targets = os.path.join(td, "targets.json")
    compile_r = _run([sys.executable, "-X", "utf8", COMPILER,
                      "--sex", "f", "--age", "30", "--height", "165",
                      "--weight", "60",
                      "--modes", ",".join(["keto"] * 7),
                      "--stages", "卵泡期,卵泡期,排卵期,排卵期,"
                                  "黄体期,黄体期,黄体期",
                      "--start-date", "2026-09-21", "--out", targets])
    check(compile_r.returncode == 0, "目标编译失败：" + compile_r.stderr[-200:])

    plan_path = os.path.join(td, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(_minimal_plan(), fh, ensure_ascii=False)

    # 1) 目标校验通过
    out1 = os.path.join(td, "out1")
    r1 = _run([sys.executable, "-X", "utf8", RUN_WEEK,
               "--plan", plan_path, "--out-dir", out1,
               "--targets", targets, "--no-render"])
    check(r1.returncode == 0, "目标校验应通过：rc=%d %s"
          % (r1.returncode, r1.stderr[-200:]))
    rep1 = json.loads(r1.stdout)
    check(rep1["ok"] is True, "报告 ok 应为 true")
    check(rep1["steps"] == [{"step": "targets", "rc": 0}],
          "步骤记录异常：%s" % rep1["steps"])

    # 2) 目标矩阵破损 → fail-fast rc 3
    broken = os.path.join(td, "broken.json")
    with open(targets, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["days"][0].pop("protein_safety_floor_g", None)
    with open(broken, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    r2 = _run([sys.executable, "-X", "utf8", RUN_WEEK,
               "--plan", plan_path, "--out-dir", os.path.join(td, "out2"),
               "--targets", broken, "--no-render"])
    check(r2.returncode == 3, "破损目标应 rc=3（实际 %d）" % r2.returncode)
    rep2 = json.loads(r2.stdout)
    check(rep2["ok"] is False, "破损目标报告 ok 应为 false")
    check("目标矩阵不完整" in r2.stderr, "破损目标应给出人话错误")

    # 3) 完整链路：目标 + 渲染
    out3 = os.path.join(td, "out3")
    r3 = _run([sys.executable, "-X", "utf8", RUN_WEEK,
               "--plan", plan_path, "--out-dir", out3,
               "--targets", targets, "--format", "html"])
    check(r3.returncode == 0, "完整链路应通过：rc=%d %s"
          % (r3.returncode, r3.stderr[-300:]))
    html = os.path.join(out3, "weekly-plan.html")
    check(os.path.isfile(html), "未生成 weekly-plan.html")
    if os.path.isfile(html):
        text = open(html, encoding="utf-8").read()
        check("html" in text[:200].lower(), "产物不是 HTML")

    # 4) plan 缺失 → rc 2
    r4 = _run([sys.executable, "-X", "utf8", RUN_WEEK,
               "--plan", os.path.join(td, "nope.json"),
               "--out-dir", os.path.join(td, "out4"), "--no-render"])
    check(r4.returncode == 2, "缺失 plan 应 rc=2（实际 %d）" % r4.returncode)

if fails:
    for f_ in fails:
        print("FAIL:", f_)
    sys.exit(1)
print("round79b 一键收尾编排：全部通过")
