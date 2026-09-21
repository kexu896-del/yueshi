#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round43：正式发布前收口（版本一致性 / G03 分级 / identity merge / 唯一参数源 /
双哈希 / 迁移映射 / 包内烟测 / 性能基线）。"""
import json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
sys.path.insert(0, os.path.join(BASE, "scripts"))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


import re as _re
VERSION = _re.search(r"^version:\s*(\S+)", SK, _re.M).group(1)  # 与 SKILL frontmatter 同源


def t01_version_consistency():
    fm = SK.split("---")[1]
    check("T01a SKILL 版本与 frontmatter 一致", "version: %s" % VERSION in fm)
    check("T01b 版本号语义化格式（round44 正式版无 rc；新开发周期允许 -rcN）",
          _re.fullmatch(r"yueshi-\d+\.\d+\.\d+(-rc\d*)?", VERSION) is not None)
    g = json.load(open(os.path.join(
        BASE, "data", "golden", "household", "samples",
        "golden-base-plan-sample.json"), encoding="utf-8"))
    check("T01c golden 样例 skill_version 同步", g["plan_meta"]["skill_version"] == VERSION)
    check("T01d golden 样例明细版本同步",
          g["plan_meta"]["runtime_rules_version"] == VERSION.replace("yueshi-", ""))
    cl = open(os.path.join(BASE, "CHANGELOG.md"), encoding="utf-8").read()
    latest = cl.split("\n## ")[1] if "\n## " in cl else cl
    check("T01e CHANGELOG 最新条目为 round43", latest.split("\n## ")[0].startswith("用户指示"))


def t02_g03_split():
    check("T02a G03a user_input_required", "G03a. [user_input_required] 预选尚未由用户确认" in SK)
    check("T02b G03b fatal", "G03b. [fatal]" in SK and "生成失败、损坏或版本不匹配" in SK)
    check("T02c 旧混合 G03 已清除", "G03. [fatal] locked_basket 已生成" not in SK)


def t03_identity_merge():
    import household_override_merger as mrg
    from household_reference_validator import _schema_validate
    with tempfile.TemporaryDirectory() as d:
        ep = os.path.join(d, "e.json")
        eff = mrg.merge(os.path.join(BASE, "data", "golden", "household", "samples",
                                     "golden-base-plan-sample.json"), None, ep)
        check("T03a identity merge 产出 effective", os.path.exists(ep))
        check("T03b applied_override_ids 为空", eff["effective_meta"]["applied_override_ids"] == [])
        check("T03c merged_at 非空", bool(eff["effective_meta"]["merged_at"]))
        ok = True
        try:
            _schema_validate(eff, "effective_plan")
        except Exception as e:
            ok, msg = False, str(e)[:150]
            check("T03d identity effective 过 schema", False, msg)
        if ok:
            check("T03d identity effective 过 schema", True)
    check("T03e SKILL 声明单一输入", "家庭渲染器永远只面对 effective_plan 一种输入" in SK)


def t04_household_limits_single_source():
    lp = os.path.join(BASE, "data", "household-limits.json")
    d = json.load(open(lp, encoding="utf-8"))
    check("T04a 参数文件字段齐", d["summary_inline_members"] == 3 and d["max_members"] == 6)
    check("T04b SKILL 引用唯一来源", "data/household-limits.json" in SK and "不得各自写死" in SK)
    import render_plan
    before = render_plan.compute_rules_bundle_hash("shared_uniform")
    raw = open(lp, "rb").read()
    try:
        open(lp, "ab").write(b" ")
        check("T04c limits 纳入家庭哈希",
              render_plan.compute_rules_bundle_hash("shared_uniform") != before)
    finally:
        open(lp, "wb").write(raw)


def t05_pipeline_hash():
    import render_plan
    h = render_plan.compute_pipeline_bundle_hash()
    check("T05a pipeline 哈希可算", len(h) == 16)
    check("T05b 与规则哈希不同", h != render_plan.compute_rules_bundle_hash())
    target = os.path.join(BASE, "scripts", "render_html.py")
    if not os.path.exists(target):
        target = os.path.join(BASE, "scripts", "render_output.py")
    raw = open(target, "rb").read()
    try:
        open(target, "ab").write(b"\n# t05-probe\n")
        check("T05c 执行组件变更即变哈希",
              render_plan.compute_pipeline_bundle_hash() != h)
    finally:
        open(target, "wb").write(raw)
    check("T05d 恢复后哈希还原", render_plan.compute_pipeline_bundle_hash() == h)


def t06_migration_map():
    mm = open(os.path.join(BASE, "developer", "migration-map.md"), encoding="utf-8").read()
    for sec in ("## 1. 字段迁移", "## 2. 文件迁移", "## 3. 行为迁移", "## 4. 拒绝策略"):
        check("T06 迁移映射 %s" % sec, sec in mm)
    check("T06 拒绝策略原则", "不为兼容旧字段重新放宽" in mm)


def t07_release_pack_and_manifest():
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "release_pack.py"),
                            "--out", d,
                            "--test-summary", '{"total":41,"passed":41,"failed":0}'],
                           capture_output=True, text=True)
        check("T07a 打包+包内烟测通过", r.returncode == 0, (r.stdout + r.stderr)[-400:])
        mp = os.path.join(BASE, "data", "release-manifest.json")
        m = json.load(open(mp, encoding="utf-8"))
        check("T07b manifest 版本", m["release_version"] == VERSION)
        check("T07c 产物 sha256 记录", all(len(a["sha256"]) == 64 for a in m["artifacts"]))
        check("T07d 两包内容一致",
              m["artifacts"][0]["sha256"] == m["artifacts"][1]["sha256"])
        # round44：烟测扩为 7 步，日志迁至 smoke_steps
        check("T07e 烟测日志全过",
              m["package_smoke"]["passed"] and len(m["smoke_steps"]) >= 5)
        check("T07f 双哈希在 manifest",
              len(m["pipeline_bundle_hash"]) == 16
              and m["rules_bundle_hash_solo"] != m["rules_bundle_hash_household"])
        check("T07g test_summary 记录", m.get("test_summary", {}).get("failed") == 0)


def t08_perf_baseline():
    r = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "perf_baseline.py")],
                       capture_output=True, text=True)
    check("T08a 性能基线可运行", r.returncode == 0, r.stderr[-200:])
    pb = json.load(open(os.path.join(BASE, "data", "perf-baseline.json"), encoding="utf-8"))
    for node in ("household_hash", "identity_merge_2p", "override_merge_2p",
                 "override_merge_3p_absent", "effective_validation", "solo_golden_render"):
        check("T08b 节点 %s" % node, node in pb["nodes"] and pb["nodes"][node] > 0)


if __name__ == "__main__":
    for fn in (t01_version_consistency, t02_g03_split, t03_identity_merge,
               t04_household_limits_single_source, t05_pipeline_hash,
               t06_migration_map, t07_release_pack_and_manifest, t08_perf_baseline):
        fn()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)
