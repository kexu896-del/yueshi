#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速模式回归：SKILL 规定默认 fast 与禁令；轻量索引存在且只含检索必需字段。"""
import io, json, os, sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sk = io.open(os.path.join(base, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md")) + "".join(open(os.path.join(base, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))

fails = []
for kw in ["execution_mode", "fast", "maintenance_audit", "不运行", "全库", "内部性能日志"]:
    if kw not in sk:
        fails.append(f"SKILL 缺快速模式要素: {kw}")
idx_path = os.path.join(base, "data", "recipe-production-index.json")
ft_path = os.path.join(base, "data", "foods-table.json")
if not os.path.exists(idx_path):
    fails.append("缺 data/recipe-production-index.json")
else:
    idx = json.load(io.open(idx_path, encoding="utf-8"))
    if not idx.get("recipes"):
        fails.append("索引为空")
    else:
        allowed = {"id", "name", "source_id", "core_ingredients", "methods", "flavors",
                   "structure", "estimated_active_minutes", "equipment", "mode_fit"}
        extra = set(idx["recipes"][0].keys()) - allowed
        if extra:
            fails.append(f"索引含非必需字段: {extra}")
if not os.path.exists(ft_path):
    fails.append("缺 data/foods-table.json")
else:
    ft = json.load(io.open(ft_path, encoding="utf-8"))
    if len(ft.get("foods", {})) < 50:
        fails.append("foods-table.json 条目异常少")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
