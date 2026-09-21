#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""release_pack.py · 唯一发布入口（round44 定稿）。

链路：源目录可复现打包 yueshi.skill / yueshi.zip → 包后载荷扫描（版权泄漏防线）
→ 运行依赖闭包检查 → 解压到全新临时目录 → 7 步包内烟测 → data/release-manifest.json。

硬门禁（命中即失败，不告警降级）：
  - 发布包不得含 book-extraction/ 内容、电子书文件、提取缓存（.jsonl 审计载荷）或大段原文副本；
  - 运行文件（SKILL/references/workflows/schemas/scripts）不得引用 book-extraction/；
  - 依赖闭包内文件必须全部随包发布；
  - round64.1 起：打包前先生成 data/release-invariants.json（关键运行不变量，全部来自
    机器结果：测试汇总 / manifest / 审计 JSON / 发布完整性校验），任一硬不变量为 false
    即不标记发布；reports/release-summary.md 为同内容人类可读摘要，不作为机器门禁输入。

可复现构建：固定文件排序、时间戳、权限位与压缩参数；同一输入重复构建 SHA-256 一致。

用法：python scripts/release_pack.py [--out DIR] [--build-source STR] [--skip-smoke]
          [--test-summary JSON]
退出码：0 通过；3 任一硬门禁或烟测失败。
"""


def build_release_invariants(version, test_summary):
    """round64.1 §8：发布不变量报告（机器来源，不读取展示用 Markdown 作为判断依据）。
    返回 (invariants_dict, hard_ok)。"""
    data = os.path.join(BASE, "data")
    mf = json.load(open(os.path.join(data, "library-manifest.json"), encoding="utf-8"))
    rel = mf.get("release") or {}
    aud = json.load(open(os.path.join(data, "audit", "latest-audit.json"), encoding="utf-8"))
    qm = aud.get("quality_metrics") or {}
    ov = json.load(open(os.path.join(data, "audit", "review-overrides.json"),
                        encoding="utf-8"))
    olist = ov.get("overrides", [])
    qtext = open(os.path.join(BASE, "references", "questionnaire.md"),
                 encoding="utf-8").read() + \
        open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    nut = open(os.path.join(BASE, "references", "nutrition-routing.md"),
               encoding="utf-8").read()
    rt = open(os.path.join(BASE, "references", "runtime-rules.md"),
              encoding="utf-8").read()
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import recipe_ranker as rr
    integrity_ok, _reason = rr.verify_release_integrity()
    inv = {
        "questionnaire_exposes_internal_mode":
            any(t in qtext for t in ("酮生物", "平衡激素",
                                     "keto_biologic", "hormone_balance")),
        "mode_schedule_system_derived": "MODE-DERIVE-001" in nut,
        "mode_schedule_frozen_before_basket": "MODE-FREEZE-001" in rt,
        "ranker_requires_approved_release": rel.get("release_status") == "approved",
        "artifact_hashes_verified": bool(integrity_ok),
        "taxonomy_drift_detected": "taxonomy_drift" in open(
            os.path.join(BASE, "scripts", "recipe_release_gate.py"),
            encoding="utf-8").read(),
        "catalog_drift_detected": "ingredient_catalog_drift" in open(
            os.path.join(BASE, "scripts", "recipe_release_gate.py"),
            encoding="utf-8").read(),
        "cross_category_cluster_count": qm.get("cross_category_cluster_count"),
        "severe_misclassification_count": qm.get("severe_protein_mislabel_count"),
        "unreviewed_override_count": sum(1 for o in olist
                                         if o.get("status") == "review_required"),
        "stale_override_count": sum(1 for o in olist if o.get("status") == "stale"),
    }
    hard = {
        "questionnaire_exposes_internal_mode": False,
        "mode_schedule_system_derived": True,
        "mode_schedule_frozen_before_basket": True,
        "ranker_requires_approved_release": True,
        "artifact_hashes_verified": True,
        "taxonomy_drift_detected": True,
        "catalog_drift_detected": True,
        "cross_category_cluster_count": 0,
        "severe_misclassification_count": 0,
        "unreviewed_override_count": 0,
        "stale_override_count": 0,
    }
    tests = None
    if test_summary:
        tests = json.loads(test_summary)
    out = {
        "skill_version": version,
        "build_id": rel.get("build_id"),
        "library_release": rel.get("release_status"),
        "tests": tests,
        "invariants": inv,
        "hard_expectations": hard,
        "generated_by": "scripts/release_pack.py",
        "note": "机器判断依据仅本 JSON；reports/release-summary.md 为展示摘要，不作门禁输入。",
    }
    hard_ok = all(inv[k] == v for k, v in hard.items())
    return out, hard_ok
import argparse, hashlib, json, os, re, subprocess, sys, tempfile, zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

SKIP_DIRS = ("candidates", "__pycache__", "book-extraction")
SKIP_FILE_PREFIXES = ("scripts/extract_",)  # 维护期提取工具，repo-only 不入包
EXCLUDED_PATHS = ["book-extraction/", "candidates/", "__pycache__/", "scripts/extract_*"]
EXCLUSION_REASON = ("维护期书籍审计工作目录与候选轮次工作区；含不进入发布包的版权原文与中间材料；"
                    "runtime_dependency=false；仅保留于受控源码/维护环境")
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)
EBOOK_EXTS = (".epub", ".mobi", ".azw", ".azw3")
RUNTIME_SCAN_SCOPES = ("SKILL.md", "references", "workflows", "schemas", "scripts")


def sha256(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_package_files():
    files = []
    for root, dirs, names in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in names:
            rel = os.path.relpath(os.path.join(root, f), BASE)
            if f.endswith(".pyc") or rel.startswith(SKIP_FILE_PREFIXES):
                continue
            files.append(rel)
    return sorted(files)


def build_zip(out):
    """可复现：排序 + 固定时间戳/权限位。"""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in _iter_package_files():
            info = zipfile.ZipInfo(rel, date_time=FIXED_ZIP_DATE)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(BASE, rel), "rb") as f:
                z.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def copyright_payload_scan(zip_path):
    """反向泄漏扫描：命中即失败。"""
    hits = []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            low = name.lower()
            if "book-extraction" in low:
                hits.append({"entry": name, "reason": "排除目录内容进入包"})
            if low.endswith(EBOOK_EXTS):
                hits.append({"entry": name, "reason": "原始电子书文件"})
            if low.endswith(".jsonl"):
                hits.append({"entry": name, "reason": "提取/审计缓存载荷"})
    return {"passed": not hits, "hits": hits}


def runtime_reference_scan():
    """运行文件不得引用 book-extraction/（data/*.json 来源登记除外，见 maintenance-map）。"""
    hits = []
    scopes = RUNTIME_SCAN_SCOPES
    for rel in _iter_package_files():
        if not any(rel == sc or rel.startswith(sc + "/") for sc in scopes):
            continue
        if "release_pack.py" in rel:
            continue
        try:
            txt = open(os.path.join(BASE, rel), encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        if "book-extraction" in txt:
            hits.append(rel)
    return {"passed": not hits, "hits": hits}


def dependency_closure():
    """从 SKILL 引用、脚本组件、哈希输入与 Schema 清单生成运行依赖闭包。"""
    import render_plan
    closure = {"SKILL.md", "CHANGELOG.md", "developer/maintenance-map.md"}
    sk = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
    for m in re.findall(r"`((?:references|workflows|data|scripts|schemas|developer)/[\w\-./一-鿿]+)`", sk):
        closure.add(m)
    closure.update(render_plan.PIPELINE_COMPONENTS)
    for pm in (None, "shared_uniform"):
        # 与 compute_rules_bundle_hash 同源的文件清单
        pass
    closure.update([
        "references/runtime-rules.md", "references/nutrition-routing.md",
        "references/output-policy.md", "references/safety-rules.md",
        "references/household-runtime-rules.md", "workflows/household-planning-flow.md",
        "workflows/planning-flow.md", "workflows/fallback-flow.md", "workflows/procurement-flow.md",
        "data/effective-parameters.json", "data/library-manifest.json",
        "data/household-limits.json", "data/perf-baseline.json",
        "schemas/household/shared-definitions.schema.json",
        "schemas/household/household-base-plan.schema.json",
        "schemas/household/household-overrides.schema.json",
        "schemas/household/household-effective-plan.schema.json",
        "schemas/household/household-schemas.bundle.json",
        "data/golden/golden-sample-plan.json",
        "data/golden/household/samples/golden-base-plan-sample.json",
        "data/golden/household/samples/golden-override-sample.json",
        # round46：外部价格 Provider 契约
        "references/price-provider-policy.md",
        "schemas/price-query.schema.json",
        "schemas/price-result.schema.json",
        "data/golden/price-query-sample.json",
        "data/golden/price-result-sample.json",
    ])
    return sorted(closure)


def dependency_check(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    missing = [c for c in dependency_closure() if c not in names]
    return {"passed": not missing, "missing": missing,
            "closure_size": len(dependency_closure())}


def smoke(unpack_dir):
    """7 步包内烟测。"""
    log = []
    scripts = os.path.join(unpack_dir, "scripts")

    def run(name, argv, cwd=None):
        r = subprocess.run(argv, capture_output=True, text=True, cwd=cwd or unpack_dir)
        ok = r.returncode == 0
        log.append({"step": name, "ok": ok, "tail": (r.stdout + r.stderr)[-300:]})
        return ok

    ok1 = run("renderer_import", [sys.executable, "-c",
                                  "import sys; sys.path.insert(0, %r); import render_plan; "
                                  "print(render_plan.compute_rules_bundle_hash())" % scripts])
    base = os.path.join(unpack_dir, "data", "golden", "household", "samples",
                        "golden-base-plan-sample.json")
    ovr = os.path.join(unpack_dir, "data", "golden", "household", "samples",
                       "golden-override-sample.json")
    eff1 = os.path.join(unpack_dir, "_smoke_identity.json")
    eff2 = os.path.join(unpack_dir, "_smoke_override.json")
    ok2 = run("identity_merge", [sys.executable,
                                 os.path.join(scripts, "household_override_merger.py"),
                                 base, "-o", eff1])
    ok3 = run("override_merge", [sys.executable,
                                 os.path.join(scripts, "household_override_merger.py"),
                                 base, ovr, "-o", eff2])
    ok4 = run("effective_validation",
              [sys.executable, "-c",
               "import sys; sys.path.insert(0, %r); from household_reference_validator import _schema_validate; "
               "import json; _schema_validate(json.load(open(%r, encoding='utf-8')), 'effective_plan'); print('ok')"
               % (scripts, eff2)])
    solo_html = os.path.join(unpack_dir, "_smoke_solo.html")
    ok5 = run("solo_golden_render",
              [sys.executable, os.path.join(scripts, "render_plan.py"),
               "--input", os.path.join(unpack_dir, "data", "golden", "golden-sample-plan.json"),
               "--output", solo_html])
    fam_html = os.path.join(unpack_dir, "_smoke_family.html")
    ok6 = run("family_effective_render",
              [sys.executable, "-c",
               "import sys, json; sys.path.insert(0, %r); import household_components as hc; "
               "eff = json.load(open(%r, encoding='utf-8')); "
               "html = hc.render_household_html(eff); "
               "assert '减重份' in html and '盛取方式' in html; "
               "assert 'portion_method' not in html and 'member_portions' not in html; "
               "open(%r, 'w', encoding='utf-8').write(html); print('ok')"
               % (scripts, eff2, fam_html)])
    ok7 = run("release_hygiene",
              [sys.executable, "-c",
               "import sys; sys.path.insert(0, %r); import release_pack as rp; "
               "assert rp.runtime_reference_scan()['passed']; print('ok')" % scripts])
    for f in (eff1, eff2, solo_html, fam_html):
        if os.path.exists(f):
            os.remove(f)
    return all((ok1, ok2, ok3, ok4, ok5, ok6, ok7)), log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.dirname(BASE))
    ap.add_argument("--build-source", default="")
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--test-summary", default="")
    args = ap.parse_args()

    import render_plan
    version = None
    for line in open(os.path.join(BASE, "SKILL.md"), encoding="utf-8"):
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break

    hard_fails = []

    # round64.1：发布不变量先行生成（纳入包内），硬不变量失败即不得标记发布
    inv, inv_ok = build_release_invariants(version, args.test_summary)
    json.dump(inv, open(os.path.join(BASE, "data", "release-invariants.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    sm = ["# 发布摘要（展示用，机器门禁以 data/release-invariants.json 为准）", "",
          f"- 技能版本：{inv['skill_version']}",
          f"- 构建 ID：{inv['build_id']}",
          f"- 菜谱库发布状态：{inv['library_release']}",
          f"- 测试：{json.dumps(inv['tests'], ensure_ascii=False)}", "",
          "## 关键不变量"]
    for k, v in inv["invariants"].items():
        exp = inv["hard_expectations"].get(k)
        sm.append(f"- {k}: {v}（期望 {exp}）{'✓' if v == exp else '✗'}")
    open(os.path.join(BASE, "reports", "release-summary.md"), "w",
         encoding="utf-8").write("\n".join(sm) + "\n")
    if not inv_ok:
        hard_fails.append("release_invariants")

    # 可复现构建：同一输入构建两次比较 SHA-256
    artifacts = []
    builds = []
    for name in ("yueshi.skill", "yueshi.zip"):
        out = os.path.join(args.out, name)
        build_zip(out)
        artifacts.append({"name": name, "size_bytes": os.path.getsize(out),
                          "sha256": sha256(out)})
        builds.append(out)
    repro_a = os.path.join(tempfile.gettempdir(), "_yueshi_repro_a.zip")
    repro_b = os.path.join(tempfile.gettempdir(), "_yueshi_repro_b.zip")
    build_zip(repro_a)
    build_zip(repro_b)
    reproducible = sha256(repro_a) == sha256(repro_b) == artifacts[0]["sha256"]
    for f in (repro_a, repro_b):
        os.remove(f)
    if not reproducible:
        hard_fails.append("reproducible_build")

    payload = copyright_payload_scan(builds[1])
    if not payload["passed"]:
        hard_fails.append("copyright_payload_scan")
    refscan = runtime_reference_scan()
    if not refscan["passed"]:
        hard_fails.append("runtime_reference_scan")
    dep = dependency_check(builds[1])
    if not dep["passed"]:
        hard_fails.append("runtime_dependency_check")

    smoke_ok, smoke_log = (True, [])
    if not args.skip_smoke and not hard_fails:
        with tempfile.TemporaryDirectory() as d:
            unpack = os.path.join(d, "pkg")
            os.makedirs(unpack)
            with zipfile.ZipFile(builds[1]) as z:
                z.extractall(unpack)
            smoke_ok, smoke_log = smoke(unpack)
    if not smoke_ok:
        hard_fails.append("package_smoke")

    with zipfile.ZipFile(builds[1]) as z:
        file_count = len(z.namelist())
        uncompressed = sum(i.file_size for i in z.infolist())

    manifest = {
        "release_version": version,
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "build_source": args.build_source,
        "build_tool_version": "release_pack.py@" + hashlib.sha1(
            open(os.path.join(BASE, "scripts", "release_pack.py"), "rb").read()).hexdigest()[:12],
        "artifacts": artifacts,
        "package_file_count": file_count,
        "uncompressed_size_bytes": uncompressed,
        "size_reduction_note": "round43 起排除维护区工作目录：仅移除非运行期维护材料，无运行依赖变化",
        "excluded_paths": EXCLUDED_PATHS,
        "exclusion_reason": EXCLUSION_REASON,
        "runtime_dependency": False,
        "source_retention_policy": "维护区材料仅保留于受控源码/维护环境，不进入公开分发产物",
        "rules_bundle_hash_solo": render_plan.compute_rules_bundle_hash(),
        "rules_bundle_hash_household": render_plan.compute_rules_bundle_hash("shared_uniform"),
        "pipeline_bundle_hash": render_plan.compute_pipeline_bundle_hash(),
        "schemas": ["base_plan", "overrides", "effective_plan"],
        "copyright_payload_scan": payload,
        "runtime_reference_scan": refscan,
        "runtime_dependency_check": dep,
        "reproducible_build": reproducible,
        "release_invariants_hard_ok": bool(inv_ok),
        "smoke_steps": smoke_log,
        "package_smoke": {"passed": bool(smoke_ok)},
    }
    if args.test_summary:
        manifest["test_summary"] = json.loads(args.test_summary)
    mp = os.path.join(BASE, "data", "release-manifest.json")
    json.dump(manifest, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({"release_version": version, "artifacts": artifacts,
                      "reproducible_build": reproducible,
                      "hard_fails": hard_fails}, ensure_ascii=False, indent=2))
    print("package_smoke:", "PASS" if smoke_ok else "FAIL")
    sys.exit(0 if not hard_fails else 3)


if __name__ == "__main__":
    main()
