# -*- coding: utf-8 -*-
"""round77（2026-09-21）：测试密封性不变量（ADR 0005）。

断言：
- 六个写库测试全部改为在 tests/sandbox.py 的临时副本中运行；
- 在真实树上依次运行这六个测试后，仓库 data/reports/scripts 逐字节不变；
- 关键生成物（发布清单 / 性能基线 / 早餐模板 / 库清单 / 审计 / 覆写）哈希不变。
"""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIX = ["test_round43_release_readiness.py", "test_round44_release_hardening.py",
       "test_round62_recipe_audit_breakfast.py", "test_round64_1_consistency_patch.py",
       "test_round64_mode_semantics_release.py", "test_round72_breakfast_semantics.py"]
KEY_ARTIFACTS = [
    "data/release-manifest.json", "data/release-invariants.json", "data/perf-baseline.json",
    "data/breakfast-templates.json", "data/library-manifest.json",
    "data/audit/latest-audit.json", "data/audit/review-overrides.json",
    "data/recipe-index.json", "data/recipe-classification.json",
    "data/recipe-fingerprints.json", "reports/release-summary.md",
    "reports/recipe-missing-tags.csv",
]

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def snap(root):
    out = {}
    for base in ("data", "reports", "scripts"):
        for r, ds, fs in os.walk(os.path.join(root, base)):
            ds[:] = [d for d in ds if d not in ("__pycache__", ".pytest_cache")]
            for f in fs:
                p = os.path.join(r, f)
                out[os.path.relpath(p, root)] = sha(p)
    return out


# ---------- 1) 六个写库测试必须使用沙箱 ----------
for f in SIX:
    src = open(os.path.join(ROOT, "tests", f), encoding="utf-8").read()
    check("from sandbox import" in src, "%s 未使用 tests/sandbox.py 沙箱" % f)
check(os.path.exists(os.path.join(ROOT, "tests", "sandbox.py")), "缺少 tests/sandbox.py")

# ---------- 2) 运行六个测试后，真实树逐字节不变 ----------
before = snap(ROOT)
key_before = {k: sha(os.path.join(ROOT, k)) for k in KEY_ARTIFACTS
              if os.path.exists(os.path.join(ROOT, k))}

env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
for t in SIX:
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tests", t)],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600, env=env)
    check(r.returncode == 0, "%s 运行失败（rc=%s）：%s" % (
        t, r.returncode, ((r.stdout or "") + (r.stderr or ""))[-200:]))

after = snap(ROOT)
diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
check(not diff, "跑测试改动了仓库：%s" % diff[:10])
for k, v in key_before.items():
    check(os.path.exists(os.path.join(ROOT, k)) and sha(os.path.join(ROOT, k)) == v,
          "关键产物被改写：%s" % k)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round77 测试密封性（六个写库测试沙箱化，仓库逐字节不变）")
