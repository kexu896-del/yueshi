#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜谱候选检索（两次生成的第二阶段）

在统一生产池里按五层过滤（所在地常见可购性已在初步篮子阶段检查，此处仅作排序加分）：
  1. locked_basket 符合性：core_ingredients ⊆ 锁定篮子 + 允许例外白名单（主食类配料可放宽，视模式）
  2. 安全与模式：过敏原/医嘱剔除；adaptability（keto_biologic / hormone_balance）为 high/medium
  3. 烹饪条件：estimated_active_minutes ≤ 上限、equipment ⊆ 用户厨具
  4. 包装与余量：易腐复用/包装消耗/清库存（排序加权）
  5. 多样性初筛：输出带指纹字段，供 diversity_checker.py 终检

用法：
  python recipe_ranker.py --basket 鸡腿,鸡蛋,菠菜,西兰花 --mode keto \
      --max-minutes 25 --equipment 炒锅,电饭煲 --limit 20
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
from mode_schedule import load_mode_schedule  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
INDEX = os.path.join(DATA, "recipe-index.json")
BOOKS = os.path.join(DATA, "book-recipes.json")
MANIFEST = os.path.join(DATA, "library-manifest.json")


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _sha256_tree(dirpath):
    import hashlib
    h = hashlib.sha256()
    for root, _dirs, files in sorted(os.walk(dirpath)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            h.update(os.path.relpath(fp, dirpath).encode("utf-8"))
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
    return "sha256:" + h.hexdigest()


_HASH_TARGETS = {
    "recipe_index": ("file", "recipe-index.json"),
    "book_recipes": ("file", "book-recipes.json"),
    "classification_output": ("file", "recipe-classification.json"),
    "fingerprints": ("file", "recipe-fingerprints.json"),
    "audit_data": ("file", os.path.join("audit", "latest-audit.json")),
    "ingredient_catalog": ("file", "ingredient-catalog.json"),
    "taxonomy_bundle": ("dir", "taxonomy"),
    "review_overrides": ("file", os.path.join("audit", "review-overrides.json")),
}


def verify_release_integrity():
    """round64 发布链防旁路：ranker 启动前校验。
    返回 (ok, reason)。校验项：
      release_status == approved；分类/指纹 build_id 与 manifest 一致；
      manifest.artifact_hashes 与当前全部生产产物内容哈希一致（批准后篡改、
      新旧产物混用、taxonomy/食材目录漂移、同 build_id 不同内容 一律拒绝）。
    manifest 缺失 → 回退白名单语义（由 production_allowed 处理），本函数不拦截。"""
    if not os.path.exists(MANIFEST):
        return True, "manifest_absent_legacy_whitelist"
    mf = json.load(open(MANIFEST, encoding="utf-8"))
    rel = mf.get("release") or {}
    if rel.get("release_status") != "approved":
        return False, f"release_not_approved:{rel.get('release_status')}"
    hashes = rel.get("artifact_hashes")
    if not hashes:
        return False, "artifact_hashes_missing:重新运行 recipe_release_gate.py 冻结哈希"
    for key, (kind, rel_path) in _HASH_TARGETS.items():
        p = os.path.join(DATA, rel_path)
        if not os.path.exists(p):
            return False, f"artifact_missing:{rel_path}"
        actual = _sha256_file(p) if kind == "file" else _sha256_tree(p)
        if hashes.get(key) != actual:
            return False, f"artifact_hash_mismatch:{key}"
    # build_id 一致性（manifest vs 分类/指纹）
    for name in ("recipe-classification.json", "recipe-fingerprints.json"):
        bid = json.load(open(os.path.join(DATA, name), encoding="utf-8")).get("build_id")
        if bid != rel.get("build_id"):
            return False, f"build_id_mismatch:{name}"
    return True, "ok"


def production_allowed(source_id):
    """双层门禁：① release_status——manifest 必须带 release 块且为 approved
    （recipe_release_gate.py 是唯一写入方；审计失败/未审计 = blocked，默认不放行）；
    ② record_status——仅 production 来源可进入生产候选池。
    manifest 文件整体缺失时回退到内置白名单（howtocook + 已批准书籍池）。"""
    try:
        mf = json.load(open(MANIFEST, encoding="utf-8"))
    except OSError:
        return source_id in ("howtocook", "book_pool_11books")
    rel = mf.get("release")
    if not rel or rel.get("release_status") != "approved":
        return False  # blocked / review_required / 无 release 块：一律不进生产
    for s in mf.get("sources", []):
        if s.get("source_id") == source_id:
            return s.get("status") == "production"
    return False


# 正餐候选池一级类型边界（taxonomy/dish-categories.json；甜点/饮品/调味品/小食不进正餐池）
MAIN_MEAL_EXCLUDED_CATS = {"dessert", "beverage", "sauce_or_condiment", "snack"}


def load_dish_categories():
    """读取 recipe-classification.json 的 dish_category（recipe_classifier.py 产物）。
    缺失返回 None（调用方按不过滤处理并记录 warning）。"""
    p = os.path.join(DATA, "recipe-classification.json")
    if not os.path.exists(p):
        return None
    cls = json.load(open(p, encoding="utf-8"))
    return {r["id"]: r for r in cls["records"]}



sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.recipe_normalization import first_of

REASON_CODES = [
    "no_production_recipe", "recipe_fingerprint_missing", "safety_or_medical_conflict",
    "allergen_conflict", "time_limit", "equipment_mismatch", "package_waste",
    "budget_pressure", "nutrition_conflict", "duplicate_protein", "low_diversity_gain",
    "lower_rank_after_constraints", "insufficient_quantity", "schedule_mismatch",
]
DECISION_BONUS = {"explicitly_wanted": 6, "accepted_batch": 3, "merely_allowed": 0}


def find_candidates(ingredient, pool, basket, allowed_extra, adapt_key, args, equipment):
    """补偿搜索：生产池中 core_ingredients 含该食材的菜，按约束分层检查。"""
    cands = []
    for src_tag, r in pool:
        core = r["core_ingredients"]
        if not any(ingredient in c or c in ingredient for c in core):
            continue
        reason = None
        if r["category"] not in set(args.categories.split(",")):
            reason = "schedule_mismatch"
        elif r["adaptability"].get(adapt_key) in ("none", "low"):
            reason = "nutrition_conflict"
        elif r["estimated_active_minutes"] > args.max_minutes:
            reason = "time_limit"
        elif r["equipment"] and not set(r["equipment"]) <= equipment | {"炒锅", "汤锅", "蒸锅"}:
            reason = "equipment_mismatch"
        else:
            def in_basket(item):
                if item in basket or item in allowed_extra:
                    return True
                return any((b in item or item in b) and len(item) >= 2 and len(b) >= 2
                           for b in basket | allowed_extra)
            missing = {c for c in core if not in_basket(c)}
            if len(missing) > 1:
                reason = "insufficient_quantity"
        hit = len([c for c in core if c in basket]) if not reason else 0
        cands.append({"name": r["original_name"], "src": src_tag, "reason": reason,
                      "score": hit * 2 if not reason else 0})
    return cands


def coverage_gate(accepted, wanted, pool, basket, allowed_extra, adapt_key, args, equipment):
    """预选覆盖门禁：accepted_batch / explicitly_wanted 食材逐项补偿搜索，
    输出 ingredient_selection_result 记录（真实原因码来自本函数，不由渲染器猜测）。"""
    results = []
    for ing, decision in [(i, "explicitly_wanted") for i in wanted] + [(i, "accepted_batch") for i in accepted]:
        if ing in basket:
            continue  # 已在篮子，进入正常检索
        cands = find_candidates(ing, pool, basket, allowed_extra, adapt_key, args, equipment)
        usable = [c for c in cands if c["reason"] is None]
        if not cands:
            rec = {"ingredient": ing, "preselection_decision": decision, "menu_status": "not_selected",
                   "candidate_count": 0, "top_candidate": None, "rejected_at": "pool_gate",
                   "reason_codes": ["no_production_recipe"], "can_swap": False, "swap_target_meal": None}
        elif not usable:
            top = cands[0]
            rec = {"ingredient": ing, "preselection_decision": decision, "menu_status": "not_selected",
                   "candidate_count": len(cands), "top_candidate": top["name"],
                   "rejected_at": "constraint_gate",
                   "reason_codes": sorted({c["reason"] for c in cands if c["reason"]}),
                   "can_swap": False, "swap_target_meal": None}
        else:
            top = sorted(usable, key=lambda c: -c["score"])[0]
            rec = {"ingredient": ing, "preselection_decision": decision, "menu_status": "compensation_candidate",
                   "candidate_count": len(usable), "top_candidate": top["name"],
                   "rejected_at": None, "reason_codes": ["lower_rank_after_constraints"],
                   "can_swap": True, "swap_target_meal": "同类蛋白重复度最高的一顿"}
        results.append(rec)
    return results


STAPLE_OK = {"米饭", "糙米", "燕麦", "红薯", "玉米", "土豆", "山药", "面条", "南瓜", "莲藕"}  # 平衡激素模式可放宽


def main():
    ok, reason = verify_release_integrity()
    if not ok:
        raise SystemExit(f"release_integrity_failed: {reason}——"
                         f"菜谱库未通过发布完整性校验，拒绝读取生产库；"
                         f"请重跑 classifier → fingerprint → auditor → release gate 链路")
    ap = argparse.ArgumentParser()
    ap.add_argument("--basket", required=True, help="篮子食材，逗号分隔")
    ap.add_argument("--mode", choices=["keto", "hormone"], default=None,
                    help="仅未提供 --mode-schedule 时可用；与冻结计划冲突即 M11 失败")
    ap.add_argument("--mode-schedule", default=None,
                    help="已冻结 mode_schedule.json（round60 起唯一模式来源，M11）")
    ap.add_argument("--audit-report", default=None,
                    help="输出选择审计 JSON（selection_audit，未计算字段记 null，不伪造数值）")
    ap.add_argument("--max-minutes", type=int, default=30)
    ap.add_argument("--equipment", default="炒锅", help="逗号分隔")
    ap.add_argument("--categories", default="荤菜,素菜,水产,汤羹,早餐,主食", help="参与检索的分类")
    ap.add_argument("--wanted", default="", help="用户点名想吃食材，逗号分隔（explicitly_wanted，最高权重）")
    ap.add_argument("--accepted", default="", help="整批接受的预选食材，逗号分隔（accepted_batch，中高权重）")
    ap.add_argument("--selection-report", default=None, help="输出预选闭环追溯 JSONL（含未入选原因码与可替换方案）")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--no-books", action="store_true", help="只搜 HowToCook 池")
    ap.add_argument("--book-quota", type=float, default=0.5,
                    help="书本菜谱在输出中的最大占比（默认 0.5，来源配比见 references/book-recipe-extraction.md）")
    args = ap.parse_args()

    # M11 模式一致性：--mode-schedule 为唯一权威来源（取整周多数模式作为检索口径）
    mode_schedule_hash = None
    if args.mode_schedule:
        ms, mode_schedule_hash = load_mode_schedule(args.mode_schedule)
        majority = "keto" if ms["mode_summary"]["keto_days"] > ms["mode_summary"]["hormone_days"] else "hormone"
        if args.mode and args.mode != majority:
            raise SystemExit(f"mode_schedule_mismatch: --mode {args.mode} ≠ 冻结计划多数模式 {majority}")
        args.mode = majority
    elif not args.mode:
        raise SystemExit("mode_schedule_invalid: 必须提供 --mode-schedule（或临时调试用手写 --mode）")

    basket = set(filter(None, args.basket.split(",")))
    equipment = set(filter(None, args.equipment.split(",")))
    cats = set(args.categories.split(","))
    adapt_key = "keto_biologic" if args.mode == "keto" else "hormone_balance"
    allowed_extra = set() if args.mode == "keto" else STAPLE_OK

    idx = json.load(open(INDEX, encoding="utf-8")) if production_allowed("howtocook") else []
    pool = [("howtocook", r) for r in idx]
    if not args.no_books and os.path.exists(BOOKS) and production_allowed("book_pool_11books"):
        for r in json.load(open(BOOKS, encoding="utf-8"))["recipes"]:
            if r.get("extraction_type") != "explicit_recipe" or r.get("pool_exclude"):
                continue
            pool.append(("book:" + r["source_book"], {
                "id": r.get("id"),
                "original_name": r["name"],
                "category": ("汤羹" if r["structure"] in ("汤羹", "汤/煮") else
                             "主食" if r["structure"] == "主食" else
                             ("荤菜" if any(w in " ".join(r["core_ingredients"])
                                            for w in ("鸡", "猪", "牛", "羊", "鱼", "虾", "蟹", "肉", "蛋", "贝", "鳝", "鸭"))
                                     else "素菜")),
                "core_ingredients": r["core_ingredients"],
                "methods": r["methods"], "flavors": r["flavors"],
                "structure": r["structure"],
                "difficulty": 2,
                "estimated_active_minutes": r.get("active_minutes") or r.get("total_minutes") or 25,
                "equipment": [],
                "adaptability": r["mode_fit"],
                "modification_notes": r.get("required_modifications") or [],
            }))
    scored = []
    # 一级类型过滤：甜点/饮品/调味品/小食与不可解析隔离项不进正餐候选池
    dish_cls = load_dish_categories()
    excluded_cat_count = 0
    for src_tag, r in pool:
        if dish_cls is not None:
            c = dish_cls.get(r.get("id"))
            if c and (c.get("excluded_from_production")
                      or c.get("dish_category") in MAIN_MEAL_EXCLUDED_CATS):
                excluded_cat_count += 1
                continue
        if r["category"] not in cats:
            continue
        ad = r["adaptability"][adapt_key]
        if ad in ("none", "low"):
            continue
        if r["estimated_active_minutes"] > args.max_minutes:
            continue
        if r["equipment"] and not set(r["equipment"]) <= equipment | {"炒锅", "汤锅"}:
            continue
        core = set(r["core_ingredients"])
        def in_basket(item):
            if item in basket or item in allowed_extra:
                return True
            return any((b in item or item in b) and len(item) >= 2 and len(b) >= 2
                       for b in basket | allowed_extra)
        missing = {c for c in core if not in_basket(c)}
        if len(missing) > 1:          # 最多容忍 1 种篮子外食材（需用户确认可加购）
            continue
        hit = len(core) - len(missing)
        # 书本菜谱不加来源优先分（规则：书籍不参与排名加成）
        score = hit * 2 + (2 if ad == "high" else 0) - (r["difficulty"] - 1)
        # 预选语义加分：explicitly_wanted > accepted_batch > merely_allowed
        wanted_set = set(filter(None, args.wanted.split(",")))
        accepted_set = set(filter(None, args.accepted.split(",")))
        for c in core:
            if c in wanted_set:
                score += DECISION_BONUS["explicitly_wanted"]
            elif c in accepted_set:
                score += DECISION_BONUS["accepted_batch"]
        scored.append((score, sorted(missing), src_tag, r))

    scored.sort(key=lambda x: -x[0])

    # round60：recipe_fingerprint 去重——主蛋白族＋核心蔬菜族＋烹法＋主要风味＋菜品形态
    # 相同指纹只保留最高分代表，候选数量不得虚高
    fam_map = {}
    try:
        cat_doc = json.load(open(os.path.join(DATA, "ingredient-catalog.json"), encoding="utf-8"))
        fam_map = {k: v.get("ingredient_family") for k, v in cat_doc.get("items", {}).items()}
    except OSError:
        fam_map = {}
    PROTEIN_FAMS = {"poultry", "pork", "beef", "lamb", "fish", "shellfish", "egg", "soy"}

    def family_of(name):
        if name in fam_map and fam_map[name]:
            return fam_map[name]
        for k, v in fam_map.items():
            if v and (k in name or name in k):
                return v
        return None

    def fingerprint(r):
        fams = [(family_of(c) or "other") for c in r["core_ingredients"]]
        prot = next((f for f in fams if f in PROTEIN_FAMS), "none")
        veg = next((f for f in fams if f not in PROTEIN_FAMS and f != "flavor"), "none")
        return "|".join([prot, veg, "+".join(sorted(r.get("methods") or [])),
                         "+".join(sorted(r.get("flavors") or [])), r.get("structure") or ""])

    candidate_count_total = len(scored)
    seen_fp, deduped = {}, []
    for item in scored:
        fp = fingerprint(item[3])
        if fp in seen_fp:
            continue
        seen_fp[fp] = item[3]["original_name"]
        item[3]["recipe_fingerprint"] = fp
        deduped.append(item)
    scored = deduped
    candidate_count_after_dedup = len(scored)

    # 来源配比：书本菜谱最多占 book_quota
    cap = int(args.limit * args.book_quota)
    picked, n_book = [], 0
    for item in scored:
        is_book = item[2].startswith("book:")
        if is_book and n_book >= cap:
            continue
        n_book += is_book
        picked.append(item)
        if len(picked) >= args.limit:
            break

    # round60/62：选择审计（canonical 字段名见 schemas/selection-audit.schema.json；
    # 未计算字段记 null，不伪造数值）
    if args.audit_report:
        audit = {
            "candidate_count_before_dedup": candidate_count_total,
            "candidate_count_after_dedup": candidate_count_after_dedup,
            "recipe_source_count": len({p[2] for p in picked}),
            "technique_count": len({m for p in picked for m in (p[3].get("methods") or [])}) or None,
            "cuisine_count": None,
            "seasonal_candidate_count": None,
            "selected_recipe_ids": [p[3]["original_name"] for p in picked],
            "selected_source_ids": sorted({p[2] for p in picked}),
            "selected_fingerprints": [p[3].get("recipe_fingerprint") for p in picked],
            "history_repeat_count": None,
            "rejected_reason_counts": None,
            "diversity_gate_result": None,
            "excluded_by_dish_category": excluded_cat_count,
            "release_gate": "approved_only",
        }
        if mode_schedule_hash:
            audit["mode_schedule_hash"] = mode_schedule_hash
        with open(args.audit_report, "w", encoding="utf-8") as f:
            json.dump(audit, f, ensure_ascii=False, indent=2)
        print(f"选择审计：{args.audit_report}"
              f"（候选 {candidate_count_total} → 指纹去重后 {candidate_count_after_dedup} → 入选 {len(picked)}）")
    # 预选闭环：accepted_batch / explicitly_wanted 未入选项补偿搜索与追溯
    wanted = list(filter(None, args.wanted.split(",")))
    accepted = list(filter(None, args.accepted.split(",")))
    if accepted or wanted or args.selection_report:
        results = coverage_gate(accepted, wanted, pool, basket, allowed_extra, adapt_key, args, equipment)
        unresolved = [r for r in results if r["menu_status"] == "not_selected"]
        if args.selection_report:
            with open(args.selection_report, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"selection report：{args.selection_report}（{len(results)} 项，未入选 {len(unresolved)} 项）")
        for r in results:
            if r["menu_status"] == "not_selected":
                print(f"  [未入选] {r['ingredient']}：{','.join(r['reason_codes'])}"
                      + (f"；最高分候选：{r['top_candidate']}" if r.get("top_candidate") else ""))
            elif r["menu_status"] == "compensation_candidate":
                print(f"  [可补偿] {r['ingredient']} → 候选 {r['candidate_count']} 道（最高：{r['top_candidate']}），可替换：{r['swap_target_meal']}")

    print(f"模式={args.mode} · ≤{args.max_minutes}min · 候选 {len(scored)} 道"
          f"（前 {len(picked)}，其中书本菜谱 {n_book} 道）\n")
    for score, missing, src_tag, r in picked:
        fp = f"{first_of(r.get('core_ingredients'), '-')}|{first_of(r.get('methods'), '-')}|{first_of(r.get('flavors'), '-')}|{r.get('structure','-')}"
        note = f"；缺 {'、'.join(missing)}" if missing else ""
        tag = "" if src_tag == "howtocook" else f"《{src_tag[5:]}》"
        print(f"  [{score:>2}] {r['original_name']}{tag}（{r['category']}·{r['estimated_active_minutes']}min·"
              f"难度{'★'*r['difficulty']}）指纹:{fp}{note}")
        if r["modification_notes"]:
            print(f"       适配: {first_of(r.get('modification_notes'), '')}")


if __name__ == "__main__":
    main()


# 一人食正餐结构白名单/黑名单（与 SKILL.md「一人食模式」一致）
ONE_POT_ALLOWED_STRUCTURES = (
    "true_one_pot",                    # 一口锅完成全部（焖饭/汤锅/烩菜）
    "synchronized_one_cooker",         # 同一厨具一次程序（电饭煲上蒸下煮/蒸锅同屉）
    "one_hot_dish_plus_ready_staple",  # 一个热菜 + 即食主食
    "one_hot_dish_plus_no_cook_side",  # 一个热菜 + 免煮配菜
)
ONE_POT_DENIED_STRUCTURES = (
    "two_independent_hot_dishes",      # 两个独立热菜
    "two_dishes_one_soup",             # 两菜一汤
    "multi_pan",                       # 多锅并行
)


def apply_one_pot_rule(candidates, is_one_person, log=None):
    """一人食模式硬过滤：正餐只保留一锅出结构（焖饭/汤锅/烩菜/蒸菜套餐）。

    结构判定优先级：① 显式 meal_structure 字段——在白名单内放行、在黑名单内剔除；
    ② 无该字段时按 cookware_count/dish_count 推断（>1 锅或多菜剔除）；
    ③ 元数据缺失时不放行也不剔除——记入 log，由人工补齐字段后再启用过滤（不得伪造字段）。
    一锅出菜谱排序加权 +50。"""
    if not is_one_person:
        return candidates
    filtered, unknown = [], []
    for c in candidates:
        ms = c.get("meal_structure")
        if ms in ONE_POT_DENIED_STRUCTURES:
            continue
        if ms in ONE_POT_ALLOWED_STRUCTURES:
            filtered.append(c)
            continue
        cw, dc = c.get("cookware_count"), c.get("dish_count")
        if cw is None or dc is None:
            unknown.append(c.get("name", "?"))
            filtered.append(c)  # 元数据缺失：放行但记录
            continue
        if cw <= 1 and dc == 1:
            filtered.append(c)
    if unknown and log is not None:
        log.append(f"one_pot 元数据缺失放行: {unknown}")
    for c in filtered:
        if c.get("style") == "one_pot" or c.get("meal_structure") in ONE_POT_ALLOWED_STRUCTURES:
            c["score"] = c.get("score", 0) + 50
    return filtered
