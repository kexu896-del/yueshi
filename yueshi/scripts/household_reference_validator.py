#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月食家庭版 · 跨引用校验器（v0.3 RC2 / RC2-3）。

职责（jsonschema 之外的脚本校验）：集合、比例、引用、状态分支、剩余归属、check 完整性。
校验对象：
  --base household base_plan.json        → 结构校验（bundle）+ 跨引用校验，回写 household_validation
  --overrides overrides_YYYYMMDD.json    → 独立校验 + 与 base 的引用一致性
用法：
  python scripts/household_reference_validator.py --base base.json [--overrides ov.json] [--write]
退出码：0 全部通过；3 校验失败（打印 check_id 明细）。
"""
import argparse, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
BUNDLE_PATH = os.path.join(BASE, "..", "schemas", "household", "household-schemas.bundle.json")

# 脚本负责的 check_id（大写，回写 household_validation；小写 13 项由生成器自检）
SCRIPT_CHECK_IDS = [
    "PRIMARY_COUNT_EQUALS_ONE", "MEMBER_ID_UNIQUE",
    "MEAL_PARTICIPANT_REFERENCE_VALID", "PORTION_MEMBER_REFERENCE_VALID",
    "OVERRIDE_MEMBER_REFERENCE_VALID", "LEFTOVER_MEMBER_REFERENCE_VALID",
    "CONDIMENT_MEMBER_REFERENCE_VALID", "PORTION_SET_EQUALS_PARTICIPANTS",
    "RATIO_SET_EQUALS_PARTICIPANTS", "RATIO_RANGE_COVERS_WHOLE",
    "SELECTED_PCT_SUM_EQUALS_100", "NOT_PARTICIPATING_EXCLUDED_FROM_PORTIONS",
    "CHECK_ID_COMPLETENESS",
]
# 生成器自检（小写，base_plan.household_validation 必须已含且恰好一次）
GENERATOR_CHECK_IDS = [
    "total_equals_portions_plus_loss", "member_nutrition_uses_member_portions",
    "purchase_matches_household_usage", "one_ingredient_per_shopping_row",
    "ratio_split_confidence_ok", "breakfast_portions_present",
    "portion_method_required", "reuse_dates_match_meals",
    "seasoning_strategy_resolved", "no_internal_terms_in_visible_text",
    "override_merge_consistent", "leftover_destination_resolved",
    "nutrition_transfer_consistent",
]


def _schema_validate(doc, which):
    import copy as _copy
    import jsonschema
    bundle = json.load(open(BUNDLE_PATH, encoding="utf-8"))
    if which == "effective_plan":
        # bundle 内 effective_plan = allOf[$ref #/base_plan] + 要求 effective_meta；
        # 抽出单用时 Draft-07 下 base 根级 additionalProperties:false 会误杀 effective_meta，
        # 故直接以 base_plan 为本体、合并 effective_meta 属性与必填（语义等价且更严格）。
        schema = _copy.deepcopy(bundle["base_plan"])
        ep = bundle["effective_plan"]
        schema.setdefault("properties", {}).update(ep.get("properties", {}))
        req = list(schema.get("required", []))
        for r in ep.get("required", []):
            if r not in req:
                req.append(r)
        schema["required"] = req
        # 契约修正（golden-cases 期望：缺席后参与者可只剩 1 人）：
        # base_plan 冻结时 participant_member_ids minItems=2（共享餐至少两人），
        # effective_plan 经缺席 patch 后合法降至 1 人，仅本路径放宽。
        schema["definitions"]["shared_meal"]["properties"][
            "participant_member_ids"]["minItems"] = 1
    else:
        schema = _copy.deepcopy(bundle[which])
    jsonschema.validate(doc, schema)


class Report:
    def __init__(self):
        self.results = []  # (check_id, status, detail)

    def add(self, cid, ok, detail=""):
        self.results.append({"check_id": cid, "status": "pass" if ok else "fail", "detail": detail})

    @property
    def failed(self):
        return [r for r in self.results if r["status"] == "fail"]


def validate_base(plan, overrides=None):
    """跨引用校验；overrides 提供时一并校验其与 base 的一致性。"""
    rep = Report()
    members = plan.get("members", [])
    mids = [m.get("member_id") for m in members]
    meals = plan.get("shared_meals", [])
    meal_ids = {m.get("meal_id") for m in meals}

    # PRIMARY_COUNT_EQUALS_ONE / MEMBER_ID_UNIQUE
    rep.add("PRIMARY_COUNT_EQUALS_ONE",
            sum(1 for m in members if m.get("is_primary")) == 1)
    rep.add("MEMBER_ID_UNIQUE", len(set(mids)) == len(mids) and all(mids))

    participant_ok = portion_ref_ok = ratio_set_ok = ratio_range_ok = pct_sum_ok = True
    notpart_ok = condiment_ok = True
    for meal in meals:
        parts = set(meal.get("participant_member_ids", []))
        if not parts <= set(mids):
            participant_ok = False
        portion_ids = {p.get("member_id") for p in meal.get("member_portions", [])}
        if portion_ids != parts or not portion_ids <= set(mids):
            portion_ref_ok = False
        # PORTION_SET_EQUALS_PARTICIPANTS 与上一行同判
        ratios = meal.get("portion_ratios", [])
        if ratios:
            rids = {r.get("member_id") for r in ratios}
            if rids != parts:
                ratio_set_ok = False
            smin = sum(r.get("pct_min", 0) for r in ratios)
            smax = sum(r.get("pct_max", 0) for r in ratios)
            if not (smin <= 100 <= smax):
                ratio_range_ok = False
            sels = [r["selected_pct"] for r in ratios if "selected_pct" in r]
            if sels and abs(sum(sels) - 100.0) > 1e-6:
                pct_sum_ok = False
        # not_participating 不得进入 participants / member_portions
        ap = meal.get("attendance_plan", {})
        notpart = {k for k, v in ap.items() if v == "not_participating"}
        if notpart & (parts | portion_ids):
            notpart_ok = False
        # L3 gate 一致性（P1-8）：L3 必须有 override 且 gate 满足分锅条件
        ss = meal.get("seasoning_strategy")
        if ss and ss.get("level") == "L3_separate":
            gate = meal.get("cooking_gate_override") or plan.get("household_default_cooking_gate", {})
            if not (gate.get("same_pot_allowed") is False or gate.get("separate_cookware_required") is True):
                rep.add("seasoning_strategy_resolved", False,
                        f"{meal.get('meal_id')} L3 但 gate 未满足 same_pot_allowed=false 或 separate_cookware_required=true")
        for c in (ss or {}).get("member_addition_nutrition", []) or []:
            if c.get("member_id") not in mids:
                condiment_ok = False
    rep.add("MEAL_PARTICIPANT_REFERENCE_VALID", participant_ok)
    rep.add("PORTION_MEMBER_REFERENCE_VALID", portion_ref_ok)
    rep.add("PORTION_SET_EQUALS_PARTICIPANTS", portion_ref_ok)
    rep.add("RATIO_SET_EQUALS_PARTICIPANTS", ratio_set_ok)
    rep.add("RATIO_RANGE_COVERS_WHOLE", ratio_range_ok)
    rep.add("SELECTED_PCT_SUM_EQUALS_100", pct_sum_ok)
    rep.add("NOT_PARTICIPATING_EXCLUDED_FROM_PORTIONS", notpart_ok)
    rep.add("CONDIMENT_MEMBER_REFERENCE_VALID", condiment_ok)

    # LEFTOVER_MEMBER_REFERENCE_VALID
    leftover_ok = True
    for lp in plan.get("leftover_plans", []):
        for k in ("source_member_id", "assigned_member_id"):
            if lp.get(k) and lp[k] not in mids:
                leftover_ok = False
        if lp.get("source_meal_id") not in meal_ids:
            leftover_ok = False
    rep.add("LEFTOVER_MEMBER_REFERENCE_VALID", leftover_ok)

    # reuse_chain 日期与餐次绑定
    for rc_ in plan.get("reuse_chains", []):
        if rc_.get("source_meal_id") not in meal_ids or rc_.get("reuse_meal_id") not in meal_ids:
            rep.add("reuse_dates_match_meals", False, rc_.get("chain_id", ""))

    # OVERRIDE_MEMBER_REFERENCE_VALID
    override_ok = True
    if overrides:
        if overrides.get("base_build_id") != plan.get("plan_meta", {}).get("build_id"):
            override_ok = False
            rep.add("override_merge_consistent", False, "base_build_id 与 base_plan 不一致")
        for ov in overrides.get("overrides", []):
            if ov.get("member_id") not in mids or ov.get("meal_id") not in meal_ids:
                override_ok = False
    rep.add("OVERRIDE_MEMBER_REFERENCE_VALID", override_ok)

    # CHECK_ID_COMPLETENESS：回写完成后每个必需 check_id 恰好一次。
    # 口径：生成器 13 项必须已存在于 household_validation 各一次；脚本 13 项不得
    # 与既有结果重复，由本校验器各补一次（含本项）。
    existing = [c.get("check_id") for c in plan.get("household_validation", {}).get("checks", [])]
    script_ids = [r["check_id"] for r in rep.results]
    complete = True
    for cid in GENERATOR_CHECK_IDS:
        if existing.count(cid) != 1:
            complete = False
    for cid in SCRIPT_CHECK_IDS:
        if cid == "CHECK_ID_COMPLETENESS":
            continue  # 本项由本条输出，计一次
        if existing.count(cid) != 0 or script_ids.count(cid) != 1:
            complete = False
    rep.add("CHECK_ID_COMPLETENESS", complete)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--overrides")
    ap.add_argument("--schema", choices=["base_plan", "overrides", "effective_plan"], default="base_plan",
                    help="输入文件契约：冻结 base_plan（默认）或合并后的 effective_plan")
    ap.add_argument("--write", action="store_true", help="把脚本校验结果回写 base 的 household_validation")
    args = ap.parse_args()
    plan = json.load(open(args.base, encoding="utf-8"))
    ov = json.load(open(args.overrides, encoding="utf-8")) if args.overrides else None
    try:
        _schema_validate(plan, args.schema)
        if ov:
            _schema_validate(ov, "overrides")
    except Exception as e:  # jsonschema.ValidationError
        print(f"Schema 校验失败: {e.message if hasattr(e, 'message') else e}", file=sys.stderr)
        sys.exit(3)
    if args.schema == "overrides":
        print("[pass] OVERRIDES_SCHEMA_VALID")
        sys.exit(0)
    rep = validate_base(plan, ov)
    for r in rep.results:
        print(f"[{r['status']}] {r['check_id']}" + (f" — {r['detail']}" if r["detail"] else ""))
    if args.write and not rep.failed:
        checks = plan.setdefault("household_validation", {}).setdefault("checks", [])
        checks.extend(rep.results)
        json.dump(plan, open(args.base, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"已回写 {len(rep.results)} 项脚本校验结果")
    sys.exit(3 if rep.failed else 0)


if __name__ == "__main__":
    main()
