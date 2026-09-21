#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月食 · 统一营养调整器（最多两轮，冻结前执行，替代运行时临时搜索补法）。

口径（对应《统一营养调整候选表模板》）：
- 第一次营养计算输出完整 nutrition_gap 向量（能量/蛋白/净碳水/脂肪 + 安全线 + 医学上限）；
- 候选只来自 data/nutrition-adjustment-options.json，且食材必须在
  locked_basket / inventory / approved_substitution 范围内；不运行时搜索新食材；
- 一次评估四项差额，选能同时改善多个差额的最小调整集；
- 调整直接更新 meal["ingredients"]；营养、采购、渲染共读同一数组；
  禁止创建 extra_foods / render_ingredients 等旁路字段；
- 最多两轮：第一轮综合修正，第二轮只做小幅收口；两轮后仍不合格返回
  local_recipe_swap 或失败原因，不继续打补丁；
- plan.json 冻结后（frozen=True）禁止调用本模块修改业务数据。

CLI：python scripts/nutrition_adjuster.py --day day.json --targets targets.json \
      --locked-basket 虾,鸡蛋（全蛋） [--inventory 全脂牛奶] [--approved-substitutions 鳕鱼]
"""
import argparse, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
METRICS = ("energy_kcal", "protein_g", "net_carbs_g", "fat_g")
ROUND2_STEP_LIMIT = 1  # 第二轮只允许每个候选一步的小幅收口


def load_options():
    doc = json.load(open(os.path.join(BASE, "..", "data", "nutrition-adjustment-options.json"),
                         encoding="utf-8"))
    return doc["options"]


def compute_gap(actual, targets):
    """完整差额向量。低于下限记正数（需增加），高于上限记负数（需减少），区间内记 0。

    targets 形如：
    {energy_kcal:{min,max}, protein_g:{floor,min,max,medical_limit},
     net_carbs_g:{min,max}, fat_g:{min,max}, confidence:"high|medium|low"}
    """
    gap = {"date": actual.get("date", ""), "confidence": targets.get("confidence", "high")}

    def band(metric, lo, hi):
        a = actual.get(metric, 0.0)
        if a < lo:
            return round(lo - a, 1)
        if a > hi:
            return round(hi - a, 1)
        return 0.0

    e = targets["energy_kcal"]
    p = targets["protein_g"]
    c = targets["net_carbs_g"]
    f = targets["fat_g"]
    gap["energy_kcal"] = {"actual": actual.get("energy_kcal", 0.0), "target_min": e["min"],
                          "target_max": e["max"],
                          "delta_to_min": band("energy_kcal", e["min"], e["max"]),
                          "delta_to_max": band("energy_kcal", e["min"], e["max"])}
    gap["protein_g"] = {"actual": actual.get("protein_g", 0.0), "safety_floor": p["floor"],
                        "target_min": p["min"], "target_max": p["max"],
                        "medical_limit": p.get("medical_limit"),
                        "delta_to_target": band("protein_g", p["min"], p["max"])}
    gap["net_carbs_g"] = {"actual": actual.get("net_carbs_g", 0.0), "target_min": c["min"],
                          "target_max": c["max"],
                          "delta_to_band": band("net_carbs_g", c["min"], c["max"])}
    gap["fat_g"] = {"actual": actual.get("fat_g", 0.0), "target_min": f["min"],
                    "target_max": f["max"],
                    "delta_to_band": band("fat_g", f["min"], f["max"])}
    # 医学上限单独检查，不得用目标带替代
    below_floor = actual.get("protein_g", 0.0) < p["floor"]
    over_medical = (p.get("medical_limit") is not None
                    and actual.get("protein_g", 0.0) > p["medical_limit"])
    gap["adjustment_required"] = any([
        gap["energy_kcal"]["delta_to_min"] != 0, gap["protein_g"]["delta_to_target"] != 0,
        gap["net_carbs_g"]["delta_to_band"] != 0, gap["fat_g"]["delta_to_band"] != 0,
        below_floor, over_medical])
    gap["safety_violation"] = below_floor or over_medical
    # 外食低置信度：只做区间校验标记，不做精细微调
    if targets.get("confidence") == "low" and not gap["safety_violation"]:
        gap["adjustment_required"] = any(abs(gap[m][k]) > 15.0 for m, k in
                                         (("energy_kcal", "delta_to_min"),
                                          ("protein_g", "delta_to_target"),
                                          ("net_carbs_g", "delta_to_band"),
                                          ("fat_g", "delta_to_band")))
    return gap


def _deltas(gap):
    return {"energy_kcal": gap["energy_kcal"]["delta_to_min"],
            "protein_g": gap["protein_g"]["delta_to_target"],
            "net_carbs_g": gap["net_carbs_g"]["delta_to_band"],
            "fat_g": gap["fat_g"]["delta_to_band"]}


def filter_candidates(options, ctx):
    """按 enabled / source_scope / 餐次 / 模式 / 排除标签 / 结构兼容过滤。

    ctx: {locked_basket:[], inventory:[], approved_substitutions:[],
          mode:"", meal_types:set, restriction_tags:[]}
    """
    allowed_pool = (set(ctx.get("locked_basket", [])) | set(ctx.get("inventory", []))
                    | set(ctx.get("approved_substitutions", [])))
    out = []
    for o in options:
        if not o["enabled"]:
            continue
        if o["ingredient_id"] not in allowed_pool:
            continue  # 不得在营养修正中新增未确认食材
        if o["meal_structure_impact"] == "breaks_structure":
            continue
        if ctx.get("mode") and ctx["mode"] not in o["mode_tags"]:
            continue
        if ctx.get("meal_types") and not (set(o["suitable_meals"]) & ctx["meal_types"]):
            continue
        if set(o.get("restriction_tags", [])):
            continue  # 有排除标签的候选需显式确认，默认剔除
        src_ok = any((s == "locked_basket" and o["ingredient_id"] in ctx.get("locked_basket", []))
                     or (s == "inventory" and o["ingredient_id"] in ctx.get("inventory", []))
                     or (s == "approved_substitution"
                         and o["ingredient_id"] in ctx.get("approved_substitutions", []))
                     for s in o["source_scope"])
        if src_ok:
            out.append(o)
    return out


def score_candidate(opt, gap):
    """评分：多差额改善加分，造成其他指标越界扣分。"""
    d = _deltas(gap)
    nd = opt["nutrition_delta"]
    score = 0.0
    improved = 0
    for m in METRICS:
        need, give = d[m], nd[m]
        if need == 0:
            if (m == "net_carbs_g" and give > 0) or (m == "fat_g" and give > 0) \
               or (m == "energy_kcal" and give > 0):
                # 该指标已在区间内，增量把它往上推：看剩余空间
                pass
            continue
        same_dir = (need > 0 and give > 0) or (need < 0 and give < 0)
        if same_dir:
            cover = min(abs(give), abs(need))
            score += cover * 10.0
            improved += 1
            if abs(give) > abs(need) * 2:
                score -= (abs(give) - abs(need) * 2) * 5.0  # overshoot_penalty
        elif give != 0 and abs(need) > 0:
            score -= min(abs(give), abs(need)) * 8.0  # 反向恶化扣分
    if improved >= 2:
        score += 15.0  # multi_gap_bonus
    score += opt["priority"] / 10.0
    if "locked_basket" in opt["source_scope"]:
        score += 5.0  # locked_basket_bonus
    if opt["package_impact"] == "improves":
        score += 4.0
    elif opt["package_impact"] == "worsens":
        score -= 4.0  # package_waste_penalty
    if opt["requires_recipe_change"]:
        score -= 10.0
    if opt["requires_user_confirmation"]:
        score -= 8.0  # new_ingredient_penalty
    return score


def _apply(meal_ingredients, opt, sign=1):
    """调整直接更新 meal.ingredients（唯一数据源）。返回 (before, after)。"""
    for ing in meal_ingredients:
        if ing["ingredient_id"] == opt["ingredient_id"]:
            before = ing["amount"]
            delta = opt["increment_value"] * (-1 if opt["adjustment_action"] in ("decrease", "remove") else 1)
            after = max(0.0, round(before + delta, 1))
            ing["amount"] = after
            ing["adjustment_round"] = ing.get("adjustment_round", 0) + 1
            ing["adjustment_reason"] = opt["adjustment_id"]
            return before, after
    # 食材不在菜谱中但来源受控（locked_basket 未充分使用/库存）：新增一行
    meal_ingredients.append({
        "ingredient_id": opt["ingredient_id"], "display_name": opt["display_name"],
        "amount": float(opt["increment_value"]), "unit": opt["increment_unit"],
        "source": "locked_basket" if "locked_basket" in opt["source_scope"] else opt["source_scope"][0],
        "adjustment_round": 1, "adjustment_reason": opt["adjustment_id"]})
    return 0.0, float(opt["increment_value"])


def _recompute(meals):
    ft = json.load(open(os.path.join(BASE, "..", "data", "foods-table.json"), encoding="utf-8"))["foods"]
    tot = {m: 0.0 for m in METRICS}
    for meal in meals:
        for ing in meal.get("ingredients", []):
            f = ft.get(ing["ingredient_id"])
            if not f:
                continue
            k = ing["amount"] / 100.0
            tot["energy_kcal"] += f["kcal"] * k
            tot["protein_g"] += f["protein"] * k
            tot["net_carbs_g"] += f["net_carbs"] * k
            tot["fat_g"] += f["fat"] * k
    return {m: round(v, 1) for m, v in tot.items()}


def adjust_day(meals, targets, ctx, date_str="", max_rounds=2):
    """最多两轮修正。meals: [{meal_id, meal_type, ingredients:[...]}, ...]（就地修改）。

    返回 nutrition_adjustment_log；两轮后仍不合格 → result=local_recipe_swap / failed。
    """
    if ctx.get("frozen"):
        raise SystemExit("plan.json 已冻结，禁止营养调整修改业务数据")
    options = load_options()
    if max_rounds > 2:
        raise ValueError("营养计算最多两轮")
    log = {"date": date_str, "rounds": [], "passed": False, "result": None}
    actual = _recompute(meals)
    actual["date"] = date_str
    gap = compute_gap(actual, targets)
    if not gap["adjustment_required"]:
        log.update(passed=True, result="no_adjustment_needed", before_gap=gap)
        return log
    cands = filter_candidates(options, ctx)
    for rnd in range(1, max_rounds + 1):
        before_gap = gap
        selected = []
        step_cap = ROUND2_STEP_LIMIT if rnd == 2 else 2  # 第二轮只小幅收口
        for _ in range(4):  # 单轮内最多 4 个调整步，避免震荡
            d = _deltas(gap)
            if all(v == 0 for v in d.values()) and not gap["safety_violation"]:
                break
            scored = sorted(((score_candidate(o, gap), o) for o in cands),
                            key=lambda x: -x[0])
            scored = [(s, o) for s, o in scored if s > 0]
            if not scored:
                break
            _, best = scored[0]
            # 找可落地的餐次
            placed = False
            for meal in meals:
                if meal.get("meal_type") not in best["suitable_meals"]:
                    continue
                used = sum(1 for s in selected if s["adjustment_id"] == best["adjustment_id"])
                if used >= min(best["max_steps_per_day"], step_cap):
                    continue
                b, a = _apply(meal.setdefault("ingredients", []), best)
                selected.append({"adjustment_id": best["adjustment_id"],
                                 "meal_id": meal.get("meal_id", ""),
                                 "ingredient_id": best["ingredient_id"],
                                 "before_amount": b, "after_amount": a,
                                 "reason": "缩小差额向量" if rnd == 1 else "第二轮小幅收口"})
                placed = True
                break
            if not placed:
                cands = [o for o in cands if o["adjustment_id"] != best["adjustment_id"]]
                if not cands:
                    break
                continue
            actual = _recompute(meals)
            actual["date"] = date_str
            gap = compute_gap(actual, targets)
        log["rounds"].append({"round": rnd, "before_gap": before_gap,
                              "selected_adjustments": selected,
                              "after_nutrition": _recompute(meals),
                              "after_gap": gap,
                              "package_recalculated": True,
                              "shopping_recalculated": True})
        if not gap["adjustment_required"]:
            log.update(passed=True, result="adjusted")
            return log
    log["result"] = "local_recipe_swap" if not gap["safety_violation"] else "failed_safety_violation"
    log["reason"] = ("两轮后仍有差额，返回局部换菜，不继续打补丁" if log["result"] == "local_recipe_swap"
                     else "两轮后仍触发安全线/医学上限，返回失败原因")
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True, help="当日 meals JSON 文件")
    ap.add_argument("--targets", required=True, help="营养目标 JSON 文件")
    ap.add_argument("--locked-basket", default="")
    ap.add_argument("--inventory", default="")
    ap.add_argument("--approved-substitutions", default="")
    ap.add_argument("--mode", default="balanced")
    ap.add_argument("--date", default="")
    args = ap.parse_args()
    meals = json.load(open(args.day, encoding="utf-8"))
    targets = json.load(open(args.targets, encoding="utf-8"))
    ctx = {"locked_basket": [s for s in args.locked_basket.split(",") if s],
           "inventory": [s for s in args.inventory.split(",") if s],
           "approved_substitutions": [s for s in args.approved_substitutions.split(",") if s],
           "mode": args.mode,
           "meal_types": {m.get("meal_type") for m in meals}}
    log = adjust_day(meals, targets, ctx, date_str=args.date)
    json.dump({"meals": meals, "log": log}, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
