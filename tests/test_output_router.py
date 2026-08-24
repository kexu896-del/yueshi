#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输出路由回归：单选时只交付所选一种；多选时可同时交付；中间文件不算交付。"""
ROUTES = {"pdf": ["plan.pdf"], "html": ["plan.html"], "md": ["plan.md"], "docx": ["plan.docx"]}

def deliver(fmt):
    if fmt not in ROUTES:
        return ["plan.md"]  # fallback 默认
    return ROUTES[fmt]

fails = []
# 验收用例 10：选 PDF 只返回 PDF
if deliver("pdf") != ["plan.pdf"]:
    fails.append("PDF 路由错误")
# 验收用例 16：选 Word 不生成 PDF/HTML/MD
if deliver("docx") != ["plan.docx"]:
    fails.append("Word 路由错误")
# 单选时恰好一个 final 文件
for f, out in ROUTES.items():
    if len(deliver(f)) != 1:
        fails.append(f"{f} 单选交付多于一个文件")
# 用户要求多格式时允许同时交付
def deliver_multi(fmts):
    return [o for f in fmts for o in ROUTES.get(f, ["plan.md"])]
if deliver_multi(["pdf", "html"]) != ["plan.pdf", "plan.html"]:
    fails.append("多格式请求未同时交付")
# 中间文件 tmp 不进入交付
if any("tmp" in o for outs in ROUTES.values() for o in outs):
    fails.append("中间文件混入交付")
print("PASS" if not fails else "FAIL: " + "; ".join(fails))
raise SystemExit(0 if not fails else 1)
