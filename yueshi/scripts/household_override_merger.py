# -*- coding: utf-8 -*-
"""household_override_merger.py 草案 v0.1
patch 合并器：base_plan + overrides_YYYYMMDD.json -> effective_plan.json（派生物，非权威源）。
用法: python household_override_merger.py base_plan.json [overrides_*.json] -o effective_plan.json（无 overrides 即 identity merge）
职责:
  - absent: 移除该餐该成员份量；3人及以上缺席时重新归一 portion_ratios.selected_pct 并重算该餐 member_portions；
    按 known_at 应用 shopping_delta（采购前 reduce_purchase）或生成 leftover 引用。
  - external_meal: 该成员该餐份量置空，不产生 leftover、不发生 nutrition_transfer；before_shopping 允许 reduce_purchase。
  - present_confirmed: 仅把 attendance_plan 的 uncertain 置为 expected。
  - 只局部重算：受影响餐次 household_ingredients / member_portions / 当日成员营养由
    household_nutrition_validator 另行重算，本合并器只负责结构与分配层。
状态: 草案，供评审；营养重算与采购金额重算留接口（callback）。
"""
import json, copy, os, sys


def normalize_ratios(meal):
    """缺席后重归一 selected_pct：按剩余成员 pct_max 比例分摊到 100。"""
    ratios = [r for r in meal.get("portion_ratios", [])
              if r["member_id"] in meal.get("participant_member_ids", [])]
    if not ratios:
        return meal
    bases = [max(r.get("pct_max", 0), 0.01) for r in ratios]
    total = sum(bases)
    for r, b in zip(ratios, bases):
        r["selected_pct"] = round(100.0 * b / total, 2)
    fix = round(100.0 - sum(r["selected_pct"] for r in ratios), 2)
    if fix:
        ratios[0]["selected_pct"] = round(ratios[0]["selected_pct"] + fix, 2)
    meal["portion_ratios"] = ratios
    return meal


def apply_override(plan, ov, applied):
    for meal in plan.get("shared_meals", []):
        if meal["meal_id"] != ov["meal_id"]:
            continue
        member = ov["member_id"]
        attendance = meal.setdefault("attendance_plan", {})
        if ov["status"] == "absent":
            meal["member_portions"] = [b for b in meal.get("member_portions", []) if b["member_id"] != member]
            meal["participant_member_ids"] = [m for m in meal.get("participant_member_ids", []) if m != member]
            if meal.get("portion_method") == "ratio_split":
                meal = normalize_ratios(meal)
            attendance[member] = "not_participating"
        elif ov["status"] == "external_meal":
            meal["member_portions"] = [b for b in meal.get("member_portions", []) if b["member_id"] != member]
            meal["participant_member_ids"] = [m for m in meal.get("participant_member_ids", []) if m != member]
            if meal.get("portion_method") == "ratio_split":
                meal = normalize_ratios(meal)
            attendance[member] = "not_participating"
        elif ov["status"] == "present_confirmed":
            if attendance.get(member) == "uncertain":
                attendance[member] = "expected"
        applied.append(ov["override_id"])
        _apply_shopping_delta(plan, ov)
    return plan


def _apply_shopping_delta(plan, ov):
    for d in ov.get("shopping_delta", []):
        for item in plan.get("shopping", []):
            if item["ingredient_id"] == d["ingredient_id"] and d["destination"] == "reduce_purchase":
                cur = item.get("new_purchase_amount", {})
                cur_grams = cur.get("canonical_grams", 0)
                cur["canonical_grams"] = max(0, cur_grams - d.get("grams", 0))
                item["new_purchase_amount"] = cur
                item.setdefault("_delta_log", []).append(d)


def _validate_effective(effective):
    """落盘前契约校验（additionalProperties:false，契约外字段即失败）。
    校验器不可用时仅警告，不阻塞（保持合并器可独立运行）。"""
    try:
        from household_reference_validator import _schema_validate
    except ImportError:
        try:
            from scripts.household_reference_validator import _schema_validate
        except ImportError:
            print("warning: 校验器不可用，跳过 effective_plan 落盘前校验", file=sys.stderr)
            return
    _schema_validate(effective, "effective_plan")


def merge(base_path, override_path, out_path, validate=True):
    """override_path 为 None 时走 identity merge：无 patch 也产出 effective_plan，
    家庭渲染器永远只面对 effective_plan 一种输入。"""
    base = json.load(open(base_path, encoding="utf-8"))
    ov_file = json.load(open(override_path, encoding="utf-8")) if override_path else {"overrides": []}
    applied = []
    effective = copy.deepcopy(base)
    for ov in ov_file.get("overrides", []):
        # 只合并已确认 patch；pending（未来待确认）保留在 override 源文件，不进入 effective
        if ov.get("merge_status", "applied") != "applied":
            print("skip pending override: %s" % ov.get("override_id"), file=sys.stderr)
            continue
        effective = apply_override(effective, ov, applied)
    effective["effective_meta"] = {
        "base_build_id": base["plan_meta"]["build_id"],
        "applied_override_ids": applied,
        "merged_at": ov_file.get("generated_at") or __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    # 合并器不重算营养；重算由 household_nutrition_validator 对受影响餐次执行。
    if validate:
        _validate_effective(effective)  # 先校验，不合法则不落盘
    tmp = out_path + ".tmp"
    json.dump(effective, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)  # 原子写出，避免半成品
    print("merged: %s (applied %d overrides) -> %s" % (override_path or "<identity>", len(applied), out_path))
    return effective


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python household_override_merger.py base.json [overrides.json] -o effective.json")
        sys.exit(2)
    args = sys.argv[1:]
    out = "effective_plan.json"
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    base = args[0]
    overrides = args[1] if len(args) > 1 else None  # 缺省 = identity merge
    merge(base, overrides, out)
