#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三档权重回归：explicitly_wanted 加分高于 accepted_batch，merely_allowed 不加分。"""
import io, os, sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rr = io.open(os.path.join(base, "scripts", "recipe_ranker.py"), encoding="utf-8").read()
fails = []
if 'DECISION_BONUS = {"explicitly_wanted": 6, "accepted_batch": 3, "merely_allowed": 0}' not in rr:
    fails.append("三档权重表缺失或数值不符（应 6 > 3 > 0）")
if "--wanted" not in rr or "--accepted" not in rr:
    fails.append("ranker 缺 wanted/accepted 入参")
osch = io.open(os.path.join(base, "references", "output-schema.md"), encoding="utf-8").read()
for kw in ["accepted_batch", "explicitly_wanted", "merely_allowed"]:
    if kw not in osch:
        fails.append(f"output-schema 缺三档定义: {kw}")
if "静默" not in osch:
    fails.append("output-schema 未禁止静默消失")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
