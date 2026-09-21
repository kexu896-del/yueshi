import os
import sys
from pathlib import Path

# v1.4（PRD）：程序文件目录与用户数据目录分离。
# 冻结（打包 EXE）：用户数据写 %LOCALAPPDATA%\YueshiDingdongHelper，
# 程序目录（Program Files）不写入任何用户数据；
# 源码开发模式：自 v1.7 起同样写 %LOCALAPPDATA%（结构优化方案第二轮），
# 项目文件夹只留源码，不再堆积 browser-profile/output/logs。
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent
DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "YueshiDingdongHelper"
)

DINGDONG_HOME = "https://wx.m.ddxq.mobi/#/"

PROFILE_DIR = DATA_DIR / "browser-profile"
OUTPUT_DIR = DATA_DIR / "output"
LOG_DIR = DATA_DIR / "logs"

# v1.3.1 修复：底层文件名一律 ASCII（zip 解压/cmd 对中文文件名不可靠）；
# 中文只出现在界面文案。输入不依赖固定文件名——见 app.resolve_query_file。
QUERY_FILE = DATA_DIR / "月食-查价清单.json"
QUERY_FILE_LEGACY = QUERY_FILE  # 同名，占位兼容
RESULT_FILE = OUTPUT_DIR / "月食-叮咚价格结果.json"
NETWORK_LOG_FILE = LOG_DIR / "network-responses.jsonl"
DIAGNOSTICS_FILE = LOG_DIR / "diagnostics.json"

# 开发模式隔离：正式构建（windowed EXE / 普通双击）代码层禁用侦察；
# 仅当显式设置环境变量 YUESHI_DEV=1 时才开放 --inspect 与开发者菜单。
INSPECT_ALLOWED = os.environ.get("YUESHI_DEV") == "1"

# 助手版本号（2026-09-18 新增）：写入结果根级 provider_version，
# 月食侧 price_snapshot_meta 透传，便于核对批次来源版本。
APP_VERSION = "2.1"

# 第一版建议只取前 5 个候选，避免无必要遍历。
MAX_CANDIDATES_PER_QUERY = 5

# 侦察模式只记录 JSON 响应的元数据和有限预览。
# 不记录 Cookie、请求头、手机号、地址全文或验证码。
MAX_RESPONSE_PREVIEW_CHARS = 3000

# 以下是占位关键词，并非对叮咚当前接口的事实描述。
# 首次 inspect 后，应根据实际响应 URL 与结构收紧。
PRODUCT_RESPONSE_URL_HINTS = (
    "search",
    "product",
    "goods",
    "item",
    "sku",
)

# 页面选择器仅作为回退候选。
# 上线前必须在真实页面中确认，不能视为已验证选择器。
SELECTORS = {
    "search_entry": [
        "input[type='search']",
        "input[placeholder*='搜索']",
        "[class*='search'] input",
        "[class*='search']",
    ],
    "search_input": [
        "input[type='search']",
        "input[placeholder*='搜索']",
        "input",
    ],
    "product_card": [
        "[class*='product']",
        "[class*='goods']",
        "[class*='item-card']",
    ],
    "product_name": [
        "[class*='name']",
        "[class*='title']",
    ],
    "package_text": [
        "[class*='spec']",
        "[class*='sub-title']",
        "[class*='subtitle']",
    ],
    "price": [
        "[class*='price']",
    ],
    "sold_out": [
        "text=已售罄",
        "text=补货中",
        "text=无货",
    ],
    "address": [
        "[class*='address']",
        "[class*='addr']",
        "[class*='location']",
        "[class*='station']",
        "[class*='position']",
        "[class*='city']",
        "[class*='area']",
        "[class*='district']",
        "[id*='address']",
        "[id*='location']",
    ],
}
# ---- 形态与加工状态词典（v2.0，对应主库 yueshi/data/product-form-dictionary.json）----
# 让候选与菜谱做法匹配：整腿需求不被肉丁/鸡块替代；熟食形态直接拒绝。
# 本字典是主库的构建快照；主库更新时同步此处并提升 FORM_DICTIONARY_VERSION。
FORM_DICTIONARY_VERSION = "1.4.0"

