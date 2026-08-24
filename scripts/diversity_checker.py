#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜谱指纹多样性校验（对应 workflows/planning-flow.md 的多样性硬规则）

输入：菜单 CSV，每行一餐：
  date,meal,dish,protein,vegetable,method,flavor,structure
  例： 2026-08-27,晚餐,咖喱鸡腿南瓜锅,鸡腿,南瓜,焖,咖喱,一锅炖煮
（dish 可空；protein/vegetable 为主蛋白/主蔬菜，可多个用、分隔）

校验规则：
  1. 相邻两顿指纹相似度 ≤70%（6 维中相同维 ≤4）
  2. 相似度 >85% 的组合一周只出现一次
  3. 同一主蛋白出现 2~3 次时，烹法或味型必须不同
  4. 同一蔬菜复用时，不能总配同种蛋白
  5. 连续两顿不都是汤羹；连续两顿不都是清淡蒸煮
  6. 高油重口（麻辣/红烧/油炸/炸）每周 ≤2 次
  7. 一周烹法覆盖 ≥3 种
"""
import csv, sys
from itertools import combinations

DIMS = ["protein", "vegetable", "method", "flavor", "structure", "texture"]
HEAVY = {"麻辣", "红烧", "酱香重", "油炸"}
BLAND_METHODS = {"蒸", "煮", "白灼"}


def load(path):
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        rows.append({d: (r.get(d) or "").strip() for d in
                     ["date", "meal", "dish"] + DIMS})
    return rows


def sim(a, b):
    same = sum(1 for d in DIMS if a[d] and a[d] == b[d])
    return same / len(DIMS)


def main(path):
    rows = load(path)
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

    # 规则 2：>85% 组合一周一次
    high = []
    for i, j in combinations(range(len(rows)), 2):
        if sim(rows[i], rows[j]) > 0.85:
            high.append((rows[i]["dish"], rows[j]["dish"]))
    if high:
        problems.append(f"存在 >85% 高度相似组合：{high}")

    # 规则 3：同一主蛋白多次出现须换烹法/味型
    by_protein = {}
    for r in rows:
        for p in filter(None, r["protein"].split("、")):
            by_protein.setdefault(p, []).append(r)
    for p, rs in by_protein.items():
        if 2 <= len(rs) <= 3:
            sigs = {(r["method"], r["flavor"]) for r in rs}
            if len(sigs) < len(rs):
                problems.append(f"主蛋白「{p}」出现 {len(rs)} 次但烹法/味型有重复：{[r['dish'] for r in rs]}")

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
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        main(sys.argv[1])
