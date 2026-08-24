#!/usr/bin/env python3
"""render_html.py —— render_plan.py 的命令行包装（HTML/PDF 入口）。

四渲染器约定（见 references/output-policy.md）：render_html / render_markdown /
render_docx / render_plan 只读取 plan.json 与统一配置文件，不各自实现菜单或营养逻辑。
PDF 由本入口渲染 HTML 后提示外部打印一次转换。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_plan import main  # noqa: E402,F401

if __name__ == "__main__":
    main()