FORM_KEYWORDS: dict[str, tuple[str, ...]] = {
    # 切配形态（限制性：菜谱未允许时不得替代原始食材）
    "diced": ("丁",),
    "shredded": ("丝",),
    "sliced": ("片",),
    "minced": ("末", "糜", "泥"),
    "cut_pieces": ("切块", "块"),
    "filled": ("馅",),
    "ball": ("丸",),
    "patty": ("排",),
    "pie": ("饼",),
    "roll": ("卷",),
    # 加工状态（限制性）
    "marinated": ("腌制", "奥尔良", "黑椒", "孜然", "调味"),
    "cooked": ("熟食", "即食", "烤", "炸", "卤", "预制", "调理", "半成品"),
    # round58 新增限制性形态（与主库 product-form-dictionary.json 1.3.0 同步）：
    # 腊制/风干（查询鲜鸡腿时腊鸡腿不得替代）；刺身/生食（刺身不是默认熟食烹饪候选）
    "cured": ("腊", "腊制", "腌腊", "风干"),
    "sashimi": ("刺身", "生鱼片", "生食"),
    # 部位/整件形态
    "whole_leg": ("琵琶腿", "整腿", "鸡大腿", "鸡腿"),
    "drumstick": ("琵琶腿",),
    "wing": ("翅",),
    "breast": ("胸",),
    "whole": ("整只", "整条", "整根", "整块", "整"),
    "whole_leaf": ("整棵", "整颗"),
    # 蛋类加工形态（限制性：查询"鸡蛋"时软饼/卤蛋/咸蛋不得替代带壳鲜蛋）
    "shell_egg": ("带壳", "鲜鸡蛋", "土鸡蛋", "谷物蛋", "柴鸡蛋", "可生食鸡蛋"),
    "pancake": ("软饼", "煎饼", "蛋饼", "手抓饼", "鸡蛋饼"),
    "pastry": ("蛋糕", "蛋酥", "蛋黄酥", "糕点"),
    "cooked_egg": ("卤蛋", "茶叶蛋", "熟蛋", "溏心蛋", "温泉蛋"),
    "salted_egg": ("咸蛋", "咸鸭", "皮蛋", "松花蛋"),
    # 保鲜状态（非限制性，仅标注）
    "fresh": ("冷鲜", "冰鲜", "鲜"),
    "frozen": ("冷冻", "速冻"),
    # round65 新增（与主库 product-form-dictionary.json 1.4.0 同步）：
    # 根茎/生鲜原料（非限制性标注）；叶部位、油炸、裹粉、即食、加工小吃（限制性）
    "raw": ("生鲜", "原料"),
    "root_tuber": ("红薯", "地瓜", "番薯", "蜜薯", "紫薯", "根茎"),
    "frozen_raw": ("冻品",),
    "leaf": ("叶", "苗", "尖"),
    "fried": ("炸", "酥", "脆"),
    "breaded": ("裹粉", "面包糠", "小方", "鸡米花"),
    "ready_to_eat": ("即食", "开袋即食", "熟食"),
    "cooked_snack": ("甘梅", "烤肠", "零食", "小吃"),
}

# 限制性形态：设置 allowed_forms 时，命中且不在允许清单内即拒
# （鸡腿块 ≠ 整腿；肉丁 ≠ 整肉）。
RESTRICTIVE_FORMS = frozenset({
    "diced", "shredded", "sliced", "minced", "cut_pieces",
    "filled", "ball", "patty", "pie", "roll",
    "marinated", "cooked", "cured", "sashimi",
    "pancake", "pastry", "cooked_egg", "salted_egg",
    "leaf", "fried", "breaded", "ready_to_eat", "cooked_snack",
})

# 形态词中的加工状态词需先过否定前缀（「免腌制」「未调味」不误伤）。
_NEGATION_PREFIXES = ("免", "无", "不含", "未", "去")

