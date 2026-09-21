#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱分类器（round63 工作流 A/B）：dish_category + 主食材族/主蛋白族重构。

对生产菜谱池（data/recipe-index.json + data/book-recipes.json）逐道产出结构化分类，
写入 data/recipe-classification.json（不修改、不覆盖原始菜谱数据文件）：

  dish_category                菜品一级类型（枚举见 data/taxonomy/dish-categories.json）
  primary_ingredient_family    最主要食材结构（去重/相似菜/采购复用）
  primary_protein_family       主要蛋白来源（营养/主蛋白重复门禁/多样性）
  secondary_protein_families   复合蛋白来源
  classification_method        rule（本脚本规则法）
  classification_confidence    high / medium / low（low 一律进人工复核队列）
  classification_evidence      分类证据（命中食材与规则），不允许只留标签没有依据

分类优先级（方案 §6.3）：
  1. 读结构化 core_ingredients，经 ingredient-catalog 归族（油/调味品不参与主食材判定）；
  2. 先判 dish_category（甜点/饮品/调味品/小食优先于主食/汤/正餐）；
  3. 甜点、饮品、调味品不得判出肉禽水产主蛋白（烘焙蛋奶不误判为主蛋白）；
  4. 主蛋白优先级：肉禽水产 > 蛋 > 乳制品 > 豆制品（不得把含鱼/鸡肉的菜归入 soy）；
  5. 证据冲突或置信度不足 → confidence=low，进复核队列，不得用 none/other 掩盖；
  6. 不可解析菜谱（缺 id/名称/核心食材/结构）从生产池隔离，进 recipe-unparseable.csv。

