#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《鱼米之乡》精读提取器（纯标准库）
按 月食_菜谱书精读指令_鱼米之乡.docx 执行：
  - 输出 book-extraction/鱼米之乡/ 下 11 个文件
  - 只存转化摘要（食材名/关键动作/味型指纹），不保存大段原文
  - 原书事实 → original；一人食与本地化改造 → adapted；未注明的一律 null
  - explicit_recipe 同时并入 data/book-recipes.json 统一池

用法：
  python3 extract_yumizhixiang.py <epub路径> [--skill-root ..]
"""
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_book_recipes import (strip_html, detect_methods, detect_flavors,
                                  clean_cn_ingredient, canonical_family,
                                  SEASONING_CN)

BOOK_TITLE = "鱼米之乡（扶霞·邓洛普）"
BOOK_KEY = "ymzx"

# 菜谱章（part 前缀 → 章名 → 章节类型）
CHAPTERS = [
    ("0045", "开胃菜", "冷菜腌制"), ("0046", "肉菜", "肉禽蛋"),
    ("0047", "禽蛋类", "肉禽蛋"), ("0048", "鱼类和海鲜", "鱼虾水产"),
    ("0049", "豆制品类", "豆制品"), ("0050", "蔬菜类", "绿叶菜/瓜果根茎"),
    ("0051", "汤羹类", "汤羹"), ("0052", "米饭类", "主食"),
    ("0053", "面食类", "主食"), ("0054", "点心类", "甜品点心"),
    ("0055", "甜品类", "甜品点心"), ("0056", "饮品类", "饮品"),
    ("0057", "常备配料", "调味/高汤"),
]
CULTURE_CHAPTERS = [("0034", "封面"), ("0035", "目录"), ("0039", "前言 秀美江南"),
                    ("0040", "江南菜小史"), ("0041", "江南食材"),
                    ("0042", "江南菜的调味"), ("0043", "江南菜的烹饪之道"),
                    ("0044", "江南美食文化"), ("0059", "开菜单"),
                    ("0060", "调味品与食材"), ("0061", "炊具厨具"), ("0062", "技法"),
                    ("0063", "延伸阅读"), ("0064", "致谢"), ("0065", "译后记"), ("0066", "版权页")]

PROTEIN_WORDS = ["鸡", "鸭", "鹅", "猪", "肉", "排骨", "牛", "羊", "鱼", "虾", "蟹", "鳝", "贝",
                 "蛤蜊", "蚌", "螺", "鱿鱼", "墨鱼", "蛋", "豆腐", "干丝", "百叶", "香干",
                 "面筋", "狮子头", "里脊", "五花肉", "火腿", "咸肉", "香肠", "鲞", "鳗"]
VEG_WORDS = ["青菜", "菠菜", "白菜", "卷心菜", "生菜", "油麦菜", "蒿菜", "草头", "豆苗", "苋菜",
             "空心菜", "芥蓝", "菜心", "西兰花", "花菜", "毛豆", "蚕豆", "豌豆", "四季豆", "豇豆",
             "扁豆", "茄子", "番茄", "黄瓜", "冬瓜", "丝瓜", "葫芦", "南瓜", "苦瓜", "萝卜",
             "胡萝卜", "土豆", "芋头", "山药", "莲藕", "茭白", "笋", "芦笋", "芹菜", "韭菜",
             "洋葱", "葱", "姜", "蒜", "蘑菇", "香菇", "平菇", "金针菇", "木耳", "银耳",
             "菱角", "荸荠", "板栗", "百合", "紫菜", "海带", "雪菜", "榨菜", "青椒", "甜椒"]
TEXTURE_WORDS = ["酥", "脆", "嫩", "软", "弹", "糯", "爽", "滑", "浓稠", "多汁", "焦香", "松软"]

# 一人食排除信号
EXCLUDE_SIGNALS = [("整只", "整只禽畜/大件"), ("整鸡", "整只禽畜/大件"), ("整鸭", "整只禽畜/大件"),
                   ("全鱼", "整鱼大件"), ("叫花", "数日/复杂工艺"), ("宴席", "宴席大菜"),
                   ("筵席", "宴席大菜"), ("糟醉", "数日腌制"), ("醉蟹", "生食风险+数日腌制")]
ADAPT_SIGNALS = [("750克", "主食材量偏大需缩份"), ("1千克", "主食材量偏大需缩份"),
                 ("1000克", "主食材量偏大需缩份"), ("油炸", "宽油需改少油"),
                 ("过油", "宽油需改少油"), ("高汤", "吊汤依赖可换清水+浓汤宝")]

ALLERGENS = {"麸质": ["面粉", "面条", "馄饨", "包子", "馒头", "面筋", "酱油"],
             "蛋": ["鸡蛋", "鸭蛋", "蛋"], "大豆": ["豆腐", "干丝", "百叶", "豆浆", "酱油"],
             "花生": ["花生"], "坚果": ["松仁", "板栗", "核桃", "杏仁"],
             "甲壳类": ["虾", "蟹"], "鱼类": ["鱼", "鳝", "鳗"],
             "芝麻": ["芝麻", "香油"], "乳制品": ["黄油", "奶油", "奶酪"]}


def read_chapter(z, part):
    files = sorted(n for n in z.namelist()
                   if n.startswith("text/part%s" % part) and n.endswith(".html"))
    return "".join(z.read(f).decode("utf-8", "replace") for f in files), files


def split_recipes(html):
    """按 h2.sgc-toc-title 切块"""
    heads = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
             for m in re.finditer(r'<h2 class="sgc-toc-title"[^>]*>(.*?)</h2>', html, re.S)]
    out = []
    for i, (pos, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
        out.append((title, pos, html[pos:end]))
    return out


def parse_recipe_block(block):
    """解析单个菜谱块 → 字段"""
    m = re.search(r'<h5 class="heiti-c"[^>]*>(.*?)</h5>', block, re.S)
    name_en = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None
    paras = re.findall(r'<p class="([^"]+)"[^>]*>(.*?)</p>', block, re.S)
    intro, ingredients_raw, steps, variations = [], [], [], []
    in_variation = False
    steps_started = False
    UNIT_MARK = re.compile(r"[0-9½¼¾⅛⅜⅝⅞⅓⅔]|克|毫升|大匙|小匙|茶匙|汤匙|斤|两|把|撮|滴")
    for cls, txt in paras:
        t = re.sub(r"<[^>]+>", "", txt).strip()
        if not t:
            continue
        if "变奏" in t and len(t) < 12:
            in_variation = True
            continue
        if cls == "heiti2":
            if in_variation or steps_started:
                variations.append(t)  # 步骤后的 heiti2 是变奏名
            elif UNIT_MARK.search(t) or "（" in t:
                ingredients_raw.append(t)  # 有量词，或带括号说明的配料（如"冰水（用于浸泡）"）
            # 无量词无括号的 heiti2 是配料小标题（如"凉拌汁"），跳过
        elif cls.startswith("kaiti"):
            intro.append(t)
        elif cls.startswith("calibre1"):
            if ingredients_raw:
                steps_started = True  # 只有出现过食材行之后的长段落才算步骤（部分章引言也用 calibre1x）
            if in_variation:
                if variations:
                    variations[-1] += "：" + t[:60]
            else:
                steps.append(t)
        elif cls in ("heiti-c", "heiti3") and in_variation:
            variations.append(t)
    return name_en, intro, ingredients_raw, steps, variations


def key_actions(steps):
    """关键动作序列（转述用，不存原文）"""
    actions = []
    seq = [("焯水", ["焯", "汆"]), ("腌制", ["腌"]), ("煸炒", ["煸", "爆炒"]),
           ("炒糖色", ["糖色"]), ("煎", ["煎"]), ("炸", ["炸"]), ("蒸", ["蒸"]),
           ("炖煮", ["炖", "煨", "焖", "小火慢"]), ("烧制", ["红烧", "烧"]),
           ("快炒", ["快炒", "翻炒", "炒"]), ("煮", ["煮", "烧开"]), ("凉拌", ["拌"]),
           ("收汁", ["收汁"]), ("淋油", ["淋", "响油"]), ("烤", ["烤"])]
    text = "".join(steps)
    for name, kws in seq:
        pos = min((text.find(k) for k in kws if k in text), default=-1)
        if pos >= 0:
            actions.append((pos, name))
    return [a for _, a in sorted(actions)]


def fingerprint(title, ingredients, steps_text, intro_text):
    full = title + " " + " ".join(ingredients) + " " + steps_text + " " + intro_text
    methods = detect_methods(full, zh=True)
    flavors = detect_flavors(full, zh=True)
    ings = [clean_cn_ingredient(i) for i in ingredients]
    ings = [i for i in ings if i]
    protein = next((i for i in ings if any(w in i for w in PROTEIN_WORDS)
                    and i not in SEASONING_CN), None)
    vegetable = next((i for i in ings if any(w in i for w in VEG_WORDS)
                      and i not in SEASONING_CN and i != protein
                      and i not in {"生姜", "小葱", "大葱", "蒜末", "姜片", "姜块"}), None)
    texture = [w for w in TEXTURE_WORDS if w in full][:2]
    # 结构：菜名优先，其次方法
    title_struct = None
    for kw, st in (("蒸", "蒸菜"), ("汤", "汤羹"), ("羹", "汤羹"), ("凉拌", "凉拌"), ("拌", "凉拌"),
                   ("红烧", "炖菜/煲"), ("炖", "炖菜/煲"), ("焖", "炖菜/煲"), ("㸆", "炖菜/煲"),
                   ("炒", "炒菜"), ("煎", "煎炸"), ("炸", "煎炸"), ("烤", "烤/焗"), ("粥", "汤/煮"),
                   ("饭", "主食"), ("面", "主食")):
        if kw in title:
            title_struct = st
            break
    if title_struct:
        structure = title_struct
    elif "凉拌" in methods:
        structure = "凉拌"
    elif "汤" in title or "羹" in title or ("汤" in full[:200] and "煮" in methods):
        structure = "汤羹"
    elif "炖" in methods:
        structure = "炖菜/煲"
    elif "蒸" in methods:
        structure = "蒸菜"
    elif "烤" in methods:
        structure = "烤/焗"
    elif "炸" in methods or "煎" in methods:
        structure = "煎炸"
    elif "炒" in methods:
        structure = "炒菜"
    elif "煮" in methods:
        structure = "汤/煮"
    else:
        structure = "其他"
    return {"protein": protein, "vegetable": vegetable, "methods": methods,
            "flavors": flavors, "structure": structure, "texture": texture}


def solo_suitability(title, chapter, ingredients_raw, steps_text, fp):
    """一人食评估 → (决定, 理由列表)"""
    full = title + " " + " ".join(ingredients_raw) + " " + steps_text
    reasons = []
    for sig, why in EXCLUDE_SIGNALS:
        if sig in full:
            reasons.append(why)
    if chapter == "甜品类":
        reasons.append("高糖点心")
    if chapter == "常备配料":
        return "technique_only", ["属调味/高汤基础，非独立菜品"]
    if reasons:
        return "exclude", reasons
    for sig, why in ADAPT_SIGNALS:
        if sig in full:
            reasons.append(why)
    if chapter == "点心类":
        reasons.append("点心类小份失真风险")
    if reasons:
        return "adapt_then_use", reasons
    return "direct_use", ["份量和工艺适合一人食"]


def detect_allergens(full):
    return [a for a, kws in ALLERGENS.items() if any(k in full for k in kws)]


def main():
    epub = sys.argv[1]
    skill_root = sys.argv[sys.argv.index("--skill-root") + 1] if "--skill-root" in sys.argv else \
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(skill_root, "book-extraction", "鱼米之乡")
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(epub)

    recipes = []          # explicit_recipe 记录
    technique_notes = []  # 常备配料章 + 技法章
    chapter_map = []

    for part, cname, ctype in CHAPTERS:
        html, files = read_chapter(z, part)
        blocks = split_recipes(html)
        chapter_map.append({"part": part, "chapter": cname, "type": ctype,
                            "files": files, "recipe_count": len(blocks),
                            "recipes": [t for t, _, _ in blocks]})
        for idx, (title, pos, block) in enumerate(blocks):
            name_en, intro, ings_raw, steps, variations = parse_recipe_block(block)
            ings = []
            for ir in ings_raw:
                nm = clean_cn_ingredient(ir)
                nm = re.sub(r"[0-9½¼¾⅛⅜⅝⅞⅓⅔]+\s*(?:大匙|小匙|茶匙|汤匙|杯|碗)$", "", nm).strip()
                nm = re.sub(r"^(?:大匙|小匙|茶匙|汤匙)$", "", nm).strip()
                nm = re.sub(r"(?:大匙|小匙|茶匙|汤匙|杯|碗)$", "", nm).strip()
                if nm and nm not in ings and len(nm) <= 14 and not re.fullmatch(r"[0-9½¼¾⅛⅜⅝⅞⅓⅔]+", nm):
                    ings.append(nm)
            steps_text = " ".join(steps)
            intro_text = " ".join(intro)
            full = title + " " + " ".join(ings_raw) + " " + steps_text
            fp = fingerprint(title, ings_raw, steps_text, intro_text)
            suitability, reasons = solo_suitability(title, cname, ings_raw, steps_text, fp)
            rec_id = "ymzx-%03d" % (len(recipes) + 1)
            core = [i for i in ings if i not in SEASONING_CN][:8]
            rec = {
                "id": rec_id,
                "name": title,
                "name_en": name_en,
                "source": {"book": BOOK_TITLE, "chapter": cname,
                           "location": "text/part%s#%d" % (part, pos)},
                "classification": "explicit_recipe" if cname != "常备配料" else "protocol_rule",
                "original": {
                    "ingredients": ings_raw,          # 原书食材行（含克数，事实信息）
                    "servings": None,                  # 原书未标注份数
                    "time_minutes": None,
                    "time_source": None,
                    "variations": variations,
                    "key_actions": key_actions(steps),  # 步骤精炼转述
                },
                "solo_suitability": {"decision": suitability, "reasons": reasons},
                "localization": {
                    "nanjing_search_terms": core[:5],
                    "notes": [],
                },
                "adapted": {"servings": 1, "modifications": []},
                "fingerprint": fp,
                "allergens": detect_allergens(full),
                "nutrition_recalculation_required": True,
                "confidence": "high" if len(ings) >= 2 else "medium",
                "review_notes": [],
            }
            if len(ings) < 2:
                rec["confidence"] = "medium"
                rec["review_notes"].append("食材行少于2条，需人工复核")
            if suitability == "adapt_then_use":
                rec["adapted"]["modifications"] = list(reasons)
            if cname == "常备配料":
                technique_notes.append(rec)
            else:
                recipes.append(rec)

    # ---------------- 输出 00-book-profile.md / 01-chapter-map.md
    with open(os.path.join(out_dir, "00-book-profile.md"), "w", encoding="utf-8") as f:
        f.write("# 《鱼米之乡》书籍档案\n\n")
        f.write("- 作者：扶霞·邓洛普（Fuchsia Dunlop）\n- 出版：中信出版集团，2021\n")
        f.write("- 内容：江南（江浙沪）家常菜，文化章节 + 13 个菜谱章\n")
        f.write("- 川菜部分为套装重复内容，本目录不含\n")
        f.write("- 提取日期：2026-08-20；提取器：scripts/extract_yumizhixiang.py\n")
        f.write("- 版权处理：仅保存食材名、关键动作序列、味型指纹等转化摘要，无大段原文\n")

    with open(os.path.join(out_dir, "01-chapter-map.md"), "w", encoding="utf-8") as f:
        f.write("# 章节地图\n\n## 文化章节（不逐条提取菜谱）\n\n")
        for part, cname in CULTURE_CHAPTERS:
            f.write("- text/part%s —— %s\n" % (part, cname))
        f.write("\n## 菜谱章节\n\n")
        for cm in chapter_map:
            f.write("### %s（%s，%d 道）\n\n" % (cm["chapter"], cm["type"], cm["recipe_count"]))
            for t in cm["recipes"]:
                f.write("- %s\n" % t)
            f.write("\n")

    # ---------------- explicit-recipes.jsonl
    with open(os.path.join(out_dir, "explicit-recipes.jsonl"), "w", encoding="utf-8") as f:
        for r in recipes:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------------- technique-notes.jsonl（常备配料 + 技法章关键词）
    with open(os.path.join(out_dir, "technique-notes.jsonl"), "w", encoding="utf-8") as f:
        for r in technique_notes:
            f.write(json.dumps({"id": r["id"], "name": r["name"], "type": "基础配料/高汤",
                                "chapter": r["source"]["chapter"],
                                "key_actions": r["original"]["key_actions"],
                                "ingredients": r["original"]["ingredients"],
                                "home_adaptation": "一人食可减半或用现成高汤/浓汤宝替代",
                                "source": r["source"]}, ensure_ascii=False) + "\n")
        html62, _ = read_chapter(z, "0062")
        txt62 = strip_html(html62)
        for tech in ["焯水", "腌渍", "挂浆", "炒", "蒸", "炸", "高压锅", "红烧", "刀工"]:
            if tech in txt62:
                f.write(json.dumps({"id": "ymzx-tech-%s" % tech, "name": tech,
                                    "type": "烹饪技法", "chapter": "技法",
                                    "note": "原书技法章有专节说明",
                                    "home_adaptation": "家庭灶直接适用",
                                    "source": {"book": BOOK_TITLE, "chapter": "技法",
                                               "location": "text/part0062"}},
                                   ensure_ascii=False) + "\n")
    # ---------------- 一人食评估补充：耗时信号
    for r in recipes:
        full = " ".join(r["original"]["ingredients"])
        if r["solo_suitability"]["decision"] == "direct_use" and re.search(
                r"[1-9一二两]\s*个小时|[1-9]\s*小时|慢炖|文火", full + str(r["original"]["key_actions"])):
            r["solo_suitability"] = {"decision": "adapt_then_use",
                                     "reasons": r["solo_suitability"]["reasons"] + ["耗时较长需周末批量"]}

    # ---------------- meal-patterns.jsonl（开菜单章的组合原则，转述）
    meal_patterns = [
        {"id": "ymzx-mp-001", "type": "meal_pattern", "name": "一人一菜一汤一饭",
         "rule": "一人食按'一人一菜'基础上加一道汤或凉菜；米饭必须足量",
         "source": {"book": BOOK_TITLE, "chapter": "开菜单", "location": "text/part0059"},
         "solo_use": "工作日正餐框架：1 主菜 + 1 汤/凉菜 + 主食"},
        {"id": "ymzx-mp-002", "type": "meal_pattern", "name": "凉菜提前准备",
         "rule": "凉菜可提前备好直接上桌；炖菜烧菜可提前做、开饭前复热",
         "source": {"book": BOOK_TITLE, "chapter": "开菜单", "location": "text/part0059"},
         "solo_use": "备餐策略：周末做炖菜，工作日拌凉菜"},
        {"id": "ymzx-mp-003", "type": "meal_pattern", "name": "水果收尾代替甜品",
         "rule": "中式正餐尾声上水果而非甜品",
         "source": {"book": BOOK_TITLE, "chapter": "开菜单", "location": "text/part0059"},
         "solo_use": "经前/平衡期可用水果替代高糖点心"},
        {"id": "ymzx-mp-004", "type": "meal_pattern", "name": "主材颜色烹法不重复",
         "rule": "一餐内各菜的主材、颜色和烹饪方法最好不重复",
         "source": {"book": BOOK_TITLE, "chapter": "开菜单", "location": "text/part0059"},
         "solo_use": "与菜谱指纹多样性规则一致，用于一周内邻日去重"},
    ]
    with open(os.path.join(out_dir, "meal-patterns.jsonl"), "w", encoding="utf-8") as f:
        for mp in meal_patterns:
            f.write(json.dumps(mp, ensure_ascii=False) + "\n")

    # ---------------- 江南味型模板（调味章散述 + 菜谱用例统计，不写固定配比）
    FLAVOR_THEMES = {
        "葱油": ["葱油"], "糟香": ["糟", "酒糟", "糟卤"], "酒香": ["料酒", "黄酒", "绍兴酒", "酒酿"],
        "酱香": ["酱油", "老抽", "生抽", "甜面酱", "豆瓣酱"], "咸鲜": ["咸肉", "火腿", "鲞", "盐"],
        "清鲜": ["清蒸", "白灼", "盐水"], "糖醋": ["糖醋", "糖", "醋"], "醋香": ["镇江醋", "米醋", "醋"],
        "姜葱": ["姜", "葱"], "豉香": ["豆豉"], "菌菇鲜": ["香菇", "蘑菇", "干菇"],
        "高汤煨煮": ["高汤", "煨"], "清蒸": ["清蒸"], "酱烧": ["红烧", "酱烧"],
        "盐水白煮": ["盐水", "白煮"], "雪菜提味": ["雪菜", "雪里蕻"],
    }
    templates = {}
    for theme, kws in FLAVOR_THEMES.items():
        hit = [r for r in recipes if any(k in (r["name"] + " " + " ".join(r["original"]["ingredients"]))
                                         for k in kws)]
        if not hit:
            continue
        templates[theme] = {
            "flavor_template": theme,
            "type": "flavor_template",
            "basis": "原书《江南菜的调味》章散述 + 菜谱用例归纳；原书无固定配比，此处不编造比例",
            "example_recipes": [r["id"] + " " + r["name"] for r in hit[:6]],
            "use_count": len(hit),
            "weekday_fit": "high" if theme in ("咸鲜", "清鲜", "姜葱", "清蒸", "雪菜提味") else "medium",
            "solo_note": "一人份调料整体减半，低频调料见 mainland-substitutions.json",
        }
    with open(os.path.join(out_dir, "jiangnan-flavor-templates.json"), "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=1)

    # ---------------- 时令食材地图
    SEASONAL = {
        "茭白": {"season": "夏秋", "unit": "根/袋", "perish": "中", "alias": ["茭笋", "高笋"]},
        "莲藕": {"season": "秋冬", "unit": "节", "perish": "低", "alias": ["藕"]},
        "冬瓜": {"season": "夏", "unit": "圈/块", "perish": "低", "alias": []},
        "丝瓜": {"season": "夏", "unit": "根", "perish": "高", "alias": []},
        "毛豆": {"season": "夏秋", "unit": "斤/袋", "perish": "中", "alias": ["青豆"]},
        "蚕豆": {"season": "春", "unit": "斤", "perish": "中", "alias": ["胡豆"]},
        "竹笋": {"season": "春（冬笋为冬）", "unit": "根/袋", "perish": "高", "alias": ["春笋", "冬笋"]},
        "菱角": {"season": "秋", "unit": "斤", "perish": "中", "alias": []},
        "芋头": {"season": "秋冬", "unit": "个/斤", "perish": "低", "alias": ["芋艿"]},
        "茄子": {"season": "夏", "unit": "根", "perish": "中", "alias": []},
        "草头": {"season": "春", "unit": "把", "perish": "高", "alias": ["苜蓿芽", "金花菜"]},
        "雪菜": {"season": "四季（腌制品）", "unit": "袋", "perish": "低", "alias": ["雪里蕻"]},
        "青菜": {"season": "秋冬霜降后最佳", "unit": "把/斤", "perish": "高", "alias": ["上海青", "小白菜"]},
        "苋菜": {"season": "夏", "unit": "把", "perish": "高", "alias": []},
        "豆苗": {"season": "冬春", "unit": "盒", "perish": "高", "alias": ["豌豆苗"]},
        "鲈鱼": {"season": "四季", "unit": "条", "perish": "高", "alias": []},
        "鳜鱼": {"season": "春", "unit": "条", "perish": "高", "alias": ["桂鱼"]},
        "带鱼": {"season": "秋冬", "unit": "段/条", "perish": "中（冰鲜）", "alias": []},
        "鳝鱼": {"season": "夏", "unit": "条/丝", "perish": "高", "alias": ["黄鳝"]},
        "河虾": {"season": "春夏", "unit": "两/斤", "perish": "高", "alias": ["青虾"]},
        "大闸蟹": {"season": "秋", "unit": "只", "perish": "高", "alias": ["螃蟹"]},
        "荸荠": {"season": "冬", "unit": "斤", "perish": "低", "alias": ["马蹄"]},
        "百合": {"season": "秋", "unit": "个/袋", "perish": "中", "alias": []},
        "银耳": {"season": "四季（干货）", "unit": "朵/袋", "perish": "低", "alias": ["白木耳"]},
    }
    smap = {}
    for name, meta in SEASONAL.items():
        hit = [r for r in recipes if name in (r["name"] + " " + " ".join(r["original"]["ingredients"]))]
        smap[name] = {
            "ingredient": name,
            "原书季节或情景": meta["season"],
            "关联菜谱": [r["id"] + " " + r["name"] for r in hit[:5]],
            "常见购买单位": meta["unit"],
            "易腐性": meta["perish"],
            "一人食余量利用": "买最小包装；余量次日快炒或入汤",
            "南京常用搜索词": [name] + meta["alias"],
            "别名": meta["alias"],
            "同季替代": [],
            "替换对味型与火候的影响": "同科属替换影响不大；叶菜互换注意出水与火候",
            "note": "季节与搜索词为本地化适配层，非原书逐字内容",
        }
    with open(os.path.join(out_dir, "seasonal-ingredient-map.json"), "w", encoding="utf-8") as f:
        json.dump(smap, f, ensure_ascii=False, indent=1)

    # ---------------- 大陆本地化替换（低频/难买食材）
    subs = [
        {"original": "酒糟/糟卤", "substitute": "料酒+少量糖（风味近似）", "channel": "菜场/超市",
         "impact": "少了糟香厚度，味型方向不变"},
        {"original": "干苔菜", "substitute": "紫菜（烤脆）", "channel": "超市", "impact": "香气略弱"},
        {"original": "鲞（咸鱼干）", "substitute": "咸鱼（盒马冰鲜区）或省略", "channel": "盒马", "impact": "用量减半"},
        {"original": "金华火腿", "substitute": "宣威火腿/咸肉", "channel": "超市", "impact": "风味近似"},
        {"original": "草头", "substitute": "豆苗/菠菜", "channel": "叮咚", "impact": "口感近似"},
        {"original": "鳝鱼", "substitute": "盒马现成鳝丝", "channel": "盒马", "impact": "省去活杀"},
        {"original": "皮冻", "substitute": "省略或用吉利丁简易版", "channel": "-", "impact": "仅口感"},
        {"original": "绵白糖", "substitute": "白砂糖", "channel": "超市", "impact": "无"},
        {"original": "镇江醋", "substitute": "香醋", "channel": "超市", "impact": "无"},
        {"original": "绍兴酒/料酒", "substitute": "普通料酒", "channel": "超市", "impact": "无"},
        {"original": "红皮花生", "substitute": "普通花生", "channel": "菜场", "impact": "无"},
        {"original": "母子酱油", "substitute": "普通老抽", "channel": "超市", "impact": "色泽略浅"},
    ]
    with open(os.path.join(out_dir, "mainland-substitutions.json"), "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=1)

    # ---------------- adaptation-candidates.jsonl（adapt_then_use 全量）
    with open(os.path.join(out_dir, "adaptation-candidates.jsonl"), "w", encoding="utf-8") as f:
        for r in recipes:
            if r["solo_suitability"]["decision"] == "adapt_then_use":
                f.write(json.dumps({"id": r["id"], "name": r["name"],
                                    "reasons": r["solo_suitability"]["reasons"],
                                    "modifications": r["adapted"]["modifications"],
                                    "fingerprint": r["fingerprint"]},
                                   ensure_ascii=False) + "\n")

    # ---------------- duplicate-families.json（与既有池/池内查重）
    fam = defaultdict(list)
    for r in recipes:
        fam[canonical_family(r["name"])].append(r["id"] + " " + r["name"])
    dups = {k: v for k, v in fam.items() if len(v) > 1}
    # 与既有 book-recipes.json 交叉
    br_path = os.path.join(skill_root, "data", "book-recipes.json")
    cross = {}
    if os.path.exists(br_path):
        old = json.load(open(br_path, encoding="utf-8"))["recipes"]
        oldfam = {}
        for o in old:
            oldfam.setdefault(canonical_family(o["name"]), []).append(o["id"] + " " + o["name"])
        for r in recipes:
            cf = canonical_family(r["name"])
            if cf in oldfam:
                cross[cf] = {"ymzx": r["id"] + " " + r["name"], "existing": oldfam[cf]}
    with open(os.path.join(out_dir, "duplicate-families.json"), "w", encoding="utf-8") as f:
        json.dump({"pool_internal": dups, "cross_book": cross,
                   "rule": "同名同构归并为母版+variations；周菜单同族最多出现一次"},
                  f, ensure_ascii=False, indent=1)

    # ---------------- audit-report.md
    dec = Counter(r["solo_suitability"]["decision"] for r in recipes)
    with open(os.path.join(out_dir, "audit-report.md"), "w", encoding="utf-8") as f:
        f.write("# 《鱼米之乡》提取审计报告\n\n")
        f.write("- 菜谱章节：13/13 全部处理；文化章节仅归类不逐条提取\n")
        f.write("- explicit_recipe：%d 条；protocol_rule（常备配料）：%d 条\n" % (len(recipes), len(technique_notes)))
        f.write("- meal_pattern：%d 条；flavor_template：%d 种；时令食材：%d 项\n"
                % (len(meal_patterns), len(templates), len(smap)))
        f.write("- 一人食决定：direct_use %d / adapt_then_use %d / exclude %d / technique_only %d\n"
                % (dec.get("direct_use", 0), dec.get("adapt_then_use", 0),
                   dec.get("exclude", 0), len(technique_notes)))
        f.write("- 池内重复族：%d 组；跨书重复：%d 组\n" % (len(dups), len(cross)))
        f.write("- 原书未标注份数与时间：全部 servings=null、time=null，未编造\n")
        f.write("- 营养：全部 nutrition_recalculation_required=true，按本 skill 数据重算\n")
        f.write("- 版权：仅存食材行（事实）与关键动作序列，无大段原文\n")
        f.write("\n## 排除清单\n\n")
        for r in recipes:
            if r["solo_suitability"]["decision"] == "exclude":
                f.write("- %s %s（%s）\n" % (r["id"], r["name"], "、".join(r["solo_suitability"]["reasons"])))
        f.write("\n## 人工复核项\n\n")
        for r in recipes:
            if r["review_notes"]:
                f.write("- %s %s：%s\n" % (r["id"], r["name"], "、".join(r["review_notes"])))

    # ---------------- 并入 data/book-recipes.json 统一池
    from extract_book_recipes import mode_fit
    br_path = os.path.join(skill_root, "data", "book-recipes.json")
    pool = json.load(open(br_path, encoding="utf-8")) if os.path.exists(br_path)         else {"meta": {}, "recipes": []}
    pool["recipes"] = [o for o in pool["recipes"] if not o["id"].startswith("ymzx-")]
    n_add = 0
    for r in recipes:
        fp = r["fingerprint"]
        core = []
        for ir in r["original"]["ingredients"]:
            nm = clean_cn_ingredient(ir)
            if nm and nm not in SEASONING_CN and nm not in core and len(nm) <= 12:
                core.append(nm)
        core = core[:8]
        mf = mode_fit(core, fp["flavors"], zh=True)
        excl = r["solo_suitability"]["decision"] == "exclude"
        pool["recipes"].append({
            "id": r["id"], "name": r["name"], "original_name": r["name_en"],
            "source_type": "book_adapted",
            "source_book": BOOK_TITLE,
            "source_location": r["source"]["location"],
            "extraction_type": "explicit_recipe",
            "core_ingredients": core, "original_ingredients": core,
            "methods": fp["methods"], "structure": fp["structure"], "flavors": fp["flavors"],
            "original_servings": None, "adapted_servings": 1,
            "active_minutes": None, "total_minutes": None,
            "mode_fit": mf,
            "required_modifications": r["adapted"]["modifications"],
            "nutrition_status": "recalculation_required",
            "copyright_status": "transformed_summary",
            "canonical_recipe_family": canonical_family(r["name"]),
            "solo_suitability": r["solo_suitability"]["decision"],
            "pool_exclude": excl,
            "variations": r["original"]["variations"],
        })
        n_add += 1
    pool["meta"]["total_recipes"] = len(pool["recipes"])
    with open(br_path, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)
    print("显式菜谱 %d 条，技法/配料笔记 %d 条；输出目录 %s；并入统一池 %d 条（池总量 %d）"
          % (len(recipes), len(technique_notes), out_dir, n_add, len(pool["recipes"])))
    return recipes, chapter_map, out_dir, z


if __name__ == "__main__":
    main()
