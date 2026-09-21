#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_output.py —— 输出总控路由：按用户所选格式分发到对应渲染器。

用法：python scripts/render_output.py --input plan.json --format pdf|html|md|docx --output <path>

规则：只生成用户选择的一种格式（output_count == 1）；用户明确要求多格式时
--format 可逗号分隔。所有渲染器只读 plan.json，本脚本不含任何菜单/营养逻辑。
"""
import argparse, io, json, os, subprocess, sys

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
    # G12/M10 渲染门禁（round54/55）：两阶段流程中正式查价清单已交付、价格结果
    # 未回传时禁止渲染任何最终产物（PDF/Word/HTML/Markdown 全拒，属正常等待、
    # 非 fatal）。plan.json 顶层 price_workflow_state == awaiting_price_result
    # 即停止（状态由 planning-flow 步骤 13 写入；无该字段或 disabled 不受限）。
    try:
        with io.open(a.input, encoding="utf-8") as fh:
            _state = json.load(fh).get("price_workflow_state")
    except (OSError, ValueError):
        _state = None  # plan.json 本身的问题由下游校验器报告
    if _state == "awaiting_price_result":
        raise SystemExit("G12/M10 渲染门禁拦截：price_workflow_state=awaiting_price_result，"
                         "叮咚价格结果未回传，禁止渲染最终产物（price_result_pending，非 fatal）")
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
