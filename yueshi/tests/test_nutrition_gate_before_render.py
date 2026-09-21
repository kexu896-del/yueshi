#!/usr/bin/env python3
# 收口轮 P1-3：营养超限必须在渲染前自动修正（管线顺序与禁令写死在 SKILL.md）
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sk = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(ROOT, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))

# 1) 固定管线完整出现且顺序正确
pipeline = ["菜单草案", "批量营养计算", "自动微调克数", "最终复核", "冻结 plan.json", "渲染 HTML/PDF"]
sec = sk[sk.find("## 营养超限的渲染前自动修正"):]
pos = [sec.find(k) for k in pipeline]
assert all(p >= 0 for p in pos), f"管线缺环节: {[k for k,p in zip(pipeline,pos) if p<0]}"
assert pos == sorted(pos), "管线顺序错误"

# 2) 禁令：渲染后手改即失败
assert "禁止渲染完成后再人工" in sk, "缺少渲染后手改禁令"

# 3) 调整留痕要求
assert "前后克数" in sk and "前后营养值" in sk and "调整原因" in sk, "缺少调整留痕字段"

# 4) 最终门禁含"冻结前自动微调"
gate = re.search(r"\*\*nutrition\*\*：([^\n]+)", sk)
assert gate and "冻结" in gate.group(1), "nutrition 门禁缺少冻结前修正条款"

print("PASS")
