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
# ---- 形态与加工状态词典（round73 单一来源化） ----
# 本段内容不再手写：由月食主库经 scripts/export_helper_semantics.py 导出为
# 内嵌快照 semantics-snapshot.json（构建时随包分发），此处只做加载与派生。
# 主库更新时提升主库版本并重跑导出；快照与代码不同版由月食侧回归测试兜底。
import json as _json

_SNAP_PATH = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) \
    / "semantics-snapshot.json"
with open(_SNAP_PATH, encoding="utf-8") as _snap_f:
    _SNAPSHOT = _json.load(_snap_f)

FORM_DICTIONARY_VERSION = _SNAPSHOT["form_dictionary"]["version"]

FORM_KEYWORDS: dict[str, tuple[str, ...]] = {
    form: tuple(spec.get("keywords") or ())
    for form, spec in _SNAPSHOT["form_dictionary"]["forms"].items()
}

# 限制性形态：设置 allowed_forms 时，命中且不在允许清单内即拒
# （鸡腿块 ≠ 整腿；肉丁 ≠ 整肉）。
RESTRICTIVE_FORMS = frozenset(
    form for form, spec in _SNAPSHOT["form_dictionary"]["forms"].items()
    if spec.get("restrictive")
)

# 形态词中的加工状态词需先过否定前缀（「免腌制」「未调味」不误伤）。
# 守卫适用形态集合与主库商品语义词汇契约一致。
_NEGATION_PREFIXES = tuple(_SNAPSHOT["form_dictionary"]["negation_prefixes"])
NEGATION_GUARD_FORMS = frozenset(
    _SNAPSHOT["commodity_vocabulary"].get("processing_state_forms") or []
)

# ---- 条件接受（round54）：本体合格但附独立调味包的商品 ----
# 命中后候选不拒绝，标记 conditional_accept 并生成 purchase_note 提示
# （如"调味牛肉（附独立调味包，可不用）"）。仅识别独立附赠包，
# 本体已调味仍走 marinated 门禁。
_CA = _SNAPSHOT["form_dictionary"]["conditional_accept"] or {}
CONDITIONAL_ACCEPT_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (attach, pack)
    for attach in _CA.get("attach_prefixes") or []
    for pack in _CA.get("packs") or []
)


CATALOG_RULES_VERSION = _SNAPSHOT["catalog"]["version"]

# ---- 食材目录规则快照（round58 起，round73 单一来源化） ----
# 精简查价清单只携带 ingredient_id + 需求 + 用途约束时，由本快照展开匹配规则；
# 清单逐项字段存在时优先（override）。字段名与主库 ingredient-catalog.json
# query_profile 一致（excluded_states 等），不再维护手抄副本。
CATALOG_RULES: dict[str, dict] = _SNAPSHOT["catalog"]["rules"]


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


def _negated(name: str, idx: int) -> bool:
    """命中位置前两字符内带否定前缀（免/无/不含/未/去）。"""
    prefix = name[max(0, idx - 2):idx]
    return any(prefix.endswith(neg) for neg in _NEGATION_PREFIXES)


def detect_forms(name: str) -> list[str]:
    """识别商品名含有的形态/加工状态（按词典登记顺序返回）。

    round73 与主词典「规则」及月食端对齐：
    - 否定前缀守卫只作用于加工状态形态（NEGATION_GUARD_FORMS）；
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
                if form in NEGATION_GUARD_FORMS and _negated(name, idx):
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
