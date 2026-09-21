#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""household_portion_solver.py · 双人/多人份量一次联合求解（round45）。

替代"模型逐项试克数 → 反复跑 Python"的试错式迭代：
把可调整食材交给脚本，一次联合求解全部成员的热量/净碳水/蛋白质/脂肪约束，
返回满足条件的克数组合（L1 最小改动：尽量靠近原菜单、尽量少改食材）。

模型只决定：哪些食材允许调整（adjustable）、哪些必须保留（locked/adjustable=false）。

输入 JSON：
{
  "members": [{"member_id": "primary",
               "targets": {"energy_min": 1240, "energy_max": 1360,
                           "carbs_max": 135, "protein_min": 70,
                           "fat_min": 40, "fat_max": 60}}],
  "ingredients": [{"ingredient_id": "rice_cooked", "name": "白米饭",
                   "per_100g": {"energy": 116, "carbs": 25.9, "protein": 2.6, "fat": 0.3},
                   "grams": {"primary": 165, "secondary": 240},
                   "adjustable": true, "min_g": 0, "max_g": 400}]
}
未给出的约束字段不参与求解；locked/未出现成员的营养按固定克数计入常量。
输出：status=optimal 时写调整后的 grams 与每人营养合计；infeasible 时退出码 3。

用法：python household_portion_solver.py input.json [-o out.json]
"""
import json, sys

NUTRI_KEYS = ("energy", "carbs", "protein", "fat")


def solve(doc):
    from scipy.optimize import linprog
    import numpy as np

    members = [m["member_id"] for m in doc["members"]]
    targets = {m["member_id"]: m.get("targets", {}) for m in doc["members"]}

    # 变量：每个 adjustable 食材 × 每个持有该食材的成员 的克数
    var_index = {}
    base_g = []
    for ing in doc["ingredients"]:
        if not ing.get("adjustable"):
            continue
        for mid in members:
            if mid in ing.get("grams", {}):
                var_index[(ing["ingredient_id"], mid)] = len(base_g)
                base_g.append(float(ing["grams"][mid]))
    n = len(base_g)
    if n == 0:
        return {"status": "no_adjustable", "adjustments": []}
    base_g = np.array(base_g)

    # 成员营养常量（locked 食材 + adjustable 之外）
    const = {mid: {k: 0.0 for k in NUTRI_KEYS} for mid in members}
    coef = {}
    for ing in doc["ingredients"]:
        p = {k: float(ing.get("per_100g", {}).get(k, 0.0)) / 100.0 for k in NUTRI_KEYS}
        for mid, g in ing.get("grams", {}).items():
            if mid not in const:
                continue
            if ing.get("adjustable") and (ing["ingredient_id"], mid) in var_index:
                coef[(ing["ingredient_id"], mid)] = p
            else:
                for k in NUTRI_KEYS:
                    const[mid][k] += p[k] * float(g)

    A_ub, b_ub, A_eq, b_eq = [], [], [], []

    def row(key, mid, sign):
        r = [0.0] * (2 * n)  # [grams..., dev_pos/neg 合并为 |delta| 松弛]
        for (iid, m2), idx in var_index.items():
            if m2 == mid:
                r[idx] = sign * coef[(iid, m2)][key]
        return r

    for mid in members:
        t = targets.get(mid, {})
        if "energy_max" in t:
            A_ub.append(row("energy", mid, 1)); b_ub.append(t["energy_max"] - const[mid]["energy"])
        if "energy_min" in t:
            A_ub.append(row("energy", mid, -1)); b_ub.append(const[mid]["energy"] - t["energy_min"])
        if "carbs_max" in t:
            A_ub.append(row("carbs", mid, 1)); b_ub.append(t["carbs_max"] - const[mid]["carbs"])
        if "protein_min" in t:
            A_ub.append(row("protein", mid, -1)); b_ub.append(const[mid]["protein"] - t["protein_min"])
        if "fat_max" in t:
            A_ub.append(row("fat", mid, 1)); b_ub.append(t["fat_max"] - const[mid]["fat"])
        if "fat_min" in t:
            A_ub.append(row("fat", mid, -1)); b_ub.append(const[mid]["fat"] - t["fat_min"])

    # L1 目标：min Σ dev_i，dev_i ≥ |g_i - g0_i|（g - g0 ≤ dev，g0 - g ≤ dev）
    for i in range(n):
        r1 = [0.0] * (2 * n); r1[i] = 1; r1[n + i] = -1
        A_ub.append(r1); b_ub.append(base_g[i])
        r2 = [0.0] * (2 * n); r2[i] = -1; r2[n + i] = -1
        A_ub.append(r2); b_ub.append(-base_g[i])
    c = [0.0] * n + [1.0] * n

    bounds = []
    for (iid, mid), idx in sorted(var_index.items(), key=lambda kv: kv[1]):
        ing = next(i for i in doc["ingredients"] if i["ingredient_id"] == iid)
        bounds.append((float(ing.get("min_g", 0)), float(ing.get("max_g", 10 ** 6))))
    bounds += [(0, None)] * n

    res = linprog(c, A_ub=A_ub or None, b_ub=b_ub or None,
                  A_eq=A_eq or None, b_eq=b_eq or None,
                  bounds=bounds, method="highs")
    if res.status != 0:
        return {"status": "infeasible", "detail": res.message, "adjustments": []}

    g = res.x[:n]
    out_grams = {}
    adjustments = []
    for (iid, mid), idx in var_index.items():
        out_grams.setdefault(iid, {})[mid] = round(float(g[idx]), 1)
        delta = round(float(g[idx]) - float(base_g[idx]), 1)
        if abs(delta) >= 0.5:
            adjustments.append({"ingredient_id": iid, "member_id": mid,
                                "from_g": round(float(base_g[idx]), 1),
                                "to_g": round(float(g[idx]), 1), "delta_g": delta})

    # 复核每人营养合计
    totals = {mid: dict(const[mid]) for mid in members}
    for (iid, mid), idx in var_index.items():
        for k in NUTRI_KEYS:
            totals[mid][k] += coef[(iid, mid)][k] * float(g[idx])
    for mid in members:
        totals[mid] = {k: round(v, 1) for k, v in totals[mid].items()}
    return {"status": "optimal", "grams": out_grams, "adjustments": adjustments,
            "totals": totals, "objective_l1_g": round(float(res.fun), 1)}


def main():
    if len(sys.argv) < 2:
        print("usage: python household_portion_solver.py input.json [-o out.json]")
        sys.exit(2)
    args = sys.argv[1:]
    out = None
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    doc = json.load(open(args[0], encoding="utf-8"))
    result = solve(doc)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if out:
        open(out, "w", encoding="utf-8").write(text)
    print(text)
    sys.exit(0 if result["status"] == "optimal" else 3)


if __name__ == "__main__":
    main()
