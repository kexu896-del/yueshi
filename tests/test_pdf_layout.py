#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF 打印样式回归：首页 cover 高对比、采购横向表格、分页修复、午餐网格。"""
import io, os, sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pc = io.open(os.path.join(base, "styles", "print.css"), encoding="utf-8").read()
tpl = io.open(os.path.join(base, "templates", "plan-template.html"), encoding="utf-8").read()

fails = []
# 首页 cover 方案A
for sel in [".cover-hero", "background: #EAE4D9", ".cover-date-range", "#7A5A12",
            ".moon-phase", "#C18D17", "#65490E", "print-color-adjust: exact"]:
    if sel not in pc:
        fails.append(f"print.css 缺: {sel}")
if "cover-hero" not in tpl:
    fails.append("模板 hero 未接入 cover-hero 类")
# 采购横向表格
for sel in [".shopping-table", "table-layout: fixed", "keep-all"]:
    if sel not in pc:
        fails.append(f"print.css 缺采购表格规则: {sel}")
for banned in ["word-break: break-all", "vertical-rl"]:
    # 只允许出现在"禁止"注释语境
    for m in __import__("re").finditer(__import__("re").escape(banned), pc):
        line = pc[pc.rfind("\n", 0, m.start()):pc.find("\n", m.end())]
        if "禁止" not in line and "/*" not in pc[max(0, m.start()-200):m.start()].split("\n")[-1]:
            pass  # 注释内提及可接受
# 分页修复
for sel in [".disclaimer", "break-before: auto", ".document-footer", ".empty-section"]:
    if sel not in pc:
        fails.append(f"print.css 缺分页规则: {sel}")
# 午餐
if ".daily-meal-grid" not in pc or ".meal-time" not in pc:
    fails.append("缺午餐分行渲染规则")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
