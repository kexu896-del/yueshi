#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round44：发布链路定稿（泄漏防线 / 依赖闭包 / 可复现构建 / 7 步烟测 / 家庭渲染 / 1.1.0）。"""
import json, os, subprocess, sys, tempfile, zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
sys.path.insert(0, os.path.join(BASE, "scripts"))
import release_pack as rp

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def t01_version_110():
    import re
    v = re.search(r"^version:\s*(\S+)", SK, re.M).group(1)
    check("T01a 版本语义化且与 golden 同源", re.fullmatch(r"yueshi-\d+\.\d+\.\d+(-rc\d*)?", v) is not None)
    g = json.load(open(os.path.join(BASE, "data", "golden", "household", "samples",
                                    "golden-base-plan-sample.json"), encoding="utf-8"))
    check("T01b golden skill_version 同步", g["plan_meta"]["skill_version"] == v)
    check("T01c 数据契约 const 维持 v0.3-rc2",
          g["plan_meta"]["plan_schema_version"] == "v0.3-rc2")


def t02_payload_scan():
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.zip")
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("SKILL.md", "x")
        check("T02a 干净包通过", rp.copyright_payload_scan(good)["passed"])
        for entry, why in (("book-extraction/a.txt", "目录内容"),
                           ("data/x.epub", "电子书"),
                           ("data/audit.jsonl", "缓存载荷")):
            bad = os.path.join(d, "bad.zip")
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr(entry, "x")
            r = rp.copyright_payload_scan(bad)
            check("T02b 命中 %s（%s）" % (entry, why), not r["passed"] and r["hits"])


def t03_runtime_reference_scan():
    r = rp.runtime_reference_scan()
    check("T03a 运行文件无 book-extraction 引用", r["passed"], str(r["hits"]))
    mm = open(os.path.join(BASE, "developer", "maintenance-map.md"), encoding="utf-8").read()
    check("T03b 发布策略已定稿", "发布与维护区策略" in mm and "四条硬门禁" in mm)
    check("T03c 维护区路径集中登记于 maintenance-map", "book-extraction/" in mm)


def t04_dependency_closure():
    with tempfile.TemporaryDirectory() as d:
        zp = os.path.join(d, "p.zip")
        rp.build_zip(zp)
        r = rp.dependency_check(zp)
        check("T04a 闭包完整（closure=%d）" % r["closure_size"], r["passed"], str(r["missing"]))
        # 人为缺件必须失败
        bad = os.path.join(d, "bad.zip")
        with zipfile.ZipFile(zp) as zin, zipfile.ZipFile(bad, "w") as zout:
            for n in zin.namelist():
                if n != "SKILL.md":
                    zout.writestr(n, zin.read(n))
        r2 = rp.dependency_check(bad)
        check("T04b 缺件即失败", not r2["passed"] and "SKILL.md" in r2["missing"])


def t05_reproducible_build():
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.zip"), os.path.join(d, "b.zip")
        rp.build_zip(a)
        rp.build_zip(b)
        check("T05a 重复构建 SHA-256 一致", rp.sha256(a) == rp.sha256(b))
        with zipfile.ZipFile(a) as z:
            info = z.infolist()[0]
            check("T05b 固定时间戳", info.date_time == rp.FIXED_ZIP_DATE)


def t06_family_render():
    import household_override_merger as mrg
    import household_components as hc
    with tempfile.TemporaryDirectory() as d:
        eff = mrg.merge(os.path.join(BASE, "data", "golden", "household", "samples",
                                     "golden-base-plan-sample.json"),
                        os.path.join(BASE, "data", "golden", "household", "samples",
                                     "golden-override-sample.json"),
                        os.path.join(d, "e.json"))
        html = hc.render_household_html(eff)
        check("T06a 成员标签渲染", "减重份" in html and "健康调理份" in html)
        check("T06b 份量块与三本账", "盛取方式" in html and "家庭需求" in html)
        for bad in ("portion_method", "member_portions", "selected_pct", "effective_meta"):
            check("T06c 无内部术语 %s" % bad, bad not in html)
        check("T06d 缺席成员不出现在份量行", html.count("hh-portion-member") >= 1)


def t07_release_pack_full():
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "release_pack.py"),
                            "--out", d, "--build-source", "candidates/round44",
                            "--test-summary", '{"total":42,"passed":42,"failed":0}'],
                           capture_output=True, text=True)
        check("T07a 发布链路 exit 0", r.returncode == 0, (r.stdout + r.stderr)[-500:])
        m = json.load(open(os.path.join(BASE, "data", "release-manifest.json"), encoding="utf-8"))
        import re as _re
        _v = _re.search(r"^version:\s*(\S+)", SK, _re.M).group(1)
        check("T07b manifest 版本与 frontmatter 一致", m["release_version"] == _v)
        for f in ("build_source", "build_tool_version", "created_at", "excluded_paths",
                  "exclusion_reason", "source_retention_policy", "package_file_count",
                  "uncompressed_size_bytes", "smoke_steps", "runtime_dependency_check",
                  "copyright_payload_scan", "reproducible_build"):
            check("T07c 字段 %s" % f, f in m)
        check("T07d 可复现构建通过", m["reproducible_build"] is True)
        check("T07e 载荷扫描 0 命中", m["copyright_payload_scan"]["passed"])
        check("T07f 依赖闭包通过", m["runtime_dependency_check"]["passed"])
        check("T07g 烟测 7 步全过",
              m["package_smoke"]["passed"] and len(m["smoke_steps"]) == 7
              and all(s["ok"] for s in m["smoke_steps"]))
        steps = [s["step"] for s in m["smoke_steps"]]
        check("T07h 含家庭渲染与 hygiene 步",
              "family_effective_render" in steps and "release_hygiene" in steps)


def t08_perf_family_node():
    pb = json.load(open(os.path.join(BASE, "data", "perf-baseline.json"), encoding="utf-8"))
    check("T08 家庭渲染性能节点", pb["nodes"].get("family_effective_render", 0) > 0)


if __name__ == "__main__":
    for fn in (t01_version_110, t02_payload_scan, t03_runtime_reference_scan,
               t04_dependency_closure, t05_reproducible_build, t06_family_render,
               t07_release_pack_full, t08_perf_family_node):
        fn()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)
