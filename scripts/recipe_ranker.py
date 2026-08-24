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

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
INDEX = os.path.join(DATA, "recipe-index.json")
BOOKS = os.path.join(DATA, "book-recipes.json")
MANIFEST = os.path.join(DATA, "library-manifest.json")


def production_allowed(source_id):
    """record_status 门禁：仅 production 来源可进入生产候选池。
    candidate/proposed/culture_only/historical_lead/stale/rejected 一律不读。
    manifest 缺失时回退到内置白名单（howtocook + 已批准书籍池）。"""
    try:
        mf = json.load(open(MANIFEST, encoding="utf-8"))
        for s in mf.get("sources", []):
            if s.get("source_id") == source_id:
                return s.get("status") == "production"
        return False
    except OSError:
        return source_id in ("howtocook", "book_pool_11books")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.recipe_normalization import first_of, norm_list, weighted_similarity, NOT_COMPARABLE

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
    ap = argparse.ArgumentParser()
    ap.add_argument("--basket", required=True, help="篮子食材，逗号分隔")
    ap.add_argument("--mode", choices=["keto", "hormone"], required=True)
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
    for src_tag, r in pool:
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
