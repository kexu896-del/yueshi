#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The Complete One Pot 精读 · 阶段二（纯标准库）
处理：全部 priority_A + priority_B 中一人食适配最高的前 80 道（每批≤20，内部连续跑批）
不处理 exclude；technique_only 只在审计中保留技法清单。

输出追加到 book-extraction/The-Complete-One-Pot/extraction/：
  selected-recipes.jsonl / weeknight-grades.jsonl / scaling-risk-report.jsonl
  mainland-substitutions.json / canonical-families.json / stage-two-audit.md
并把入选菜谱并入 data/book-recipes.json（id 前缀 tcop-）

用法：
  python3 extract_tcop_stage2.py <epub路径> [--skill-root ..]
"""
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_book_recipes import (strip_html, clean_en_ingredient, detect_methods,
                                  detect_flavors, canonical_family, mode_fit,
                                  drop_seasonings)
from extract_tcop_stage1 import CHAPTERS, parse_recipe, parse_minutes, BOOK_TITLE

BATCH = 20

# 本地化替换（大陆名称/搜索词/可否省略/影响）
SUBS = {
    "chicken broth": ("鸡汤/浓汤宝", "可用浓汤宝半块+水；钠偏高减量"),
    "beef broth": ("牛肉高汤/浓汤宝", "同上"),
    "vegetable broth": ("蔬菜高汤/清水+浓汤宝", "同上"),
    "canned diced tomatoes": ("番茄罐头", "盒马/进口超市；或鲜番茄2个+番茄膏"),
    "crushed tomatoes": ("番茄碎罐头", "同上"),
    "tomato paste": ("番茄膏", "小包装，开封冷藏分装"),
    "tomato sauce": ("番茄沙司（无糖醋版）", "注意含糖"),
    "canned beans": ("罐头豆/干豆自煮", "鹰嘴豆芸豆均有罐头"),
    "sour cream": ("酸奶油", "可用无糖希腊酸奶替代"),
    "heavy cream": ("淡奶油", "小盒装，余量做酱/甜品"),
    "cream cheese": ("奶油奶酪", "盒马有售"),
    "cheddar": ("切达奶酪", "可换马苏里拉"),
    "parmesan": ("帕玛森", "买小块磨粉；可长期保存"),
    "feta": ("菲达奶酪", "盒马；或省略"),
    "monterey jack": ("蒙特利杰克奶酪", "换马苏里拉"),
    "fresh thyme": ("鲜百里香", "换干百里香1/3量"),
    "fresh rosemary": ("鲜迷迭香", "换干料1/3量"),
    "fresh oregano": ("鲜牛至", "换干牛至"),
    "fresh basil": ("鲜罗勒", "叮咚有售；或干罗勒"),
    "cilantro": ("香菜", "菜场常见"),
    "worcestershire": ("辣酱油（喼汁）", "进口超市；可省略+少许生抽醋"),
    "dijon mustard": ("第戎芥末", "进口超市；黄芥末酱替代"),
    "white wine": ("白葡萄酒", "可用料酒+少许醋"),
    "red wine": ("红葡萄酒", "可用料酒"),
    "dry sherry": ("干雪莉酒", "料酒替代"),
    "chorizo": ("西班牙辣肠", "川味腊肠近似替代"),
    "andouille": ("烟熏辣肠", "烟熏腊肠替代"),
    "pancetta": ("意式腌肉", "培根替代"),
    "prosciutto": ("意式火腿", "宣威火腿薄片"),
    "kielbasa": ("波兰熏肠", "哈尔滨红肠近似"),
    "italian sausage": ("意式香肠", "去肠衣可用猪肉末+茴香籽替代"),
    "egg noodles": ("鸡蛋面", "挂面替代"),
    "orzo": ("米粒面", "换小形意面或米饭"),
    "couscous": ("库斯库斯", "换小米（蒸煮法）"),
    "quinoa": ("藜麦", "盒马/电商"),
    "farro": ("法罗小麦", "换大麦粒/糙米"),
    "bulgur": ("布格麦", "换碎小麦/小米"),
    "polenta": ("玉米糊", "玉米面调制"),
    "panko": ("日式面包糠", "普通面包糠"),
    "tortilla": ("墨西哥薄饼", "盒马；或烙饼"),
    "tomatillo": ("黏果酸浆", "无可替代物，换青番茄+青柠"),
    "adobo chipotle": ("烟熏辣酱", "辣椒粉+烟熏红椒粉近似"),
    "sriracha": ("是拉差辣酱", "盒马有售"),
    "hoisin": ("海鲜酱", "超市常见"),
    "fish sauce": ("鱼露", "超市常见"),
    "coconut milk": ("椰浆", "纸盒装，开封分装冷冻"),
    "red curry paste": ("红咖喱酱", "泰式咖喱酱盒马有售"),
    "kimchi": ("韩式泡菜", "超市/盒马常见"),
    "sun-dried tomatoes": ("油浸番茄干", "进口超市；可省略"),
    "kalamata olives": ("黑橄榄", "罐头黑橄榄"),
    "capers": ("刺山柑", "可省略或换酸黄瓜碎"),
    "buttermilk": ("酪浆", "牛奶+少许柠檬汁静置10分钟"),
}


def parse_steps(block):
    steps = re.findall(r'<p class="method"[^>]*>(.*?)</p>', block, re.S)
    out = []
    for s in steps:
        t = strip_html(re.sub(r'<span class="meth">[^<]*</span>', '', s))
        out.append(t.strip())
    return out


def solo_score(c):
    """priority_B 排序分：食材少、时间短、for_two、设备常见、无大块肉"""
    s = 0
    s += max(0, 14 - c["ingredient_count"])
    if c["total_minutes"]:
        s += max(0, (60 - c["total_minutes"]) // 5)
    if c["for_two_version"]:
        s += 5
    if c["equipment"] in ("SKILLET", "SAUCEPAN", "DUTCH OVEN", "STOCKPOT", "WOK"):
        s += 4
    if c["oven_dependent"]:
        s -= 2
    if c["slowcooker_dependent"]:
        s -= 3
    if c["na_processed_dependencies"]:
        s -= 4
    if c["big_cut"]:
        s -= 4
    if c["source"]["chapter"] == "Desserts":
        s -= 99
    return s


def weeknight_grade(total_min, n_steps, serves):
    if total_min is None:
        return "weeknight_B", {"total": None, "active_estimated": 20}
    active = min(25, max(10, int(total_min * 0.45)))  # 估算：标 estimated
    if total_min <= 30 and active <= 15:
        return "weeknight_A", {"total": total_min, "active_estimated": active}
    if total_min <= 45 and active <= 20:
        return "weeknight_B", {"total": total_min, "active_estimated": active}
    if total_min <= 75:
        return "weekend_prep", {"total": total_min, "active_estimated": active}
    return "batch_only", {"total": total_min, "active_estimated": active}


def scaling_risk(c, ing_names):
    """缩份风险评估"""
    risks = []
    if c["equipment"] in ("SHEET PAN", "CASSEROLE"):
        risks.append("烤盘面积固定，缩半易烤干，建议改小烤盘或空气炸锅（需实测）")
    if c["equipment"] in ("DUTCH OVEN", "STOCKPOT") and (c["total_minutes"] or 0) > 45:
        risks.append("小份炖煮蒸发比例增大，液体减量少于一半")
    if any("broth" in i for i in ing_names):
        risks.append("高汤用量大，缩份后余量需冷冻分装")
    if any("tomato" in i and "can" in i for i in ing_names):
        risks.append("罐头开封余量：冷藏3天或冷冻")
    if c["equipment"] in ("INSTANT POT", "PRESSURE COOKER"):
        risks.append("压力锅有最低液体量（约250ml），缩份不降液体")
    if c["slowcooker_dependent"]:
        risks.append("慢炖锅有最低装载量，不建议缩至1份")
        return "not_recommended", risks
    if not risks:
        return "low", ["常规缩份即可"]
    return ("high" if len(risks) >= 2 else "medium"), risks


def main():
    epub = sys.argv[1]
    skill_root = sys.argv[sys.argv.index("--skill-root") + 1] if "--skill-root" in sys.argv else \
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(skill_root, "book-extraction", "The-Complete-One-Pot", "extraction")
    inv = [json.loads(l) for l in open(os.path.join(out_dir, "candidate-inventory.jsonl"),
                                       encoding="utf-8")]
    pool_a = [c for c in inv if c["preliminary_decision"] == "priority_A"]
    pool_b = sorted([c for c in inv if c["preliminary_decision"] == "priority_B"],
                    key=solo_score, reverse=True)[:80]
    tech = [c for c in inv if c["preliminary_decision"] == "technique_only"]
    selected = pool_a + pool_b
    print("阶段二入选：A %d + B %d = %d（technique_only 另列 %d）"
          % (len(pool_a), len(pool_b), len(selected), len(tech)))

    z = zipfile.ZipFile(epub)
    # 建立 name → block 索引
    blocks = {}
    for part, cname in CHAPTERS:
        html = z.read("OEBPS/Text/part%s.xhtml" % part).decode("utf-8", "replace")
        heads = [(m.start(), strip_html(m.group(1)).strip())
                 for m in re.finditer(r'<h2[^>]*class="recipe_head[^"]*"[^>]*>(.*?)</h2>', html, re.S)]
        for i, (pos, t) in enumerate(heads):
            end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
            blocks[t] = (cname, html[pos:end])

    sel_recs, grades, risks = [], [], []
    subs_used = defaultdict(list)
    n_batch = 0
    for bi in range(0, len(selected), BATCH):
        batch = selected[bi:bi + BATCH]
        n_batch += 1
        for c in batch:
            if c["name"] not in blocks:
                continue
            cname, block = blocks[c["name"]]
            title, eq, serves, ttime, ing_names, txt = parse_recipe(block)
            steps = parse_steps(block)
            grade, ginfo = weeknight_grade(c["total_minutes"], len(steps), serves)
            risk, risk_notes = scaling_risk(c, ing_names)
            cn_ings, en_ings = [], []
            for nm in ing_names:
                cn, en = clean_en_ingredient(nm)
                if cn:
                    cn_ings.append(cn)
                    en_ings.append(en)
            cn_ings, en_ings = drop_seasonings(cn_ings, en_ings)
            for en in en_ings:
                for k, v in SUBS.items():
                    if k in en.lower():
                        subs_used[k].append(c["id"])
            methods = detect_methods(title + " " + " ".join(steps)[:600], zh=False)
            flavors = detect_flavors(title + " " + " ".join(ing_names), zh=False)
            rec = {
                "id": c["id"], "name": title,
                "source": {"book": BOOK_TITLE, "chapter": cname, "location": c["source"]["location"]},
                "classification": "explicit_recipe",
                "original": {"servings": serves, "total_time": ttime,
                             "equipment": eq, "ingredients": ing_names[:14],
                             "step_count": len(steps)},
                "adapted": {"servings": 1 if not c["for_two_version"] else 2,
                            "note": "原书有 for Two 版本" if c["for_two_version"] else "按 1/4 量缩份"},
                "weeknight_grade": grade, "time_detail": ginfo,
                "scaling_risk": {"level": risk, "notes": risk_notes},
                "fingerprint": {
                    "protein": c["protein"], "carb": c["carb"],
                    "methods": methods, "flavors": flavors,
                    "structure": ("汤羹" if "soup" in title.lower() or "stew" in title.lower()
                                  or "chili" in title.lower() or "chowder" in title.lower()
                                  else "一锅出"),
                    "equipment": eq},
                "core_ingredients_cn": cn_ings[:8],
                "nutrition_recalculation_required": True,
                "copyright_status": "transformed_summary",
                "confidence": c["confidence"],
                "review_notes": [],
            }
            sel_recs.append(rec)
            grades.append({"id": c["id"], "name": title, "grade": grade, **ginfo})
            risks.append({"id": c["id"], "name": title, "risk": risk, "notes": risk_notes})
        print("  批 %d：%d 道完成" % (n_batch, len(batch)))

    with open(os.path.join(out_dir, "selected-recipes.jsonl"), "w", encoding="utf-8") as f:
        for r in sel_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "weeknight-grades.jsonl"), "w", encoding="utf-8") as f:
        for g in grades:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "scaling-risk-report.jsonl"), "w", encoding="utf-8") as f:
        for g in risks:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")

    subs_out = []
    for k, v in SUBS.items():
        if k in subs_used:
            subs_out.append({"original": k, "大陆名称/搜索词": v[0], "影响": v[1],
                             "used_by_count": len(subs_used[k]), "examples": subs_used[k][:4]})
    with open(os.path.join(out_dir, "mainland-substitutions.json"), "w", encoding="utf-8") as f:
        json.dump(subs_out, f, ensure_ascii=False, indent=1)

    # 家族去重：蛋白+碳水+方法
    fam = defaultdict(list)
    for r in sel_recs:
        fp = r["fingerprint"]
        key = "%s|%s|%s" % (fp["protein"] or "-", fp["carb"] or "-",
                            (fp["methods"] or ["?"])[0])
        fam[key].append(r["id"] + " " + r["name"])
    families = {k: v for k, v in fam.items() if len(v) > 1}
    with open(os.path.join(out_dir, "canonical-families.json"), "w", encoding="utf-8") as f:
        json.dump({"families": families,
                   "rule": "同蛋白+同碳水+同烹法归并；保留采购最易、结构最清楚的为母版"},
                  f, ensure_ascii=False, indent=1)

    gc = Counter(g["grade"] for g in grades)
    rc = Counter(r["risk"] for r in risks)
    with open(os.path.join(out_dir, "stage-two-audit.md"), "w", encoding="utf-8") as f:
        f.write("# TCOP 阶段二审计\n\n")
        f.write("- 精读：%d 道（A %d + B %d，每批≤20，共 %d 批）\n"
                % (len(sel_recs), len(pool_a), len(pool_b), n_batch))
        f.write("- 工作日评级：%s\n" % dict(gc))
        f.write("- 缩份风险：%s\n" % dict(rc))
        f.write("- 独立家族：%d（重复族 %d 组）\n" % (len(fam), len(families)))
        f.write("- 本地化替换项：%d 种（全部标跨菜复用次数）\n" % len(subs_out))
        f.write("- technique_only 未精读，保留技法清单 %d 道\n" % len(tech))
        f.write("\n## 低频调料约束\n\n- 椰浆/甜酱油等跨菜使用已在 mainland-substitutions.json 标注\n"
                "- 每周新增低频调料≤1 种的规则在排菜时由 SKILL 门禁执行\n")
    # 更新 audit-log
    with open(os.path.join(out_dir, "audit-log.md"), "a", encoding="utf-8") as f:
        f.write("\n- 阶段二完成：精读 %d 道（A %d + B %d）\n" % (len(sel_recs), len(pool_a), len(pool_b)))

    # 并入统一池
    br_path = os.path.join(skill_root, "data", "book-recipes.json")
    pool = json.load(open(br_path, encoding="utf-8"))
    pool["recipes"] = [o for o in pool["recipes"] if not o["id"].startswith("tcop-")]
    for r in sel_recs:
        fp = r["fingerprint"]
        core = r["core_ingredients_cn"]
        mf = mode_fit(core, fp["flavors"], zh=False)
        pool["recipes"].append({
            "id": r["id"], "name": r["name"], "original_name": r["name"],
            "source_type": "book_adapted", "source_book": BOOK_TITLE,
            "source_location": r["source"]["location"],
            "extraction_type": "explicit_recipe",
            "core_ingredients": core, "original_ingredients": core,
            "methods": fp["methods"], "structure": fp["structure"], "flavors": fp["flavors"],
            "original_servings": r["original"]["servings"],
            "adapted_servings": r["adapted"]["servings"],
            "active_minutes": r["time_detail"]["active_estimated"],
            "total_minutes": parse_minutes(r["original"]["total_time"]),
            "mode_fit": mf, "required_modifications": [],
            "nutrition_status": "recalculation_required",
            "copyright_status": "transformed_summary",
            "canonical_recipe_family": canonical_family(r["name"]),
            "weeknight_grade": r["weeknight_grade"],
            "scaling_risk": r["scaling_risk"]["level"],
            "pool_exclude": False,
        })
    pool["meta"]["total_recipes"] = len(pool["recipes"])
    with open(br_path, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)
    print("阶段二完成：%d 道入库，统一池 %d" % (len(sel_recs), len(pool["recipes"])))


if __name__ == "__main__":
    main()
