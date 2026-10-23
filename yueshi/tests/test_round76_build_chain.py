# -*- coding: utf-8 -*-
"""round76（2026-09-21）：菜谱库构建链单一深模块（ADR 0004）。

断言：
- build_commands：固定顺序、build_id 传导、审批参数仅按需透传、快速索引为末步；
- run_chain：注入 runner 验证顺序 / 任一步失败即停 / 三种状态退出码；
- --check：只读校验（approved + 产物哈希 + 快速索引新鲜度），损坏副本必须失败；
- 快速索引：由池 + manifest 可确定性重建，提交文件与当前池一致；
- MAINTENANCE.md 引用编排器。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_library as bl  # noqa: E402
import build_quick_indices as bqi  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def _run(script, args, cwd=ROOT):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, "-X", "utf8", os.path.join(cwd, "scripts", script)] + args,
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, env=env)


# ---------- 1) 命令装配 ----------
cmds = bl.build_commands("2026-09-21-r73")
names = [n for n, _ in cmds]
check(names == list(bl.CHAIN_STEPS), "构建顺序应为 %s（实际 %s）" % (list(bl.CHAIN_STEPS), names))
by_name = dict(cmds)
check("2026-09-21-r73" in by_name["classifier"] and "--build-id" in by_name["classifier"],
      "classifier 未传 build_id")
check("2026-09-21-r73" in by_name["fingerprint"] and "--build-id" in by_name["fingerprint"],
      "fingerprint 未传 build_id")
check("latest-audit.json" in " ".join(by_name["audit"]), "audit 未使用 latest-audit.json")
check("--approve" not in by_name["gate"] and "--approved-by" not in by_name["gate"],
      "未请求审批时 gate 不得带审批参数")
check(by_name["quick_indices"][-1].endswith("build_quick_indices.py"), "快速索引应为末步")
cmds2 = dict(bl.build_commands("x", approve=True, approved_by="审批人"))
check("--approve" in cmds2["gate"] and "审批人" in cmds2["gate"], "审批参数未透传")

# ---------- 2) 注入 runner：顺序与失败即停 ----------
calls = []


def runner_ok(cmd):
    calls.append(cmd)
    return 0


rc = bl.run_chain(runner=runner_ok, build_id="bid-1", status_reader=lambda: "approved")
check(rc == 0, "approved 状态应返回 0（实际 %s）" % rc)
check([os.path.basename(c[1]) for c in calls] ==
      ["recipe_classifier.py", "recipe_fingerprint_builder.py",
       "recipe_library_auditor.py", "recipe_release_gate.py", "build_quick_indices.py"],
      "整链调用顺序异常：%s" % [os.path.basename(c[1]) for c in calls])

fail_calls = []


def runner_fail_at_fingerprint(cmd):
    fail_calls.append(cmd)
    return 1 if cmd[1].endswith("recipe_fingerprint_builder.py") else 0


rc = bl.run_chain(runner=runner_fail_at_fingerprint, build_id="bid-2",
                  status_reader=lambda: "approved")
check(rc == 1, "步骤失败应透传退出码（实际 %s）" % rc)
check(len(fail_calls) == 2, "失败后应立即中止（实际调用 %d 步）" % len(fail_calls))

# ---------- 3) 状态退出码 ----------
rc = bl.run_chain(runner=runner_ok, build_id="bid-3", status_reader=lambda: "review_required")
check(rc == 2, "review_required 未审批应返回 2（实际 %s）" % rc)
rc = bl.run_chain(runner=runner_ok, build_id="bid-4", approve=True, approved_by="x",
                  status_reader=lambda: "review_required")
check(rc == 3, "已审批仍 review_required 属异常，应返回 3（实际 %s）" % rc)
rc = bl.run_chain(runner=runner_ok, build_id="bid-5", status_reader=lambda: "blocked")
check(rc == 3, "blocked 应返回 3（实际 %s）" % rc)

# ---------- 4) 快速索引：确定性重建与提交一致性 ----------
prod1, inv1 = bqi.build_documents()
prod2, inv2 = bqi.build_documents()
check(bqi.render(prod1) == bqi.render(prod2) and bqi.render(inv1) == bqi.render(inv2),
      "快速索引重建不确定（两次结果不同）")
mf = json.load(open(os.path.join(ROOT, "data", "library-manifest.json"), encoding="utf-8"))
rel = mf.get("release") or {}
check(prod1["production_pool_version"] == rel.get("build_id"),
      "生产索引版本应绑定当前构建：%s vs %s" % (prod1["production_pool_version"], rel.get("build_id")))
check(inv1["build_version"] == rel.get("build_id"), "倒排索引版本应绑定当前构建")
for name, doc in (("recipe-production-index.json", prod1),
                  ("ingredient-recipe-inverted.json", inv1)):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        check(f.read() == bqi.render(doc), "%s 与当前池/manifest 不一致" % name)

# ---------- 5) --check：真实树通过 ----------
r = _run("build_library.py", ["--check"])
check(r.returncode == 0, "--check 真实树应通过：%s" % (r.stdout + r.stderr)[-200:])

# ---------- 6) --check：损坏副本必须失败 ----------
with tempfile.TemporaryDirectory() as td:
    dst = os.path.join(td, "yueshi")
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(
        "book-extraction", "__pycache__", ".pytest_cache"))
    p = os.path.join(dst, "data", "recipe-production-index.json")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    with open(p, "w", encoding="utf-8") as f:
        f.write(text + " ")
    r = _run("build_library.py", ["--check"], cwd=dst)
    check(r.returncode != 0 and "recipe-production-index" in (r.stdout + r.stderr),
          "损坏的快速索引未被 --check 拦截")

# ---------- 7) 文档接线 ----------
mt = open(os.path.join(ROOT, "MAINTENANCE.md"), encoding="utf-8").read()
check("build_library.py" in mt, "MAINTENANCE.md 未引用构建链编排器")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round76 菜谱库构建链（顺序/失败即停/状态退出码/--check/快速索引）全部通过")