# ---- 条件接受（round54）：本体合格但附独立调味包的商品 ----
# 命中后候选不拒绝，标记 conditional_accept 并生成 purchase_note 提示
# （如"调味牛肉（附独立调味包，可不用）"）。仅识别独立附赠包，
# 本体已调味仍走 marinated 门禁。
CONDITIONAL_ACCEPT_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (attach, pack)
    for attach in ("附", "赠", "含", "送", "配")
    for pack in ("调味包", "酱料包", "料包", "酱汁包", "蘸料")
)


CATALOG_RULES_VERSION = "1.6.0"

# ---- 食材目录规则快照（round58，对应主库 ingredient-catalog.json 1.3.0 query_profile）----
# 精简查价清单只携带 ingredient_id + 需求 + 用途约束时，由本快照展开匹配规则；
# 清单逐项字段存在时优先（override）。主库更新时同步此处并提升 CATALOG_RULES_VERSION。
CATALOG_RULES: dict[str, dict] = {
    "鸡腿": {
        "exact_terms": ["鸡腿"],
        "aliases": ["鸡大腿", "琵琶腿"],
        "allowed_forms": ["whole_leg", "drumstick"],
        "excluded_forms": ["marinated", "cooked", "cured"],
        # 拒绝腊制、腌制（round58 人工剔除规则回写）
        "hard_excluded_terms": ["腊鸡腿", "腊制"],
    },
    "三文鱼": {
        "exact_terms": ["三文鱼"],
        "aliases": ["鲑鱼"],
        "excluded_forms": ["sashimi", "marinated"],
        # 刺身不是默认熟食烹饪候选；附独立调味包走 conditional_accept，本体调味由 marinated 拒绝
        "hard_excluded_terms": ["刺身", "生鱼片"],
    },
    "玉米": {
        "exact_terms": ["鲜玉米", "甜玉米", "玉米"],
        "aliases": ["甜玉米", "水果玉米"],
        "excluded_forms": ["cooked"],
        # 拒绝玉米须茶等饮品
        "hard_excluded_terms": ["玉米须", "玉米茶", "茶饮", "饮品"],
    },
    "芹菜": {
        "exact_terms": ["芹菜"],
        "aliases": ["香芹"],
        # 拒绝芹菜牛肉丝等组合菜（芹菜用量不可控，主料非芹菜）
        "hard_excluded_terms": ["牛肉丝", "肉丝", "组合菜", "芹菜牛肉"],
    },
    # round65 新增（与主库 ingredient-catalog.json 1.6.0 query_profile 同步）：
    "鸡蛋": {
        "exact_terms": ["鸡蛋"],
        "aliases": ["鲜鸡蛋", "土鸡蛋", "谷物蛋"],
        "allowed_forms": ["shell_egg", "fresh", "frozen"],
        "excluded_forms": ["cooked", "pancake", "pastry", "cooked_egg", "salted_egg", "ready_to_eat"],
        # 鸡蛋软饼/蛋糕/卤蛋等蛋制品不得替代带壳鲜蛋
        "hard_excluded_terms": ["软饼", "煎饼", "蛋糕", "卤蛋", "茶叶蛋", "咸蛋", "皮蛋"],
    },
    "红薯": {
        "exact_terms": ["红薯", "地瓜"],
        "aliases": ["番薯", "山芋", "蜜薯", "紫薯"],
        "required_category": "root_tuber",
        "allowed_forms": ["root_tuber", "fresh", "raw", "whole"],
        "excluded_forms": ["leaf", "cooked_snack", "fried", "ready_to_eat", "pastry"],
        # 地瓜叶/番薯叶是茎叶不是根茎；甘梅地瓜条是加工小吃
        "hard_excluded_terms": ["地瓜叶", "番薯叶", "红薯叶", "甘梅", "地瓜条", "红薯干"],
    },
    "猪里脊": {
        "exact_terms": ["猪里脊", "里脊肉"],
        "aliases": ["猪里脊肉", "小里脊"],
        "allowed_forms": ["raw", "fresh", "frozen_raw"],
        "excluded_forms": ["cooked", "fried", "breaded", "ready_to_eat", "marinated"],
        # 香炸里脊小方等油炸/裹粉预制制品不得作为生鲜里脊候选
        "hard_excluded_terms": ["炸", "小方", "裹粉", "即食", "熟食"],
    },
}


