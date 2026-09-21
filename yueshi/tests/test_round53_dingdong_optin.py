#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round53：问卷新增叮咚查价选答项，选"是"才在预选环节生成查价清单。

覆盖：
1. questionnaire.md 含选答第 9 行与默认否口径；
2. runtime-rules.md 含 dingdong_helper_opt_in 门禁（未选不生成、不走 dingdong_web_direct）；
3. SKILL.md 摘要同步前置门禁；
4. planning-flow.md 步骤 8/13 的生成与定稿时机；
5. price-provider-policy.md §4.1 前置门禁；
6. 旧门禁回归：填写区仍不得出现「主要购买方式」。
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


fails = []

q = _read("references/questionnaire.md")
rr = _read("references/runtime-rules.md")
skill = _read("SKILL.md")
flow = _read("workflows/planning-flow.md")
policy = _read("references/price-provider-policy.md")

# 1. 问卷模板（round58：逐计划周期必显选答，不再有"默认 B"）
for needle in ("叮咚查价", "月食叮咚查价助手", "必显选答", "pending"):
    if needle not in q:
        fails.append(f"questionnaire 缺: {needle}")
if "不填默认 B" in q:
    fails.append("questionnaire 仍有旧的默认否口径")
# round55：预选只登记意愿，唯一正式清单在菜单/营养/新购需求确定后生成
if "只有用户明确选 A" not in q or "唯一正式" not in q:
    fails.append("questionnaire 缺生成门禁口径")

# 2. runtime-rules
for needle in ("dingdong_helper_opt_in", "dingdong_price_choice", "不跨周继承",
               "不走 `dingdong_web_direct`"):
    if needle not in rr:
        fails.append(f"runtime-rules 缺: {needle}")
if "叮咚查价（默认否，不追问）" in rr:
    fails.append("runtime-rules 仍有旧的默认否口径")
if "预选阶段只登记意愿" not in rr or "唯一正式的「月食-查价清单.json」在步骤 13 生成" not in rr:
    fails.append("runtime-rules 缺统一生成时机口径")

# 3. SKILL.md
if "只有选 A" not in skill or "才启用查价链路" not in skill:
    fails.append("SKILL.md 缺问卷选答门禁摘要")
if "逐计划周期必显选答" not in skill or "不跨周" not in skill:
    fails.append("SKILL.md 缺逐周必显选答口径")
if "不静默判定为" not in skill:
    fails.append("SKILL.md 缺不静默判否口径")
if "默认否、不追问" in skill:
    fails.append("SKILL.md 仍有旧的默认否口径")

# 4. planning-flow
if "只登记派生只读字段 `dingdong_helper_opt_in: yes`" not in flow or "不生成任何查价文件" not in flow:
    fails.append("planning-flow 步骤 8 缺只登记口径")
if "dingdong_price_choice" not in flow or "pending" not in flow:
    fails.append("planning-flow 缺价格方式 pending 收集口径")
if "唯一正式的「月食-查价清单.json」" not in flow:
    fails.append("planning-flow 步骤 13 缺唯一正式清单生成点")

# 5. policy
if "前置门禁（round53" not in policy:
    fails.append("policy §4.1 缺前置门禁")

# 6. 旧门禁回归：填写区不得出现「主要购买方式」
fill_area = q.split("## 必填与默认值")[0]
if "主要购买方式" in fill_area:
    fails.append("填写区仍存在已删除项: 主要购买方式")

print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
