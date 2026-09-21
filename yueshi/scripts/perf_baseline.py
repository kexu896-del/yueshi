#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perf_baseline.py · 性能基线（round43）。

按节点分段计时（不是只测总耗时），覆盖 solo / 2 人 / 3 人 / override 场景：
  rule_loading / household_hash / override_merge / identity_merge /
  effective_validation / renderer_import / solo_golden_render。
输出 data/perf-baseline.json（本机参考值，供回归对比趋势，不作硬门禁）。
"""
import json, os, subprocess, sys, tempfile, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
SAMPLES = os.path.join(BASE, "data", "golden", "household", "samples")
CASES = os.path.join(BASE, "data", "golden", "household")


def _t(fn, n=3):
    best = None
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return round(best * 1000, 3)  # ms


def main():
    sys.path.insert(0, SCRIPTS)
    results = {"generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
               "unit": "ms (best of 3)", "nodes": {}}

    import render_plan
    results["nodes"]["rule_loading_solo_hash"] = _t(lambda: render_plan.compute_rules_bundle_hash())
    results["nodes"]["household_hash"] = _t(lambda: render_plan.compute_rules_bundle_hash("shared_uniform"))
    results["nodes"]["pipeline_hash"] = _t(lambda: render_plan.compute_pipeline_bundle_hash())

    import household_override_merger as mrg
    from household_reference_validator import _schema_validate
    base2 = os.path.join(SAMPLES, "golden-base-plan-sample.json")
    ovr2 = os.path.join(SAMPLES, "golden-override-sample.json")
    ovr8 = os.path.join(CASES, "case-08-three-absent-redistribute.overrides.json")
    base8 = os.path.join(CASES, "case-08-three-absent-redistribute.base.json")

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "e.json")
        results["nodes"]["identity_merge_2p"] = _t(lambda: mrg.merge(base2, None, out))
        results["nodes"]["override_merge_2p"] = _t(lambda: mrg.merge(base2, ovr2, out))
        results["nodes"]["override_merge_3p_absent"] = _t(lambda: mrg.merge(base8, ovr8, out))
        eff = mrg.merge(base2, ovr2, out)
        results["nodes"]["effective_validation"] = _t(lambda: _schema_validate(eff, "effective_plan"))
        solo = os.path.join(BASE, "data", "golden", "golden-sample-plan.json")
        html = os.path.join(d, "s.html")

        def _render():
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "render_plan.py"),
                            "--input", solo, "--output", html],
                           capture_output=True).check_returncode()
        results["nodes"]["solo_golden_render"] = _t(_render, n=1)
        import household_components as hc
        results["nodes"]["family_effective_render"] = _t(lambda: hc.render_household_html(eff))

    # round46：价格门禁节点（外部 Provider 的 browser_start_ms / login_wait_ms /
    # query_total_ms 等在 Provider 侧记录，login_wait_ms 是用户操作等待，
    # 必须与自动执行耗时分开，不计入本基线）。
    import price_result_validator as prv
    sample_result = os.path.join(BASE, "data", "golden", "price-result-sample.json")
    if os.path.exists(sample_result):
        results["nodes"]["price_gate_validate"] = _t(lambda: prv.validate_result(sample_result))

    mp = os.path.join(BASE, "data", "perf-baseline.json")
    json.dump(results, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
