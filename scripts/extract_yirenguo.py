#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《一人锅：一个人的小锅料理》（小田真规子）精读提取器（纯标准库）
按 月食菜谱书精读指令.docx B 节执行：
  - 汤底家族 / 投料顺序 / 主食收尾 / 异名同构去重 / 一人食逐道评估
  - 输出 book-extraction/一人锅/extraction/ 下全部文件
  - explicit_recipe 并入 data/book-recipes.json 统一池（id 前缀 yrg-）
  - 不保存大段原文；原书未给份数/时间写 null 或 estimated

用法：
  python3 extract_yirenguo.py <epub路径> [--skill-root ..]
"""
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_book_recipes import (strip_html, detect_flavors, clean_cn_ingredient,
                                  canonical_family, SEASONING_CN)

NS = "{http://www.daisy.org/z3986/2005/ncx/}"
BOOK_TITLE = "一人锅：一个人的小锅料理（小田真规子）"
BOOK_KEY = "yrg"

BROTH_FAMILIES = [
    ("昆布柴鱼清汤", ["昆布", "柴鱼", "鲣鱼", "木鱼花", "日式高汤", "出汁"]),
    ("味噌", ["味噌"]), ("酱油", ["酱油"]), ("盐味", ["盐…", "盐味"]),
    ("豆浆", ["豆浆"]), ("番茄", ["番茄"]), ("咖喱", ["咖喱"]),
    ("泡菜", ["泡菜"]), ("辣味", ["豆瓣", "辣椒", "辣油", "韩式辣酱", "柚子胡椒"]),
    ("酸味", ["醋", "柑橘醋", "柚子醋", "柠檬"]),
    ("鸡汤", ["鸡汤", "鸡高汤", "鸡精"]), ("鱼贝汤", ["蛤蜊", "贝", "鱼露", "小鱼干", "银鱼"]),
    ("奶味", ["牛奶", "奶油", "芝士"]), ("寿喜烧风味", ["寿喜"]),
    ("芝麻油香", ["芝麻油", "香油"]), ("酒糟/酒", ["酒糟", "清酒", "米酒"]),
]
FINISH_CARBS = ["米饭", "乌冬面", "乌冬", "荞麦面", "面条", "拉面", "米粉", "粉丝",
                "年糕", "杂炊", "鸡蛋粥", "粥", "面包", "馕"]
ORDER_GROUPS = [("根茎", ["萝卜", "胡萝卜", "土豆", "藕", "山药", "芋头", "牛蒡", "洋葱", "南瓜"]),
                ("菌菇", ["香菇", "金针菇", "平菇", "杏鲍菇", "舞菇", "蟹味菇"]),
                ("肉鱼", ["肉", "鸡", "鱼", "鲑鱼", "鳕鱼", "虾", "贝", "丸"]),
                ("豆腐", ["豆腐", "油豆腐", "豆泡", "腐竹"]),
                ("叶菜", ["白菜", "菠菜", "青菜", "小松菜", "水菜", "韭菜", "生菜", "卷心菜", "茼蒿"])]
ALLERGENS = {"麸质": ["面", "乌冬", "酱油", "荞麦"], "蛋": ["蛋"], "大豆": ["豆腐", "味噌", "酱油", "豆浆"],
             "鱼类": ["鲑鱼", "鳕鱼", "金枪鱼", "银鱼", "柴鱼"], "甲壳类": ["虾", "蟹"],
             "芝麻": ["芝麻", "香油"], "乳制品": ["牛奶", "奶油", "芝士"], "花生": ["花生"]}

LOW_FREQ_JP = {  # 日式低频调料 → 大陆平替
    "柚子胡椒": ("辣椒酱+柠檬皮屑（风味近似）", "低频：每周限1种新调料"),
    "柑橘醋/柚子醋（ポン酢）": ("生抽2:米醋1+少许糖", "可自调，不必买瓶装"),
    "味噌": ("盒马/超市均有", "买小盒，味噌汤/锅/腌菜可复用"),
    "木鱼花/柴鱼片": ("可省略或用鸡精少许", "高汤风味减弱"),
    "昆布": ("干海带代替", "同科属，风味近似"),
    "清酒": ("料酒", "无差别替代"),
    "味醂": ("料酒+少许糖", "经典替代"),
    "日式高汤包": ("浓汤宝半块", "钠偏高，减量用"),
    "七味粉": ("辣椒粉+芝麻", "可省略"),
    "蛋黄酱（日式）": ("普通蛋黄酱", "无差别"),
}


def parse_recipe_page(text):
    """解析单个菜谱页（已去标签的文本）→ 字段"""
    sec = {"食材": [], "汤底": [], "酱汁": [], "steps": [], "note": ""}
    cur = None
    in_steps = False
    for ln in [l.strip() for l in text.split("\n") if l.strip()]:
        if ln.startswith("【") and "】" in ln:
            cur = ln.strip("【】").split("】")[0]
            in_steps = False
            continue
        if "制作方法" in ln:
            cur = "steps"
            in_steps = True
            continue
        m = re.match(r"^[❶❷❸❹❺❻❼]", ln)
        if in_steps or m:
            sec["steps"].append(ln)
            in_steps = True
            continue
        if cur in ("食材", "汤底", "酱汁") and "…" in ln:
            sec[cur].append(ln)
            continue
        if cur == "steps" or (sec["steps"] and not cur):
            sec["note"] += ln + " "
    return sec


def parse_ing_line(ln):
    """'菠菜（去根切成两段）…1/2把（100g）' → (菠菜, 1/2把（100g）)"""
    name, _, qty = ln.partition("…")
    name = re.sub(r"（[^）]*）", "", name).strip()
    return name, qty.strip()


def detect_broth_family(broth_lines, sauce_lines, name):
    text = " ".join(broth_lines + sauce_lines) + " " + name
    for fam, kws in BROTH_FAMILIES:
        if any(k in text for k in kws):
            return fam
    return "盐味清汤"


def order_sequence(ings):
    """投料顺序分组：按食材名单在组列表中的出现排序"""
    seq = []
    for grp, kws in ORDER_GROUPS:
        if any(any(k in i for k in kws) for i in ings):
            seq.append(grp)
    return seq


def finishing_carb(note, steps):
    text = note + " " + " ".join(steps)
    return [c for c in FINISH_CARBS if c in text]


def main():
    epub = sys.argv[1]
    skill_root = sys.argv[sys.argv.index("--skill-root") + 1] if "--skill-root" in sys.argv else \
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(skill_root, "book-extraction", "一人锅", "extraction")
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(epub)

    ncx = [n for n in z.namelist() if n.endswith(".ncx")][0]
    base = os.path.dirname(ncx)
    root = ET.fromstring(z.read(ncx))
    toc = []
    for np_ in root.iter(NS + "navPoint"):
        t = np_.find(NS + "navLabel/" + NS + "text")
        c = np_.find(NS + "content")
        if t is not None and c is not None:
            toc.append(((t.text or "").strip(), c.get("src")))

    SKIP = re.compile(r"封面|书名页|版权|快读|前言|目录|Part|第\d+章|专栏|索引|作者|小锅生活|调味料图鉴|后记")
    entries = [(t, s) for t, s in toc if not SKIP.search(t)]

    recipes, columns, chapter_map = [], [], []
    chapter = "未分章"
    for t, s in toc:
        if re.search(r"第\d+章", t):
            chapter = t
            chapter_map.append({"chapter": t, "src": s, "type": "菜谱章"})
        if re.search(r"专栏", t):
            columns.append((t, s))
            chapter_map.append({"chapter": t, "src": s, "type": "专栏/技法"})
    chapter_map.append({"chapter": "前言/小锅生活", "src": "part0004-0006", "type": "文化"})

    for title, src in entries:
        html = z.read(base + "/" + src.split("#")[0]).decode("utf-8", "replace")
        text = strip_html(html)
        # 去掉页首重复标题行
        text = text.replace(title, "", 1)
        sec = parse_recipe_page(text)
        if len(sec["食材"]) < 2:
            continue
        ings = [parse_ing_line(l) for l in sec["食材"]]
        broth = [parse_ing_line(l) for l in sec["汤底"]]
        sauce = [parse_ing_line(l) for l in sec["酱汁"]]
        ing_names = [i[0] for i in ings]
        core = [n for n in ing_names if n not in SEASONING_CN][:8]
        broth_family = detect_broth_family(sec["汤底"], sec["酱汁"], title)
        fin = finishing_carb(sec["note"], sec["steps"])
        order = order_sequence(ing_names)
        flavors = detect_flavors(" ".join(ing_names) + " " + " ".join(sec["汤底"]) + " " + title, zh=True)
        full = title + " " + " ".join(ing_names)
        allerg = [a for a, kws in ALLERGENS.items() if any(k in full for k in kws)]
        n_ings = len(ing_names)
        # 逐道评估
        quick = "10分钟" in chapter or n_ings <= 6
        rec = {
            "id": "%s-%03d" % (BOOK_KEY, len(recipes) + 1),
            "name": title,
            "source": {"book": BOOK_TITLE, "chapter": chapter, "location": src},
            "classification": "explicit_recipe",
            "original": {
                "servings": 1, "servings_note": "全书定位一人份小锅料理",
                "time_minutes": None, "time_source": "estimated",
                "estimated_minutes": 10 if "10分钟" in chapter else 20,
                "ingredients": sec["食材"], "broth": sec["汤底"], "sauce": sec["酱汁"],
                "step_count": len(sec["steps"]),
                "key_actions": [s[:20] for s in sec["steps"][:3]],
                "note_summary": sec["note"][:60] if sec["note"] else None,
            },
            "fingerprint": {
                "broth_family": broth_family,
                "protein": next((n for n in core if any(w in n for w in
                                 ["肉", "鸡", "鱼", "鲑", "鳕", "虾", "贝", "蛋", "豆腐", "金枪鱼"])), None),
                "primary_vegetable": next((n for n in core if any(w in n for w in
                                 ["菜", "菇", "萝卜", "葱", "韭菜", "洋葱", "番茄", "瓜", "笋", "豆"])), None),
                "cooking_sequence": order,
                "finishing_carb": fin,
                "flavor": flavors,
                "structure": "汤锅",
                "texture": [w for w in ["浓稠", "清爽", "滑嫩", "软糯"] if w in (sec["note"] or "")][:1],
            },
            "solo_suitability": {"decision": "direct_use",
                                 "reasons": ["原书即一人份设计"]},
            "pot_size": "小锅（约16至18cm，一人份）",
            "allergens": allerg,
            "ingredient_count": n_ings,
            "quick_10min": bool("10分钟" in chapter),
            "nutrition_recalculation_required": True,
            "confidence": "high",
            "review_notes": [] if sec["steps"] else ["步骤行未识别，需人工复核"],
        }
        recipes.append(rec)

    # ---------------- 汤底模板
    broths = {}
    for r in recipes:
        fam = r["fingerprint"]["broth_family"]
        b = broths.setdefault(fam, {"broth_family": fam, "type": "flavor_template",
                                    "recipes": [], "typical_liquid": [],
                                    "note": "原书汤底用料见各菜谱 original.broth；未给比例处不编造"})
        b["recipes"].append(r["id"] + " " + r["name"])
        for ln in r["original"]["broth"]:
            if "水…" in ln or "高汤…" in ln:
                b["typical_liquid"].append(ln)
    for b in broths.values():
        b["use_count"] = len(b["recipes"])
        b["typical_liquid"] = b["typical_liquid"][:3]
        b["solo_note"] = "一人份液体量以原书为准（多为水2杯/约400ml）"
    with open(os.path.join(out_dir, "broth-templates.json"), "w", encoding="utf-8") as f:
        json.dump(broths, f, ensure_ascii=False, indent=1)

    # ---------------- 投料顺序规则
    order_rules = {}
    for r in recipes:
        key = "→".join(r["fingerprint"]["cooking_sequence"]) or "全部下锅"
        order_rules.setdefault(key, []).append(r["id"] + " " + r["name"])
    with open(os.path.join(out_dir, "simmering-order-rules.json"), "w", encoding="utf-8") as f:
        json.dump({"rules": [{"sequence": k, "count": len(v), "examples": v[:4],
                              "principle": "根茎菌菇先下耐煮，肉鱼居中，叶菜豆腐最后防老"}
                             for k, v in sorted(order_rules.items(), key=lambda x: -len(x[1]))],
                   "general": "小锅可全部下锅后煮沸撇沫；难熟根茎建议先煮3分钟"},
                  f, ensure_ascii=False, indent=1)

    # ---------------- 主食收尾
    fin_map = defaultdict(list)
    for r in recipes:
        for c in r["fingerprint"]["finishing_carb"]:
            fin_map[c].append(r["id"] + " " + r["name"])
    fin_map["_column"] = ["专栏❺ 收尾主食的吃法：米饭/乌冬面可分小份冷冻，直接下锅无需解冻"]
    with open(os.path.join(out_dir, "finishing-carb-patterns.json"), "w", encoding="utf-8") as f:
        json.dump({k: {"carb": k, "count": len(v), "examples": v[:5],
                       "keto_note": "酮生物模式不强制加入主食，可省略收尾"}
                   for k, v in fin_map.items()}, f, ensure_ascii=False, indent=1)

    # ---------------- 组合模式（汤底×蛋白）
    asm = defaultdict(list)
    for r in recipes:
        fp = r["fingerprint"]
        key = "%s×%s" % (fp["broth_family"], fp["protein"] or "素")
        asm[key].append(r["id"] + " " + r["name"])
    with open(os.path.join(out_dir, "hotpot-assembly-patterns.json"), "w", encoding="utf-8") as f:
        json.dump([{"pattern": k, "count": len(v), "examples": v[:4]}
                   for k, v in sorted(asm.items(), key=lambda x: -len(x[1]))],
                  f, ensure_ascii=False, indent=1)

    # ---------------- 平替
    with open(os.path.join(out_dir, "mainland-substitutions.json"), "w", encoding="utf-8") as f:
        json.dump([{"original": k, "substitute": v[0], "note": v[1]} for k, v in LOW_FREQ_JP.items()],
                  f, ensure_ascii=False, indent=1)

    # ---------------- 去重家族
    fam = defaultdict(list)
    fam_swapmeat = defaultdict(list)   # 同汤底同蔬菜换肉
    fam_swapbroth = defaultdict(list)  # 同肉同菜换汤底
    for r in recipes:
        fp = r["fingerprint"]
        key = canonical_family("%s-%s-%s" % (fp["broth_family"], fp["protein"] or "素",
                                             (fp["primary_vegetable"] or "")[:4]))
        fam[key].append(r["id"] + " " + r["name"])
        fam_swapmeat[(fp["broth_family"], (fp["primary_vegetable"] or "")[:4])].append(r["id"] + " " + r["name"])
        fam_swapbroth[(fp["protein"] or "素", (fp["primary_vegetable"] or "")[:4])].append(r["id"] + " " + r["name"])
    dups = {k: v for k, v in fam.items() if len(v) > 1}
    dup_meat = {"%s×%s" % k: v for k, v in fam_swapmeat.items() if len(v) > 1}
    dup_broth = {"%s×%s" % k: v for k, v in fam_swapbroth.items() if len(v) > 1}
    with open(os.path.join(out_dir, "duplicate-families.json"), "w", encoding="utf-8") as f:
        json.dump({"families_exact": dups,
                   "same_broth_swap_meat": dup_meat,
                   "same_ingredients_swap_broth": dup_broth,
                   "rule": "同汤底换肉/同食材换汤底/只换收尾主食 → 归并母版+variations；周菜单同族一次"},
                  f, ensure_ascii=False, indent=1)

    # ---------------- 逐章 jsonl 单文件（全部章合并）
    with open(os.path.join(out_dir, "explicit-recipes.jsonl"), "w", encoding="utf-8") as f:
        for r in recipes:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------------- profile / chapter-map / parse-report / audit
    with open(os.path.join(out_dir, "00-book-profile.md"), "w", encoding="utf-8") as f:
        f.write("# 《一人锅：一个人的小锅料理》书籍档案\n\n"
                "- 作者：小田真规子\n- 主题：一人份小锅料理（锅具即餐具）\n"
                "- 结构：入门篇（10分钟家常锅）+ 佐酒锅 + 其他章 + 5 个专栏\n"
                "- 版权处理：仅存食材/汤底名与用量（事实）+ 步骤数量与摘要，无大段原文\n")
    with open(os.path.join(out_dir, "01-chapter-map.md"), "w", encoding="utf-8") as f:
        f.write("# 章节地图\n\n")
        for cm in chapter_map:
            f.write("- %s（%s）%s\n" % (cm["chapter"], cm["type"], cm["src"]))
        f.write("\n共识别菜谱 %d 道（逐页一菜）\n" % len(recipes))
    with open(os.path.join(out_dir, "parse-report.md"), "w", encoding="utf-8") as f:
        bad = [r for r in recipes if r["review_notes"]]
        f.write("# 解析报告\n\n- EPUB 直读，无 DRM，无 OCR 依赖\n- 菜谱页 %d 个，成功 %d，待复核 %d\n"
                % (len(entries), len(recipes), len(bad)))
    dec = Counter(r["solo_suitability"]["decision"] for r in recipes)
    with open(os.path.join(out_dir, "audit-report.md"), "w", encoding="utf-8") as f:
        f.write("# 《一人锅》审计报告\n\n")
        f.write("- 原书菜谱：%d；成功提取：%d；OCR 影响：0\n" % (len(entries), len(recipes)))
        f.write("- 汤底家族：%d 个（%s）\n" % (len(broths), "、".join(broths)))
        f.write("- 独立菜谱家族：%d（完全同构 %d 组；同汤底换肉 %d 组；同料换汤底 %d 组）\n"
                % (len(fam), len(dups), len(dup_meat), len(dup_broth)))
        f.write("- 一人食决定：%s\n" % dict(dec))
        f.write("- 10分钟章菜谱：%d 道\n" % sum(1 for r in recipes if r["quick_10min"]))
        f.write("- 营养：全部待按实际克数重算\n")
        f.write("\n## 主候选池（10分钟+食材≤6）\n\n")
        for r in recipes:
            if r["quick_10min"] and r["ingredient_count"] <= 6:
                f.write("- %s %s（%s汤底）\n" % (r["id"], r["name"], r["fingerprint"]["broth_family"]))
        f.write("\n## 人工复核项\n\n")
        for r in recipes:
            if r["review_notes"]:
                f.write("- %s %s\n" % (r["id"], r["name"]))

    # ---------------- 并入统一池
    br_path = os.path.join(skill_root, "data", "book-recipes.json")
    pool = json.load(open(br_path, encoding="utf-8")) if os.path.exists(br_path) \
        else {"meta": {}, "recipes": []}
    pool["recipes"] = [o for o in pool["recipes"] if not o["id"].startswith("yrg-")]
    from extract_book_recipes import mode_fit
    for r in recipes:
        fp = r["fingerprint"]
        core = [clean_cn_ingredient(i) for i in r["original"]["ingredients"]]
        core = [c for c in core if c and c not in SEASONING_CN][:8]
        mf = mode_fit(core, fp["flavor"], zh=True)
        if fp["finishing_carb"]:
            mf["keto_biologic"] = "medium" if mf["keto_biologic"] == "high" else mf["keto_biologic"]
        pool["recipes"].append({
            "id": r["id"], "name": r["name"], "original_name": r["name"],
            "source_type": "book_adapted", "source_book": BOOK_TITLE,
            "source_location": r["source"]["location"],
            "extraction_type": "explicit_recipe",
            "core_ingredients": core, "original_ingredients": core,
            "methods": ["煮", "炖"], "structure": "汤锅", "flavors": fp["flavor"],
            "original_servings": 1, "adapted_servings": 1,
            "active_minutes": 10 if r["quick_10min"] else 20,
            "total_minutes": r["original"]["estimated_minutes"],
            "mode_fit": mf,
            "required_modifications": ["酮生物模式省略收尾主食"] if fp["finishing_carb"] else [],
            "nutrition_status": "recalculation_required",
            "copyright_status": "transformed_summary",
            "canonical_recipe_family": canonical_family(r["name"]),
            "broth_family": fp["broth_family"], "pool_exclude": False,
        })
    pool["meta"]["total_recipes"] = len(pool["recipes"])
    with open(br_path, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)
    print("一人锅：提取 %d 道（汤底家族 %d，重复族 %d）；统一池总量 %d"
          % (len(recipes), len(broths), len(dups), len(pool["recipes"])))


if __name__ == "__main__":
    main()
