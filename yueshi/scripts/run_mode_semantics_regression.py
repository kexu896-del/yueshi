#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模式营养语义回归（round68，2026-09-18）

同一套用户事实下对平衡激素模式（hormone）与酮生物模式（keto）做受控对照，
验证模式不只是显示标签：目标来自 approved 参数、进入篮子/ranker/营养管线、
差异可追溯、安全规则优先。

用法：
  python scripts/run_mode_semantics_regression.py --out-dir <目录> [--start-date 2026-09-18]
产物：mode-semantics-regression.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(BASE, "scripts"))
sys.path.insert(0, os.path.join(BASE, "scripts", "common"))
import daily_target_compiler as dtc  # noqa: E402
import visible_messages as vm  # noqa: E402

FACTS = dict(sex="f", age=28, height=163, weight=70, activity=1.4, goal="lose")
STAGES = ["manifestation", "manifestation", "power2", "power2", "power2", "power2", "nurture"]
MODE_CN = {"hormone": "hormone_balance", "keto": "keto_biologic"}
TARGET_PARAMS = {
    "hormone": ["hormone_net_carb_weightloss_g", "hormone_protein_reference_cap_g"],
    "keto": ["keto_net_carb_cap_g", "keto_fat_energy_min_pct", "keto_protein_reference_cap_g"],
}
COMMON_PARAMS = ["protein_tolerance_pct"]


def _sha(obj):
    canonical = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()[:16]


def _run(cmd, cwd):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    r = subprocess.run([sys.executable, "-X", "utf8"] + cmd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, cwd=cwd)
    return r


