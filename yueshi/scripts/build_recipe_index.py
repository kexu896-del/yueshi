#!/usr/bin/env python3
# build_recipe_index.py — 把 HowToCook 菜名索引（Markdown 表格）离线预处理为
# data/recipe-index.json。每道菜只保留检索所需字段（方案七）：
# id / original_name / category / core_ingredients / methods / structure /
# flavors / difficulty / estimated_active_minutes / equipment /
# adaptability / modification_notes / source_kcal（仅用于高能量初筛）
#
# 用法: python3 build_recipe_index.py 输入.md 输出.json
# 字段由规则推断，供运行时过滤参考；入选菜谱仍须按本计划克数重算营养。
import json, re, sys

SEASONINGS = set('''盐 糖 白糖 冰糖 红糖 生抽 老抽 酱油 蒸鱼豉油 蚝油 料酒 醋 白醋 香醋 陈醋 米醋
油 植物油 花生油 菜籽油 大豆油 橄榄油 香油 麻油 芝麻油 猪油 味精 鸡精 胡椒粉 白胡椒粉
黑胡椒粉 黑胡椒 花椒 花椒粉 麻椒 八角 桂皮 香叶 草果 山奈 白蔻 小茴 小茴香 十三香 五香粉
孜然 孜然粉 辣椒粉 辣椒面 干辣椒 小米椒 小米辣 朝天椒 泡椒 豆瓣酱 郫县豆瓣酱 豆豉
姜 生姜 老姜 姜片 蒜 大蒜 蒜蓉 蒜泥 葱 小葱 大葱 香葱 香菜 淀粉 生粉 玉米淀粉 红薯淀粉
面粉 高筋面粉 低筋面粉 中筋面粉 小苏打 泡打粉 酵母 干酵母 蜂蜜 芝麻酱 花生酱 咖喱粉
芥末 黄芥末 番茄酱 茄汁 米酒 白酒 黄酒 啤酒 白葡萄酒 红酒 水 清水 高汤 凉白开
海盐 椒盐 味极鲜 鱼露 甜面酱 柱候酱 叉烧酱 海鲜酱 沙茶酱 老干妈 腐乳 南乳 味淋
照烧汁 黑椒汁 炼乳 淡奶油 吉利丁 吉利丁片 可可粉 抹茶粉 椰蓉 糖粉 糖霜 食用盐'''.split())

EQUIP_WORDS = ['烤箱', '空气炸锅', '电饭煲', '电饭锅', '微波炉', '砂锅', '高压锅', '压力锅', '蒸锅', '平底锅', '不粘锅']

STAPLE_WORDS = ['米饭', '大米', '面', '挂面', '面条', '意面', '意大利面', '通心粉', '米粉', '米线', '河粉',
    '粉丝', '粉条', '红薯粉', '土豆粉', '年糕', '糯米', '汤圆', '饼', '馒头', '面包', '披萨', '饼皮',
    '土豆', '马铃薯', '红薯', '紫薯', '芋头', '山药', '玉米', '南瓜', '莲藕', '藕', '板栗', '粥']
SUGAR_WORDS = ['可乐', '雪碧', '糖', '冰糖', '蜂蜜', '糖浆', '糖醋', '拔丝', '甜']

PROTEIN_WORDS = ['鸡', '鸭', '鹅', '猪', '牛', '羊', '鱼', '虾', '蟹', '贝', '蚝', '蛋', '肉', '排骨',
    '蹄', '肝', '肠', '肚', '腰', '舌', '爪', '翅', '腿', '胸', '里脊', '五花', '腩', '蛙', '兔', '鸽',
    '豆腐', '豆干', '香干', '千张', '腐竹', '豆皮']

def clean_name(n):
    n = n.strip()
    n = re.sub(r'\.md$', '', n)
    n = re.sub(r'的做法$', '', n)
    return n.strip()

