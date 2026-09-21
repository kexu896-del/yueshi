#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱库覆盖审计（round62 第一优先）。

对生产菜谱池（data/recipe-index.json + data/book-recipes.json）生成离线覆盖审计，
只在审计显示明确缺口时才针对缺口补书——不泛泛增加综合菜谱书。

用法：
  python scripts/recipe_library_auditor.py [--json out.json] [--md out.md]

审计口径（启发式均在报告中明示，不伪装为人工标注）：
  - 可解析：有 id/名称 且 core_ingredients 非空 且 structure 非空；
  - 缺来源：书池缺 source_book，或索引条目无 source_id 字段（索引来源视为 howtocook）；
  - 缺烹法/菜系/季节标签：methods 空 / 无 cuisine 字段 / 无 season_months 字段；
  - 主要食材族：经 data/ingredient-catalog.json 的 ingredient_family 判定，
    首个蛋白族为 primary_protein_family，无命中即"缺主要食材族"；
  - 指纹：主蛋白族|核心蔬菜族|烹法|风味|形态（与 recipe_ranker.py 同口径）；
  - 近似指纹簇：同一指纹下 ≥2 道菜的簇；高度重复：同一指纹内被去重压掉的菜数；
  - 快手菜：estimated_active_minutes / active_minutes ≤ 15（启发式）；
  - 一人食适用（启发式）：active ≤ 30 且难度 ≤3（书池无难度字段，按 total ≤45 近似）；
  - 家庭模式适用（启发式）：份量可放大（书池 adapted/original_servings ≥2）或
    结构为一锅炖煮/汤羹/主食的索引菜。
