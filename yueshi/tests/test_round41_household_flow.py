#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round41：SKILL 联动修订（家庭模式接入入口）回归测试。"""
import copy, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(BASE, "data", "golden", "household", "samples")
sys.path.insert(0, os.path.join(BASE, "scripts"))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def load_sample(name):
    doc = json.load(open(os.path.join(SAMPLES, name), encoding="utf-8"))
    # 样例中的占位哈希按"缺省跳过"口径归零（渲染门禁对缺省哈希跳过比对）
    if doc.get("plan_meta", {}).get("rules_bundle_hash") == "GOLDEN_HASH_PLACEHOLDER":
        doc["plan_meta"]["rules_bundle_hash"] = ""
    return doc


def t01_files_exist():
    for rel in ("workflows/household-planning-flow.md",
                "references/household-runtime-rules.md",
                "scripts/household_override_merger.py",
                "scripts/household_components.py",
                "data/golden/household/samples/golden-base-plan-sample.json",
                "data/golden/household/samples/golden-override-sample.json"):
        check("t01 文件存在 %s" % rel, os.path.isfile(os.path.join(BASE, rel)))


def t02_skill_version_and_triggers():
    sk = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
    import re as _re
    _v = _re.search(r"^version:\s*(\S+)", sk, _re.M).group(1)
    check("t02a 版本号已脱离 1.0.x", not _v.startswith("yueshi-1.0"))
    for w in ("双人餐", "两人吃饭", "全家食谱", "同餐不同量", "多人共餐", "家庭版"):
        check("t02b 触发词 %s" % w, w in sk.split("---")[1])


def t03_skill_flow_and_gate():
    sk = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
    check("t03a 家庭 13 步分支", "household-planning-flow.md` 的 13 步" in sk and "不得逐成员各跑一遍 15 步" in sk)
    check("t03b 完整性门禁按 plan_mode 扩展", "不降级为 solo" in sk and "schemas/household/" in sk)
    # round42：检查项编号统一为 H01–H06（原 12–17，烟测意见 P1-5）
    for i in range(1, 7):
        check("t03c 家庭检查项 H%02d" % i, ("H%02d. [auto_fix]" % i) in sk)


def t04_skill_terminology():
    sk = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
    for w in ("portion_method", "attendance_override", "selected_pct", "external_meal",
              "member_portions", "shopping_delta", "pending_attendance_resolution"):
        check("t04a 禁用词 %s" % w, w in sk)
    for m in ("portion_method → 盛取方式", "external_meal → 外食", "uncertain → 待定",
              "selected_pct → 实际分配比例", "attendance_override → 就餐变化"):
        check("t04b 显示转换 %s" % m, m in sk)


