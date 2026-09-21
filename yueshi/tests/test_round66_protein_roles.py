# -*- coding: utf-8 -*-
"""round66（2026-09-18）：蛋白角色全量对齐回归。

断言：
- catalog 全部蛋白质（32 种）逐一显式登记 staple/rotation/exploratory；
- roles 不含 catalog 不存在的死条目（非 catalog 名称按默认 rotation 处理即可）；
- 鳕鱼按经济型预算口径为 rotation；
- 未登记食材 candidate_role 默认 rotation（不因缺失而误判 staple/exploratory）；
- 角色枚举与槽位参数不变（total 5 / minimum_staple 3 / maximum_exploratory 1 / 不强制水产）。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import candidate_roles  # noqa: E402

fails = []

cat = json.load(open(os.path.join(ROOT, "data", "ingredient-catalog.json"), encoding="utf-8"))
rules = json.load(open(os.path.join(ROOT, "data", "protein-candidate-roles.json"), encoding="utf-8"))

proteins = [n for n, v in cat["items"].items() if v.get("category") == "蛋白质"]
assigned = {name for role in rules["roles"].values() for name in role}

missing = [p for p in proteins if p not in assigned]
if missing:
    fails.append("未分类蛋白质：%s" % "、".join(missing))

dead = [name for name in assigned if name not in cat["items"]]
if dead:
    fails.append("roles 含 catalog 不存在的死条目：%s" % "、".join(dead))

if candidate_roles.candidate_role("鳕鱼") != "rotation":
    fails.append("鳕鱼应为 rotation（经济型预算口径）")

if candidate_roles.candidate_role("未登记食材XYZ") != "rotation":
    fails.append("未登记食材默认应为 rotation")

slots = rules["slots"]
if slots != {"total": 5, "minimum_staple": 3, "maximum_exploratory": 1}:
    fails.append("槽位参数被改动：%s" % slots)
if rules.get("mandatory_aquatic_slot") is not False:
    fails.append("mandatory_aquatic_slot 应为 false")
if rules.get("candidate_role_enum") != ["staple", "rotation", "exploratory"]:
    fails.append("角色枚举被改动")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round66 蛋白角色全量对齐（catalog %d 种全部登记，无死条目）" % len(proteins))
