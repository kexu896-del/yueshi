#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_output.py —— 输出总控路由：按用户所选格式分发到对应渲染器。

用法：python scripts/render_output.py --input plan.json --format pdf|html|md|docx --output <path>

规则：只生成用户选择的一种格式（output_count == 1）；用户明确要求多格式时
--format 可逗号分隔。所有渲染器只读 plan.json，本脚本不含任何菜单/营养逻辑。
"""
import argparse, os, subprocess, sys

RENDERERS = {
    "html": "render_html.py",
    "pdf": "render_pdf.py",
    "md": "render_markdown.py",
    "docx": "render_docx.py",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", required=True, help="pdf / html / md / docx，多格式用逗号分隔")
    ap.add_argument("--output", required=True, help="单格式时为文件路径；多格式时为输出目录")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    fmts = [f.strip() for f in a.format.split(",") if f.strip()]
    for f in fmts:
        if f not in RENDERERS:
            raise SystemExit(f"未知格式: {f}（可选 {list(RENDERERS)}）")
    if len(fmts) == 1:
        targets = [(fmts[0], a.output)]
    else:
        os.makedirs(a.output, exist_ok=True)
        targets = [(f, os.path.join(a.output, f"plan.{f}")) for f in fmts]
    for f, out in targets:
        r = subprocess.run([sys.executable, os.path.join(here, RENDERERS[f]),
                            "--input", a.input, "--output", out],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"{f} 渲染失败: {r.stderr.strip()}")
        print(r.stdout.strip())


if __name__ == "__main__":
    main()
