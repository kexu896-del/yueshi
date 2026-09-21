#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_pdf.py —— plan.json → PDF 渲染器（四渲染器之一，只读 plan.json）。

用法：python scripts/render_pdf.py --input plan.json --output plan.pdf

链路（固定）：调用 render_html/render_plan 生成临时自包含 HTML →
Chromium 无头打印一次 → 删除临时文件。本脚本不重算营养、不改菜单。

round58 定稿：正式 PDF 只渲染一次；分页问题只通过样式/分页规则修复
（整行 break-inside、分类标题与首行绑定、表头跨页重复），
**禁止为消除孤行而缩短或改写食材名、菜名、需求量、剩余去向等业务文本**；
布局重试次数计入运行记录 pdf_layout_retry_count。
"""
import argparse, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_plan import render_document, validate_html, check_plan_meta  # noqa: E402
import json  # noqa: E402


def find_browser() -> str | None:
    """浏览器探测链（2026-09-18，与叮咚助手同款口径，废弃手工 .shim）：
    环境变量 YUESHI_BROWSER → PATH（chromium/Chrome/Edge）→ 常见安装路径（含每用户目录）。
    安全口径：显式不传 --no-sandbox（与助手发布要求一致）。"""
    env = os.environ.get("YUESHI_BROWSER")
    if env and os.path.exists(env):
        return env
    for name in ("chromium", "chromium-browser", "chrome", "google-chrome", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pfx = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    lad = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pfx, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(lad, "Google", "Chrome", "Application", "chrome.exe") if lad else "",
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pfx, "Microsoft", "Edge", "Application", "msedge.exe"),
        # 企业电脑常见：无管理员权限时 Edge 装在每用户目录。
        os.path.join(lad, "Microsoft", "Edge", "Application", "msedge.exe") if lad else "",
    ]
    for exe in candidates:
        if exe and os.path.exists(exe):
            return exe
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    plan = json.load(open(a.input, encoding="utf-8"))
    check_plan_meta(plan)
    html = render_document(plan, fmt="pdf")
    validate_html(html, plan)
    # round67：输出必须是文件路径；传目录/无扩展名一律显式失败，不得静默"成功"。
    if os.path.isdir(a.output) or a.output.endswith(("/", "\\")):
        print(f"--output 必须是文件路径（当前为目录）：{a.output}", file=sys.stderr)
        return 2
    browser = find_browser()
    if not browser:
        print("未找到可用浏览器：请安装 Microsoft Edge 或 Chrome，"
              "或设置环境变量 YUESHI_BROWSER 指向浏览器可执行文件。", file=sys.stderr)
        return 2
    fd, tmp = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        subprocess.run([browser, "--headless", "--disable-gpu",
                        f"--print-to-pdf={a.output}", "--no-pdf-header-footer",
                        f"file://{tmp}"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    # round67：产物存在性校验（存在、非空、可打开并有页面）
    if not os.path.exists(a.output) or os.path.getsize(a.output) <= 0:
        print(f"PDF 未生成或为空：{a.output}", file=sys.stderr)
        return 3
    try:
        import fitz  # PyMuPDF：可选依赖，用于页数校验
        with fitz.open(a.output) as doc:
            if doc.page_count < 1:
                print(f"PDF 无有效页面：{a.output}", file=sys.stderr)
                return 3
    except ImportError:
        pass
    print(f"PDF 已生成: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