def _basket_for(mode, start_date, workdir):
    """构造 mode_schedule 并跑 basket_builder，返回 (basket, schedule_hash)。"""
    internal = MODE_CN[mode]
    dates = ["2026-09-%02d" % (18 + i) for i in range(7)]
    schedule = {
        "plan_id": "regression-%s" % internal,
        "mode_schedule": {d: internal for d in dates},
        "mode_summary": {"keto_days": 7 if mode == "keto" else 0,
                         "hormone_days": 0 if mode == "keto" else 7},
        "fasting_hours_default": 12,
        "fasting_level": "L0",
    }
    sp = os.path.join(workdir, "mode_schedule_%s.json" % mode)
    json.dump(schedule, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    r = _run([os.path.join(BASE, "scripts", "basket_builder.py"),
              "--meals-per-day", "1", "--month", "9", "--budget-tier", "economy",
              "--seed", "20260918", "--mode-schedule", sp, "--avoid", "香菜"], cwd=BASE)
    basket = {}
    if r.stdout:
        try:
            basket, _ = json.JSONDecoder().raw_decode(r.stdout.lstrip())
        except ValueError:
            pass
    return basket, _sha(schedule)


def _ranker_for(mode, start_date, workdir):
    """跑 recipe_ranker，返回 (候选数, 模式标签)。"""
    sp = os.path.join(workdir, "mode_schedule_%s.json" % mode)
    r = _run([os.path.join(BASE, "scripts", "recipe_ranker.py"),
              "--basket", "鸡蛋,鸡腿,菠菜,西兰花,南瓜,红薯",
              "--mode-schedule", sp, "--max-minutes", "30", "--limit", "40"], cwd=BASE)
    count = None
    label = None
    for line in (r.stdout or "").splitlines():
        if line.startswith("模式="):
            label = line.split("·")[0].replace("模式=", "").strip()
            try:
                count = int(line.split("候选 ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass
    return count, label


def _parameter_sources():
    doc = json.load(open(os.path.join(BASE, "data", "effective-parameters.json"),
                         encoding="utf-8"))
    plist = doc.get("parameters", [])
    return {p.get("parameter_id"): p for p in plist}


def run_regression(out_dir, start_date="2026-09-18"):
    os.makedirs(out_dir, exist_ok=True)
    params = _parameter_sources()

    fixtures = []
    target_docs = {}
    baskets = {}
    ranker = {}
    for mode in ("hormone", "keto"):
        doc = dtc.compile_daily_targets(**FACTS, modes=[mode] * 7, stages=STAGES,
                                        start_date=start_date)
        errs = dtc.validate_targets(doc)
        target_docs[mode] = doc
        d0 = doc["days"][0]
        used = TARGET_PARAMS[mode] + COMMON_PARAMS
        source_rule_ids = sorted({params[p]["source_rule_id"] for p in used if p in params})
        approved = all(params.get(p, {}).get("audit_status") == "approved" for p in used)
        basket, sched_hash = _basket_for(mode, start_date, out_dir)
        baskets[mode] = basket
        rcount, rlabel = _ranker_for(mode, start_date, out_dir)
        ranker[mode] = {"candidate_count": rcount, "mode_label": rlabel}
        display = vm.mode_display(MODE_CN[mode])["display_name"]
        fixtures.append({
            "fixture_id": "%s_control" % MODE_CN[mode],
            "mode": MODE_CN[mode],
            "display_name": display,
            "source_rule_ids": source_rule_ids,
            "parameter_version": doc.get("targets_version"),
            "targets_hash": _sha(doc["days"]),
            "targets": {
                "calories_target_kcal": d0["calories_target_kcal"],
                "calorie_safety_floor_kcal": d0["calorie_safety_floor_kcal"],
                "net_carb_max_g": d0["net_carb_max_g"],
                "protein_safety_floor_g": d0["protein_safety_floor_g"],
                "protein_individual_target_g": d0["protein_individual_target_g"],
                "protein_tolerance_upper_g": d0["protein_tolerance_upper_g"],
                "protein_book_reference_g": d0["protein_book_reference_g"],
                "fat_min_energy_pct": d0["fat_min_energy_pct"],
            },
            "basket_constraints_hash": _sha(basket.get("weekly_basket", {})),
            "basket_summary": {
                "carbohydrates": basket.get("weekly_basket", {}).get("carbohydrates", []),
                "fat_extras": basket.get("weekly_basket", {}).get("fat_extras", []),
            },
            "menu_constraints_hash": _sha(ranker[mode]),
            "ranker": ranker[mode],
            "validation": "passed" if not errs and approved and basket else "failed",
            "validation_errors": errs,
        })

    h = target_docs["hormone"]["days"][0]
    k = target_docs["keto"]["days"][0]
    expected_diff = (
        k["net_carb_max_g"] < h["net_carb_max_g"]
        and k["fat_min_energy_pct"] > h["fat_min_energy_pct"]
        and k["protein_book_reference_g"] != h["protein_book_reference_g"])
    baskets_differ = baskets["hormone"].get("weekly_basket") != baskets["keto"].get("weekly_basket")
    ranker_differ = (ranker["hormone"]["candidate_count"] != ranker["keto"]["candidate_count"]
                     or ranker["hormone"]["mode_label"] != ranker["keto"]["mode_label"])

    # 渲染器不定义目标：render_plan 不得包含目标参数名或自行计算 BMR
    renderer_src = open(os.path.join(BASE, "scripts", "render_plan.py"), encoding="utf-8").read()
    renderer_clean = all(p not in renderer_src for p in (
        "keto_net_carb_cap_g", "hormone_net_carb_cap_g", "bmr_mifflin", "calc_targets"))

    # 安全优先：安全线 = BMR×1.1，蛋白地板来自参数化公式；安全规则文档声明优先级
    safety_doc = open(os.path.join(BASE, "references", "safety-rules.md"), encoding="utf-8").read()
    safety_ok = ("热量不低于安全线" in safety_doc and "蛋白质不低于安全下限" in safety_doc
                 and h["calorie_safety_floor_kcal"] > 0
                 and h["protein_safety_floor_g"] <= h["protein_individual_target_g"])

    report = {
        "skill_version": _skill_version(),
        "parameter_version": params.get("protein_tolerance_pct", {}).get("protocol_version",
                                                                         "2026-08-21"),
        "generated_at": start_date,
        "facts": FACTS,
        "fixtures": fixtures,
        "cross_mode_checks": {
            "expected_differences_present": bool(expected_diff),
            "differences_traceable_to_approved_parameters": all(
                f["source_rule_ids"] and f["validation"] == "passed" for f in fixtures),
            "baskets_differ_between_modes": bool(baskets_differ),
            "ranker_constraints_differ_between_modes": bool(ranker_differ),
            "renderer_does_not_define_targets": bool(renderer_clean),
            "safety_precedence_verified": bool(safety_ok),
        },
        "targets": {
            "hormone": h,
            "keto": k,
        },
    }
    path = os.path.join(out_dir, "mode-semantics-regression.json")
    json.dump(report, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return report, path


def _skill_version():
    for line in open(os.path.join(BASE, "SKILL.md"), encoding="utf-8"):
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="模式营养语义回归")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start-date", default="2026-09-18")
    args = ap.parse_args()
    report, path = run_regression(args.out_dir, args.start_date)
    checks = report["cross_mode_checks"]
    print("written:", path)
    print(json.dumps(checks, ensure_ascii=False))
    bad = [k for k, v in checks.items() if not v]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
