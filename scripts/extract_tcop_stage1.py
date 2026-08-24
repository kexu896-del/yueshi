#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The Complete One Pot（America's Test Kitchen）精读 · 阶段一（纯标准库）
只做全书候选清点与筛选，不逐道精读（阶段二需用户指令"开始阶段二"）。

输出 book-extraction/The-Complete-One-Pot/extraction/：
  00-book-profile.md / 01-chapter-map.md / parse-report.md / audit-log.md
  candidate-inventory.jsonl / equipment-map.json / stage-one-summary.md

用法：
  python3 extract_tcop_stage1.py <epub路径> [--skill-root ..]
"""
import json
import os
import re
import sys
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_book_recipes import (strip_html, clean_en_ingredient, detect_flavors,
                                  canonical_family)

BOOK_TITLE = "The Complete One Pot (America's Test Kitchen)"
CHAPTERS = [("0011", "Soups"), ("0012", "Stews and Chilis"), ("0013", "Chicken"),
            ("0014", "Beef"), ("0015", "Pork and Lamb"), ("0016", "Seafood"),
            ("0017", "Vegetarian"), ("0018", "Pasta and Noodles"), ("0019", "Desserts")]
EQ_CN = {"DUTCH OVEN": ("深炖锅/珐琅锅", "high", "可用深汤锅或电饭煲替代"),
         "SAUCEPAN": ("小汤锅", "high", "大陆常见"),
         "SKILLET": ("平底煎锅", "high", "大陆常见"),
         "STOCKPOT": ("大汤锅", "high", "大陆常见"),
         "SHEET PAN": ("烤盘", "medium", "需烤箱；部分可改空气炸锅（需逐菜判断，不默认可行）"),
         "CASSEROLE": ("焗烤盘", "medium", "需烤箱"),
         "SLOW COOKER": ("慢炖锅", "low", "可用电饭煲保温档/明火小火替代但需看护"),
         "INSTANT POT": ("电压力锅", "medium", "大陆电压力锅通用"),
         "PRESSURE COOKER": ("压力锅", "medium", "明火压力锅通用"),
         "GRILL": ("烤架", "low", "多为户外设备"),
         "WOK": ("炒锅", "high", "大陆常见"),
         "BROILER": ("上火烤", "low", "国内烤箱多无上火独立烤管")}
NA_PROCESSED = ["crescent roll", "bisquick", "cream of ", "velveeta", "rotel", "tater tot",
                "refrigerated", "frozen dinner", "ranch dressing mix", "onion soup mix",
                "condensed", "cheez", "cornbread mix", "pie crust", "puff pastry"]
PROTEIN_EN = ["chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon", "cod", "shrimp",
              "prawn", "sausage", "bacon", "tofu", "bean", "lentil", "chickpea", "egg",
              "clams", "mussels", "scallop", "crab", "chorizo", "meatball", "steak", "ham"]
CARB_EN = ["rice", "pasta", "noodle", "potato", "bread", "tortilla", "quinoa", "barley",
           "couscous", "polenta", "grits", "beans", "lentil", "chickpea", "stuffing", "bun",
           "spaghetti", "penne", "orzo", "farro", "bulgur", "dumpling", "gnocchi", "ramen",
           "macaroni", "linguine", "fettuccine", "tortellini", "crust", "flour", "cornmeal",
           "oats", "sweet potato", "squash"]
BIG_CUT = ["whole chicken", "whole turkey", "brisket", "pork shoulder", "pork butt",
           "rib roast", "leg of lamb", "whole fish", "bone-in roast", "chuck roast",
           "short ribs", "pork loin roast", "beef roast", "turkey breast", "ham,", "rack of"]


def parse_recipe(block):
    txt = strip_html(block)
    eq = re.search(r'recipe_specs[^"]*">([^<]+)<', block)
    serves = re.search(r"<b>Serves</b>\s*([^<]+)<", block)
    ttime = re.search(r"<b>Total Time</b>\s*([^<]+)<", block)
    ings = re.findall(r'<p class="IL_item"[^>]*>(.*?)</p>', block, re.S)
    ing_names = []
    for it in ings:
        t = re.sub(r'<span class="num">([^<]*)</span>', r'\1 ', it)
        t = strip_html(t)
        nm, _ = clean_en_ingredient(t)
        if nm:
            ing_names.append(nm)
    title_m = re.search(r'class="recipe_head[^"]*"[^>]*>(.*?)</h2>', block, re.S)
    title = strip_html(title_m.group(1)).strip() if title_m else ""
    return title, (eq.group(1).strip() if eq else "other"), \
        (serves.group(1).strip() if serves else None), \
        (ttime.group(1).strip() if ttime else None), ing_names, txt


def parse_minutes(s):
    if not s:
        return None
    m = re.match(r"(\d+)\s*(?:to\s*(\d+))?\s*(hours?|minutes?)", s)
    if not m:
        return None
    v = int(m.group(2) or m.group(1))
    return v * 60 if m.group(3).startswith("hour") else v


def grade_candidate(name, chapter, eq, serves, total_min, ing_names, txt):
    """→ (decision, reasons, flags)"""
    low = (name + " " + " ".join(ing_names)).lower()
    reasons, flags = [], {}
    flags["oven_dependent"] = eq in ("SHEET PAN", "CASSEROLE") or "bake" in low or "roast" in low
    flags["pressure_dependent"] = "INSTANT POT" in eq or "PRESSURE" in eq
    flags["slowcooker_dependent"] = "SLOW COOKER" in eq
    flags["dessert"] = chapter == "Desserts"
    n_ing = len(ing_names)
    flags["ingredient_count"] = n_ing
    na_hits = [w for w in NA_PROCESSED if w in low]
    flags["na_processed"] = na_hits
    big = [w for w in BIG_CUT if w in low]
    flags["big_cut"] = big
    for_two = "for two" in name.lower()
    flags["for_two_version"] = for_two
    protein = next((i for i in ing_names if any(w in i for w in PROTEIN_EN)), None)
    carb = next((i for i in ing_names if any(w in i for w in CARB_EN)), None)

    # 决策
    if flags["dessert"]:
        reasons.append("甜点章，平衡激素期低频")
        return "exclude", reasons, flags, protein, carb
    if big:
        reasons.append("大块肉/整禽：" + "、".join(big[:2]))
    if na_hits:
        reasons.append("北美加工食品依赖：" + "、".join(na_hits[:2]))
    if total_min and total_min > 75 and not flags["slowcooker_dependent"]:
        reasons.append("总时间过长（%dmin）" % total_min)
    if eq in ("GRILL",):
        reasons.append("户外烤架依赖")
    if na_hits or (big and not for_two) or eq == "GRILL":
        return "exclude", reasons, flags, protein, carb
    if big and for_two:
        reasons.append("有 for Two 版本可缩份")
    score_a = (total_min is not None and total_min <= 45 and n_ing <= 12
               and eq in ("DUTCH OVEN", "SAUCEPAN", "SKILLET", "STOCKPOT", "WOK",
                          "INSTANT POT", "PRESSURE COOKER")
               and not big and not na_hits)
    if for_two:
        reasons.append("原书自带 2 人份版本")
    if score_a:
        if total_min and total_min <= 30:
            reasons.append("总时间≤30min")
        return "priority_A", reasons or ["一锅主厨具、时间食材量达标"], flags, protein, carb
    if flags["slowcooker_dependent"]:
        reasons.append("慢炖锅：适合周末预制")
        return "priority_B", reasons, flags, protein, carb
    if flags["oven_dependent"]:
        reasons.append("烤箱/烤盘菜：设备中等可得")
        return "priority_B", reasons, flags, protein, carb
    if total_min and total_min <= 75:
        reasons.append("时间略长或食材偏多，改造后可用")
        return "priority_B", reasons, flags, protein, carb
    return "technique_only", reasons or ["价值在单锅技法/液体规则"], flags, protein, carb


def main():
    epub = sys.argv[1]
    skill_root = sys.argv[sys.argv.index("--skill-root") + 1] if "--skill-root" in sys.argv else \
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(skill_root, "book-extraction", "The-Complete-One-Pot", "extraction")
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(epub)

    inventory = []
    eq_map = {}
    chapter_stats = []
    for part, cname in CHAPTERS:
        html = z.read("OEBPS/Text/part%s.xhtml" % part).decode("utf-8", "replace")
        heads = [(m.start(), strip_html(m.group(1)).strip())
                 for m in re.finditer(r'<h2[^>]*class="recipe_head[^"]*"[^>]*>(.*?)</h2>', html, re.S)]
        cnt = Counter()
        for i, (pos, _t) in enumerate(heads):
            end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
            block = html[pos:end]
            title, eq, serves, ttime, ing_names, txt = parse_recipe(block)
            if not title:
                continue
            total_min = parse_minutes(ttime)
            decision, reasons, flags, protein, carb = grade_candidate(
                title, cname, eq, serves, total_min, ing_names, txt)
            if eq not in eq_map:
                cn, avail, note = EQ_CN.get(eq.upper(), ("其他", "medium", ""))
                eq_map[eq] = {"equipment": eq, "大陆对应": cn, "大陆常见性": avail,
                              "适配建议": note, "recipe_count": 0}
            eq_map[eq]["recipe_count"] += 1
            inventory.append({
                "id": "tcop-%03d" % (len(inventory) + 1),
                "name": title,
                "source": {"book": BOOK_TITLE, "chapter": cname,
                           "location": "part%s#%d" % (part, pos)},
                "servings": serves, "equipment": eq,
                "total_time": ttime, "total_minutes": total_min,
                "protein": protein, "primary_vegetable": None, "carb": carb,
                "ingredient_count": flags["ingredient_count"],
                "na_processed_dependencies": flags["na_processed"],
                "big_cut": flags["big_cut"], "for_two_version": flags["for_two_version"],
                "oven_dependent": flags["oven_dependent"],
                "pressure_dependent": flags["pressure_dependent"],
                "slowcooker_dependent": flags["slowcooker_dependent"],
                "one_pot_authentic": eq.upper() in EQ_CN,
                "scalable_to_1_2": flags["for_two_version"] or (serves or "").startswith(("2", "4")),
                "preliminary_decision": decision,
                "reasons": reasons,
                "confidence": "high" if ing_names else "medium",
                "flavors": detect_flavors(title + " " + " ".join(ing_names), zh=False),
            })
            cnt[decision] += 1
        chapter_stats.append((cname, len(heads), dict(cnt)))

    with open(os.path.join(out_dir, "candidate-inventory.jsonl"), "w", encoding="utf-8") as f:
        for r in inventory:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "equipment-map.json"), "w", encoding="utf-8") as f:
        json.dump(eq_map, f, ensure_ascii=False, indent=1)

    dec_all = Counter(r["preliminary_decision"] for r in inventory)
    with open(os.path.join(out_dir, "00-book-profile.md"), "w", encoding="utf-8") as f:
        f.write("# The Complete One Pot 书籍档案\n\n- 作者：America's Test Kitchen\n"
                "- 结构：9 个菜谱章（按蛋白/类型）+ 营养信息附录\n"
                "- 处理策略：两阶段；本目录当前仅阶段一（候选清点），阶段二待指令\n"
                "- 版权：仅存菜名、份数、设备、时间、食材名（事实），无步骤原文\n")
    with open(os.path.join(out_dir, "01-chapter-map.md"), "w", encoding="utf-8") as f:
        f.write("# 章节地图\n\n")
        for cname, n, cnt in chapter_stats:
            f.write("- %s：%d 道（A %d / B %d / technique %d / exclude %d）\n"
                    % (cname, n, cnt.get("priority_A", 0), cnt.get("priority_B", 0),
                       cnt.get("technique_only", 0), cnt.get("exclude", 0)))
    with open(os.path.join(out_dir, "parse-report.md"), "w", encoding="utf-8") as f:
        f.write("# 解析报告\n\n- EPUB 直读，无 DRM，无 OCR 依赖\n"
                "- recipe_head 标记规整：%d 个菜谱块全部解析\n" % len(inventory))
    with open(os.path.join(out_dir, "audit-log.md"), "w", encoding="utf-8") as f:
        f.write("# 审计日志\n\n- 阶段一完成：%d 道候选清点\n- 决策分布：%s\n"
                "- 阶段二未启动（等待指令）\n" % (len(inventory), dict(dec_all)))
    # 阶段一总结
    with open(os.path.join(out_dir, "stage-one-summary.md"), "w", encoding="utf-8") as f:
        f.write("# 阶段一总结\n\n")
        f.write("## 决策分布\n\n")
        for d, n in dec_all.most_common():
            f.write("- %s：%d 道\n" % (d, n))
        f.write("\n## priority_A 清单（%d 道）\n\n" % dec_all.get("priority_A", 0))
        for r in inventory:
            if r["preliminary_decision"] == "priority_A":
                f.write("- %s %s（%s · %s · %s · %d种食材）\n"
                        % (r["id"], r["name"], r["chapter"] if "chapter" in r else r["source"]["chapter"],
                           r["equipment"], r["total_time"], r["ingredient_count"]))
        f.write("\n## 设备依赖\n\n")
        for eq, v in sorted(eq_map.items(), key=lambda x: -x[1]["recipe_count"]):
            f.write("- %s → %s（%d 道；%s）\n" % (eq, v["大陆对应"], v["recipe_count"], v["适配建议"]))
        f.write("\n## 人工复核项\n\n")
        for r in inventory:
            if r["confidence"] != "high":
                f.write("- %s %s：食材行解析不足\n" % (r["id"], r["name"]))
    print("TCOP 阶段一：%d 道候选 | %s" % (len(inventory), dict(dec_all)))


if __name__ == "__main__":
    main()
