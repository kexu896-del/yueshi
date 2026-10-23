# -*- coding: utf-8 -*-
"""round75（2026-09-21）：跨仓探针策略（ADR 0003）。

断言：
- probe_common 的双布局解析（平铺/嵌套/缺失）与文件读取、模块加载行为；
- 三个历史跨仓测试 + round73 统一使用 probe_common；
- 无助手兄弟仓时，test_round67 / test_round69 必须 SKIP（exit 0）而非崩溃；
- 助手在位时，两个测试必须硬校验（输出不得出现 SKIP）。
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_common as pc  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def _run(test_path, cwd):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, "-X", "utf8", test_path],
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, env=env)


# ---------- 1) probe_common 布局解析与加载 ----------
with tempfile.TemporaryDirectory() as td:
    skill = os.path.join(td, "yueshi")
    os.makedirs(skill)
    hsrc = os.path.join(td, "yueshi-dingdong-helper", "src")
    os.makedirs(hsrc)
    with open(os.path.join(hsrc, "semantics.py"), "w", encoding="utf-8") as f:
        f.write("X = 1\n")
    check(pc.helper_src_dir(skill) == os.path.abspath(hsrc), "平铺布局解析失败")
    check(pc.read_helper("semantics.py", skill) == "X = 1\n", "read_helper 平铺读取失败")
    mod = pc.load_helper_module("probe_mod_flat", "semantics.py", skill)
    check(mod is not None and getattr(mod, "X", None) == 1, "load_helper_module 平铺加载失败")
    check(pc.read_helper("missing.py", skill) is None, "缺失文件应返回 None")

with tempfile.TemporaryDirectory() as td:
    skill = os.path.join(td, "yueshi")
    os.makedirs(skill)
    hsrc = os.path.join(td, "yueshi-dingdong-helper", "yueshi-dingdong-helper", "src")
    os.makedirs(hsrc)
    with open(os.path.join(hsrc, "config.py"), "w", encoding="utf-8") as f:
        f.write("Y = 2\n")
    check(pc.helper_src_dir(skill) == os.path.abspath(hsrc), "嵌套布局解析失败")

with tempfile.TemporaryDirectory() as td:
    skill = os.path.join(td, "yueshi")
    os.makedirs(skill)
    check(pc.helper_src_dir(skill) is None, "缺失布局应返回 None")
    check(pc.read_helper("app.py", skill) is None, "缺失布局 read_helper 应返回 None")
    check(pc.load_helper_module("probe_mod_none", "app.py", skill) is None,
          "缺失布局 load_helper_module 应返回 None")

# ---------- 2) 统一探针模块接线 ----------
for f in ("test_round65_realrun.py", "test_round67_runtime_reliability.py",
          "test_round69_universal_gate.py", "test_round73_semantics_single_source.py"):
    p = os.path.join(ROOT, "tests", f)
    with open(p, encoding="utf-8") as fh:
        src = fh.read()
    check("probe_common" in src, "%s 未使用统一探针模块 probe_common" % f)

# ---------- 3) 无助手仓：67/69 必须 SKIP（exit 0） ----------
with tempfile.TemporaryDirectory() as td:
    dst = os.path.join(td, "yueshi")
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(
        "book-extraction", "__pycache__", ".pytest_cache"))
    for t in ("test_round67_runtime_reliability.py", "test_round69_universal_gate.py"):
        r = _run(os.path.join(dst, "tests", t), dst)
        out = (r.stdout or "") + (r.stderr or "")
        check(r.returncode == 0,
              "%s 无助手时应 SKIP 而非失败（rc=%s）：%s" % (t, r.returncode, out[-200:]))
        check("SKIP" in out, "%s 无助手时应输出 SKIP" % t)

# ---------- 4) 助手在位：两个测试必须硬校验（无 SKIP） ----------
if pc.helper_src_dir() is None:
    pc.skip("当前布局无助手仓，跳过‘在位硬校验’验证")
else:
    check("evaluate_candidate" in (pc.read_helper("semantics.py") or ""),
          "在位时应能读到助手判定器（探针路径失效）")
    for t in ("test_round67_runtime_reliability.py", "test_round69_universal_gate.py"):
        r = _run(os.path.join(ROOT, "tests", t), ROOT)
        out = (r.stdout or "") + (r.stderr or "")
        check(r.returncode == 0, "%s 在位时应通过（rc=%s）" % (t, r.returncode))
        check("SKIP" not in out, "%s 在位时不得 SKIP（探针被静默跳过）" % t)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round75 跨仓探针策略（双布局/SKIP/在位硬校验）全部通过")
