#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""午餐时间/状态分行渲染回归：12:00、12:30、外食、自制、无午餐五个用例；禁拼接禁绝对定位。"""
import io, os, re, sys, unicodedata

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tpl = io.open(os.path.join(base, "templates", "plan-template.html"), encoding="utf-8").read()
pc = io.open(os.path.join(base, "styles", "print.css"), encoding="utf-8").read()

def clean(text):
    text = unicodedata.normalize("NFC", text)
    for ch in ["\u00ad", "\ufeff", "\u200b"]:
        text = text.replace(ch, "")
    return text

def render_meal(time_str, status):
    time_str, status = clean(time_str), clean(status)
    t = f'<div class="meal-time">{time_str}</div>' if time_str else ""
    s = f'<div class="meal-status">{status}</div>' if status else ""
    return f'<div class="daily-meal-grid">{t}{s}</div>'

fails = []
cases = [("12:00", "外食 · 区间估算"), ("12:30", "外食 · 区间估算"),
         ("12:00", "自制"), ("", "外食 · 区间估算"), ("12:00", "")]
for t, s in cases:
    html = render_meal(t, s)
    # 时间与状态不得拼接在同一段文本
    if t and s and (t + s) in html.replace(" ", ""):
        fails.append(f"时间状态被拼接: {t}{s}")
    if t and f'class="meal-time">{t}<' not in html:
        fails.append(f"时间字段缺失: {t}")
    if s and f'class="meal-status">{s}<' not in html:
        fails.append(f"状态字段缺失: {s}")
# 模板与样式约束
if 'class="meal-time"' not in tpl:
    fails.append("模板缺 meal-time 独立字段")
for rule in ["position: static", "white-space: nowrap", "overflow-wrap: anywhere"]:
    if rule.replace(": ", ":") not in pc.replace(": ", ":"):
        fails.append(f"print.css 缺规则: {rule}")
if "daily-meal-grid" not in pc:
    fails.append("print.css 缺打印网格")
if re.search(r"\.meal-(time|status)[^{]*\{[^}]*absolute", tpl + pc):
    fails.append("时间/状态使用 absolute 定位")
# 文本清理用例
dirty = "外食\u00ad估算\u200b"
if clean(dirty) != "外食估算":
    fails.append("软连字符/零宽字符清理失败")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
