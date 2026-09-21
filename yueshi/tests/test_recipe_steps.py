#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""做法规则回归：问卷必选无默认；选B不读取不渲染；选A只展开复杂中晚饭；模板有插槽。"""
import io, os, sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sk = io.open(os.path.join(base, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md")) + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))
q = io.open(os.path.join(base, "references", "questionnaire.md"), encoding="utf-8").read()
osch = io.open(os.path.join(base, "references", "output-schema.md"), encoding="utf-8").read()
tpl = io.open(os.path.join(base, "templates", "plan-template.html"), encoding="utf-8").read()

fails = []
for cond in ["步骤 ≥4 步", "提前腌制", "焯水", "焖烧", "碗汁", "火力", "熟度", "空气炸锅"]:
    if cond not in sk:
        fails.append(f"SKILL 缺复杂判定条件: {cond}")
if "complexity" not in sk:
    fails.append("SKILL 缺 complexity 元数据优先规则")
if "recipe_instruction" not in osch:
    fails.append("output-schema 缺 recipe_instruction 契约")
for f in ["steps", "preparation_notes", "heat_or_temperature", "doneness_signal", "advance_prep"]:
    if f not in osch:
        fails.append(f"recipe_instruction 缺字段: {f}")
if "recipe-steps" not in tpl:
    fails.append("模板缺 recipe_steps 渲染插槽")
# 问卷必选、无默认
if "中饭晚饭要不要附做法" not in q or "A. 需要" not in q or "B. 不需要" not in q:
    fails.append("问卷缺做法必选项 A/B")
if "默认附做法" in sk or "默认附做法" in q or "用户说不要才不附" in sk or "用户说不要才不附" in q:
    fails.append("残留'默认附做法'旧表述")
if "不设默认" not in q:
    fails.append("问卷未声明做法项不设默认")
if "读取数=0" not in sk and "读取数为 0" not in sk and "不读取" not in sk:
    fails.append("SKILL 未规定选B时不读取 recipe_steps")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