"""
import argparse
import collections
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PROTEIN_FAMS = {"poultry", "pork", "beef", "lamb", "fish", "shellfish", "egg", "soy"}


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def build_family_map(cat):
    fam = {k: v.get("ingredient_family") for k, v in cat.get("items", {}).items()}

    def family_of(name):
        if fam.get(name):
            return fam[name]
        for k, v in fam.items():
            if v and (k in name or name in k):
                return v
        return None
    return family_of


def normalize(rows, default_source=None):
    """统一两池字段：source/technique/cuisine/season/family 审计视图。"""
    out = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "name": r.get("original_name") or r.get("name"),
            "source": r.get("source_id") or r.get("source_book") or default_source,
            "category": r.get("category"),
            "core_ingredients": r.get("core_ingredients") or [],
            "methods": r.get("methods") or [],
            "flavors": r.get("flavors") or [],
            "structure": r.get("structure") or "",
            "cuisine": r.get("cuisine"),
            "season_months": r.get("season_months"),
            "active_minutes": r.get("estimated_active_minutes", r.get("active_minutes")),
            "total_minutes": r.get("total_minutes"),
            "difficulty": r.get("difficulty"),
            "servings": r.get("adapted_servings") or r.get("original_servings"),
            "extraction_type": r.get("extraction_type", "index"),
        })
    return out


def audit(recipes, family_of):
    total = len(recipes)
    parseable = [r for r in recipes if r["id"] and r["name"] and r["core_ingredients"] and r["structure"]]
    missing = {
        "source": [r for r in recipes if not r["source"]],
        "technique": [r for r in recipes if not r["methods"]],
        "cuisine": [r for r in recipes if not r["cuisine"]],
        "season": [r for r in recipes if not r["season_months"]],
    }

    def fingerprint(r):
        fams = [(family_of(c) or "other") for c in r["core_ingredients"]]
        prot = next((f for f in fams if f in PROTEIN_FAMS), "none")
        veg = next((f for f in fams if f not in PROTEIN_FAMS and f != "flavor"), "none")
        return "|".join([prot, veg, "+".join(sorted(r["methods"])),
                         "+".join(sorted(r["flavors"])), r["structure"]])

    fam_missing = [r for r in parseable
                   if not any(family_of(c) for c in r["core_ingredients"])]
    fps = {}
    for r in parseable:
        fps.setdefault(fingerprint(r), []).append(r["name"])
    clusters = {k: v for k, v in fps.items() if len(v) >= 2}
    dup_count = sum(len(v) - 1 for v in clusters.values())

    def cover(keyfn, universe=None):
        c = collections.Counter()
        for r in parseable:
            v = keyfn(r)
            if isinstance(v, list):
                for x in v:
                    c[x] += 1
            elif v:
                c[v] += 1
        return dict(c.most_common())

    protein_cover = cover(lambda r: next((f for f in
                                          [(family_of(c) or "other") for c in r["core_ingredients"]]
                                          if f in PROTEIN_FAMS), None))
    technique_cover = cover(lambda r: r["methods"])
    cuisine_cover = cover(lambda r: r["cuisine"])

    quick = [r for r in parseable if r["active_minutes"] is not None and r["active_minutes"] <= 15]

    def solo_ok(r):
        if r["difficulty"] is not None and r["active_minutes"] is not None:
            return r["difficulty"] <= 3 and r["active_minutes"] <= 30
        return r["total_minutes"] is not None and r["total_minutes"] <= 45

    def household_ok(r):
        if r["servings"] is not None:
            try:
                return float(r["servings"]) >= 2
            except (TypeError, ValueError):
                return False
        return r["structure"] in ("一锅炖煮", "汤羹", "汤/煮", "主食")

    per_source = collections.Counter(r["source"] for r in parseable)
    return {
        "total_recipes": total,
        "parseable_recipes": len(parseable),
        "unparseable_recipes": total - len(parseable),
        "missing_source": len(missing["source"]),
        "missing_technique": len(missing["technique"]),
        "missing_cuisine": len(missing["cuisine"]),
        "missing_season": len(missing["season"]),
        "missing_primary_family": len(fam_missing),
        "fingerprint_cluster_count": len(clusters),
        "high_duplicate_recipes": dup_count,
        "protein_family_coverage": protein_cover,
        "technique_coverage": technique_cover,
        "cuisine_coverage": cuisine_cover,
        "quick_recipes": len(quick),
        "solo_friendly_recipes": sum(1 for r in parseable if solo_ok(r)),
        "household_friendly_recipes": sum(1 for r in parseable if household_ok(r)),
        "per_source_counts": dict(per_source.most_common()),
        "top_fingerprint_clusters": sorted(
            ({"fingerprint": k, "count": len(v), "examples": v[:5]} for k, v in clusters.items()),
            key=lambda x: -x["count"])[:10],
    }


def acceptance_layer(rep_prev=None):
    """round63 验收层：消费 recipe_classifier / recipe_fingerprint_builder 产物，
    产出 audit_status / blocking_issues / warnings / 覆盖率指标 / 版本比较。

    数据缺失即 failed（fail-closed，不得手工改状态绕过）。"""
    cls_path = os.path.join(DATA, "recipe-classification.json")
    fp_path = os.path.join(DATA, "recipe-fingerprints.json")
    layer = {"classification_build_id": None, "build_id": None}
    if not (os.path.exists(cls_path) and os.path.exists(fp_path)):
        layer.update({
            "audit_status": "failed",
            "blocking_issues": ["classification_or_fingerprint_missing"],
            "warnings": [],
        })
        return layer

    cls = json.load(open(cls_path, encoding="utf-8"))
    fps = json.load(open(fp_path, encoding="utf-8"))
    records = cls["records"]
    prod = [r for r in records if not r.get("excluded_from_production")]
    n = max(len(prod), 1)
    main_meal = {"main_dish", "staple", "soup", "side", "composite_meal"}
    flesh = {"poultry", "pork", "beef", "lamb", "fish", "shellfish"}

    dish_cov = sum(1 for r in prod if r["dish_category"]) / n
    fam_cov = sum(1 for r in prod if r["primary_ingredient_family"]) / n
    # 应有主蛋白：正餐类且证据中含蛋白族食材
    prot_expected = [r for r in prod if r["dish_category"] in main_meal
                     and any(e.get("family") in
                             {"poultry", "pork", "beef", "lamb", "fish", "shellfish",
                              "egg", "dairy", "soy", "other_protein"}
                             for e in r["classification_evidence"][1:])]
    prot_cov = (sum(1 for r in prot_expected if r["primary_protein_family"])
                / max(len(prot_expected), 1))
    severe = [r for r in prod
              if r["dish_category"] in {"dessert", "beverage", "sauce_or_condiment"}
              and r["primary_protein_family"] in flesh]
    low_conf = [r for r in prod if r["classification_confidence"] == "low"]

    # 跨类型聚类失败信号（方案 §2.1 的病理口径）：非正餐类（甜点/饮品/调味品/小食）
    # 落入以肉禽水产为主食材族的语义簇——即"蛋糕进了 poultry 簇、糖浆和肉菜同簇"。
    # 蛋/谷/蔬菜跨 staple/soup/side 属正常形态差异，只进复核，不判死。
    by_key = collections.defaultdict(set)
    cls_dc = {r["id"]: r["dish_category"] for r in records}
    for f in fps["fingerprints"]:
        if not f["excluded_from_production"]:
            by_key[f["semantic_cluster_key"]].add(f["id"])
    non_main = {"dessert", "beverage", "sauce_or_condiment", "snack"}
    cross = 0
    cross_review = []
    for key, ids in by_key.items():
        if len(ids) < 2:
            continue
        dcs = {cls_dc[i] for i in ids}
        if dcs & non_main and dcs - non_main:
            fam = key.split("|", 1)[0]
            if fam in flesh:
                cross += 1
            else:
                cross_review.append({"semantic_cluster_key": key,
                                     "dish_categories": sorted(dcs), "count": len(ids)})

    # 人工抽样准确率：data/audit/human-review.json 存在才计算；未计算保持 null，不伪造
    hr_path = os.path.join(DATA, "audit", "human-review.json")
    sample_acc = None
    reviewed_ids = set()
    sampling_meta = None
    per_field_acc = None
    sample_split = None
    if os.path.exists(hr_path):
        hr = json.load(open(hr_path, encoding="utf-8"))
        res = hr.get("reviews", [])
        reviewed_ids = {x.get("id") for x in res}
        # 准确率口径：correct / (correct + incorrect)；ambiguous（高汤带入次要蛋白等
        # 合理边界）不计入分母。复核方法与样本量以 human-review.json 为准。
        # round64 §10.3：优先按随机分层子集计算无偏总体准确率；风险样本只用于发现问题
        rand = [x for x in res if x.get("sample_kind") != "risk"]
        pool = rand or res
        decidable = [x for x in pool if x.get("review_result") in ("correct", "incorrect")]
        if decidable:
            sample_acc = round(sum(1 for x in decidable if x["review_result"] == "correct")
                               / len(decidable), 4)
        sampling_meta = hr.get("sampling")
        per_field_acc = hr.get("accuracy")
        sample_split = hr.get("sample_split")

    stats = fps.get("stats", {})
    metrics = {
        "dish_category_coverage": round(dish_cov, 4),
        "primary_ingredient_family_coverage": round(fam_cov, 4),
        "primary_protein_family_coverage": round(prot_cov, 4),
        "classification_sample_accuracy": sample_acc,
        "cross_category_cluster_count": cross,
        "severe_protein_mislabel_count": len(severe),
        "low_confidence_count": len(low_conf),
        "low_confidence_reviewed_count": sum(1 for r in low_conf if r["id"] in reviewed_ids),
        "unparseable_isolated_count": len(records) - len(prod),
        "exact_duplicate_recipes": stats.get("exact_duplicate_recipes"),
        "diversity_duplicate_recipes": stats.get("diversity_duplicate_recipes"),
    }
    # round64 §10：抽样可复现元数据 + 分字段准确率 + 样本分离（原样透传，不再计算）
    if sampling_meta is not None:
        metrics["sampling"] = sampling_meta
    if per_field_acc is not None:
        metrics["per_field_accuracy"] = per_field_acc
    if sample_split is not None:
        metrics["sample_split"] = sample_split

    # round64 §12 / round64.1 §7（P2）：门禁后的有效候选覆盖漏斗——
    # 字段覆盖率高≠真实场景候选充足。口径：总数 → 生产池 → 正餐池 → 去精确重复
    # → 互斥时间桶（quick/regular/slow/unknown 总和必须等于去重后正餐数）
    # → 各主蛋白族真实约束切片（一人食/家庭/30 分钟/常见厨具/价格可解析）。
    eff = None
    try:
        info = {}
        ri = json.load(open(os.path.join(DATA, "recipe-index.json"), encoding="utf-8"))
        for r in ri:
            info[r["id"]] = {
                "active": r.get("estimated_active_minutes"),
                "difficulty": r.get("difficulty"),
                "servings": None,
                "equipment": r.get("equipment") or [],
                "core_ingredients": r.get("core_ingredients") or [],
                "structure": r.get("structure") or "",
            }
        br = json.load(open(os.path.join(DATA, "book-recipes.json"),
                             encoding="utf-8"))["recipes"]
        for r in br:
            sv = r.get("adapted_servings") or r.get("original_servings")
            try:
                sv = float(sv) if sv is not None else None
            except (TypeError, ValueError):
                sv = None
            info[r["id"]] = {
                "active": r.get("active_minutes"),
                "difficulty": None,
                "servings": sv,
                "equipment": None,  # 书池未标注厨具 → 按常见家庭厨具处理
                "core_ingredients": r.get("core_ingredients") or [],
                "structure": r.get("structure") or "",
            }
        cat_items = set(json.load(open(os.path.join(DATA, "ingredient-catalog.json"),
                                       encoding="utf-8")).get("items", {}))
        main_ids = [r["id"] for r in prod if r["dish_category"] in main_meal]
        # 精确重复分析：输入/重复组/重复记录/保留 四方闭合
        frec = {f["id"]: f for f in fps["fingerprints"]}
        ex_groups = collections.defaultdict(list)
        for rid in main_ids:
            ex_groups[frec.get(rid, {}).get("exact_fingerprint") or rid].append(rid)
        dup_groups = {k: v for k, v in ex_groups.items() if len(v) > 1}
        dedup_ids = [v[0] for v in ex_groups.values()]  # canonical_selection_policy: keep_first
        # 互斥时间桶
        buckets = {"quick_le_15": 0, "regular_gt_15_le_30": 0,
                   "slow_gt_30": 0, "time_unknown": 0}
        for rid in dedup_ids:
            a = info.get(rid, {}).get("active")
            if a is None:
                buckets["time_unknown"] += 1
            elif a <= 15:
                buckets["quick_le_15"] += 1
            elif a <= 30:
                buckets["regular_gt_15_le_30"] += 1
            else:
                buckets["slow_gt_30"] += 1
        fam_fp = collections.defaultdict(set)
        method_fp = collections.defaultdict(set)
        for rid in dedup_ids:
            f = frec.get(rid)
            if not f:
                continue
            fam, method = f["semantic_cluster_key"].split("|", 1)
            fam_fp[fam].add(f["diversity_fingerprint"])
            method_fp[method].add(f["diversity_fingerprint"])
        COMMON_EQ = {"炒锅", "电饭煲", "蒸锅", "煮锅", "平底锅", "烤箱", "空气炸锅", "砂锅"}

        def slices(rid):
            r = info.get(rid, {})
            a = r.get("active")
            solo_ok = (r.get("difficulty") is not None and a is not None
                       and r["difficulty"] <= 3 and a <= 30) or \
                      (r.get("difficulty") is None and a is not None and a <= 30)
            hh = (r.get("servings") is not None and r["servings"] >= 2) or \
                 r.get("structure") in ("一锅炖煮", "汤羹", "汤/煮", "主食")
            eq = True if r.get("equipment") is None else \
                set(r["equipment"]) <= COMMON_EQ
            price = bool(r.get("core_ingredients")) and \
                all(c in cat_items for c in r["core_ingredients"])
            return solo_ok, hh, eq, price, a

        pfam = {}
        for rid in dedup_ids:
            c = next((r for r in prod if r["id"] == rid), None)
            fam = (c or {}).get("primary_protein_family") or "none"
            s, hh, eq, price, a = slices(rid)
            d = pfam.setdefault(fam, {"diversity_fingerprints": set(),
                                      "solo_quick": 0, "solo_regular": 0,
                                      "household_regular": 0, "common_equipment": 0,
                                      "price_resolvable": 0, "total": 0})
            f = frec.get(rid)
            if f:
                d["diversity_fingerprints"].add(f["diversity_fingerprint"])
            d["total"] += 1
            if s and a is not None and a <= 15:
                d["solo_quick"] += 1
            if s:
                d["solo_regular"] += 1
            if hh:
                d["household_regular"] += 1
            if eq:
                d["common_equipment"] += 1
            if price:
                d["price_resolvable"] += 1
        eff = {
            "total_recipes": len(records),
            "production_pool": len(prod),
            "main_meal_pool": len(main_ids),
            "exact_duplicate_analysis": {
                "input_count": len(main_ids),
                "duplicate_group_count": len(dup_groups),
                "duplicate_record_count": sum(len(v) for v in dup_groups.values()),
                "retained_count": len(dedup_ids),
                "canonical_selection_policy": "keep_first",
            },
            "after_exact_dedup": len(dedup_ids),
            "active_time_buckets": {
                **buckets,
                "mutually_exclusive": True,
                "closure": "quick+regular+slow+unknown == after_exact_dedup",
                "closure_ok": sum(buckets.values()) == len(dedup_ids),
            },
            "distinct_diversity_fingerprints_by_protein_family":
                {k: len(v) for k, v in sorted(fam_fp.items())},
            "distinct_diversity_fingerprints_by_method":
                {k: len(v) for k, v in sorted(method_fp.items())},
            "protein_family_coverage": {
                k: {kk: (sorted(vv) if kk == "diversity_fingerprints" else vv)
                    for kk, vv in v.items()}
                for k, v in sorted(pfam.items())},
            "note": "切片口径：solo=难度≤3且active≤30min（书池无难度字段时按 active≤30）；"
                    "household=份数≥2 或一锅/汤/主食结构；common_equipment=厨具⊆常见家庭厨具"
                    "（书池未标注按可用计）；price_resolvable=核心食材全部在食材目录可解析。"
                    "本表为扩库决策唯一依据（真实约束切片稳定不足才扩库，不只看原始数量）。",
        }
    except (OSError, KeyError):
        eff = None

    blocking, warnings = [], []
    if dish_cov < 1.0:
        blocking.append("dish_category_missing")
    if fam_cov < 0.98:
        blocking.append("primary_ingredient_family_missing")
    if prot_cov < 0.98:
        blocking.append("primary_protein_family_missing")
    if severe:
        blocking.append("severe_protein_mislabel")
    if cross:
        blocking.append("cross_category_cluster_detected")
    if sample_acc is not None and sample_acc < 0.95:
        blocking.append("classification_accuracy_below_threshold")
    if sample_acc is None:
        warnings.append("classification_accuracy_not_verified")
    unreviewed_low = [r for r in low_conf if r["id"] not in reviewed_ids]
    if unreviewed_low:
        warnings.append("low_confidence_review_pending")
    if cross_review:
        warnings.append("soft_cross_category_clusters_for_review")

    layer["quality_metrics"] = metrics
    if eff is not None:
        layer["effective_candidate_coverage"] = eff
    layer["cross_category_review_clusters"] = cross_review[:50]
    layer["classification_build_id"] = cls.get("build_id")
    layer["build_id"] = cls.get("build_id")
    layer["blocking_issues"] = blocking
    layer["warnings"] = warnings
    layer["audit_status"] = ("failed" if blocking
                             else ("passed_with_warnings" if warnings else "passed"))

    # 与上一版比较（rep_prev 为上一次审计 JSON；无则 null，不伪造）
    if rep_prev:
        comp = {}
        for k in ("total_recipes", "parseable_recipes", "missing_primary_family",
                  "high_duplicate_recipes"):
            if k in rep_prev:
                comp[k] = {"previous": rep_prev.get(k)}
        pm = rep_prev.get("quality_metrics") or {}
        for k in ("dish_category_coverage", "primary_ingredient_family_coverage",
                  "primary_protein_family_coverage", "classification_sample_accuracy",
                  "cross_category_cluster_count"):
            if k in pm:
                comp[k] = {"previous": pm.get(k)}
        layer["comparison_with_previous"] = comp
    else:
        layer["comparison_with_previous"] = None
    return layer


def gap_findings(rep):
    """缺口判读（自动启发式阈值，供维护者决策，不作硬结论）。"""
    g = []
    t = rep["parseable_recipes"] or 1
    if rep["missing_cuisine"] == rep["total_recipes"]:
        g.append("菜系标签整体缺失：增加书籍不会改善菜系多样性，应先补结构化标签")
    if rep["missing_season"] == rep["total_recipes"]:
        g.append("季节标签整体缺失：时令评分无法落到菜谱层，应先补标签（与 S01–S04 联动）")
    for fam, n in rep["protein_family_coverage"].items():
        if n < 30:
            g.append(f"主蛋白族 {fam} 覆盖偏少（{n} 道）")
    for m, n in rep["technique_coverage"].items():
        if m in ("蒸", "砂锅", "炖", "煎") and n < 100:
            g.append(f"烹法「{m}」覆盖偏少（{n} 道）")
    if rep["quick_recipes"] < 0.2 * t:
        g.append(f"快手菜（≤15min）占比偏低：{rep['quick_recipes']}/{t}")
    if rep["high_duplicate_recipes"] > 0.1 * t:
        g.append(f"指纹重复度高：{rep['high_duplicate_recipes']} 道可被簇去重压掉"
                 f"（占 {rep['high_duplicate_recipes'] * 100 // t}%），候选数量存在虚高")
    if rep["missing_primary_family"] > 0.15 * t:
        g.append(f"{rep['missing_primary_family']} 道缺主要食材族标注，指纹与多样性门禁对它们失效")
    if not g:
        g.append("未检出明确缺口")
    return g


def to_md(rep):
    L = ["# 菜谱库覆盖审计报告", ""]
    if "audit_status" in rep:
        L += [f"## 本次审计结论：{rep['audit_status']}", ""]
        if rep.get("blocking_issues"):
            L += ["### 阻断发布问题", ""]
            L += [f"- {x}" for x in rep["blocking_issues"]] + [""]
        if rep.get("warnings"):
            L += ["### 警告问题", ""]
            L += [f"- {x}" for x in rep["warnings"]] + [""]
        gm = rep.get("quality_metrics", {})
        if gm:
            L += ["### 质量指标（生产准入口径）", ""]
            L += [f"- {k}：{v}" for k, v in gm.items()] + [""]
        L += ["### 是否满足生产准入门槛", "",
              ("否（存在阻断问题，release_status 只能为 blocked/review_required）"
               if rep.get("blocking_issues") else "是（见 recipe_release_gate.py 判定）"), ""]
        cmp_ = rep.get("comparison_with_previous")
        L += ["### 与上一版比较", ""]
        if cmp_:
            for k, v in cmp_.items():
                cur = rep.get(k, gm.get(k))
                L.append(f"- {k}：{v.get('previous')} → {cur}")
        else:
            L.append("- 无上一版审计基线（首轮，记 null，不伪造）")
        L.append("")
        L += ["### 修复清单产物", "",
              "- reports/recipe-unparseable.csv（不可解析隔离）",
              "- reports/recipe-low-confidence.csv（低置信度人工复核队列）",
              "- reports/recipe-classification-fixes.csv（自动修复记录）",
              "- reports/recipe-duplicate-review.csv（精确重复簇复核）",
              "- reports/recipe-missing-tags.csv（缺菜系/季节标签清单）", ""]
    L += ["> 生成方式：scripts/recipe_library_auditor.py 离线统计（生产池："
          "recipe-index.json + book-recipes.json；分类与指纹：recipe-classification.json / "
          "recipe-fingerprints.json）；启发式口径见脚本 docstring。", ""]
    L += ["## 缺口判读（自动启发式）", ""]
    L += [f"- {x}" for x in gap_findings(rep)] + [""]
    L += ["## 总量与完整性", "",
          f"- 总菜谱数：{rep['total_recipes']}",
          f"- 可解析菜谱数：{rep['parseable_recipes']}（不可解析 {rep['unparseable_recipes']}）",
          f"- 缺来源：{rep['missing_source']}",
          f"- 缺烹法标签：{rep['missing_technique']}",
          f"- 缺菜系标签：{rep['missing_cuisine']}",
          f"- 缺季节标签：{rep['missing_season']}",
          f"- 缺主要食材族：{rep['missing_primary_family']}",
          f"- 近似指纹簇数量：{rep['fingerprint_cluster_count']}",
          f"- 高度重复菜谱数量（指纹簇内可被去重压掉）：{rep['high_duplicate_recipes']}", ""]
    L += ["## 覆盖分布", "", "### 主蛋白族", ""]
    L += [f"- {k}：{v}" for k, v in rep["protein_family_coverage"].items()]
    L += ["", "### 烹法", ""]
    L += [f"- {k}：{v}" for k, v in rep["technique_coverage"].items()]
    L += ["", "### 菜系", ""]
    L += ([f"- {k}：{v}" for k, v in rep["cuisine_coverage"].items()] or ["- （无菜系标签数据）"])
    L += ["", "## 适用性覆盖（启发式）", "",
          f"- 快手菜（active ≤15min）：{rep['quick_recipes']}",
          f"- 一人食适用：{rep['solo_friendly_recipes']}",
          f"- 家庭模式适用：{rep['household_friendly_recipes']}", "",
          "## 来源分布", ""]
    L += [f"- {k}：{v}" for k, v in rep["per_source_counts"].items()]
    L += ["", "## 前 10 个近似指纹簇（去重收益最大的簇）", ""]
    for c in rep["top_fingerprint_clusters"]:
        L.append(f"- `{c['fingerprint']}` × {c['count']}：{'、'.join(c['examples'])}")
    L.append("")
    return "\n".join(L)


def write_missing_tags_csv(recipes, path):
    """缺菜系/季节标签修复清单（recipe-missing-tags.csv）。"""
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "source", "missing_fields"])
        for r in recipes:
            miss = []
            if not r["cuisine"]:
                miss.append("cuisine")
            if not r["season_months"]:
                miss.append("season_months")
            if miss:
                w.writerow([r["id"], r["name"], r["source"], "+".join(miss)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--prev", default=os.path.join(DATA, "audit", "previous-audit.json"),
                    help="上一次审计 JSON（用于版本间比较；不存在则比较项记 null）")
    ap.add_argument("--reports-dir", default=os.path.join(os.path.dirname(DATA), "reports"))
    ap.add_argument("--save-history", default=None,
                    help="把本次审计 JSON 存为该路径（供下次 --prev 比较）")
    args = ap.parse_args()
    idx = load("recipe-index.json")
    books = load("book-recipes.json")["recipes"]
    family_of = build_family_map(load("ingredient-catalog.json"))
    rows = normalize(idx, default_source="howtocook") + normalize(books)
    rep = audit(rows, family_of)

    prev = None
    if args.prev and os.path.exists(args.prev):
        prev = json.load(open(args.prev, encoding="utf-8"))
    rep.update(acceptance_layer(prev))
    write_missing_tags_csv(rows, os.path.join(args.reports_dir, "recipe-missing-tags.csv"))

    if args.json:
        json.dump(rep, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if args.md:
        open(args.md, "w", encoding="utf-8").write(to_md(rep))
    if args.save_history:
        os.makedirs(os.path.dirname(args.save_history), exist_ok=True)
        json.dump(rep, open(args.save_history, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: rep[k] for k in ("total_recipes", "parseable_recipes", "missing_cuisine",
                                          "missing_season", "fingerprint_cluster_count",
                                          "high_duplicate_recipes", "quick_recipes")},
                     ensure_ascii=False))
    if "audit_status" in rep:
        print(json.dumps({"audit_status": rep["audit_status"],
                          "blocking_issues": rep["blocking_issues"],
                          "warnings": rep["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