def t05_merger_absent_and_meta():
    import household_override_merger as mrg
    base = load_sample("golden-base-plan-sample.json")
    frozen = copy.deepcopy(base)
    ov = json.load(open(os.path.join(SAMPLES, "golden-override-sample.json"), encoding="utf-8"))
    with tempfile.TemporaryDirectory() as d:
        bp, op, ep = (os.path.join(d, n) for n in ("b.json", "o.json", "e.json"))
        json.dump(base, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(ov, open(op, "w", encoding="utf-8"), ensure_ascii=False)
        eff = mrg.merge(bp, op, ep)
    check("t05a base 未被修改", base == frozen)
    meal = eff["shared_meals"][0]
    check("t05b 缺席成员份量移除",
          [b["member_id"] for b in meal["member_portions"]] == ["primary"])
    check("t05c 参与者集合收缩", meal["participant_member_ids"] == ["primary"])
    check("t05d attendance 置 not_participating",
          meal["attendance_plan"].get("secondary") == "not_participating")
    check("t05e effective_meta 记录", eff["effective_meta"]["applied_override_ids"] ==
          ["ovr-wed-lunch-secondary-absent"] and
          eff["effective_meta"]["base_build_id"] == "golden-20260825-01")
    check("t05f effective_plan 无 schema 外内部字段",
          "_pending_leftover_refs" not in eff and "_note" not in eff)
    # effective_plan 必须过 effective_plan 契约（缺席后参与者可合法降至 1 人）
    r = subprocess.run([sys.executable,
                        os.path.join(BASE, "scripts", "household_reference_validator.py"),
                        "--base", ep, "--schema", "effective_plan"],
                       capture_output=True, text=True)
    check("t05g effective_plan 过 schema", "Schema 校验失败" not in r.stderr,
          r.stderr[-200:])


def t06_merger_ratio_renorm():
    from household_override_merger import normalize_ratios
    meal = {"portion_method": "ratio_split",
            "participant_member_ids": ["a", "b"],
            "portion_ratios": [
                {"member_id": "a", "pct_min": 25, "pct_max": 35, "selected_pct": 30},
                {"member_id": "b", "pct_min": 30, "pct_max": 40, "selected_pct": 35},
                {"member_id": "c", "pct_min": 30, "pct_max": 40, "selected_pct": 35}]}
    out = normalize_ratios(copy.deepcopy(meal))
    s = sum(r["selected_pct"] for r in out["portion_ratios"])
    check("t06a 重归一 Σ=100", abs(s - 100) < 0.01, str(s))
    check("t06b 缺席成员被剔除", [r["member_id"] for r in out["portion_ratios"]] == ["a", "b"])


def t07_merger_present_confirmed_and_delta():
    import household_override_merger as mrg
    base = {"plan_meta": {"build_id": "x"},
            "shared_meals": [{"meal_id": "m1", "participant_member_ids": ["a", "b"],
                              "member_portions": [{"member_id": "a"}, {"member_id": "b"}],
                              "attendance_plan": {"b": "uncertain"}}],
            "shopping": [{"ingredient_id": "rice",
                          "new_purchase_amount": {"canonical_grams": 1000}}]}
    ovs = {"generated_at": "t", "overrides": [
        {"override_id": "o1", "meal_id": "m1", "member_id": "b", "status": "present_confirmed"},
        {"override_id": "o2", "meal_id": "m1", "member_id": "b", "status": "absent",
         "known_at": "before_shopping",
         "shopping_delta": [{"ingredient_id": "rice", "grams": 300,
                             "destination": "reduce_purchase"}]}]}
    with tempfile.TemporaryDirectory() as d:
        bp, op, ep = (os.path.join(d, n) for n in ("b.json", "o.json", "e.json"))
        json.dump(base, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(ovs, open(op, "w", encoding="utf-8"), ensure_ascii=False)
        eff = mrg.merge(bp, op, ep, validate=False)  # 合成夹具非完整契约，落盘前校验由 t05（真实 golden 样例）覆盖
    # o1 先确认（uncertain→expected），o2 再缺席
    check("t07a present_confirmed 不误删份量", len(eff["shared_meals"][0]["member_portions"]) >= 1)
    check("t07b shopping_delta 减采购",
          eff["shopping"][0]["new_purchase_amount"]["canonical_grams"] == 700)


def t08_samples_schema_and_validator():
    import jsonschema
    bundle = json.load(open(os.path.join(
        BASE, "schemas", "household", "household-schemas.bundle.json"), encoding="utf-8"))
    base = load_sample("golden-base-plan-sample.json")
    ov = json.load(open(os.path.join(SAMPLES, "golden-override-sample.json"), encoding="utf-8"))
    ok1 = ok2 = True
    try:
        jsonschema.validate(base, bundle["base_plan"])
    except Exception as e:
        ok1, msg = False, str(e)[:200]
        check("t08a base 样例过 schema", False, msg)
    if ok1:
        check("t08a base 样例过 schema", True)
    try:
        jsonschema.validate(ov, bundle["overrides"])
    except Exception as e:
        ok2 = False
        check("t08b override 样例过 schema", False, str(e)[:200])
    if ok2:
        check("t08b override 样例过 schema", True)
    r = subprocess.run([sys.executable,
                        os.path.join(BASE, "scripts", "household_reference_validator.py"),
                        "--base", os.path.join(SAMPLES, "golden-base-plan-sample.json"),
                        "--overrides", os.path.join(SAMPLES, "golden-override-sample.json")],
                       capture_output=True, text=True)
    check("t08c 引用校验器通过（exit 0/3 视样例完整度）", r.returncode in (0, 3),
          (r.stdout + r.stderr)[-300:])


def t09_components_rendering():
    import household_components as hc
    base = load_sample("golden-base-plan-sample.json")
    meal = base["shared_meals"][0]
    html = hc.portion_block(meal)
    check("t09a 份量块可见术语", "盛取方式" in html)
    for bad in ("portion_method", "member_portions", "selected_pct"):
        check("t09b 份量块无内部术语 %s" % bad, bad not in html)
    item = base["shopping"][0]
    row = hc.shopping_three_ledger_row(item)
    check("t09c 三本账行三列齐", row.count("<td>") == 4 and "960 g" in row and "1000 g" in row)
    member = base["members"][0]
    nb = hc.member_nutrition_block(member, {"calories_kcal": 1280, "protein_g": 72})
    check("t09d 成员营养块独立行", "减重份" in nb and "1280" in nb and "hh-nut-row" in nb)


def t10_schema_fix_not_regressed():
    """用户重传 schema 回退了 round40 的逐字段 not 修复——正式版必须保持修复态。"""
    raw = open(os.path.join(BASE, "schemas", "household", "shared-definitions.schema.json"),
               encoding="utf-8").read()
    check("t10a 不含多字段 not/required 缺陷模式",
          '"not": {\n        "required": [\n          "action",\n          "leftover_plan_id"' not in raw
          and '"required": [\n          "action",\n          "shopping_delta"' not in raw)
    check("t10b 逐字段 not 仍在", raw.count('"not"') >= 6)


if __name__ == "__main__":
    for fn in (t01_files_exist, t02_skill_version_and_triggers, t03_skill_flow_and_gate,
               t04_skill_terminology, t05_merger_absent_and_meta, t06_merger_ratio_renorm,
               t07_merger_present_confirmed_and_delta, t08_samples_schema_and_validator,
               t09_components_rendering, t10_schema_fix_not_regressed):
        fn()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)
