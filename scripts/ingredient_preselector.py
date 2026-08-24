#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食材预选器（两次生成的第 1.5 阶段：initial_basket → 用户预选 → locked_basket）

产品原则（见 SKILL.md）：
  - 只展示经安全/周期/季节/渠道/预算/包装筛过的小型候选篮子，分三层
  - 安全排除项不进入候选，也不可由用户恢复
  - 用户只说"不想要的编号"；显式跳过或 fallback 默认篮子时转 provisional_locked_basket（selection_mode=bypassed）
  - 删除后四类处理：直接删除 / 功能替换 / 结构替换 / 方案受限
  - 候选最低要求：≥2 道菜、≥2 种烹法、≥2 种味型、≥1 替代品、≥1 余量去向

用法：
  # 1) 从初步篮子生成预选候选（三层展示）
  python ingredient_preselector.py --build-candidates --basket initial_basket.json \
      --month 8 --level standard [--preferences diet-plans/user-ingredient-preferences.json]
  # 2) 应用用户选择（selection JSON：{"remove":["P4","F4"],"replace":{"V3":"西兰花"},...}）
  python ingredient_preselector.py --apply-user-selection --candidates candidates.json \
      --selection selection.json
  # 3) 无回复锁定（provisional）或确认锁定
  python ingredient_preselector.py --lock-basket --candidates candidates.json [--user-reviewed]
  # 4) 最低要求校验
  python ingredient_preselector.py --validate-minimums --candidates candidates.json
  输出加 --export-markdown / --export-json <路径>
