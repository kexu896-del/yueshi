#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜谱指纹多样性校验（对应 workflows/planning-flow.md 的多样性硬规则）

输入：菜单 CSV，每行一餐：
  date,meal,dish,protein,vegetable,method,flavor,structure
  例： 2026-08-27,晚餐,咖喱鸡腿南瓜锅,鸡腿,南瓜,焖,咖喱,一锅炖煮
（dish 可空；protein/vegetable 为主蛋白/主蔬菜，可多个用、分隔）

可选列 recipe_id + 参数 --fingerprints data/recipe-fingerprints.json：
  命中时该行 diversity 维度改由菜谱「多样性指纹」提供
  （dish_category|primary_ingredient_family|primary_cooking_method|structure|flavor_family），
  即 protein 维取主食材族、method 取主烹法、flavor 取主味型族、structure 取餐型。
  菜单级多样性校验使用多样性指纹，不使用精确指纹（exact_fingerprint 仅用于数据去重）。

校验规则（round60 起与 planning-flow.md D01–D07 对应）：
  1. 相邻两顿指纹相似度 ≤70%（6 维中相同维 ≤4）［对应 D03］
  2. 相似度 >85% 的组合一周只出现一次［对应 D03］
  3. 同一主蛋白最多出现 2 次，重复时烹法或味型必须不同［D01，round61 定稿］
  4. 同一蔬菜复用时，不能总配同种蛋白
  5. 连续两顿不都是汤羹；连续两顿不都是清淡蒸煮
  6. 高油重口（麻辣/红烧/油炸/炸）每周 ≤2 次
  7. 一周烹法覆盖 ≥3 种［对应 D02，从严］
  8. D04：相邻自炊餐不得同时为「快炒＋咸鲜」组合
  （D05 来源不包揽、D06 近 4 周重复降权、D07 点名保留豁免在检索/装配侧执行）
