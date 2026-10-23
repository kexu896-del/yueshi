#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱库构建链编排（round76）

把此前只写在 MAINTENANCE.md 里的固定顺序升级为代码强制：

    recipe_classifier.py → recipe_fingerprint_builder.py
    → recipe_library_auditor.py → recipe_release_gate.py
    → build_quick_indices.py（快速索引）

- 任一步非零退出即停，并透传退出码；
- 同一 build_id 贯穿分类与指纹（门禁会校验一致性）；
- 门禁的人工审批参数（--approve/--approved-by）由本编排器透传，默认不自动审批；
- 链结束后读取 library-manifest 的 release_status：
    approved → 0；review_required 且未审批 → 2（提示审批参数）；blocked/未知 → 3。

用法：
  python scripts/build_library.py --build-id 2026-09-21-r73
  python scripts/build_library.py --build-id <id> --approve --approved-by <谁>
  python scripts/build_library.py --check      # 只读校验当前产物与门禁状态

--check 校验：① release_status == approved；② artifact_hashes 与当前产物一致；
③ 两份快速索引与当前池/manifest 一致。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
DATA = os.path.join(ROOT, "data")
MANIFEST = os.path.join(DATA, "library-manifest.json")

CHAIN_STEPS = ("classifier", "fingerprint", "audit", "gate", "quick_indices")


def build_commands(build_id, approve=False, approved_by=None):
    """返回 [(步骤名, 命令列表)]；顺序固定。"""
    py = sys.executable
    gate_cmd = [py, os.path.join(SCRIPTS, "recipe_release_gate.py"),
                "--audit", os.path.join(DATA, "audit", "latest-audit.json")]
    if approve:
        gate_cmd += ["--approve", "--approved-by", approved_by or "build_library.py"]
    return [
        ("classifier", [py, os.path.join(SCRIPTS, "recipe_classifier.py"),
                        "--build-id", build_id]),
        ("fingerprint", [py, os.path.join(SCRIPTS, "recipe_fingerprint_builder.py"),
                         "--build-id", build_id]),
        ("audit", [py, os.path.join(SCRIPTS, "recipe_library_auditor.py"),
                   "--json", os.path.join(DATA, "audit", "latest-audit.json")]),
        ("gate", gate_cmd),
        ("quick_indices", [py, os.path.join(SCRIPTS, "build_quick_indices.py")]),
    ]


def _default_runner(cmd):
    return subprocess.run(cmd, cwd=ROOT).returncode


def read_release_status():
    with open(MANIFEST, encoding="utf-8") as f:
        return ((json.load(f).get("release") or {}).get("release_status"))


def run_chain(runner=None, build_id=None, approve=False, approved_by=None,
              status_reader=None):
    """执行整链；返回退出码（0=approved / 2=待审批 / 3=blocked / 步骤失败码）。"""
    runner = runner or _default_runner
    status_reader = status_reader or read_release_status
    build_id = build_id or date.today().isoformat()
    for name, cmd in build_commands(build_id, approve, approved_by):
        print("[step] %s" % name, flush=True)
        rc = runner(cmd)
        if rc != 0:
            print("[FAIL] %s（退出码 %s），构建链中止" % (name, rc))
            return rc if rc > 0 else 1
    status = status_reader()
    print("[status] release_status=%s" % status)
    if status == "approved":
        return 0
    if status == "review_required":
        if approve:
            print("[FAIL] 已请求审批但门禁仍为 review_required，请检查门禁输出")
            return 3
        print("构建链停在人工审批：请复核 warnings 后追加 --approve --approved-by <审批人> 重跑。")
        return 2
    print("构建链被门禁阻断（%s）：按 blocking_issues 修复后重跑。" % status)
    return 3


def check() -> int:
    """只读校验：门禁状态 + 产物哈希 + 快速索引新鲜度。"""
    import build_quick_indices as bqi
    import recipe_release_gate as gate

    problems = []
    with open(MANIFEST, encoding="utf-8") as f:
        mf = json.load(f)
    rel = mf.get("release") or {}
    status = rel.get("release_status")
    if status != "approved":
        problems.append("release_status=%s（应为 approved）" % status)

    hashes, err = gate.compute_artifact_hashes()
    if err:
        problems.append("产物哈希计算失败: %s" % err)
    recorded = rel.get("artifact_hashes") or {}
    for key, value in recorded.items():
        if (hashes or {}).get(key) != value:
            problems.append("artifact_hash 不一致: %s" % key)
    for key in (hashes or {}):
        if key not in recorded:
            problems.append("artifact_hash 未登记: %s" % key)

    prod, inv = bqi.build_documents()
    for name, doc in (("recipe-production-index.json", prod),
                      ("ingredient-recipe-inverted.json", inv)):
        p = os.path.join(DATA, name)
        if not os.path.exists(p):
            problems.append("%s 不存在" % name)
            continue
        with open(p, encoding="utf-8") as f:
            if f.read() != bqi.render(doc):
                problems.append("%s 与当前池/manifest 不一致（请重跑构建链）" % name)

    if problems:
        for p in problems:
            print("FAIL: " + p)
        return 1
    print("OK: 构建链产物一致 | build_id=%s | 快速索引 %d 条" % (
        rel.get("build_id"), prod["record_count"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="菜谱库构建链编排（round76）")
    ap.add_argument("--build-id", default=None, help="构建 ID（默认当天日期）")
    ap.add_argument("--approve", action="store_true", help="人工放行门禁 warnings")
    ap.add_argument("--approved-by", default=None, help="审批人留痕（--approve 时必填）")
    ap.add_argument("--check", action="store_true", help="只读校验，不执行构建")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.approve and not args.approved_by:
        raise SystemExit("--approve 必须同时给 --approved-by 留痕")
    return run_chain(build_id=args.build_id, approve=args.approve,
                     approved_by=args.approved_by)


if __name__ == "__main__":
    raise SystemExit(main())
