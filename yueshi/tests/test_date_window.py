#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日期窗口规则回归：默认 request_date+1 起连续 7 天；两周=14 天；用户指定优先。"""
from datetime import date, timedelta

def plan_window(request_date, user_start=None, weeks=1):
    start = user_start or (request_date + timedelta(days=1))
    days = 7 * weeks
    return start, start + timedelta(days=days - 1)

fails = []
# 验收用例 9：2026-08-21 发问未指定日期 → 2026-08-22 至 2026-08-28
s, e = plan_window(date(2026, 8, 21))
if (s, e) != (date(2026, 8, 22), date(2026, 8, 28)):
    fails.append(f"默认窗口错误: {s} ~ {e}")
# 两周 = 连续 14 天
s, e = plan_window(date(2026, 8, 21), weeks=2)
if (e - s).days != 13:
    fails.append("两周不等于连续14天")
# 跨月连续
s, e = plan_window(date(2026, 8, 30))
if (s, e) != (date(2026, 8, 31), date(2026, 9, 6)):
    fails.append(f"跨月窗口错误: {s} ~ {e}")
# 跨年连续
s, e = plan_window(date(2026, 12, 30))
if (s, e) != (date(2026, 12, 31), date(2027, 1, 6)):
    fails.append(f"跨年窗口错误: {s} ~ {e}")
# 用户指定开始日期优先
s, e = plan_window(date(2026, 8, 21), user_start=date(2026, 8, 25))
if s != date(2026, 8, 25):
    fails.append("用户指定日期未生效")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
raise SystemExit(0 if not fails else 1)