产物：
  data/recipe-classification.json      分类结果（含 build_id、script_version）
  reports/recipe-unparseable.csv       不可解析隔离清单
  reports/recipe-low-confidence.csv    低置信度人工复核队列
  reports/recipe-classification-fixes.csv  相对旧口径的自动修复记录
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import re
import unicodedata


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _sha256_tree(dirpath):
    h = hashlib.sha256()
    for root, _dirs, files in sorted(os.walk(dirpath)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            h.update(os.path.relpath(fp, dirpath).encode("utf-8"))
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
    return "sha256:" + h.hexdigest()

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(BASE, "data")
REPORTS = os.path.join(BASE, "reports")
SCRIPT_VERSION = "1.0.0"

PROTEIN_FAMS = ("poultry", "pork", "beef", "lamb", "fish", "shellfish",
                "egg", "dairy", "soy", "other_protein")
FLESH_FAMS = ("poultry", "pork", "beef", "lamb", "fish", "shellfish", "other_protein")
NON_PRIMARY = {"flavor", "oil"}
MAIN_MEAL = {"main_dish", "staple", "soup", "side", "composite_meal"}
NO_FLESH_CATS = {"dessert", "beverage", "sauce_or_condiment", "snack"}

# 菜名关键词 → 食材族兜底（catalog 未命中时使用，证据记 name_keyword）
NAME_FAMILY_HINTS = [
    ("egg", ["蛋", "egg", "eggs", "omelet", "omelette", "炒蛋", "煎蛋", "蒸蛋", "玉子"]),
    ("poultry", ["鸡", "鸭", "鹅", "鸽", "chicken", "duck", "turkey", "wing", "wings", "鸡翅", "鸡腿", "鸡胸", "啤酒鸭", "gà"]),
    ("pork", ["猪", "排骨", "五花", "里脊", "pork", "bacon", "培根", "火腿", "ham", "香肠", "sausage", "腊肠", "猪蹄", "肘子", "belly pork", "红烧肉", "炒肉", "肉丝", "肉片", "肉末", "肉馅", "肉燥", "卤肉", "咕咾肉", "咕噜肉", "狮子头", "pig", "heo", "thịt heo", "sườn", "腰花", "猪腰", "猪肝", "猪肚", "猪大肠", "kidney", "kidneys", "bratwurst", "培根肉"]),
    ("lamb", ["羊", "lamb", "mutton", "羊肉串"]),
    ("beef", ["牛", "beef", "steak", "牛排", "牛腩", "肥牛", "牛腱", "bò"]),
    ("fish", ["鱼", "鲑", "鳕", "鲈", "鲫", "鲤", "带鱼", "黄花鱼", "salmon", "cod", "tuna", "fish", "fishcake", "trout", "鲷", "鳗", "鳝", "鱔", "eel", "鲟", "鲢", "鳙", "草鱼", "黑鱼", "桂鱼", "鳜", "鲶鱼", "catfish", "龙利", "巴沙", "basa", "seabass", "sea bass", "cá"]),
    ("shellfish", ["虾", "蟹", "贝", "蛤蜊", "扇贝", "牡蛎", "生蚝", "海参", "shrimp", "prawn", "crab", "clam", "mussel", "scallop", "squid", "鱿鱼", "墨鱼", "章鱼", "octopus", "lobster", "龙虾", "sea cucumber", "seafood", "cua", "crawfish", "crayfish", "小龙虾"]),
    ("gourd", ["黄瓜", "丝瓜", "苦瓜", "西葫芦", "瓠", "葫芦", "cucumber", "zucchini", "茄子", "eggplant", "aubergine", "番茄", "西红柿", "tomato", "青椒", "彩椒", "辣椒", "pepper", "秋葵", "okra", "玉米", "corn", "豌豆", "豆角", "四季豆", "豇豆", "荷兰豆", "蚕豆", "扁豆", "green bean", "green beans"]),
    ("soy", ["豆腐", "豆干", "豆皮", "腐竹", "千张", "素鸡", "豆花", "tofu", "tempeh", "豆浆", "毛豆", "纳豆", "soy bean", "soy beans", "soybean", "soybeans", "edamame", "绿豆", "红豆", "黑豆", "鹰嘴豆", "chickpea", "chickpeas", "lentil", "lentils", "小扁豆", "bean", "beans", "broad bean", "fava", "white bean", "black bean", "面筋", "烤麸", "gluten"]),
    ("dairy", ["奶", "cheese", "芝士", "奶酪", "黄油", "butter", "cream", "奶油", "酸奶", "yogurt", "milk", "奶茶"]),
    ("leafy_green", ["菠菜", "生菜", "青菜", "白菜", "油麦菜", "空心菜", "通心菜", "芥蓝", "苋菜", "spinach", "lettuce", "kale", "卷心菜", "包菜", "cabbage", "娃娃菜", "上海青", "小白菜", "韭菜", "芹菜", "茼蒿", "菜心", "沙拉", "salad", "雪菜", "酸菜", "泡菜", "芽菜", "香椿", "香菜", "葱花", "小葱", "大葱", "香葱", "薄荷", "mint", "罗勒", "basil", "greens", "chua", "苜蓿", "草头"]),
    ("crucifer", ["西兰花", "花菜", "菜花", "broccoli", "cauliflower", "羽衣甘蓝", "抱子甘蓝"]),
    ("root", ["土豆", "马铃薯", "胡萝卜", "萝卜", "红薯", "紫薯", "山药", "芋头", "莲藕", "藕", "potato", "potatoes", "carrot", "carrots", "radish", "beet", "甜菜", "洋葱", "onion", "南瓜", "pumpkin", "squash", "冬瓜", "笋", "芦笋", "asparagus", "莴笋", "茭白", "凉薯", "豆薯", "薯条", "fries"]),
    ("grain", ["米", "饭", "面", "粉", "粥", "饼", "面包", "馒头", "花卷", "汤圆", "元宵", "粽子", "醪糟", "饺子", "馄饨", "燕麦", "oats", "oatmeal", "rice", "noodle", "pasta", "bread", "quinoa", "藜麦", "荞麦", "玉米面", "面粉", "flour", "糕", "蛋糕", "cake", "披萨", "pizza", "司康", "吐司", "toast", "couscous", "taco", "tortilla", "魔芋", "konjac", "凉粉", "粉条", "宽粉", "水饺", "spaghetti", "linguine", "penne", "拉面", "乌冬", "udon", "wonton", "wontons", "orzo", "polenta", "bun", "pilaf", "farro", "pappardelle", "cavatelli", "granola", "bao", "雪花酥", "牛轧", "炒糖", "糖浆", "syrup", "蔗糖", "糖色", "糖", "sugar"]),
    ("mushroom", ["蘑菇", "香菇", "金针菇", "杏鲍菇", "平菇", "口蘑", "木耳", "银耳", "mushroom", "shiitake", "菌", "portobello"]),
    ("fruit", ["苹果", "apple", "香蕉", "banana", "橙", "柠檬", "lemon", "lime", "莓", "berry", "芒果", "mango", "菠萝", "pineapple", "牛油果", "avocado", "桃", "pear", "梨", "葡萄", "grape", "西瓜", "哈密瓜", "猕猴桃", "kiwi", "蓝莓", "blueberry", "草莓", "strawberry", "椰", "coconut", "柚", "pomelo", "柑", "橘", "桔", "plum", "梅", "山楂", "hawthorn", "枣", "date", "无花果", "fig", "百香果", "passion", "木瓜", "papaya", "榴", "莲雾", "枇杷", "杨梅", "cherry", "樱桃", "车厘子", "peach", "apricot", "杏"]),
    ("nut", ["核桃", "杏仁", "almond", "腰果", "cashew", "花生", "peanut", "芝麻", "sesame", "walnut", "榛子", "开心果", "chia", "奇亚籽", "亚麻籽", "flax"]),
    ("other_vegetable", ["蔬菜", "vegetable", "时蔬", "杂菜", "什锦菜"]),
    ("other_protein", ["肉丸", "丸子", "肉松", "午餐肉", "meatball", "兔", "rabbit", "鹿", "venison", "牛蛙", "frog", "鸽子", "鹌鹑", "quail", "驴", "狗肉", "肝", "liver", "血", "毛肚", "百叶", "黄喉", "鸭血", "鸡皮", "卤味", "卤菜"]),
]

# 菜名肉类线索黑名单：这些固定词中的"肉名"不代表主蛋白（鱼香肉丝不是鱼）
FLESH_NAME_BLACKLIST = ["鱼香", "鸡精", "虾片", "蟹棒", "猫眼"]

# 关键词级豁免：命中这些词时不算对应线索（牛至/牛油果不是牛肉，鸡蛋不是禽肉）
HINT_BLACKLIST = {
    "牛": ["牛至", "牛油果", "牛奶", "牛顿", "牛蛙"],
    "鸡": ["鸡蛋", "鸡油"],
    "鱼": ["鱼香", "鱼露"],
    "肉丝": ["牛肉丝", "羊肉丝", "鸡肉丝"],
    "肉片": ["牛肉片", "羊肉片", "鸡肉片"],
    "肉末": ["牛肉末", "羊肉末"],
    "肉丸": ["牛肉丸"],
    "炒肉": ["牛肉"],
}


def kw_blocked(kw, text):
    return any(b in text for b in HINT_BLACKLIST.get(kw, []))

FAMILY_ZH = {
    "poultry": "禽肉", "pork": "猪肉", "beef": "牛肉", "lamb": "羊肉", "fish": "鱼",
    "shellfish": "水产贝类", "egg": "蛋", "dairy": "乳制品", "soy": "豆制品",
    "other_protein": "其他蛋白", "leafy_green": "叶菜", "crucifer": "十字花科",
    "root": "根茎", "gourd": "瓜果茄豆", "mushroom": "菌菇", "grain": "谷物主食",
    "fruit": "水果", "nut": "坚果种子", "other_vegetable": "其他蔬菜", "other": "其他",
}


def load(name, base=DATA):
    return json.load(open(os.path.join(base, name), encoding="utf-8"))


def kw_match(keyword, text):
    """中英文分制匹配：纯 ASCII 关键词按词边界，中文按子串；越南语等带调文字先拆调。
    防止 Steamed 误中 tea、Buttery 误中 tart 这类英文子串误判。"""
    if not keyword:
        return False
    k = unicodedata.normalize("NFKD", str(keyword)).encode("ascii", "ignore").decode().lower().strip()
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    if re.fullmatch(r"[a-z0-9 +\-]+", k, re.I):
        return re.search(r"(?<![a-z])" + re.escape(k) + r"(?:e?s)?(?![a-z])", t) is not None
    return keyword in text


def build_family_of(cat):
    fam = {k: v.get("ingredient_family") for k, v in cat.get("items", {}).items()}

    def family_of(name):
        if not name:
            return None, None
        n = str(name).strip()
        if fam.get(n):
            return fam[n], n
        for k, v in fam.items():
            if v and (k in n or n in k):
                return v, k
        for f, kws in NAME_FAMILY_HINTS:
            for kw in kws:
                if kw_match(kw, n) and not kw_blocked(kw, n):
                    return f, f"name:{kw}"
        return None, None
    return family_of


def name_family_hint(name):
    """菜名食材族线索（模块级，供判型与主食材族判定共用）。"""
    for f, kws in NAME_FAMILY_HINTS:
        if any(kw_match(w, name or "") and not kw_blocked(w, name or "") for w in kws):
            return f
    return None


def name_flesh_hint(name):
    """菜名肉禽水产线索（与 name_family_hint 独立，蛋/乳/豆命中不掩盖肉线索）。"""
    if any(b in (name or "") for b in FLESH_NAME_BLACKLIST):
        return None
    for f, kws in NAME_FAMILY_HINTS:
        if f in FLESH_FAMS and any(kw_match(w, name or "") and not kw_blocked(w, name or "")
                                   for w in kws):
            return f
    return None


def build_classifier(tax):
    kw = tax["name_keyword_rules"]

    def dish_category(name, structure, methods, category):
        n = (name or "").lower()
        hint = name_family_hint(name)
        has_flesh = name_flesh_hint(name) is not None
        for dc in ("dessert", "beverage", "sauce_or_condiment", "snack"):
            for w in kw.get(dc, []):
                if not kw_match(w, name or ""):
                    continue
                # 弱词保护：菜名带肉禽水产/蛋白/主食线索时，"with sauce"、咸味 pie
                # 一类关键词不判非正餐（Tamale Pie / Chicken with Tarragon Sauce）
                if has_flesh:
                    continue
                # 酱料本体 vs "带酱的菜"：有任何食材族菜名线索即不判调味品
                if dc == "sauce_or_condiment" and hint is not None:
                    continue
                # 弱甜点词（pie/tart/crumble）：蔬菜线索的咸味烤饼不判甜点
                if dc == "dessert" and w in ("pie", "tart", "crumble") and hint in (
                        "leafy_green", "crucifer", "root", "gourd", "mushroom", "other_vegetable"):
                    continue
                return dc, f"name:{w}"
        if category == "早餐" or (structure or "") == "早餐":
            return "breakfast", "category:早餐"
        for w in kw.get("breakfast", []):
            if kw_match(w, name or "") and not has_flesh:
                return "breakfast", f"name:{w}"
        for w in kw.get("soup", []):
            if kw_match(w, name or ""):
                if any(x in (name or "") for x in ("汤圆", "汤团", "汤包")):
                    break
                if (structure or "") == "一锅炖煮" and "汤" not in n:
                    break
                return "soup", f"name:{w}"
        for w in kw.get("staple", []):
            if kw_match(w, name or ""):
                return "staple", f"name:{w}"
        st = structure or ""
        if st in ("汤羹", "汤/煮"):
            if has_flesh:
                # 书源 structure 误标（淡奶油鸡被标"汤/煮"）：菜名带肉禽水产且
                # 无汤名线索时按正餐菜
                return "main_dish", f"structure:{st}+name_flesh"
            return "soup", f"structure:{st}"
        if st == "主食":
            return "staple", f"structure:{st}"
        if st in ("一锅炖煮", "整盘", "套餐", "一锅餐"):
            return "composite_meal", f"structure:{st}"
        if st in ("凉拌", "小菜", "配菜"):
            # 书源 structure 偶有误标（烤鸡被标"凉拌"）：菜名带肉禽水产线索时按正餐菜
            if has_flesh:
                return "main_dish", f"structure:{st}+name_flesh"
            return "side", f"structure:{st}"
        if category in ("荤菜", "素菜") or st:
            if category == "素菜" and st in ("", "小炒", "快炒"):
                return "side", f"category:{category}"
            return "main_dish", f"category:{category or st}"
        if category in ("饮品", "饮料"):
            return "beverage", f"category:{category}"
        return "main_dish", "default:unclassified_structure"

    return dish_category


def parseable(r):
    if not (r.get("id") and (r.get("original_name") or r.get("name"))
            and r.get("core_ingredients") and (r.get("structure") or r.get("methods"))):
        return False
    # 书源索引噪声（目录页/章节标题被误提为"菜谱"）：非食物名称直接隔离
    name = str(r.get("original_name") or r.get("name") or "")
    junk = ("BOOKS BY", "KNOW-HOW", "RECIPES AND", "INDEX", "CONTENTS", "目录")
    if any(j in name.upper() for j in junk):
        return False
    if re.fullmatch(r"\s*(\d+\s+)?(soups?|snacks?|casseroles?|recipes?|special[a-z \-]*)\s*",
                    name, re.I):
        return False
    # 编号章节头（"5 Pork and Beef"、"8 Rice and Noodles"）
    if re.fullmatch(r"\s*\d+\s+(pork|beef|chicken|fish|seafood|vegetarian|rice|noodles?|pasta|salads?|soups?|snacks?|desserts?)[a-z &]*\s*",
                    name, re.I):
        return False
    return True


def classify_one(r, family_of, cat_fn):
    name = r.get("original_name") or r.get("name")
    core = r.get("core_ingredients") or []
    dc, dc_ev = cat_fn(name, r.get("structure"), r.get("methods") or [], r.get("category"))
    nh = name_family_hint(name)

    fam_hits = []  # (family, ingredient, via)
    for c in core:
        f, via = family_of(c)
        if f:
            fam_hits.append((f, c, via or c))
    # 菜名兜底：核心食材全部未命中、或命中的全是油/调味品时用菜名
    if not [h for h in fam_hits if h[0] not in NON_PRIMARY]:
        f, via = family_of(name)
        if f:
            fam_hits.append((f, name, via))

    usable = [h for h in fam_hits if h[0] not in NON_PRIMARY]
    prots = [h for h in usable if h[0] in PROTEIN_FAMS]

    # 主蛋白：肉禽水产 > 蛋 > 乳 > 豆；甜点/饮品/调味品/小食不判肉禽水产
    primary_protein = None
    if prots:
        pool = prots
        if dc in NO_FLESH_CATS:
            pool = [h for h in prots if h[0] not in FLESH_FAMS]
        if pool:
            def rank(h):
                f = h[0]
                if f in FLESH_FAMS:
                    return (0, FLESH_FAMS.index(f))
                return (1, PROTEIN_FAMS.index(f))
            primary_protein = sorted(pool, key=rank)[0][0]
    secondary = sorted({f for f, _, _ in prots if f != primary_protein
                        and not (dc in NO_FLESH_CATS and f in FLESH_FAMS)})

    # 菜名肉类线索优先于"食材仅命中豆/蛋/乳"的弱证据（含鱼/鸡的菜不得归入 soy）；
    # 鱼香肉丝类固定词由黑名单豁免（§6.4：不得仅凭菜名单个关键词定主蛋白——
    # 此处仅在食材证据中没有任何肉禽水产时启用，且记录双证据）
    if primary_protein not in FLESH_FAMS and not any(h[0] in FLESH_FAMS for h in prots):
        name_f = name_flesh_hint(name)
        if name_f and dc not in NO_FLESH_CATS:
            if primary_protein and primary_protein not in secondary:
                secondary = sorted(set(secondary) | {primary_protein})
            primary_protein = name_f
            fam_hits.append((name_f, name, f"name:{name_f}"))
            usable = usable or fam_hits
    # 菜名蛋白线索（含豆/蛋/乳）：食材证据完全无蛋白时启用（Chile Crisp Tofu）
    if primary_protein is None and nh in PROTEIN_FAMS and dc not in NO_FLESH_CATS:
        primary_protein = nh
        fam_hits.append((nh, name, f"name:{nh}"))
        usable = usable or fam_hits
    # 主食材族：优先主蛋白，否则第一个非蛋白非调味族；
    # sauce_or_condiment 允许以 flavor/oil 为主食材结构（糖浆/葱油本体即调味品）
    primary_family = primary_protein
    if not primary_family:
        nonprot = [h for h in usable if h[0] not in PROTEIN_FAMS]
        if nonprot:
            primary_family = nonprot[0][0]
    if not primary_family and dc == "sauce_or_condiment" and fam_hits:
        primary_family = fam_hits[0][0]
        usable = usable or fam_hits

    # 菜名食材族线索优先于食材推导（菜名是结构最强证据；食材里的次要蛋白不喧宾夺主）
    if nh and primary_family != nh:
        primary_family = nh

    # 主食类优先以谷物为主食材结构（芝麻/花生等点缀不喧宾夺主）
    if dc in ("staple", "composite_meal") and any(h[0] == "grain" for h in usable):
        if primary_family in (None, "nut", "fruit"):
            primary_family = "grain"

    evidence = [{"ingredient": c, "family": f, "via": via} for f, c, via in usable[:6]]
    evidence.insert(0, {"rule": "dish_category", "value": dc, "via": dc_ev})

    catalog_hits = sum(1 for _, _, via in usable if not str(via).startswith("name:"))
    name_hit = any(str(via).startswith("name:") for _, _, via in usable)
    if primary_family and catalog_hits >= max(1, len([c for c in core]) // 2 + 1):
        conf = "high"
    elif primary_family and (catalog_hits or name_hit):
        conf = "medium"
    elif primary_family:
        conf = "low"
    else:
        conf = "low"
    if not parseable(r):
        conf = "low"

    return {
        "id": r.get("id"),
        "name": name,
        "source": r.get("source_id") or r.get("source_book"),
        "dish_category": dc,
        "primary_ingredient_family": primary_family,
        "primary_protein_family": primary_protein,
        "secondary_protein_families": secondary,
        "classification_method": "rule",
        "classification_confidence": conf,
        "classification_evidence": evidence,
    }


def classify_all(recipes, family_of, cat_fn):
    out, unparseable = [], []
    for r in recipes:
        rec = classify_one(r, family_of, cat_fn)
        if not parseable(r):
            rec["excluded_from_production"] = True
            unparseable.append(rec)
        out.append(rec)
    return out, unparseable


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DATA, "recipe-classification.json"))
    ap.add_argument("--reports-dir", default=REPORTS)
    ap.add_argument("--build-id", default=None)
    args = ap.parse_args()
    build_id = args.build_id or datetime.date.today().isoformat() + "-r63"

    cat = load("ingredient-catalog.json")
    tax = load("taxonomy/dish-categories.json")
    family_of = build_family_of(cat)
    cat_fn = build_classifier(tax)
    idx = load("recipe-index.json")
    books = load("book-recipes.json")["recipes"]
    for r in idx:
        r.setdefault("source_id", "howtocook")
    recipes = idx + books

    records, unparseable = classify_all(recipes, family_of, cat_fn)
    low = [r for r in records if r["classification_confidence"] == "low"
           and not r.get("excluded_from_production")]

    payload = {
        "build_id": build_id,
        "script": "scripts/recipe_classifier.py",
        "script_version": SCRIPT_VERSION,
        "taxonomy_version": tax.get("taxonomy_version"),
        # round64：冻结本次分类所依据的 taxonomy bundle 与食材目录内容哈希，
        # 供 release gate 检测「taxonomy/目录变更后未重新分类」的漂移
        "source_hashes": {
            "taxonomy_bundle": _sha256_tree(os.path.join(DATA, "taxonomy")),
            "ingredient_catalog": _sha256_file(os.path.join(DATA, "ingredient-catalog.json")),
        },
        "record_count": len(records),
        "records": records,
    }
    json.dump(payload, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    rd = args.reports_dir
    write_csv(os.path.join(rd, "recipe-unparseable.csv"),
              ["id", "name", "source", "reason"],
              [[r["id"], r["name"], r.get("source"), "缺 id/名称/核心食材/结构，已从生产池隔离"]
               for r in unparseable])
    write_csv(os.path.join(rd, "recipe-low-confidence.csv"),
              ["id", "name", "source", "dish_category", "primary_ingredient_family",
               "primary_protein_family", "evidence"],
              [[r["id"], r["name"], r.get("source"), r["dish_category"],
                r["primary_ingredient_family"] or "", r["primary_protein_family"] or "",
                json.dumps(r["classification_evidence"], ensure_ascii=False)] for r in low])
    write_csv(os.path.join(rd, "recipe-classification-fixes.csv"),
              ["id", "name", "source", "field", "old_value", "new_value", "via"],
              [[r["id"], r["name"], r.get("source"), "dish_category", "", r["dish_category"],
                r["classification_evidence"][0].get("via", "")] for r in records]
              + [[r["id"], r["name"], r.get("source"), "primary_ingredient_family", "",
                  r["primary_ingredient_family"] or "review_required", "rule"] for r in records])

    cov = collections.Counter(r["dish_category"] for r in records)
    fam_cov = sum(1 for r in records if r["primary_ingredient_family"]
                  and not r.get("excluded_from_production"))
    prod = len(records) - len(unparseable)
    print(json.dumps({
        "build_id": build_id, "total": len(records), "production": prod,
        "unparseable_isolated": len(unparseable),
        "dish_category_coverage": 1.0,
        "primary_ingredient_family_coverage": round(fam_cov / max(prod, 1), 4),
        "low_confidence": len(low), "category_dist": dict(cov.most_common()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
