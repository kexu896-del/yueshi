#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
书籍菜谱提取器（纯标准库）
按照 references/book-recipe-extraction.md 的七步流程，从 EPUB 烹饪书中提取菜谱，
输出统一的 data/book-recipes.json。

原则：
  - TOC 优先定位菜谱，逐章处理，保留来源位置（文件 + 锚点）
  - 三种提取类型：explicit_recipe / meal_pattern / protocol_rule
  - 只存转化摘要（食材名、做法关键词、味型、结构），不存原文整段
    → copyright_status 固定为 transformed_summary
  - 营养统一标记 recalculation_required，由营养素脚本按本 skill 数据重算
  - 英文书食材经翻译表归一为中文名，未命中保留英文小写并标记

用法：
  python3 extract_book_recipes.py <epub目录> [-o ../data/book-recipes.json]
"""

import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NCX_NS = "{http://www.daisy.org/z3986/2005/ncx/}"

# ---------------------------------------------------------------- 基础工具

def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h1|h2|h3|h4|ol|ul|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
           .replace("&gt;", ">").replace("&#8217;", "'").replace("&#8216;", "'")
           .replace("&#8220;", '"').replace("&#8221;", '"').replace("&#8212;", "—")
           .replace("&#8211;", "–").replace("&rsquo;", "'").replace("&lsquo;", "'")
           .replace("&ldquo;", '"').replace("&rdquo;", '"').replace("&mdash;", "—")
           .replace("&hellip;", "…").replace("&#189;", "½").replace("&#188;", "¼")
           .replace("&#190;", "¾").replace("&#8539;", "⅛"))
    s = re.sub(r"[ \t　]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


class Epub:
    def __init__(self, path):
        self.path = path
        self.z = zipfile.ZipFile(path)
        ncx = [n for n in self.z.namelist() if n.endswith(".ncx")][0]
        self.base = os.path.dirname(ncx)
        root = ET.fromstring(self.z.read(ncx))
        self.toc = []
        for np_ in root.iter(NCX_NS + "navPoint"):
            t = np_.find(NCX_NS + "navLabel/" + NCX_NS + "text")
            c = np_.find(NCX_NS + "content")
            if t is not None and c is not None:
                self.toc.append(((t.text or "").strip(), c.get("src")))

    def read(self, src):
        src = src.split("#")[0]
        full = os.path.normpath(os.path.join(self.base, src)).replace("\\", "/") if self.base else src
        for cand in (full, src):
            try:
                return self.z.read(cand).decode("utf-8", "replace")
            except KeyError:
                continue
        return ""

    def anchor_pos(self, html, anchor):
        for pat in (r'id="%s"' % re.escape(anchor), r"id='%s'" % re.escape(anchor)):
            m = re.search(pat, html)
            if m:
                return m.start()
        return -1


# ---------------------------------------------------------------- 指纹关键词（与 build_recipe_index.py 保持一致思路）

def detect_methods(text, zh):
    kws = {
        "炒": ["炒", "stir-fry", "stir fry", "sauté", "saute", "pan-fry"],
        "煎": ["煎", "seared", "griddle"],
        "炸": ["炸", "deep-fry", "deep fry", "crispy fried"],
        "烤": ["烤", "roast", "bake", "baked", "grill", "oven", "traybake", "sheet pan"],
        "蒸": ["蒸", "steam"],
        "煮": ["煮", "boil", "simmer", "poach", "blanch"],
        "炖": ["炖", "焖", "煨", "braise", "stew", "slow cook", "casserole", "hotpot", "hot pot"],
        "凉拌": ["凉拌", "拌", "salad", "dressing", "no-cook", "tossed"],
        "腌": ["腌", "marinate", "pickle", "cure"],
        "卤": ["卤", "酱", "brine", "soy-braised", "master stock"],
    }
    out = []
    low = text.lower()
    for m, words in kws.items():
        if any((w in text) if zh else (w in low) for w in words):
            out.append(m)
    return out or (["煮"] if not zh else ["其他"])


def detect_flavors(text, zh):
    kws = {
        "麻辣": ["麻辣", "麻婆", "花椒", "numbing", "sichuan pepper"],
        "香辣": ["辣椒", "辣酱", "香辣", "chilli", "chili", "hot bean", "spicy", "红油"],
        "酸辣": ["酸辣", "sour-and-hot", "sour and hot", "hot and sour"],
        "酸甜": ["糖醋", "酸甜", "sweet and sour", "sweet-and-sour"],
        "咸鲜": ["咸鲜", "鲜咸", "umami", "savoury", "savory", "soy sauce"],
        "酱香": ["酱香", "甜面酱", "黄豆酱", "miso", "bean sauce", "hoisin"],
        "咖喱": ["咖喱", "curry"],
        "奶香": ["奶油", "牛奶", "芝士", "奶酪", "cream", "cheese", "parmesan", "butter"],
        "酸甜口": ["maple", "honey", "sugar", "糖", "sweet"],
        "蒜香": ["蒜", "garlic"],
        "香草": ["basil", "thyme", "rosemary", "herb", "香菜", "薄荷", "mint", "lemongrass"],
        "鱼露": ["fish sauce", "鱼露"],
        "清淡": ["清炒", "清蒸", "清淡", "清汤", "light"],
    }
    low = text.lower()
    return [f for f, words in kws.items() if any((w in text) if zh else (w in low) for w in words)][:3]


def classify_structure(text, zh, methods):
    if "凉拌" in methods or (not zh and "salad" in text.lower()):
        return "凉拌"
    for m, s in (("炖", "炖菜/煲"), ("烤", "烤/焗"), ("蒸", "蒸菜"),
                 ("炸", "煎炸"), ("煎", "煎炸"), ("煮", "汤/煮"), ("炒", "炒菜")):
        if m in methods:
            return "汤羹" if (m == "煮" and ("汤" in text or "soup" in text.lower() or "broth" in text.lower())) else s
    return "其他"


# ---------------------------------------------------------------- 食材名归一

CN_QTY = re.compile(r"[（(].*?[)）]|（.*?）|\d+(?:\.\d+)?\s*(?:克|千克|斤|两|毫升|升|大匙|小匙|勺|杯|根|个|只|片|块|瓣|段|把|撮|滴|条|尾|茶匙|汤匙|大勺|小勺)|\d+|适量|少许|若干|½|¼|¾|⅛|⅜|⅝|⅞|⅓|⅔")

EN_UNITS = ("cup|cups|tbsp|tablespoon|tablespoons|tsp|teaspoon|teaspoons|g|kg|ml|l|lb|oz|"
            "pound|pounds|ounce|ounces|cm|mm|inch|inches|clove|cloves|slice|slices|piece|pieces|"
            "bunch|bunches|sprig|sprigs|stalk|stalks|can|cans|tin|tins|pack|packet|handful|pinch|"
            "dash|knob|rashers?|fillets?|breasts?|thighs?|whole|large|medium|small|about|approx")
EN_QTY = re.compile(
    r"^(?:(?:\d+(?:\.\d+)?(?:\s*[½¼¾⅛⅜⅝⅞⅓⅔])?(?:\s*(?:[–/-]|to)\s*\d+(?:\s*[½¼¾⅛⅜⅝⅞⅓⅔])?)?|[½¼¾⅛⅜⅝⅞⅓⅔])\s*(?:[×x]\s*(?:\d+\s*(?:g|kg|ml|l)\s*)?(?:jar|tins?|cans?|pack(?:et)?s?)\s*(?:of\s*)?)?|a|an|few|some|large|medium|small|heaped|heaping|level|generous|good)\s*"
    r"(?:\((?:[^)]*)\)\s*)?(?:(?:" + EN_UNITS + r")\b\.?\s*)?(?:of\s+)?", re.I)
EN_PAREN = re.compile(r"\([^)]*\)")

# 常见食材英→中（命中前缀即替换；保持小写匹配）
EN2CN = [
    ("whole peeled tomatoes", "番茄罐头"), ("whole tomatoes", "番茄罐头"),
    ("sandwich bread", "吐司"), ("white bread", "白吐司"), ("crusty bread", "欧包"),
    ("ears corn", "玉米"), ("ear corn", "玉米"), ("vegetable broth", "蔬菜高汤"),
    ("chicken broth", "鸡汤"), ("beef broth", "牛肉高汤"), ("leek", "大葱"),
    ("bell pepper", "甜椒"), ("arugula", "芝麻菜"), ("escarole", "苦苣"),
    ("kale", "羽衣甘蓝"), ("swiss chard", "瑞士甜菜"), ("collard", "羽衣甘蓝"),
    ("fennel bulb", "球茎茴香"), ("butternut", "南瓜"), ("acorn squash", "橡子南瓜"),
    ("yukon gold", "黄心土豆"), ("russet", "褐皮土豆"), ("red bliss", "红皮土豆"),
    ("fine sea salt", "盐"), ("caster  sugar", "细砂糖"), ("caster sugar", "细砂糖"),
    ("light brown sugar", "红糖"), ("dark brown sugar", "红糖"), ("soft brown sugar", "红糖"),
    ("ground coriander", "香菜籽粉"), ("coriander seed", "香菜籽"), ("natural yoghurt", "酸奶"),
    ("natural yogurt", "酸奶"), ("greek yogurt", "希腊酸奶"), ("greek yoghurt", "希腊酸奶"),
    ("ground ginger", "姜粉"), ("fresh ginger", "姜"), ("dijon mustard", "第戎芥末"),
    ("wholegrain mustard", "粗粒芥末"), ("red chilli", "红辣椒"), ("green chilli", "青辣椒"),
    ("cherry tomatoes", "小番茄"), ("mixed-colour cherry tomatoes", "小番茄"),
    ("runny honey", "蜂蜜"), ("ground nutmeg", "肉豆蔻粉"), ("nutmeg", "肉豆蔻"),
    ("chinese five-spice", "五香粉"), ("five-spice powder", "五香粉"), ("five spice", "五香粉"),
    ("ground turmeric", "姜黄粉"), ("bay leaf", "香叶"), ("bay leaves", "香叶"),
    ("water", "水"), ("hot water", "水"), ("cold water", "水"), ("warm water", "水"),
    ("fish sauce", "鱼露"), ("sweetcorn", "玉米粒"), ("miso", "味噌"),
    ("dukkah", "杜卡香料"), ("flatbread", "薄饼"), ("leg of lamb", "羊腿"),
    ("barrel-aged feta", "菲达奶酪"), ("feta cheese", "菲达奶酪"),
    ("kosher salt", "盐"), ("sea salt", "盐"), ("fine salt", "盐"), ("table salt", "盐"),
    ("ground black pepper", "黑胡椒"), ("black peppercorns", "黑胡椒粒"),
    ("all-purpose flour", "中筋面粉"), ("plain flour", "中筋面粉"),
    ("self-raising flour", "自发粉"), ("self-rising flour", "自发粉"),
    ("granulated sugar", "细砂糖"), ("superfine sugar", "细砂糖"),
    ("ground cinnamon", "肉桂粉"), ("baking powder", "泡打粉"), ("baking soda", "小苏打"),
    ("canola", "植物油"), ("neutral oil", "植物油"), ("vegetable oil", "植物油"),
    ("extra-virgin olive oil", "橄榄油"), ("extra virgin olive oil", "橄榄油"),
    ("room temperature butter", "黄油"), ("cold butter", "黄油"), ("melted butter", "黄油"),
    ("ground cumin", "孜然粉"), ("cumin seed", "孜然粒"), ("smoked paprika", "烟熏红椒粉"),
    ("grated parmesan", "帕玛森"), ("parmesan cheese", "帕玛森"),
    ("round shallot", "红葱头"), ("peeled and chopped yellow onion", "黄洋葱"),
    ("1% milk", "牛奶"), ("whole milk", "全脂牛奶"), ("skimmed milk", "脱脂牛奶"),
    ("2% milk", "牛奶"), ("full-fat milk", "全脂牛奶"),
    ("freshly ground", ""), ("recently ground", ""),
    ("chicken thigh", "鸡腿"), ("chicken breast", "鸡胸肉"), ("chicken wing", "鸡翅"),
    ("chicken", "鸡肉"), ("minced beef", "牛肉末"), ("ground beef", "牛肉末"),
    ("beef steak", "牛排"), ("beef", "牛肉"), ("pork belly", "五花肉"),
    ("minced pork", "猪肉末"), ("ground pork", "猪肉末"), ("pork chop", "猪排"),
    ("pork tenderloin", "猪里脊"), ("pork loin", "猪里脊"), ("pork", "猪肉"),
    ("lamb", "羊肉"), ("bacon", "培根"), ("pancetta", "意式腌肉"), ("sausage", "香肠"),
    ("chorizo", "西班牙辣肠"), ("salmon", "三文鱼"), ("cod", "鳕鱼"), ("tuna", "金枪鱼"),
    ("sea bass", "鲈鱼"), ("sea bream", "鲷鱼"), ("trout", "鳟鱼"), ("mackerel", "鲭鱼"),
    ("prawn", "虾"), ("shrimp", "虾"), ("squid", "鱿鱼"), ("mussel", "贻贝"),
    ("clam", "蛤蜊"), ("scallop", "扇贝"), ("crab", "蟹"), ("fish sauce", "鱼露"),
    ("tofu", "豆腐"), ("egg", "鸡蛋"), ("duck egg", "鸭蛋"), ("duck", "鸭肉"),
    ("rice noodle", "米粉"), ("rice vermicelli", "细米粉"), ("egg noodle", "鸡蛋面"),
    ("udon", "乌冬面"), ("noodle", "面条"), ("pasta", "意面"), ("spaghetti", "意面"),
    ("linguine", "扁意面"), ("pappardelle", "宽意面"), ("tagliatelle", "宽意面"),
    ("penne", "通心粉"), ("lasagne", "千层面"), ("rice", "大米"), ("jasmine rice", "香米"),
    ("basmati", "印度香米"), ("brown rice", "糙米"), ("quinoa", "藜麦"), ("couscous", "库斯库斯"),
    ("bread", "面包"), ("baguette", "法棍"), ("tortilla", "墨西哥薄饼"), ("flour", "面粉"),
    ("oats", "燕麦"), ("oat", "燕麦"), ("potato", "土豆"), ("sweet potato", "红薯"),
    ("butternut squash", "南瓜"), ("pumpkin", "南瓜"), ("squash", "南瓜"),
    ("aubergine", "茄子"), ("eggplant", "茄子"), ("courgette", "西葫芦"), ("zucchini", "西葫芦"),
    ("broccoli", "西蓝花"), ("cauliflower", "花菜"), ("cabbage", "卷心菜"), ("red cabbage", "紫甘蓝"),
    ("pak choi", "小白菜"), ("bok choy", "小白菜"), ("spinach", "菠菜"), ("kale", "羽衣甘蓝"),
    ("lettuce", "生菜"), ("watercress", "西洋菜"), ("morning glory", "空心菜"),
    ("water spinach", "空心菜"), ("bean sprout", "豆芽"), ("sprouts", "豆芽"),
    ("green bean", "四季豆"), ("mangetout", "荷兰豆"), ("sugar snap", "甜豆"),
    ("asparagus", "芦笋"), ("celery", "芹菜"), ("carrot", "胡萝卜"), ("onion", "洋葱"),
    ("spring onion", "小葱"), ("scallion", "小葱"), ("shallot", "红葱头"), ("leek", "大葱"),
    ("garlic", "大蒜"), ("ginger", "姜"), ("chilli", "辣椒"), ("chili", "辣椒"),
    ("red pepper", "红甜椒"), ("bell pepper", "甜椒"), ("pepper", "甜椒"),
    ("tomato", "番茄"), ("cherry tomato", "小番茄"), ("cucumber", "黄瓜"),
    ("mushroom", "蘑菇"), ("shiitake", "香菇"), ("oyster mushroom", "平菇"),
    ("enoki", "金针菇"), ("wood ear", "木耳"), ("avocado", "牛油果"),
    ("corn", "玉米"), ("peas", "豌豆"), ("edamame", "毛豆"), ("lentil", "扁豆"),
    ("chickpea", "鹰嘴豆"), ("black bean", "黑豆"), ("kidney bean", "芸豆"),
    ("cannellini", "白芸豆"), ("butter bean", "白扁豆"), ("paneer", "印度奶酪"),
    ("mozzarella", "马苏里拉"), ("parmesan", "帕玛森"), ("cheddar", "切达奶酪"),
    ("feta", "菲达奶酪"), ("halloumi", "哈罗米奶酪"), ("cottage cheese", "茅屋奶酪"),
    ("ricotta", "里科塔奶酪"), ("cream cheese", "奶油奶酪"), ("double cream", "淡奶油"),
    ("single cream", "稀奶油"), ("heavy cream", "淡奶油"), ("crème fraîche", "法式酸奶油"),
    ("sour cream", "酸奶油"), ("yogurt", "酸奶"), ("yoghurt", "酸奶"), ("milk", "牛奶"),
    ("coconut milk", "椰浆"), ("coconut cream", "椰浆"), ("butter", "黄油"),
    ("olive oil", "橄榄油"), ("sesame oil", "香油"), ("vegetable oil", "植物油"),
    ("groundnut oil", "花生油"), ("peanut oil", "花生油"), ("sunflower oil", "葵花籽油"),
    ("soy sauce", "酱油"), ("light soy", "生抽"), ("dark soy", "老抽"),
    ("oyster sauce", "蚝油"), ("hoisin", "海鲜酱"), ("miso", "味噌"), ("mirin", "味醂"),
    ("rice vinegar", "米醋"), ("white wine vinegar", "白酒醋"), ("apple cider vinegar", "苹果醋"),
    ("balsamic", "巴萨米克醋"), ("vinegar", "醋"), ("lime", "青柠"), ("lemon", "柠檬"),
    ("orange", "橙子"), ("apple", "苹果"), ("pear", "梨"), ("banana", "香蕉"),
    ("mango", "芒果"), ("pineapple", "菠萝"), ("pomegranate", "石榴"), ("dates", "椰枣"),
    ("peanut", "花生"), ("cashew", "腰果"), ("almond", "杏仁"), ("walnut", "核桃"),
    ("pecan", "山核桃"), ("sesame", "芝麻"), ("pine nut", "松子"),
    ("coriander", "香菜"), ("cilantro", "香菜"), ("mint", "薄荷"), ("basil", "罗勒"),
    ("thai basil", "九层塔"), ("dill", "莳萝"), ("parsley", "欧芹"), ("thyme", "百里香"),
    ("rosemary", "迷迭香"), ("oregano", "牛至"), ("sage", "鼠尾草"), ("lemongrass", "香茅"),
    ("chive", "细香葱"), ("dashi", "日式高汤"), ("stock", "高汤"), ("broth", "高汤"),
    ("honey", "蜂蜜"), ("maple syrup", "枫糖浆"), ("brown sugar", "红糖"), ("sugar", "糖"),
    ("salt", "盐"), ("black pepper", "黑胡椒"), ("sichuan pepper", "花椒"),
    ("star anise", "八角"), ("cinnamon", "肉桂"), ("cumin", "孜然"), ("turmeric", "姜黄"),
    ("paprika", "红椒粉"), ("curry powder", "咖喱粉"), ("garam masala", "印度混合香料"),
    ("five spice", "五香粉"), ("chilli flake", "辣椒碎"), ("gochujang", "韩式辣酱"),
    ("sriracha", "是拉差辣酱"), ("tabasco", "塔巴斯科辣酱"), ("mustard", "芥末"),
    ("mayonnaise", "蛋黄酱"), ("tahini", "芝麻酱"), ("peanut butter", "花生酱"),
    ("tomato purée", "番茄膏"), ("tomato paste", "番茄膏"), ("passata", "番茄酱泥"),
    ("chopped tomatoes", "番茄罐头"), ("anchovy", "凤尾鱼"), ("olive", "橄榄"),
    ("caper", "刺山柑"), ("gherkin", "酸黄瓜"), ("pickle", "腌菜"),
    ("ham", "火腿"), ("prosciutto", "意式火腿"), ("salami", "萨拉米"),
    ("smoked salmon", "烟熏三文鱼"), ("white fish", "白肉鱼"), ("monkfish", "安康鱼"),
    ("pollock", "狭鳕"), ("haddock", "黑线鳕"), ("prawn", "虾"),
    ("buttermilk", "酪浆"), ("gnocchi", "意式土豆团子"), ("pearl barley", "大麦粒"),
    ("chocolate", "巧克力"), ("cocoa", "可可粉"), ("vanilla", "香草精"),
    ("blueberry", "蓝莓"), ("strawberry", "草莓"), ("raspberry", "树莓"),
    ("blackberry", "黑莓"), ("grape", "葡萄"), ("fig", "无花果"), ("plum tomato", "番茄"), ("wide rice noodle", "河粉"),
    ("button mushroom", "口蘑"), ("chestnut mushroom", "口蘑"), ("white mushroom", "口蘑"),
    ("borlotti bean", "斑豆"), ("focaccia", "佛卡夏面包"), ("mascarpone", "马斯卡彭"),
    ("green papaya", "青木瓜"), ("papaya", "木瓜"), ("pomelo", "柚子"), ("kohlrabi", "苤蓝"),
    ("corn kernel", "玉米粒"), ("fresh corn", "玉米"), ("cayenne", "卡宴辣椒粉"),
    ("borlotti", "斑豆"), ("cavolo nero", "黑甘蓝"), ("rocket", "芝麻菜"), ("arugula", "芝麻菜"),
    ("water chestnut", "荸荠"), ("bamboo shoot", "竹笋"), ("banana shallot", "香蕉葱"),
    ("tinned tomatoes", "番茄罐头"), ("chicken stock", "鸡汤"), ("vegetable stock", "蔬菜高汤"),
    ("beef stock", "牛肉高汤"), ("coconut water", "椰子水"), ("creme fraiche", "法式酸奶油"),
    ("soured cream", "酸奶油"), ("pecorino", "佩科里诺奶酪"), ("gruyère", "格吕耶尔奶酪"),
    ("gruyere", "格吕耶尔奶酪"), ("goat cheese", "山羊奶酪"), ("breadcrumbs", "面包糠"),
    ("panko", "日式面包糠"), ("vermicelli", "粉丝"), ("cellophane noodle", "粉丝"),
    ("ciabatta", "恰巴塔面包"), ("sourdough", "酸面包"), ("sticky rice", "糯米"),
    ("glutinous rice", "糯米"), ("pork shoulder", "猪肩肉"), ("pork fillet", "猪里脊"),
    ("beef brisket", "牛腩"), ("beef shin", "牛腱"), ("oxtail", "牛尾"),
    ("minced lamb", "羊肉末"), ("tiger prawn", "虎虾"), ("king prawn", "大虾"),
    ("octopus", "章鱼"), ("shiso", "紫苏"), ("perilla", "紫苏"),
    ("shaoxing", "绍兴酒"), ("sesame seed", "芝麻"), ("toasted sesame", "熟芝麻"),
    ("dried shrimp", "虾米"), ("shrimp paste", "虾酱"), ("tamarind", "罗望子"),
    ("palm sugar", "棕榈糖"), ("rock sugar", "冰糖"), ("caster sugar", "细砂糖"),
    ("icing sugar", "糖粉"), ("demerara", "粗红糖"), ("groundnut", "花生"),
    ("rapeseed oil", "菜籽油"), ("lard", "猪油"), ("duck fat", "鸭油"),
    ("harissa", "哈里萨辣酱"), ("kimchi", "韩式泡菜"), ("sauerkraut", "德式酸菜"),
    ("unsalted butter", "黄油"), ("salted butter", "黄油"), ("nước mắm", "鱼露"),
    ("nước chấm", "越式蘸水"), ("tenderstem", "嫩茎西蓝花"), ("flaked almond", "杏仁片"),
    ("lasagne sheet", "千层面"), ("eating apple", "苹果"), ("fuji apple", "富士苹果"),
    ("yellow onion", "黄洋葱"), ("white onion", "白洋葱"), ("red onion", "红洋葱"),
    ("plum", "李子"),
    ("peach", "桃"), ("nectarine", "油桃"), ("apricot", "杏"), ("cherry", "樱桃"),
    ("raisin", "葡萄干"), ("sultana", "无核葡萄干"), ("coconut", "椰子"),
    ("creamed coconut", "椰子膏"), ("egg white", "蛋清"), ("egg yolk", "蛋黄"),
    ("turkey", "火鸡"), ("venison", "鹿肉"), ("beef mince", "牛肉末"), ("pork mince", "猪肉末"),
    ("lamb mince", "羊肉末"), ("mince", "肉末"), ("steak", "牛排"), ("ribs", "排骨"),
    ("fennel", "茴香"), ("radish", "樱桃萝卜"), ("daikon", "白萝卜"), ("beetroot", "甜菜根"),
    ("turnip", "芜菁"), ("parsnip", "欧防风"), ("swede", "瑞典甘蓝"), ("leek", "大葱"),
    ("mange tout", "荷兰豆"), ("okra", "秋葵"), ("artichoke", "洋蓟"), ("olive", "橄榄"),
]
EN2CN.sort(key=lambda x: -len(x[0]))

SEASONING_CN = {"盐", "糖", "细砂糖", "生抽", "老抽", "酱油", "醋", "镇江醋", "米醋", "料酒", "黄酒",
                "香油", "花椒", "花椒面", "花椒油", "大料", "八角", "桂皮", "葱", "姜", "蒜", "红油",
                "芝麻酱", "辣椒", "干辣椒", "植物油", "食用油", "蚝油", "味噌", "黑胡椒", "白胡椒",
                "五香粉", "孜然", "咖喱粉", "高汤", "鸡汤", "味精", "鸡精", "香叶", "蜂蜜", "水"}


def clean_cn_ingredient(line):
    """从中文食材行提取食材名"""
    line = line.strip().strip("：:")
    line = line.replace("～", "").replace("~", "")
    line = re.sub(r"[（(][^)）]*$", "", line)
    line = re.sub(r"^[^(）]*[)）]", "", line) if line.count("）") > line.count("（") else line
    line = CN_QTY.sub("", line).strip(" ，,。；;")
    if "或" in line:
        line = line.split("或")[0]
    if "、" in line and len(line) > 8:
        line = line.split("、")[0]
    line = re.sub(r"^(?:新鲜|冰鲜|速冻|冷冻|优质|有机)", "", line)
    return line.strip()


def clean_en_ingredient(line):
    """从英文食材行提取食材名，并归一为中文（命中翻译表时）"""
    s = line.strip()
    s = EN_PAREN.sub("", s)
    s = EN_QTY.sub("", s).strip()
    # 去掉制备说明（逗号后的 chopped/sliced 等）
    s = re.split(r",\s*(?:finely|roughly|roughy|thinly|thickly|chopped|sliced|diced|minced|crushed|"
                 r"grated|peeled|trimmed|halved|quartered|torn|shredded|cut|deseeded|de-seeded|"
                 r"skins? removed|boneless|skinless|cooked|raw|drained|rinsed|toasted|roasted|"
                 r"softened|melted|beaten|whisked|divided|plus extra|at room temperature|to serve|"
                 r"to garnish|optional|if you|such as|or )", s, flags=re.I)[0]
    s = re.sub(r"^(?:juice|zest|juice and zest) of\s+", "", s, flags=re.I)
    s = re.sub(r"^(?:peeled(?: and (?:chopped|sliced|diced|grated))?|chopped|sliced|diced|minced|"
               r"crushed|grated|shredded|torn|toasted|roasted|cooked|drained|dried|fresh|freshly|"
               r"frozen|good-quality|quality|ripe|unripe|raw|boneless|skinless)(?:\s+|$)", "", s, flags=re.I)
    s = s.strip(" ,;.").lower()
    if not s:
        return "", ""
    low = s
    for en, cn in EN2CN:
        if low.startswith(en):
            return cn, s
    return s, s  # 未命中：保留英文小写


SEASONING_DROP = SEASONING_CN | {
    "盐", "黑胡椒", "黑胡椒粒", "水", "植物油", "泡打粉", "小苏打", "肉桂粉", "糖", "细砂糖",
    "糖粉", "粗红糖", "孜然粉", "孜然粒", "烟熏红椒粉", "红椒粉", "卡宴辣椒粉",
}


def drop_seasonings(ings, origs):
    if len(ings) <= 3:
        return ings, origs
    pairs = [(i, o) for i, o in zip(ings, origs) if i not in SEASONING_DROP]
    if len(pairs) >= 2:
        return [x[0] for x in pairs], [x[1] for x in pairs]
    return ings, origs


def canonical_family(name):
    """生成 canonical_recipe_family：小写、去标点、空格转连字符"""
    s = re.sub(r"[’'\"“”‘’]", "", name.lower())
    s = re.sub(r"[^0-9a-z一-鿿]+", "-", s).strip("-")
    return s[:60]


# ---------------------------------------------------------------- 营养模式适配粗判

STAPLE_WORDS = ["米饭", "大米", "糙米", "面条", "意面", "米粉", "面包", "法棍", "土豆", "通心粉",
                "千层面", "宽意面", "扁意面", "乌冬面", "库斯库斯", "燕麦", "面粉", "玉米", "藜麦",
                "大麦粒", "团子", "pasta", "rice", "noodle", "bread", "potato", "couscous"]
HIGH_CARB = ["糖", "蜂蜜", "枫糖浆", "巧克力", "椰枣", "葡萄干", "面包", "honey", "maple", "sugar"]


def mode_fit(ingredients, flavors, zh):
    joined = " ".join(ingredients)
    staple_hit = sum(1 for w in STAPLE_WORDS if (w in joined) if True)
    sweet_hit = any((w in joined) for w in HIGH_CARB)
    fried = any(f in flavors for f in ())  # 味型不判油炸，用方法判断
    has_protein = any(p in joined for p in
                      ["鸡", "猪", "牛", "羊", "鱼", "虾", "豆腐", "蛋", "鲑", "鳕", "蛤蜊", "贝",
                       "chicken", "pork", "beef", "fish", "tofu", "egg", "prawn", "salmon"])
    if staple_hit == 0 and not sweet_hit and has_protein:
        keto = "high"
    elif staple_hit <= 1 and not sweet_hit and has_protein:
        keto = "medium"
    else:
        keto = "low"
    if sweet_hit and staple_hit >= 2:
        hormone = "low"
    elif staple_hit >= 1:
        hormone = "high"
    else:
        hormone = "medium"
    return {"keto_biologic": keto, "hormone_balance": hormone}


# ---------------------------------------------------------------- 记录构造

_BOOK_COUNTER = {}


def make_record(book_id, book_title, name, name_zh, location, extraction_type,
                core_ingredients, orig_ingredients, text_sample, zh,
                original_servings=None, total_minutes=None, active_minutes=None,
                required_modifications=None):
    _BOOK_COUNTER[book_id] = _BOOK_COUNTER.get(book_id, 0) + 1
    methods = detect_methods(text_sample, zh)
    flavors = detect_flavors(text_sample, zh)
    structure = classify_structure(text_sample, zh, methods)
    mf = mode_fit(core_ingredients, flavors, zh)
    mods = list(required_modifications or [])
    if mf["keto_biologic"] == "low":
        mods.append("酮生物模式需去掉主食/糖或换低碳替代")
    rec = {
        "id": "%s-%03d" % (book_id, _BOOK_COUNTER[book_id]),
        "name": name_zh or name,
        "original_name": name,
        "source_type": "book_adapted" if extraction_type == "explicit_recipe" else "book_pattern_derived",
        "source_book": book_title,
        "source_location": location,
        "extraction_type": extraction_type,
        "core_ingredients": drop_seasonings(core_ingredients, orig_ingredients)[0][:8],
        "original_ingredients": drop_seasonings(core_ingredients, orig_ingredients)[1][:8],
        "methods": methods,
        "structure": structure,
        "flavors": flavors,
        "original_servings": original_servings,
        "adapted_servings": 1,
        "active_minutes": active_minutes,
        "total_minutes": total_minutes,
        "mode_fit": mf,
        "required_modifications": mods,
        "nutrition_status": "recalculation_required",
        "copyright_status": "transformed_summary",
        "canonical_recipe_family": canonical_family(name_zh or name),
    }
    return rec


# ---------------------------------------------------------------- 各书适配器

def parse_servings_en(text):
    m = re.search(r"\bSERVES?\s+(\d+)(?:\s*[–-]\s*\d+)?", text, re.I)
    if not m:
        m = re.search(r"\bMAKES\b[^\n.]{0,30}?(\d+)", text, re.I)
    return int(m.group(1)) if m else None


def parse_minutes_en(text):
    total = None
    m = re.search(r"TOTAL\s+(?:TIME[:\s]*)?(\d+)\s*(?:HOURS?\s*)?(\d+)?\s*MIN", text, re.I)
    if m:
        total = int(m.group(1)) * (60 if m.group(2) or "HOUR" in m.group(0).upper() else 1)
        if m.group(2):
            total += int(m.group(2))
    if total is None:
        pm = re.search(r"PREP(?:\s*TIME)?[:\s]+(\d+)\s*MIN", text, re.I)
        cm = re.search(r"COOK(?:\s*TIME)?[:\s]+(\d+)\s*MIN", text, re.I)
        if pm and cm:
            total = int(pm.group(1)) + int(cm.group(1))
    if total is None:
        m = re.search(r"TAKES\s+(?:ABOUT\s+)?(\d+)\s*(?:HOURS?\s*)?(\d+)?\s*MINUTES?", text, re.I)
        if m:
            total = int(m.group(1)) + int(m.group(2) or 0)
            if "HOUR" in m.group(0).upper():
                total = int(m.group(1)) * 60 + int(m.group(2) or 0)
    active = None
    m = re.search(r"PREP(?:\s*TIME)?[:\s]*(\d+)\s*MIN", text, re.I)
    if m:
        active = int(m.group(1))
    return active, total


ING_LINE_EN = re.compile(
    r"^(?:\d|½|¼|¾|⅛|⅜|⅝|⅞|⅓|⅔|a |an |few |some |small |large |medium |about )", re.I)
METHOD_START_EN = re.compile(
    r"^(?:heat|preheat|put|place|bring|cut|slice|chop|meanwhile|first|to serve|boil|drain|"
    r"in a |add |season|pour|peel|trim|finely|roughly|wash|pat |score|toast|crush|"
    r"using a|get|set |light|make |mix |whisk|stir |fry|cook |bake|roast)\b", re.I)


def guess_ingredients_from_text(lines, zh, max_n=25):
    """从纯文本行中猜食材行（英文：以数量/单位开头；中文：短行且含量词）"""
    ings, origs = [], []
    for ln in lines:
        ln = ln.strip()
        if not ln or len(ln) > 90:
            continue
        if zh:
            if re.search(r"\d+\s*(?:克|毫升|大匙|小匙|勺|杯|根|个|只|片|块|瓣|把|撮)", ln) and len(ln) < 40:
                nm = clean_cn_ingredient(ln)
                if nm and nm not in ings and len(nm) <= 12:
                    ings.append(nm)
                    origs.append(nm)
        else:
            if ING_LINE_EN.match(ln) and not METHOD_START_EN.match(ln):
                nm, orig = clean_en_ingredient(ln)
                if nm and 2 <= len(nm) <= 30 and nm not in ings:
                    ings.append(nm)
                    origs.append(orig)
        if len(ings) >= max_n:
            break
    return ings, origs


# ---------------------------------------------------------------- 通用切片器


def files_between(book, f1, f2):
    """同一目录下、文件名仅数字不同的 split 文件，返回 f1 与 f2 之间的有序文件列表"""
    def key(f):
        m = re.search(r"(\d+)(?=\D*$)", os.path.basename(f))
        return (os.path.dirname(f), re.sub(r"\d+(?=\D*$)", "", os.path.basename(f)),
                int(m.group(1)) if m else -1)
    d1, d2 = os.path.dirname(f1), os.path.dirname(f2)
    if os.path.dirname(f1) != os.path.dirname(f2):
        d1 = d1 or ""
    pat1 = re.sub(r"\d+(?=\D*$)", "", os.path.basename(f1))
    pat2 = re.sub(r"\d+(?=\D*$)", "", os.path.basename(f2))
    if pat1 != pat2 or os.path.dirname(f1) != os.path.dirname(f2):
        return []
    allf = sorted([n for n in book.z.namelist()
                   if os.path.dirname(n) == os.path.dirname(f1)
                   and re.sub(r"\d+(?=\D*$)", "", os.path.basename(n)) == pat1], key=key)
    try:
        i1, i2 = allf.index(f1), allf.index(f2)
        return allf[i1 + 1:i2] if i2 > i1 else []
    except ValueError:
        return []

def slice_by_markers(book, entries):
    """entries: [(title, src#anchor)] → [(title, location, text_slice)]
    同文件多个锚点按锚点位置切；下一条目在后续文件时，拼接中间所有文件
    （适配 calibre split 文件：标题在 split_N，正文在 split_N+1）。"""
    out = []
    n = len(entries)
    cache = {}

    def load(f):
        if f not in cache:
            cache[f] = book.read(f)
        return cache[f]

    for i, (title, src) in enumerate(entries):
        fname, _, anchor = src.partition("#")
        html = load(fname)
        start = book.anchor_pos(html, anchor) if anchor else 0
        if start < 0:
            m = re.search(re.escape(strip_html(title)[:20]), strip_html(html))
            start = 0 if m is None else m.start()
        parts = [html[start:]]
        for j in range(i + 1, n):
            f2, _, a2 = entries[j][1].partition("#")
            if f2 == fname:
                h2 = load(f2)
                p2 = book.anchor_pos(h2, a2) if a2 else -1
                if p2 > start:
                    parts = [html[start:p2]]
                break
            # 拼接 fname 与 f2 之间的所有中间文件（calibre split 正文常在标题后一个文件）
            mid = files_between(book, fname, f2)
            for mf in mid:
                parts.append(load(mf))
            h2 = load(f2)
            p2 = book.anchor_pos(h2, a2) if a2 else -1
            if p2 >= 0:
                parts.append(h2[:p2])
                break
            m2 = re.search(re.escape(strip_html(entries[j][0])[:20]), strip_html(h2))
            if m2 is not None and m2.start() < 500:
                break
            parts.append(h2)
        out.append((title, src, strip_html("".join(parts))))
    return out


# ---------------------------------------------------------------- 各书提取

FRONT_MATTER = re.compile(
    r"扉页|目录|版权|序言|前言|引言|introduction|contents|copyright|index|glossary|"
    r"acknowledg|about the author|conversion|equipment|pantry|tips|techniques|"
    r"how to (use|read)|stocking|appendix|bibliography", re.I)

# 章节入口类（菜谱在章节文件内部，不按 TOC 逐条列出）
CHAPTER_STYLE = ("sichuan", "uyenluu")


def extract_cooking_for_one(book):
    """The Ultimate Cooking for One Cookbook —— 每菜谱独立 xhtml，结构化 li"""
    recs = []
    for title, src in book.toc:
        if "_rec" not in src:
            continue
        html = book.read(src)
        ings = re.findall(r'<li class="rec-item">(.*?)</li>', html, re.S)
        core, orig = [], []
        for it in ings:
            nm, og = clean_en_ingredient(strip_html(it))
            if nm and nm not in core:
                core.append(nm)
                orig.append(og)
        if len(core) < 2:
            continue
        text = strip_html(html)
        active, total = parse_minutes_en(text)
        servings = parse_servings_en(text) or 1
        recs.append(make_record("ucfo", "The Ultimate Cooking for One Cookbook",
                                title, None, src, "explicit_recipe",
                                core, orig, text, zh=False,
                                original_servings=servings,
                                total_minutes=total, active_minutes=active))
    return recs


def extract_gouweier(book):
    """够味儿 —— TOC 逐条菜谱，主料/调料结构"""
    entries = []
    started = False
    for title, src in book.toc:
        if re.match(r"第[二2]", title):
            started = True
        if re.match(r"第[一1]章", title) or not started or FRONT_MATTER.match(title):
            continue
        if re.match(r"第[二三四五六七八九十]+", title) and "章" in title:
            continue  # 章标题本身
        entries.append((title, src))
    recs = []
    for title, src, text in slice_by_markers(book, entries):
        lines = [l for l in text.split("\n") if l.strip()]
        # 主料/调料 行
        ings, origs = [], []
        for m in re.finditer(r"(?:主料|调料|辅料|配料)[:：]([^\n]+)", text):
            for part in re.split(r"[，,、；;]", m.group(1)):
                nm = clean_cn_ingredient(part)
                if nm and nm not in ings and len(nm) <= 12:
                    ings.append(nm)
                    origs.append(nm)
        if not ings:
            ings, origs = guess_ingredients_from_text(lines, zh=True)
        if len(ings) < 2:
            continue  # 非菜谱条目（技巧页等）
        recs.append(make_record("gwe", "够味儿：80道经典家常菜烹饪详解",
                                None, title, src, "explicit_recipe",
                                ings, origs, text, zh=True))
    return recs


def extract_sichuan(book):
    """川菜（扶霞）—— 章节文件内 h3 为菜谱名（英文+中文两行）"""
    recs = []
    chapter_srcs = [src for title, src in book.toc
                    if re.match(r"凉菜|肉菜|蛋与家禽|水产海鲜|蔬菜|豆腐|汤|主食|小吃|甜品|点心|面", title)]
    for src in chapter_srcs:
        html = book.read(src)
        # 找所有 h3（英文 + 中文名）
        heads = [(m.start(), m.group(1)) for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.S)]
        for i, (pos, htxt) in enumerate(heads):
            raw = strip_html(htxt).strip()
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            en = lines[0] if lines else ""
            zhname = lines[1] if len(lines) > 1 else ""
            zhname = zhname if re.search(r"[一-鿿]", zhname) else ""
            end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
            text = strip_html(html[pos:end])
            lines2 = [l for l in text.split("\n") if l.strip()]
            ings, origs = guess_ingredients_from_text(lines2, zh=True)
            if len(ings) < 2:
                continue
            recs.append(make_record("sichuan", "川菜（扶霞·邓洛普）", en, zhname or None,
                                    "%s#%d" % (src, pos), "explicit_recipe",
                                    ings, origs, text, zh=True))
    return recs


def extract_uyenluu(book):
    """Vietnamese (Uyen Luu) —— 章节内 p.ct2 为菜谱名，p.hang 为食材行"""
    recs = []
    chapter_srcs = [src for title, src in book.toc if re.match(r"chapter\d+\.xhtml", src.split("#")[0])
                    and re.search(r"Chapter [1-9]", title)]
    for src in chapter_srcs:
        fname = src.split("#")[0]
        html = book.read(fname)
        heads = [(m.start(), m.group(1)) for m in re.finditer(r'<p class="ct2">(.*?)</p>', html, re.S)]
        for i, (pos, htxt) in enumerate(heads):
            name = strip_html(htxt).strip()
            end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
            block = html[pos:end]
            text = strip_html(block)
            ings, origs = [], []
            for m in re.finditer(r'<p class="hang">(.*?)</p>', block, re.S):
                nm, og = clean_en_ingredient(strip_html(m.group(1)))
                if nm and nm not in ings and len(nm) <= 30:
                    ings.append(nm)
                    origs.append(og)
            if len(ings) < 2:
                continue
            servings = parse_servings_en(text)
            active, total = parse_minutes_en(text)
            recs.append(make_record("uyenluu", "Vietnamese (Uyen Luu)", name, None,
                                    "%s#%d" % (fname, pos), "explicit_recipe",
                                    ings, origs, text, zh=False,
                                    original_servings=servings,
                                    total_minutes=total, active_minutes=active))
    return recs


def _toc_recipe_entries(book, chapter_pat, skip_first_chapter_title=True):
    """英文 calibre/常规书：TOC 逐条列菜谱；过滤章节首页与前后辅文"""
    entries = []
    seen_chapter = set()
    for title, src in book.toc:
        if FRONT_MATTER.match(title):
            continue
        f = src.split("#")[0]
        # 章节首页（与后续菜谱同文件但无锚点且标题像章节名）跳过
        if f in seen_chapter and src.endswith(f) and "#" not in src and re.match(r"^(chapter|CHAPTER|PART|\d+\s)", title):
            continue
        seen_chapter.add(f)
        entries.append((title, src))
    return entries


def extract_dinner_in_one(book):
    entries = _toc_recipe_entries(book, None)
    recs = []
    for title, src, text in slice_by_markers(book, entries):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 8:
            continue
        ings, origs = guess_ingredients_from_text(lines, zh=False)
        if len(ings) < 3:
            continue
        servings = parse_servings_en(text)
        active, total = parse_minutes_en(text)
        recs.append(make_record("d1", "Dinner in One (Melissa Clark)", title, None,
                                src, "explicit_recipe", ings, origs, text, zh=False,
                                original_servings=servings, total_minutes=total,
                                active_minutes=active))
    return recs


def _html_slices(book, entries):
    """slice_by_markers 的 HTML 版：返回原始 HTML 切片（供按标签提取食材）"""
    out = []
    cache = {}

    def load(f):
        if f not in cache:
            cache[f] = book.read(f)
        return cache[f]

    n = len(entries)
    for i, (title, src) in enumerate(entries):
        fname, _, anchor = src.partition("#")
        html = load(fname)
        start = book.anchor_pos(html, anchor) if anchor else 0
        if start < 0:
            m = re.search(re.escape(strip_html(title)[:20]), strip_html(html))
            start = 0 if m is None else m.start()
        parts = [html[start:]]
        for j in range(i + 1, n):
            f2, _, a2 = entries[j][1].partition("#")
            if f2 == fname:
                p2 = book.anchor_pos(h2, a2) if a2 else -1
                if p2 > start:
                    parts = [html[start:p2]]
                break
            for mf in files_between(book, fname, f2):
                parts.append(load(mf))
            h2 = load(f2)
            p2 = book.anchor_pos(h2, a2) if a2 else -1
            if p2 >= 0:
                parts.append(h2[:p2])
                break
            m2 = re.search(re.escape(strip_html(entries[j][0])[:20]), strip_html(h2))
            if m2 is not None and m2.start() < 500:
                break
            parts.append(h2)
        out.append((title, src, "".join(parts)))
    return out


def extract_jamie_one(book):
    """Jamie Oliver《One》—— 食材在 blockquote 标签中"""
    entries = _toc_recipe_entries(book, None)
    recs = []
    for title, src, html in _html_slices(book, entries):
        ings_raw = re.findall(r"<blockquote[^>]*>(.*?)</blockquote>", html, re.S)
        ings, origs = [], []
        for it in ings_raw:
            nm, og = clean_en_ingredient(strip_html(it))
            if nm and 2 <= len(nm) <= 30 and nm not in ings:
                ings.append(nm)
                origs.append(og)
        if len(ings) < 3:
            continue
        text = strip_html(html)
        servings = parse_servings_en(text)
        active, total = parse_minutes_en(text)
        recs.append(make_record("jone", "One: Simple One-Pan Wonders (Jamie Oliver)",
                                title, None, src, "explicit_recipe",
                                ings, origs, text, zh=False,
                                original_servings=servings, total_minutes=total,
                                active_minutes=active))
    return recs


def extract_one_pot(book):
    entries = _toc_recipe_entries(book, None)
    recs = []
    for title, src, text in slice_by_markers(book, entries):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 6:
            continue
        ings, origs = guess_ingredients_from_text(lines, zh=False)
        if len(ings) < 3:
            continue
        servings = parse_servings_en(text)
        active, total = parse_minutes_en(text)
        recs.append(make_record("opop", "One Pot, One Portion (Eleanor Wilkinson)",
                                title, None, src, "explicit_recipe",
                                ings, origs, text, zh=False,
                                original_servings=servings, total_minutes=total,
                                active_minutes=active))
    return recs


def extract_vfad(book):
    entries = _toc_recipe_entries(book, None)
    recs = []
    for title, src, text in slice_by_markers(book, entries):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 6:
            continue
        ings, origs = guess_ingredients_from_text(lines, zh=False)
        if len(ings) < 3:
            continue
        servings = parse_servings_en(text)
        active, total = parse_minutes_en(text)
        recs.append(make_record("vfad", "Vietnamese Food Any Day (Andrea Nguyen)",
                                title, None, src, "explicit_recipe",
                                ings, origs, text, zh=False,
                                original_servings=servings, total_minutes=total,
                                active_minutes=active))
    return recs


# ---------------------------------------------------------------- 主流程

BOOK_DEFS = [
    # (文件名片段, book_key, 提取函数) —— 顺序即匹配优先级，具体的在前
    ("Cooking for One", "ucfo", extract_cooking_for_one),
    ("够味儿", "gwe", extract_gouweier),
    ("川菜", "sichuan", extract_sichuan),
    ("Food Any Day", "vfad", extract_vfad),
    ("Uyen Luu", "uyenluu", extract_uyenluu),
    ("Dinner in One", "d1", extract_dinner_in_one),
    ("One Pot, One Portion", "opop", extract_one_pot),
    ("One _ simple one-pan", "jone", extract_jamie_one),
]

PROTOCOL_HINTS = re.compile(r"^(how to|basic|perfect|essential|master|技巧|基础)", re.I)


def classify_type(rec):
    """explicit_recipe 之外的轻量归类：无具体份量的基础做法标为 protocol_rule"""
    if len(rec["core_ingredients"]) <= 2 and rec["total_minutes"] is None:
        rec["extraction_type"] = "protocol_rule"
        rec["source_type"] = "book_pattern_derived"
    return rec


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else "/mnt/agents/upload"
    out_path = "../data/book-recipes.json"
    if "-o" in sys.argv:
        out_path = sys.argv[sys.argv.index("-o") + 1]
    epubs = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.lower().endswith(".epub")]
    all_recs, report = [], []
    used = set()
    for path in sorted(epubs):
        base = os.path.basename(path)
        fn = None
        for frag, key, f in BOOK_DEFS:
            if frag in base and key not in used:
                fn, used_key = f, key
                break
        if fn is None:
            report.append((base, 0, "未匹配适配器"))
            continue
        used.add(used_key)
        try:
            book = Epub(path)
            recs = [classify_type(r) for r in fn(book)]
            all_recs.extend(recs)
            report.append((base[:40], len(recs), used_key))
        except Exception as e:
            report.append((base[:40], 0, "错误: %s" % e))

    # canonical_recipe_family 去重标记
    fam = {}
    for r in all_recs:
        fam.setdefault(r["canonical_recipe_family"], []).append(r["id"])
    for r in all_recs:
        dups = [i for i in fam[r["canonical_recipe_family"]] if i != r["id"]]
        if dups:
            r["duplicate_of"] = dups

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"meta": {"books": len(report), "total_recipes": len(all_recs),
                            "note": "全部标记 recalculation_required；营养以本 skill 数据重算为准"},
                   "recipes": all_recs}, f, ensure_ascii=False, indent=1)
    print("共提取 %d 条" % len(all_recs))
    for b, n, k in report:
        print("  %-42s %4d 条  (%s)" % (b, n, k))


if __name__ == "__main__":
    main()
