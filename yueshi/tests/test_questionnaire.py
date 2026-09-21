#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问卷模板回归：一行式+行内示例、必填口径、默认值项不进问卷、删除项清除。"""
import io, os, sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q = io.open(os.path.join(base, "references", "questionnaire.md"), encoding="utf-8").read()

fails = []
# 一行式模板要素：示例答案在行内
for snippet in ["女，32岁", "165cm", "55kg", "减重 / 增肌 / 维持 / 健康调理", "在南京",
                "早餐自己做", "午餐食堂", "周末三餐都自己做", "中餐为主", "300元左右", "Markdown"]:
    if snippet not in q:
        fails.append(f"模板缺行内示例: {snippet}")
# 目标四选一呈现
if "减重 / 增肌 / 维持 / 健康调理" not in q:
    fails.append("目标选项未以四选一呈现")
# 必填口径
for kw in ["基本情况", "避开情况", "吃饭做饭", "菜系口味", "预算"]:
    if kw not in q:
        fails.append(f"必填项缺失: {kw}")
# 做法为必选项、无默认
if "中饭晚饭要不要附做法" not in q:
    fails.append("问卷缺做法必选项")
if "不设默认" not in q:
    fails.append("做法项未声明不设默认")
if "默认发问次日开始连续 7 天" not in q:
    fails.append("日期默认值未写明")
# 删除项
fill_area = q.split("## 必填与默认值")[0]
if "主要购买方式" in fill_area:
    fails.append("填写区仍存在已删除项: 主要购买方式")
if "165" not in q or "55" not in q:
    fails.append("示例未统一为 165cm/55kg")
if "复制框外" not in q:
    fails.append("未规定引导语在复制框外")
# 输出格式规则
if "选一种就只给一种" not in q:
    fails.append("输出格式规则缺失")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