"""
import csv, sys
from itertools import combinations

DIMS = ["protein", "vegetable", "method", "flavor", "structure", "texture"]
HEAVY = {"麻辣", "红烧", "酱香重", "油炸"}
BLAND_METHODS = {"蒸", "煮", "白灼"}


def load(path):
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        row = {d: (r.get(d) or "").strip() for d in
               ["date", "meal", "dish"] + DIMS}
        row["recipe_id"] = (r.get("recipe_id") or "").strip()
        rows.append(row)
    return rows


def apply_fingerprints(rows, fp_path):
    """命中 recipe_id 的行，diversity 维度改用多样性指纹（不用精确指纹）。"""
    import json, os
    if not fp_path or not os.path.exists(fp_path):
        return 0
    data = json.load(open(fp_path, encoding="utf-8"))
    fps = data.get("fingerprints", data if isinstance(data, list) else [])
    by_id = {}
    for rec in fps:
        rid = rec.get("id") or rec.get("recipe_id")
        dv = rec.get("diversity_fingerprint")
        if rid and isinstance(dv, str):
            # 格式：dish_category|primary_ingredient_family|primary_cooking_method|meal_structure|dominant_flavor_family
            p = dv.split("|")
            if len(p) == 5:
                by_id[rid] = {"family": p[1], "method": p[2],
                              "structure": p[3], "flavor": p[4]}
    hit = 0
    for r in rows:
        dv = by_id.get(r.get("recipe_id"))
        if not dv:
            continue
        hit += 1
        if dv["family"]:
            r["protein"] = dv["family"]
        if dv["method"]:
            r["method"] = dv["method"]
        if dv["flavor"]:
            r["flavor"] = dv["flavor"]
        if dv["structure"]:
            r["structure"] = dv["structure"]
    return hit


def sim(a, b):
    same = sum(1 for d in DIMS if a[d] and a[d] == b[d])
    return same / len(DIMS)


def main(path, fp_path=None):
    rows = load(path)
    fp_hit = apply_fingerprints(rows, fp_path)
    if fp_path:
        print(f"多样性指纹接入：{fp_hit}/{len(rows)} 行命中 recipe-fingerprints.json")
    if len(rows) < 2:
        print("餐次不足，无需校验")
        return
    problems, notes = [], []

    # 规则 1、5：相邻两顿（按输入顺序）
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        s = sim(a, b)
        if s > 0.70:
            problems.append(f"相邻两顿相似度 {s:.0%} >70%：{a['dish'] or a['protein']} → {b['dish'] or b['protein']}")
        if a["structure"] == b["structure"] == "汤羹":
            problems.append(f"连续两顿都是汤羹：{a['dish']} → {b['dish']}")
        if a["method"] in BLAND_METHODS and b["method"] in BLAND_METHODS \
           and a["flavor"] == b["flavor"] == "清淡":
            notes.append(f"连续两顿清淡蒸煮：{a['dish']} → {b['dish']}，建议其中一顿换味型")
        # D04（round60）：相邻自炊餐不得同时为"快炒＋咸鲜"组合
        if a["method"] in {"炒", "快炒"} and b["method"] in {"炒", "快炒"} \
           and a["flavor"] == b["flavor"] == "咸鲜":
            problems.append(f"D04 相邻两顿都是「快炒+咸鲜」：{a['dish'] or a['protein']} → {b['dish'] or b['protein']}")

    # 规则 2：>85% 组合一周一次
    high = []
    for i, j in combinations(range(len(rows)), 2):
        if sim(rows[i], rows[j]) > 0.85:
            high.append((rows[i]["dish"], rows[j]["dish"]))
    if high:
        problems.append(f"存在 >85% 高度相似组合：{high}")

    # 规则 3（D01，round61 定稿）：同一主蛋白最多 2 次，且重复时烹法或味型必须不同
    by_protein = {}
    for r in rows:
        for p in filter(None, r["protein"].split("、")):
            by_protein.setdefault(p, []).append(r)
    for p, rs in by_protein.items():
        if len(rs) > 2:
            problems.append(f"D01 主蛋白「{p}」出现 {len(rs)} 次 >2 次上限"
                            f"（库存/包装/预算/点名/备餐豁免须记录 reason_code）")
        if 2 <= len(rs):
            sigs = {(r["method"], r["flavor"]) for r in rs}
            if len(sigs) < len(rs):
                problems.append(f"D01 主蛋白「{p}」出现 {len(rs)} 次但烹法/味型有重复：{[r['dish'] for r in rs]}")

    # 规则 4：同一蔬菜复用不能总配同种蛋白
    by_veg = {}
    for r in rows:
        for v in filter(None, r["vegetable"].split("、")):
            by_veg.setdefault(v, []).append(r)
    for v, rs in by_veg.items():
        if len(rs) >= 2:
            prots = {r["protein"] for r in rs}
            if len(prots) == 1:
                notes.append(f"蔬菜「{v}」复用 {len(rs)} 次都配同一蛋白，建议换一种蛋白搭配")

    # 规则 6：高油重口
    heavy_n = sum(1 for r in rows if r["flavor"] in HEAVY or r["method"] in {"炸", "油炸"})
    if heavy_n > 2:
        problems.append(f"高油重口 {heavy_n} 次 >2 次/周")

    # 规则 7：烹法覆盖
    methods = {r["method"] for r in rows if r["method"]}
    if len(methods) < 3:
        problems.append(f"烹法覆盖仅 {len(methods)} 种（{methods}），需 ≥3 种")

    print(f"校验 {len(rows)} 餐 · 烹法 {len(methods)} 种 · 高油重口 {heavy_n} 次")
    if problems:
        print("\n✗ 需修正：")
        for p in problems: print(" ", p)
    else:
        print("\n✓ 多样性硬规则全部通过")
    if notes:
        print("\n· 建议（不强制）：")
        for n in notes: print(" ", n)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fp = None
    for i, a in enumerate(sys.argv):
        if a == "--fingerprints" and i + 1 < len(sys.argv):
            fp = sys.argv[i + 1]
    if not args:
        print(__doc__)
    else:
        main(args[0], fp)
