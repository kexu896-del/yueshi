#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱指纹体系（round63 工作流 C）：去重与菜单多样性拆分。

三类指纹职责互不混用（方案 §7）：

  exact_fingerprint       精确重复指纹：标准化标题+核心食材集合+主烹法+来源。
                          只用于数据清洗/同源跨书重复检测/生产池重复计数。
  diversity_fingerprint   菜单多样性指纹：dish_category|primary_ingredient_family|
                          primary_cooking_method|meal_structure|dominant_flavor_family。
                          只用于七天菜单结构多样性、相邻餐次去重复、烹法味型组合检查。
  semantic_cluster_key    审计聚类键（宽松，不含 dish_category）：发现异常簇与
                          跨类型聚类，只进人工审计，不作为硬门禁。

主烹法拆分：primary_cooking_method 取 methods 中 taxonomy 优先级最高者，
其余进 secondary_cooking_methods；多样性指纹只用 primary，避免步骤并集聚类（§7.3）。

输入：data/recipe-classification.json（recipe_classifier.py 产物）+ 原菜谱数据。
输出：data/recipe-fingerprints.json（含 build_id、script_version、字段来源说明）、
      reports/recipe-duplicate-review.csv（精确重复簇人工复核清单）。

验收口径：数据重复率、多样性重复率分别统计；跨 dish_category 的语义簇自动判为
审计失败信号（由 recipe_library_auditor.py 消费，不在本脚本判死）。
"""
import argparse
import collections
import hashlib
import json
import os
import re

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(BASE, "data")
REPORTS = os.path.join(BASE, "reports")
SCRIPT_VERSION = "1.0.0"

FIELD_SOURCES = {
    "exact_fingerprint": "标准化标题 + 标准化核心食材(排序) + 主烹法 + 来源标识",
    "diversity_fingerprint": "dish_category + primary_ingredient_family + primary_cooking_method + meal_structure + dominant_flavor_family",
    "semantic_cluster_key": "primary_ingredient_family + primary_cooking_method（不含 dish_category，仅供审计）",
    "primary_cooking_method": "methods 中按 taxonomy/cooking-methods.json 优先级最高者",
}


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def norm_text(s):
    s = re.sub(r"[\s（）()\[\],，、·'\"'\.]+", "", str(s or "").lower())
    return s


def norm_ingredients(core):
    return sorted({norm_text(c) for c in (core or []) if c})


def primary_method(methods, priority):
    ms = [m for m in (methods or []) if m]
    if not ms:
        return "unknown", []
    pri = {m: i for i, m in enumerate(priority)}
    ordered = sorted(ms, key=lambda m: (pri.get(m, len(pri)), ms.index(m)))
    return ordered[0], ordered[1:]


def flavor_family(flavors, alias):
    if not flavors:
        return "其他"
    f0 = flavors[0]
    return alias.get(f0, f0 if f0 in set(alias.values()) else "其他")


def build(recipes, cls_by_id, priority, alias):
    out = []
    for r in recipes:
        rid = r.get("id")
        c = cls_by_id.get(rid, {})
        pm, sec = primary_method(r.get("methods"), priority)
        name = r.get("original_name") or r.get("name")
        core_norm = norm_ingredients(r.get("core_ingredients"))
        src = r.get("source_id") or r.get("source_book") or "unknown"
        dc = c.get("dish_category", "main_dish")
        pif = c.get("primary_ingredient_family") or "review_required"
        structure = r.get("structure") or "unknown"
        ff = flavor_family(r.get("flavors"), alias)

        exact_raw = "|".join([norm_text(name), ",".join(core_norm), pm, src])
        diversity_fp = "|".join([dc, pif, pm, structure, ff])
        semantic_key = "|".join([pif, pm])
        out.append({
            "id": rid,
            "name": name,
            "source": src,
            "excluded_from_production": bool(c.get("excluded_from_production")),
            "primary_cooking_method": pm,
            "secondary_cooking_methods": sec,
            "exact_fingerprint": hashlib.sha1(exact_raw.encode()).hexdigest()[:12],
            "diversity_fingerprint": diversity_fp,
            "semantic_cluster_key": semantic_key,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DATA, "recipe-fingerprints.json"))
    ap.add_argument("--reports-dir", default=REPORTS)
    ap.add_argument("--classification", default=os.path.join(DATA, "recipe-classification.json"))
    ap.add_argument("--build-id", default=None)
    args = ap.parse_args()

    cls = json.load(open(args.classification, encoding="utf-8"))
    build_id = args.build_id or cls.get("build_id")
    cls_by_id = {r["id"]: r for r in cls["records"]}
    priority = load("taxonomy/cooking-methods.json")["primary_method_priority"]
    alias = load("taxonomy/flavor-families.json")["alias_to_family"]

    idx = load("recipe-index.json")
    for r in idx:
        r.setdefault("source_id", "howtocook")
    recipes = idx + load("book-recipes.json")["recipes"]
    fps = build(recipes, cls_by_id, priority, alias)

    prod = [f for f in fps if not f["excluded_from_production"]]
    exact_clusters = collections.defaultdict(list)
    for f in prod:
        exact_clusters[f["exact_fingerprint"]].append(f["name"])
    exact_dups = {k: v for k, v in exact_clusters.items() if len(v) >= 2}
    div_clusters = collections.Counter(f["diversity_fingerprint"] for f in prod)
    div_dup = sum(n - 1 for n in div_clusters.values() if n >= 2)

    os.makedirs(args.reports_dir, exist_ok=True)
    import csv
    with open(os.path.join(args.reports_dir, "recipe-duplicate-review.csv"),
              "w", encoding="utf-8-sig", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["exact_fingerprint", "count", "names"])
        for k, v in sorted(exact_dups.items(), key=lambda x: -len(x[1])):
            w.writerow([k, len(v), "、".join(v[:10])])

    payload = {
        "build_id": build_id,
        "script": "scripts/recipe_fingerprint_builder.py",
        "script_version": SCRIPT_VERSION,
        "field_sources": FIELD_SOURCES,
        "record_count": len(fps),
        "stats": {
            "exact_duplicate_clusters": len(exact_dups),
            "exact_duplicate_recipes": sum(len(v) - 1 for v in exact_dups.values()),
            "diversity_duplicate_recipes": div_dup,
            "production_recipes": len(prod),
        },
        "fingerprints": fps,
    }
    json.dump(payload, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(payload["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