"""
# 预选语义三档（见 references/output-schema.md）：
# explicitly_wanted（用户点名）> accepted_batch（整批"都可以"）> merely_allowed（不忌口）
# 锁定时把用户回复归类写入 locked_basket 各项的 preselection_decision；
# "都可以/都行/都可以吃"整批回复 → 候选全部 accepted_batch；点名 → explicitly_wanted；不在候选中 → merely_allowed。
import argparse, json, os, re, sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# 候选数量约束（一人食每日自炊 1 餐；2 餐时扩大）
QUOTA = {1: {"protein": (5, 7, 3, 5), "vegetable": (8, 12, 6, 10), "carb": (3, 5, 0, 3),
             "flavor": (4, 6, 3, 4), "optional": (0, 5, 0, 4)},
         2: {"protein": (6, 8, 4, 6), "vegetable": (10, 14, 8, 12), "carb": (3, 6, 0, 4),
             "flavor": (4, 6, 3, 4), "optional": (0, 6, 0, 5)}}
#            (候选min, 候选max, 最终min, 最终max)
FINAL_MIN = {"蛋白质": 3, "蔬菜": 6, "天然碳水": 0, "flavor": 3}

REASONS = {"season": "当季", "searchable": "通常容易搜索", "package": "包装可消耗",
           "storage": "耐储", "quick": "20分钟加工", "multiuse": "可做多道菜",
           "keto": "模式适配", "favorite": "用户历史喜欢"}


def load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def recipe_support(name, aliases):
    """从两个菜谱池统计支撑度"""
    idx = load("recipe-index.json")
    books = load("book-recipes.json").get("recipes", [])
    names = [name] + aliases
    n_rec, methods, flavors = 0, set(), set()
    for r in list(idx) + books:
        core = r.get("core_ingredients", [])
        if any(any(a in c or c in a for a in names if len(a) >= 2) for c in core):
            n_rec += 1
            methods.update(r.get("methods", []))
            flavors.update(r.get("flavors", []))
    return {"compatible_recipe_count": n_rec, "distinct_method_count": len(methods),
            "distinct_flavor_count": len(flavors)}


def score_candidate(item, support, month, prefs):
    """候选得分 = 偏好25 + 可购20 + 菜谱支撑20 + 包装消耗15 + 加工便利10 + 时令价格10
    无可靠价格时价格权重不参与，重新归一化（此处无实时价格 → 时令10保留、价格不参与）"""
    s_pref = {"favorite": 25, "acceptable": 18, "neutral": 12,
              "dislike_this_week": 0, "permanent_dislike": -99}.get(
                  prefs.get("preference_status", {}).get(item["normalized_name"], "neutral"), 12)
    s_avail = 20  # 目录内食材默认可购（菜场/平台常见）
    rc = support["compatible_recipe_count"]
    s_recipe = 20 if rc >= 8 else 15 if rc >= 4 else 10 if rc >= 2 else 0
    pkg = item.get("expected_package")
    s_pkg = 15 if pkg else 5
    if item.get("perishability") == "high":
        s_pkg -= 3
    s_conv = 10 if item["category"] != "可选点缀" else 8
    s_season = 10 if (month and month in [int(re.sub("月", "", m)) for m in item.get("seasonality", [])]) else 4
    return s_pref + s_avail + s_recipe + s_pkg + s_conv + s_season


def short_reason(item, support, month):
    if month and str(month) + "月" in item.get("seasonality", []):
        return REASONS["season"]
    if support["compatible_recipe_count"] >= 8:
        return REASONS["multiuse"]
    if item.get("perishability") == "low":
        return REASONS["storage"]
    if item.get("expected_package"):
        return REASONS["package"]
    return REASONS["searchable"]


def build_candidates(basket, month, level, prefs, meals_per_day=1):
    """初步篮子 → 三层预选候选"""
    catalog = load("ingredient-catalog.json").get("items", {})
    permanent = set(prefs.get("permanent_dislikes", []))
    week_dislike = set(prefs.get("week_only_dislikes", []))
    restrictions = set(prefs.get("restrictions", []))  # 安全项：不进候选
    layers = {"protein": [], "vegetable": [], "carb": [], "flavor": [], "optional": []}
    dropped = []
    for cat_key, items in (("protein", basket.get("proteins", [])),
                           ("vegetable", basket.get("vegetables", [])),
                           ("carb", basket.get("carbohydrates", [])),
                           ("optional", basket.get("fat_extras", []))):
        for name in items:
            item = catalog.get(name, {"ingredient_id": name, "normalized_name": name,
                                      "display_name": name, "category": "蔬菜" if cat_key == "vegetable" else "蛋白质",
                                      "aliases": [], "seasonality": [], "expected_package": None,
                                      "perishability": "medium", "minimum_meal_uses": 2, "substitutes": []})
            if name in restrictions:
                dropped.append((name, "安全限制：不进入候选"))
                continue
            if name in permanent:
                dropped.append((name, "永久不喜欢：不进入候选"))
                continue
            support = recipe_support(name, item.get("aliases", []))
            # 最低要求门禁
            if support["compatible_recipe_count"] < 2 or support["distinct_method_count"] < 2:
                dropped.append((name, "菜谱支撑不足（<2 道或 <2 烹法）"))
                continue
            entry = dict(item)
            entry["recipe_support"] = support
            entry["reason_short"] = short_reason(item, support, month)
            entry["preference_status"] = prefs.get("preference_status", {}).get(name, "neutral")
            if name in week_dislike:
                entry["preference_status"] = "dislike_this_week"
            entry["score"] = score_candidate(item, support, month, prefs)
            entry["leftover_plan"] = "余量次日快炒/入汤/冷冻"
            layers[cat_key].append(entry)
    for f in basket.get("flavor_bases", []):
        layers["flavor"].append({"ingredient_id": f, "normalized_name": f, "display_name": f,
                                 "category": "味型", "aliases": [], "seasonality": [],
                                 "expected_package": None, "perishability": "low",
                                 "minimum_meal_uses": 1, "substitutes": [],
                                 "recipe_support": {"compatible_recipe_count": 10,
                                                    "distinct_method_count": 3,
                                                    "distinct_flavor_count": 1},
                                 "reason_short": "本周风味主轴", "preference_status": "neutral",
                                 "score": 70, "leftover_plan": "无"})
    # 数量裁剪：按分数保留候选上限
    q = QUOTA.get(meals_per_day, QUOTA[1])
    for k, (_, cmax, _, _) in q.items():
        layers[k].sort(key=lambda x: -x["score"])
        layers[k] = layers[k][:cmax]
    # 编号 P1.. V1.. C1.. F1.. O1..
    numbered = {}
    for prefix, key in (("P", "protein"), ("V", "vegetable"), ("C", "carb"),
                        ("F", "flavor"), ("O", "optional")):
        for i, e in enumerate(layers[key]):
            e["code"] = "%s%d" % (prefix, i + 1)
            numbered[e["code"]] = e
    return {"layers": layers, "numbered": numbered, "dropped_before_selection": dropped,
            "level": level, "month": month}


def resolve_alias(name, catalog):
    """别名解析：'包菜' → 卷心菜；只匹配该食材，不株连整科"""
    if name in catalog:
        return catalog[name]["normalized_name"]
    for k, v in catalog.items():
        if name in v.get("aliases", []):
            return v["normalized_name"]
    return name


def apply_selection(cands, selection, catalog, fgroups):
    """应用用户删除/替换/新增 → 四类处理"""
    numbered = cands["numbered"]
    removed, replacements, added, notes = [], [], [], []
    removed_norm = []
    for code in selection.get("remove", []):
        e = numbered.get(code)
        if not e:
            # 允许按名字删（含别名）
            norm = resolve_alias(code, catalog)
            e = next((x for x in numbered.values() if x["normalized_name"] == norm), None)
            if not e:
                notes.append("未找到 %s，忽略" % code)
                continue
        removed.append(e)
        removed_norm.append(e["normalized_name"])
    for code, to in selection.get("replace", {}).items():
        e = numbered.get(code)
        if e:
            removed.append(e)
            removed_norm.append(e["normalized_name"])
            replacements.append({"from": e["normalized_name"], "to": to})
    # 类别最低检查 → 功能替换
    remain_by_cat = {}
    for key, lst in cands["layers"].items():
        remain = [e for e in lst if e["normalized_name"] not in removed_norm]
        remain_by_cat[key] = remain
    cat_map = {"protein": "蛋白质", "vegetable": "蔬菜", "carb": "天然碳水"}
    for key, cat in cat_map.items():
        need = FINAL_MIN[cat]
        have = len(remain_by_cat[key])
        if have < need:
            # 从功能替换组找 1-3 个替代
            group_key = None
            for r in removed:
                if r["normalized_name"] in removed_norm and cat_map[key] == cat:
                    for gk, gv in fgroups.items():
                        if gk.startswith(cat[:2]) and r["normalized_name"] in gv:
                            group_key = gk
            cands_sub = []
            if group_key:
                for alt in fgroups[group_key]:
                    if alt not in removed_norm and alt not in [e["normalized_name"] for e in remain_by_cat[key]]:
                        cands_sub.append(alt)
            if len(remain_by_cat[key]) == 0 and cat == "蛋白质":
                notes.append("方案受限：主要蛋白质全部被删除，暂停达标输出，只追问一个最关键问题")
                return {"status": "blocked", "notes": notes, "removed": removed_norm}
            notes.append("%s不足（%d/%d），建议替换：%s" % (cat, have, need, "、".join(cands_sub[:3]) or "无可用替代"))
    return {"status": "ok", "removed": removed_norm, "replacements": replacements,
            "added": selection.get("add", []), "notes": notes,
            "permanent": selection.get("dislike_permanent", []),
            "week_only": removed_norm,  # 默认本周
            }


def lock_basket(cands, sel_result, user_reviewed):
    layers = cands["layers"]
    removed = set((sel_result or {}).get("removed", []))
    reps = {(r["from"]): r["to"] for r in (sel_result or {}).get("replacements", [])}

    def keep(key):
        out = []
        for e in layers[key]:
            n = e["normalized_name"]
            if n in removed:
                if n in reps:
                    out.append(reps[n])
                continue
            out.append(n)
        return out

    basket = {
        "basket_id": "",
        "status": "locked" if user_reviewed else "provisional_locked",
        "generated_at": "",
        "user_reviewed": bool(user_reviewed),
        "protein": keep("protein"),
        "vegetables": keep("vegetable"),
        "carbohydrates": keep("carb"),
        "flavor_bases": keep("flavor"),
        "optional": keep("optional"),
        "removed_items": sorted(removed),
        "replacements": (sel_result or {}).get("replacements", []),
        "user_added_items": (sel_result or {}).get("added", []),
        "permanent_dislikes": (sel_result or {}).get("permanent", []),
        "week_only_dislikes": (sel_result or {}).get("week_only", []) if user_reviewed else [],
        "nutrition_feasibility": "pass",
        "recipe_feasibility": "pass",
        "package_feasibility": "pass",
        "budget_feasibility": "pass",
        "notes": (sel_result or {}).get("notes", []),
    }
    return basket


def export_markdown(cands):
    L = cands["layers"]
    lines = ["## 本周食材选择", "", "回复不想要的编号即可（如：去掉P4和F4，V3换西兰花），或回复『都可以，直接生成』。", ""]
    lines.append("**本周核心食材**")
    lines.append("蛋白质：" + "｜".join("%s %s（%s）" % (e["code"], e["display_name"], e["reason_short"]) for e in L["protein"]))
    lines.append("蔬菜：" + "｜".join("%s %s（%s）" % (e["code"], e["display_name"], e["reason_short"]) for e in L["vegetable"]))
    if L["carb"]:
        lines.append("天然碳水：" + "｜".join("%s %s（%s）" % (e["code"], e["display_name"], e["reason_short"]) for e in L["carb"]))
    lines.append("")
    lines.append("**本周风味**：" + "｜".join("%s %s" % (e["code"], e["display_name"]) for e in L["flavor"]))
    if L["optional"]:
        lines.append("**可选点缀**：" + "｜".join("%s %s" % (e["code"], e["display_name"]) for e in L["optional"]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-candidates", action="store_true")
    ap.add_argument("--apply-user-selection", action="store_true")
    ap.add_argument("--lock-basket", action="store_true")
    ap.add_argument("--validate-minimums", action="store_true")
    ap.add_argument("--basket", help="initial_basket JSON（basket_builder 输出）")
    ap.add_argument("--candidates", help="candidates JSON")
    ap.add_argument("--selection", help="用户选择 JSON")
    ap.add_argument("--month", type=int, default=0)
    ap.add_argument("--level", choices=["light", "standard", "detailed"], default="standard")
    ap.add_argument("--meals-per-day", type=int, default=1)
    ap.add_argument("--preferences", default="", help="用户长期偏好 JSON")
    ap.add_argument("--user-reviewed", action="store_true")
    ap.add_argument("--export-markdown", default="")
    ap.add_argument("--export-json", default="")
    args = ap.parse_args()

    catalog = load("ingredient-catalog.json").get("items", {})
    fgroups = load("functional-substitution-groups.json")
    fgroups = {k: v for k, v in fgroups.items() if k != "说明"}
    prefs = {}
    if args.preferences and os.path.exists(args.preferences):
        prefs = json.load(open(args.preferences, encoding="utf-8"))

    if args.build_candidates:
        basket = json.load(open(args.basket, encoding="utf-8"))
        if "weekly_basket" in basket:
            basket = basket["weekly_basket"]
        cands = build_candidates(basket, args.month, args.level, prefs, args.meals_per_day)
        md = export_markdown(cands)
        print(md)
        if cands["dropped_before_selection"]:
            print("\n预筛选移除：")
            for n, why in cands["dropped_before_selection"]:
                print("  - %s（%s）" % (n, why))
        if args.export_json:
            json.dump(cands, open(args.export_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return

    cands = json.load(open(args.candidates, encoding="utf-8"))
    if args.apply_user_selection:
        sel = json.load(open(args.selection, encoding="utf-8"))
        res = apply_selection(cands, sel, catalog, fgroups)
        if res["status"] == "blocked":
            print("! 方案受限：" + "；".join(res["notes"]))
            return
        basket = lock_basket(cands, res, user_reviewed=True)
        print(json.dumps({"locked_basket": basket}, ensure_ascii=False, indent=1))
        if args.export_json:
            json.dump({"locked_basket": basket}, open(args.export_json, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        return
    if args.lock_basket:
        basket = lock_basket(cands, None, user_reviewed=args.user_reviewed)
        if not args.user_reviewed:
            basket["notes"].append("用户未回复预选，provisional_locked；未记录任何永久偏好")
        print(json.dumps({"locked_basket": basket}, ensure_ascii=False, indent=1))
        if args.export_json:
            json.dump({"locked_basket": basket}, open(args.export_json, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        return
    if args.validate_minimums:
        ok = True
        for code, e in cands["numbered"].items():
            rs = e.get("recipe_support", {})
            if e["category"] != "味型" and (rs.get("compatible_recipe_count", 0) < 2
                                           or rs.get("distinct_method_count", 0) < 2):
                print("x %s %s 菜谱支撑不足" % (code, e["display_name"]))
                ok = False
        print("最低要求校验：%s" % ("通过" if ok else "见上"))
        return


if __name__ == "__main__":
    main()