def split_ingredients(cell):
    cell = re.sub(r'\（[^）]*\）', '', cell)          # 去括号注释
    cell = cell.replace('（', '、').replace('）', '、')
    parts = re.split(r'[、，,/]| - |^- ', cell)
    out, seen = [], set()
    EQUIP_ONLY = {'平底锅', '炒锅', '砂锅', '碗', '盆', '汤锅', '蒸锅', '搅拌器', '料理机', '破壁机'}
    for p in parts:
        p = p.strip(' -　').strip()
        if not p or len(p) > 12: continue
        p = re.sub(r'\d+\s*(厘米|cm|克|g|ml|毫升|个|只|片|块|根|勺|茶匙|汤匙|颗|袋|盒|罐)\s*$', '', p).strip()
        p = re.sub(r'\d+\s*(厘米|cm).*$', '', p).strip()   # "32 厘米以上的炒锅一个"类
        if not p: continue
        if p in EQUIP_ONLY or (('锅' in p or '碗' in p or '盆' in p) and not re.search(r'(肉|鸡|鸭|鱼|虾|蛋|菜|菇|椒|豆|瓜|笋|藕|米|面|腐)', p)):
            continue
        p = re.sub(r'^(或|或者|及|和|与)\s*', '', p)
        p = p.split(' or ')[0].split('/')[0].strip()
        p = re.sub(r'^(新鲜|冰鲜|速冻|冷冻|有机)', '', p).strip()
        base = p
        if base and base not in seen:
            seen.add(base); out.append(base)
    return out

def is_seasoning(x):
    if x in SEASONINGS: return True
    return any(x == s or x.endswith(s) and len(x) <= len(s)+2 for s in SEASONINGS)

def detect_methods(text):
    m = []
    for kw, name in [('凉拌', '凉拌'), ('白灼', '白灼'), ('清蒸', '蒸'), ('蒸', '蒸'),
        ('红烧', '烧'), ('黄焖', '焖'), ('焖', '焖'), ('炖', '炖'), ('煲汤', '煲'), ('煲', '煲'),
        ('煮汤', '煮'), ('煮', '煮'), ('煎', '煎'), ('炸', '炸'), ('烤', '烤'),
        ('卤', '卤'), ('烩', '烩'), ('炒', '炒'), ('腌', '腌'), ('冻', '冷藏定型'), ('打发', '烘焙')]:
        if kw in text and name not in m:
            m.append(name)
    if '烘焙' in text and '烘焙' not in m: m.append('烘焙')
    return m or ['炒']

def detect_flavors(text):
    f = []
    for kw, name in [('麻辣', '麻辣'), ('香辣', '麻辣'), ('酸辣', '酸辣'), ('泡椒', '酸辣'),
        ('糖醋', '酸甜'), ('酸甜', '酸甜'), ('茄汁', '酸甜'), ('番茄', '酸甜'), ('菠萝', '酸甜'),
        ('咖喱', '咖喱'), ('孜然', '孜然'), ('蒜蓉', '蒜香'), ('蒜香', '蒜香'),
        ('黑椒', '黑椒'), ('照烧', '照烧'), ('椒盐', '椒盐'), ('葱油', '葱香'), ('葱烧', '葱香'),
        ('红烧', '酱香'), ('黄焖', '酱香'), ('酱', '酱香'), ('卤', '酱香'), ('豆豉', '豉香'),
        ('蚝油', '咸鲜'), ('清蒸', '清淡'), ('白灼', '清淡'), ('上汤', '清淡'), ('清炒', '清淡'),
        ('清炖', '清淡'), ('奶油', '奶香'), ('芝士', '奶香'), ('奶酪', '奶香'), ('黄油', '奶香'),
        ('啤酒', '酒香'), ('咸甜', '咸甜'), ('咸香', '咸鲜')]:
        if kw in text and name not in f:
            f.append(name)
    return f[:2] or ['咸鲜']

def detect_equipment(text, methods):
    eq = [w for w in EQUIP_WORDS if w in text]
    if not eq:
        if '烤' in methods: eq = ['烤箱']
        elif '蒸' in methods: eq = ['蒸锅']
        elif '炒' in methods: eq = ['炒锅']
        elif '炸' in methods or '煎' in methods: eq = ['平底锅']
        else: eq = ['汤锅']
    return list(dict.fromkeys(eq))

