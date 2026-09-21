#!/usr/bin/env python3
# round24：餐次覆盖追问 + 默认三餐 + 早餐轮换 防回退
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sk = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(ROOT, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))
q = open(os.path.join(ROOT, "references", "questionnaire.md"), encoding="utf-8").read()

# 1) 默认三餐 + 少提一餐必须追问
assert "默认提供三餐完整方案" in sk
assert "必须在信息采集或动态追问阶段问一句" in sk, "少提餐次缺追问规则"
# 2) 用户自己解决的餐次：不安排食谱、不入采购、有搭配建议
assert "自己简单解决" in sk and "不得降级为 `guidance_only`" in sk
# 3) 餐次不足 3 餐时先提补能选项
assert "补能选项" in sk
# 4) 问卷示例含早餐写法 + 追问规则
assert "早餐自己做" in q
assert "餐次覆盖追问" in q
# 5) 早餐轮换：同结构一周 ≤3 次，至少 2~3 种结构
assert "碳水轮换四组" in sk and "相邻两天不同组" in sk and "轮换" in sk
# 6) 常备基础确认行
assert "常备基础确认" in sk

print("PASS")
