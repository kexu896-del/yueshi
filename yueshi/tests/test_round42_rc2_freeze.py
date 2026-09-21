#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round42：v1.1.0-rc 烟测后修改意见（3 P0 + 5 P1 + T01–T08）回归测试。"""
import copy, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(BASE, "data", "golden", "household", "samples")
SK = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read()
sys.path.insert(0, os.path.join(BASE, "scripts"))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def _run_validator(plan_path, schema, extra=()):
    return subprocess.run([sys.executable,
                           os.path.join(BASE, "scripts", "household_reference_validator.py"),
                           "--base", plan_path, "--schema", schema, *extra],
                          capture_output=True, text=True)


def _golden_effective(tmp):
    import household_override_merger as mrg
    bp = os.path.join(SAMPLES, "golden-base-plan-sample.json")
    op = os.path.join(SAMPLES, "golden-override-sample.json")
    ep = os.path.join(tmp, "effective.json")
    return mrg.merge(bp, op, ep), ep


def t01_split_safety_in_household_set():
    """T01/P0-1：split_safety_required 不被 shared_* 条件漏掉。"""
    check("T01a SKILL 定义 household_plan_modes 集合",
          "household_plan_modes` = {shared_uniform, shared_meal_personalized, split_safety_required}" in SK)
    check("T01b 禁止前缀匹配的说明", "禁止用 \"shared_*\" 字符串前缀匹配" in SK)
    body = SK.split("household_plan_modes` = {")[1]
    check("T01c 正文不再用 shared_* 作条件", "shared_* 时" not in body and "plan_mode=shared_*" not in body)
    for doc in ("references/household-runtime-rules.md",):
        t = open(os.path.join(BASE, doc), encoding="utf-8").read()
        check("T01d %s 无 shared_* 条件" % doc, "shared_*" not in t)
    import render_plan
    check("T01e 代码常量含 split_safety_required",
          "split_safety_required" in render_plan.HOUSEHOLD_PLAN_MODES)
    check("T01f split 模式哈希走家庭规则包",
          render_plan.compute_rules_bundle_hash("split_safety_required")
          == render_plan.compute_rules_bundle_hash("shared_uniform")
          != render_plan.compute_rules_bundle_hash("solo"))