def classify_structure(cat, methods, name):
    if cat in ('汤羹',): return '汤羹'
    if cat in ('主食', '米饭'): return '主食'
    if cat in ('饮品',): return '饮品'
    if cat in ('酱料',): return '酱料'
    if cat in ('半成品加工',): return '半成品'
    if cat == '甜品': return '甜品'
    if '凉拌' in methods or '白灼' in methods: return '凉拌'
    if '焖' in methods or '炖' in methods or '煲' in methods: return '一锅炖煮'
    if '蒸' in methods: return '蒸菜'
    if '烤' in methods or '烘焙' in methods: return '烤制'
    if '炸' in methods or '煎' in methods: return '煎炸'
    if '烧' in methods or '卤' in methods or '烩' in methods: return '烧菜'
    if '煮' in methods: return '煮菜'
    if '炒' in methods: return '快炒'
    if '腌' in methods: return '腌制'
    return '其他'

def adaptability(cat, ings, methods, text, kcal):
    low_carb_block = any(w in ''.join(ings) for w in STAPLE_WORDS) or cat in ('主食', '米饭', '饮品')
    sweet_block = any(w in text for w in ['糖醋', '拔丝', '可乐', '糖浆']) or cat == '甜品'
    fried = '炸' in methods
    protein_based = any(w in ''.join(ings) for w in PROTEIN_WORDS)

    if cat in ('甜品', '饮品', '酱料', '半成品加工'):
        keto = 'none'
    elif low_carb_block and protein_based:
        keto = 'medium'   # 主食/薯芋可去掉或换叶菜
    elif low_carb_block:
        keto = 'low'
    elif sweet_block:
        keto = 'medium'   # 去糖后可入
    elif protein_based:
        keto = 'high'
    else:
        keto = 'medium'

    if cat in ('甜品', '饮品', '酱料'):
        hormone = 'none' if cat != '饮品' else 'low'
    elif fried or (kcal and kcal >= 900) or sweet_block:
        hormone = 'low'
    elif low_carb_block or protein_based:
        hormone = 'high'
    else:
        hormone = 'medium'
    return {'keto_biologic': keto, 'hormone_balance': hormone}

def mod_notes(keto, hormone, cat, methods, text, kcal):
    n = []
    if keto == 'high': n.append('酮生物模式直接可用')
    elif keto == 'medium':
        if any(w in text for w in ['糖', '糖醋', '可乐']): n.append('去糖/代糖后可入酮生物')
        if any(w in text for w in ['勾芡', '淀粉']): n.append('不勾芡可降净碳水')
        n.append('主食/薯芋配料去掉或换叶菜后可入酮生物' if keto == 'medium' else '')
    elif keto == 'low': n.append('含主食/薯芋，酮生物模式仅可极少量改造')
    else: n.append('主食/甜品/酱料类，酮生物模式不可用')
    if hormone == 'high': n.append('平衡激素模式直接可用，可配糙米/薯类')
    elif hormone == 'low': n.append('高油或高糖，平衡激素模式每周限 1 次内')
    if '炸' in methods: n.append('油炸菜品，建议每周≤1次')
    if kcal and kcal >= 800: n.append(f'原始方约 {kcal} kcal/份，注意减量分食')
    return [x for x in n if x]

DIFF_MIN = {1: 10, 2: 15, 3: 20, 4: 30, 5: 45}

# 食材列为空时的兜底词表（从做法/介绍文本里扫食材）
FOOD_VOCAB = ['鸡腿', '鸡翅', '鸡胸肉', '鸡蛋', '鸭蛋', '猪肉', '五花肉', '里脊', '排骨', '猪蹄', '肘子',
    '牛肉', '牛腩', '牛排', '牛柳', '羊肉', '羊排', '鱼', '鲈鱼', '鳕鱼', '三文鱼', '带鱼', '虾', '蟹',
    '豆腐', '豆干', '香干', '千张', '豆皮', '腐竹', '丸子', '米饭', '大米', '面条', '意面', '面粉',
    '土豆', '胡萝卜', '洋葱', '西红柿', '番茄', '青椒', '黄瓜', '白菜', '菠菜', '生菜', '西兰花',
    '南瓜', '玉米', '红薯', '山药', '莲藕', '香菇', '木耳', '金针菇', '魔芋', '凉粉', '咖喱块',
    '牛奶', '酸奶', '黄油', '芝士', '奶酪', '奶油', '牛油果', '燕麦', '糙米', '藜麦']