def catalog_rule_for(ingredient_id: str) -> dict:
    """按 ingredient_id 查目录规则快照；无记录返回空 dict。"""
    return CATALOG_RULES.get(ingredient_id) or {}


def detect_conditional_accept(name: str) -> bool:
    """识别「附/赠/含/送/配 + 调味包/酱料包/料包/酱汁包/蘸料」的独立调味包提示。"""
    return any(attach + pack in name for attach, pack in CONDITIONAL_ACCEPT_PAIRS)


def conditional_accept_note(name: str) -> str:
    """生成购买备注；未命中返回空串。"""
    if not detect_conditional_accept(name):
        return ""
    for attach, pack in CONDITIONAL_ACCEPT_PAIRS:
        if attach + pack in name:
            return f"附独立{pack}，可不用"
    return ""


def form_keywords(forms: list[str]) -> list[str]:
    """展开形态名为关键词；未登记形态按原样作为关键词兜底。"""
    words: list[str] = []
    for form in forms:
        words.extend(FORM_KEYWORDS.get(form, (form,)))
    return list(dict.fromkeys(words))


def _negated(name: str, idx: int) -> bool:
    """命中位置前两字符内带否定前缀（免/无/不含/未/去）。"""
    prefix = name[max(0, idx - 2):idx]
    return any(prefix.endswith(neg) for neg in _NEGATION_PREFIXES)


def detect_forms(name: str) -> list[str]:
    """识别商品名含有的形态/加工状态（按词典登记顺序返回）。

    - 否定前缀守卫：「免腌制」不识别为 marinated；
    - 「整块」归 whole 不归 cut_pieces（切块才是 cut_pieces）。
    """
    found: list[str] = []
    for form, words in FORM_KEYWORDS.items():
        for word in words:
            start = 0
            hit = False
            while True:
                idx = name.find(word, start)
                if idx < 0:
                    break
                if form in ("marinated", "cooked") and _negated(name, idx):
                    start = idx + 1
                    continue
                if form == "cut_pieces" and name[max(0, idx - 1):idx] == "整":
                    start = idx + 1
                    continue
                hit = True
                break
            if hit:
                found.append(form)
                break
    return found


# ---- 价格单位门禁 ----
# 数值型价格字段必须在此显式登记单位后才允许换算。
# 未登记字段一律标记 PRICE_UNIT_UNCONFIRMED，
# 禁止按数值大小猜测单位（禁止 price > 100 就 /100 的启发式）。
# 首次 inspect 确认真实字段语义后，按实际字段名登记，例如：
# PRICE_FIELD_UNITS = {"price": "cent", "sale_price": "cent"}
# 2026-08-26 经真实 search/searchProduct 响应确认：
# price / origin_price / vip_price 均为字符串形式、单位元。
PRICE_FIELD_UNITS: dict[str, str] = {
    "price": "yuan",
    "origin_price": "yuan",
    "vip_price": "yuan",
}

# ---- 只读门禁 ----
# 正式代码禁止出现的动作。
FORBIDDEN_ACTIONS = (
    "购物车按钮点击",
    "结算按钮点击",
    "支付按钮点击",
    "领取优惠券",
    "提交订单",
    "修改地址",
)

# 当前 URL 命中以下片段时中止运行，避免误入交易链路。
FORBIDDEN_URL_HINTS = (
    "cart",
    "checkout",
    "/pay",
    "order/submit",
    "coupon",
)

# 程序只允许点击搜索入口；点击前若识别到以下按钮文本则拒绝执行。
FORBIDDEN_BUTTON_TEXTS = (
    "加入购物车",
    "去结算",
    "立即结算",
    "立即支付",
    "提交订单",
    "领取优惠券",
    "修改地址",
)