def t02_foreign_field_injection():
    """T02：effective 任一层注入契约外字段即失败。"""
    with tempfile.TemporaryDirectory() as d:
        eff, ep = _golden_effective(d)
        for field in ("_note", "debug"):
            bad = copy.deepcopy(eff)
            bad[field] = "x"
            p = os.path.join(d, "bad.json")
            json.dump(bad, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            r = _run_validator(p, "effective_plan")
            check("T02 顶层注入 %s 被拒" % field, r.returncode == 3 and "Schema 校验失败" in r.stderr)
        bad = copy.deepcopy(eff)
        bad["shared_meals"][0]["_debug"] = 1
        p = os.path.join(d, "bad2.json")
        json.dump(bad, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        r = _run_validator(p, "effective_plan")
        check("T02 嵌套注入 _debug 被拒", r.returncode == 3)


def t03_base_to_single_participant_meal():
    """T03：双人 base 通过；缺席后 effective 通过；成员主数据仍两人。"""
    with tempfile.TemporaryDirectory() as d:
        r = _run_validator(os.path.join(SAMPLES, "golden-base-plan-sample.json"), "base_plan")
        check("T03a base 过 schema", "Schema 校验失败" not in r.stderr, r.stderr[-150:])
        eff, ep = _golden_effective(d)
        check("T03b 成员主数据仍 2 人", len(eff["members"]) == 2)
        check("T03c 单餐参与者降至 1 人",
              eff["shared_meals"][0]["participant_member_ids"] == ["primary"])
        r = _run_validator(ep, "effective_plan")
        check("T03d effective 过 schema", "Schema 校验失败" not in r.stderr, r.stderr[-150:])
        check("T03e effective 仍保留 base_build_id",
              eff["effective_meta"]["base_build_id"] == "golden-20260825-01")


def t04_wrong_schema_mode():
    """T04：用错 schema 模式必须明确失败。"""
    with tempfile.TemporaryDirectory() as d:
        eff, ep = _golden_effective(d)
        r = _run_validator(ep, "base_plan")
        check("T04a effective 按 base 校验失败", r.returncode == 3 and "Schema 校验失败" in r.stderr)
        r = _run_validator(os.path.join(SAMPLES, "golden-override-sample.json"), "effective_plan")
        check("T04b overrides 按 effective 校验失败", r.returncode == 3)
        r = _run_validator(os.path.join(SAMPLES, "golden-override-sample.json"), "overrides")
        check("T04c overrides 按 overrides 校验通过", r.returncode == 0, r.stderr[-150:])


def t05_future_pending_override():
    """T05：pending override 不影响当前 effective，保留在源文件。"""
    import household_override_merger as mrg
    with tempfile.TemporaryDirectory() as d:
        base = json.load(open(os.path.join(SAMPLES, "golden-base-plan-sample.json"), encoding="utf-8"))
        ovs = {"generated_at": "2026-08-26T08:00:00+08:00", "overrides": [
            {"override_id": "ovr-future", "date": "2026-08-27", "meal_id": "wed_lunch",
             "member_id": "secondary", "status": "absent", "known_at": "before_cooking",
             "action": "keep_batch_for_leftover", "merge_status": "pending"}]}
        bp, op, ep = (os.path.join(d, n) for n in ("b.json", "o.json", "e.json"))
        json.dump(base, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(ovs, open(op, "w", encoding="utf-8"), ensure_ascii=False)
        eff = mrg.merge(bp, op, ep)
        check("T05a pending 未被应用", eff["effective_meta"]["applied_override_ids"] == [])
        check("T05b 份量未被移除", len(eff["shared_meals"][0]["member_portions"]) == 2)
        check("T05c pending 保留在源文件",
              json.load(open(op, encoding="utf-8"))["overrides"][0]["merge_status"] == "pending")


def t06_external_meal_no_leftover():
    """T06：external_meal 不产生 leftover；采购去向可经契约字段追溯。"""
    import household_override_merger as mrg
    with tempfile.TemporaryDirectory() as d:
        base = json.load(open(os.path.join(SAMPLES, "golden-base-plan-sample.json"), encoding="utf-8"))
        ovs = {"generated_at": "2026-08-26T12:00:00+08:00", "overrides": [
            {"override_id": "ovr-ext", "date": "2026-08-26", "meal_id": "wed_lunch",
             "member_id": "secondary", "status": "external_meal",
             "known_at": "after_shopping"}]}
        bp, op, ep = (os.path.join(d, n) for n in ("b.json", "o.json", "e.json"))
        json.dump(base, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(ovs, open(op, "w", encoding="utf-8"), ensure_ascii=False)
        eff = mrg.merge(bp, op, ep)
        check("T06a 未物化 leftover", eff.get("leftover_plans", []) == [])
        check("T06b 份量移除且采购字段仍在",
              len(eff["shared_meals"][0]["member_portions"]) == 1
              and eff["shopping"] and "new_purchase_amount" in eff["shopping"][0])
        check("T06c 可追溯到 override_id", eff["effective_meta"]["applied_override_ids"] == ["ovr-ext"])


def t07_four_members_layout_policy():
    """T07：人数与分页口径（文案级，渲染连线属 RC2-6）。"""
    check("T07a 摘要页最多 3 人并排", "家庭摘要页最多并排展示 3 名成员" in SK)
    check("T07b 成员总数可大于 3", "成员总数可大于 3" in SK)
    check("T07c 超限不静默截断", "不在渲染阶段静默截断" in SK)
    check("T07d 家庭页数预算", "基础 9 页 + 成员附页预算" in SK and "禁止为卡页数降低字号" in SK)
    op = open(os.path.join(BASE, "references", "output-policy.md"), encoding="utf-8").read()
    check("T07e output-policy 家庭页数预算", "基础 9 页 + 成员附页" in op)
    check("T07f 旧『上限 3 名成员』表述已清除", "正式支持上限 3 名成员" not in SK)


def t08_household_hash_change():
    """T08：家庭规则或 Schema 变更 → rules_bundle_mismatch。"""
    import render_plan
    target = os.path.join(BASE, "references", "household-runtime-rules.md")
    before = render_plan.compute_rules_bundle_hash("shared_meal_personalized")
    solo_before = render_plan.compute_rules_bundle_hash("solo")
    raw = open(target, "rb").read()
    try:
        open(target, "ab").write(b"\n<!-- t08-probe -->\n")
        check("T08a 家庭哈希随规则变化",
              render_plan.compute_rules_bundle_hash("shared_meal_personalized") != before)
        check("T08b solo 哈希不受家庭规则影响",
              render_plan.compute_rules_bundle_hash("solo") == solo_before)
    finally:
        open(target, "wb").write(raw)
    check("T08c 恢复后哈希还原", render_plan.compute_rules_bundle_hash("shared_meal_personalized") == before)
    schema = os.path.join(BASE, "schemas", "household", "household-base-plan.schema.json")
    raw = open(schema, "rb").read()
    try:
        open(schema, "ab").write(b" ")
        check("T08d 家庭哈希随 Schema 变化",
              render_plan.compute_rules_bundle_hash("shared_meal_personalized") != before)
    finally:
        open(schema, "wb").write(raw)


def t09_gate_numbering_and_pending_wording():
    """P1-3/P1-5：G01–G11 / H01–H06 编号与 pending 口径。"""
    # round43：G03 拆分为 G03a/G03b（机器可读分级）
    for i in range(1, 12):
        if i == 3:
            check("T09 G03a 编号", "G03a. [" in SK)
            check("T09 G03b 编号", "G03b. [" in SK)
            continue
        check("T09 G%02d 编号" % i, ("G%02d. [" % i) in SK)
    for i in range(1, 7):
        check("T09 H%02d 编号" % i, ("H%02d. [" % i) in SK)
    check("T09 pending 口径收窄",
          "仅禁止本次 effective 截止时间前且影响当前输出的 pending 遗留" in SK)
    check("T09 未来事项不判失败", "未来待确认事项保留在 override 源文件" in SK)


def t10_merger_atomic_and_prewrite_validation():
    """§四.1：合并器先校验再原子落盘；坏产物不落盘。"""
    import household_override_merger as mrg
    with tempfile.TemporaryDirectory() as d:
        base = json.load(open(os.path.join(SAMPLES, "golden-base-plan-sample.json"), encoding="utf-8"))
        base["members"] = base["members"][:1]  # 破坏契约（members 仅剩 1 且缺 primary 配对）
        ovs = {"generated_at": "t", "overrides": []}
        bp, op, ep = (os.path.join(d, n) for n in ("b.json", "o.json", "e.json"))
        json.dump(base, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(ovs, open(op, "w", encoding="utf-8"), ensure_ascii=False)
        failed = False
        try:
            mrg.merge(bp, op, ep)
        except Exception:
            failed = True
        check("T10a 契约破坏时合并失败", failed)
        check("T10b 不落盘半成品", not os.path.exists(ep) and not os.path.exists(ep + ".tmp"))


if __name__ == "__main__":
    for fn in (t01_split_safety_in_household_set, t02_foreign_field_injection,
               t03_base_to_single_participant_meal, t04_wrong_schema_mode,
               t05_future_pending_override, t06_external_meal_no_leftover,
               t07_four_members_layout_policy, t08_household_hash_change,
               t09_gate_numbering_and_pending_wording, t10_merger_atomic_and_prewrite_validation):
        fn()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)
