#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_pdf.py —— plan.json → PDF 渲染器（四渲染器之一，只读 plan.json）。

用法：python scripts/render_pdf.py --input plan.json --output plan.pdf

链路（固定）：调用 render_html/render_plan 生成临时自包含 HTML →
Chromium 无头打印一次 → 删除临时文件。本脚本不重算营养、不改菜单。
"""
import argparse, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_plan import render_document, validate_html, check_plan_meta  # noqa: E402
import json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    plan = json.load(open(a.input, encoding="utf-8"))
    check_plan_meta(plan)
    html = render_document(plan)
    validate_html(html, plan)
    fd, tmp = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        subprocess.run(["chromium", "--headless", "--disable-gpu", "--no-sandbox",
                        f"--print-to-pdf={a.output}", "--no-pdf-header-footer",
                        f"file://{tmp}"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"PDF 已生成: {a.output}")


if __name__ == "__main__":
    main()
