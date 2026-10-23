# -*- coding: utf-8 -*-
"""测试沙箱（round77）

写库测试（release_pack / perf_baseline / build_breakfast_templates /
recipe_release_gate 等会写 data/ 与 reports/）在技能树的临时副本中运行：

    from sandbox import make_sandbox
    ROOT = make_sandbox()          # 或 pathlib.Path(make_sandbox())

副本排除 book-extraction 与缓存目录；进程退出时自动删除。策略见
docs/adr/0005-test-hermeticity.md——跑测试不得改变工作树。
"""
import atexit
import os
import shutil
import tempfile

SKIP = ("book-extraction", "__pycache__", ".pytest_cache")


def make_sandbox(skill_root=None):
    """复制技能树到临时目录并返回副本根路径（绝对路径）。"""
    src = skill_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.mkdtemp(prefix="yueshi-sandbox-")
    target = os.path.join(tmp, "yueshi")
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(*SKIP))
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    return target