MAIN_CATS = ['荤菜', '水产', '素菜', '汤羹', '主食', '早餐', '饮品', '甜品', '酱料', '半成品加工']
FISH_WORDS = ['鱼', '虾', '蟹', '贝', '蚝', '蛏', '鳝', '鱔', '鲈', '桂鱼', '鳜', '鲍', '螺', '鱿', '带鱼', '鳕鱼', '三文鱼']
MEAT_WORDS = ['鸡', '鸭', '鹅', '猪', '牛', '羊', '肉', '排骨', '蹄', '肝', '肠', '蛙', '兔', '鸽', '鸡爪', '培根', '腊肠', '火腿']
DESSERT_WORDS = ['蛋糕', '冰淇淋', '奶冻', '饼干', '司康', '雪媚娘', '雪花酥', '布丁', '冰粉', '龟苓膏', '蛋挞', '面包', '芋头', 'dessert', '芝士']
DRINK_WORDS = ['特调', '冰沙', '金汤力', '金菲士', '柠檬水', '酸梅汤', '醪糟', '红茶', '咖啡']
STAPLE_NAME = ['饭', '面', '粉', '饼', '汤圆', '煲仔饭', '炊饭', '拌饭', '凉粉', '粥']

def normalize_category(cat, name, ings):
    if cat in MAIN_CATS:
        return '甜品' if cat == 'dessert' else cat
    t = name + ''.join(ings)
    if any(w in t for w in FISH_WORDS) and not any(w in name for w in ['蛋挞']): return '水产'
    if any(w in name for w in DESSERT_WORDS): return '甜品'
    if any(w in name for w in DRINK_WORDS): return '饮品'
    if '汤' in name or '羹' in name: return '汤羹'
    if any(w in name for w in STAPLE_NAME): return '主食'
    if any(w in t for w in MEAT_WORDS): return '荤菜'
    return '素菜'

def main(src, dst):
    rows = []
    for line in open(src, encoding='utf-8'):
        line = line.strip()
        if not line.startswith('|'): continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 6: continue
        if cells[0] in ('菜名', '') or set(cells[0]) <= set('-: '): continue
        rows.append(cells)
    out, seen = [], {}
    for c in rows:
        name = clean_name(c[0])
        if not name or name == '示例菜': continue
        if name in seen: continue
        seen[name] = 1
        cat = c[1]
        raw_cat = cat
        diff = c[2].count('★') or 1
        mk = re.search(r'(\d+)\s*大卡', c[3])
        kcal = int(mk.group(1)) if mk else None
        ings = split_ingredients(c[4])
        text = ' '.join([name, c[5], c[6] if len(c) > 6 else ''])
        methods = detect_methods(text + ' ' + c[4])
        core = [x for x in ings if not is_seasoning(x)][:5]
        guessed = False
        if not core:
            core = [w for w in FOOD_VOCAB if w in text][:5]
            guessed = bool(core)
        cat = normalize_category(raw_cat, name, core)
        struct = classify_structure(cat, methods, name)
        minutes = DIFF_MIN.get(diff, 20)
        if struct in ('汤羹', '一锅炖煮'): minutes = min(minutes, 20)
        if struct == '凉拌': minutes = min(minutes, 15)
        ad = adaptability(cat, core, methods, text, kcal)
        equipment = detect_equipment(text + ' ' + c[4], methods)
        if cat == '饮品':
            methods, equipment = ['调制'], []
        elif cat == '甜品' and '烘焙' not in methods and '烤' not in methods:
            methods = ['调制']
        out.append({
            'id': f'htc-{len(out)+1:03d}',
            'original_name': name,
            'category': cat,
            'core_ingredients': core,
            'core_guessed': guessed,
            'methods': methods[:3],
            'structure': struct,
            'flavors': detect_flavors(text),
            'difficulty': diff,
            'estimated_active_minutes': minutes,
            'equipment': equipment,
            'adaptability': ad,
            'modification_notes': mod_notes(ad['keto_biologic'], ad['hormone_balance'], cat, methods, text, kcal),
            'source_kcal': kcal,
        })
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cats = {}
    for r in out: cats[r['category']] = cats.get(r['category'], 0) + 1
    print(f'{len(out)} 道菜 → {dst}')
    print('分类分布:', dict(sorted(cats.items(), key=lambda x: -x[1])))
    keto = sum(1 for r in out if r['adaptability']['keto_biologic'] == 'high')
    horm = sum(1 for r in out if r['adaptability']['hormone_balance'] == 'high')
    print(f'酮生物直接可用 {keto} 道 · 平衡激素直接可用 {horm} 道')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
