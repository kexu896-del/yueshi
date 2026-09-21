#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品语义门禁（round67，2026-09-18）

原则（references/price-provider-policy.md §7-§11）：
- 商品名称命中只用于召回，不能单独决定接受；
- 门禁顺序：食品/非食品 → 大品类一致 → 物种/植物主体一致 → 部位/可食部分一致
  → 单一原料/复合食品一致 → 加工状态符合用途 → 特定要求（无添加糖/全谷物）满足；
- 三态决策：accepted / rejected / review_required；证据不足一律 review_required，
  不得自动进入正式采购建议；
- 维护原因类别，不维护具体商品全称。
"""
import json, os, re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

DECISIONS = ("accepted", "rejected", "review_required")

REJECTION_REASONS = (
    "non_food_product", "category_conflict", "species_conflict", "wrong_plant_part",
    "wrong_animal_cut", "composite_food", "prepared_dish", "snack_product",
    "wrong_processing_state", "requirement_not_verified", "insufficient_identity_evidence",
    # round68：plain 单品要求下的调味/混合拒收（如「0蔗糖酸奶（西柚脐橙燕麦爆珠）」）
    "flavored_product", "mixed_composition",
)

SPECIES_TERMS = {
    "猪": ["猪"], "牛": ["牛"], "羊": ["羊"], "鸡": ["鸡"], "鸭": ["鸭"], "鹅": ["鹅"],
}
# round67.1：物种词误伤守卫——「牛奶/奶油/牛油果/牛油/蜗牛」不是牛肉冲突。
SPECIES_TERM_EXCEPTIONS = {
    "牛": ["牛奶", "奶油", "牛油果", "牛油", "蜗牛"],
    "鸡": ["鸡蛋"],
}

CATEGORY_TERMS = {
    "yogurt": ["酸奶", "发酵乳", "乳酪"],
    "fermented_milk": ["发酵乳", "酸奶"],
    "bread": ["面包", "吐司", "欧包", "贝果", "法棍", "餐包", "列巴", "司康"],
    "tofu": ["豆腐"],
    "pumpkin": ["南瓜"],
    "celery": ["芹菜", "香芹"],
    "hairtail": ["带鱼"],
}

COMPOSITE_TERMS = ["香干", "炒", "沙拉", "汉堡", "三明治", "披萨", "寿司", "便当",
                   "盖饭", "炒饭", "拌面", "套餐", "组合", "拼盘", "串", "粗粮包", "混合装"]
# round69：按通用框架维度拆分——预制菜属 composition，调味/即食属 processing。
# （round67.1 已删除裸「卤」：卤水豆腐是凝固工艺不是预制菜。）
COMPOSITION_PREPARED_TERMS = ["预制", "半成品", "料理包", "快手菜", "王牌菜", "加热即食"]
SNACK_TERMS = ["零食", "小吃", "脆片", "薯片", "果干", "果脯", "点心", "饼干"]
FRIED_TERMS = ["油炸", "炸", "酥", "天妇罗", "脆皮", "油豆腐", "油面筋"]
SEASONED_TERMS = ["香煎", "秘制", "红烧", "糖醋", "腌制", "调味", "奥尔良",
                  "黑椒", "孜然", "麻辣", "藤椒"]
READY_TO_EAT_TERMS = ["即食", "开袋即食", "熟食", "凉菜", "凉拌", "卤味", "卤制", "卤蛋", "卤肉"]
NON_FOOD_TERMS = ["火锅", "特惠", "任选", "折", "券", "水", "湿巾", "垃圾袋"]

NO_SUGAR_TERMS = ["无糖", "无蔗糖", "0蔗糖", "0%蔗糖", "零蔗糖", "0添加蔗糖",
                  "不加蔗糖", "裸酸奶", "断糖", "0糖"]
SUGAR_PRESENT_TERMS = ["含糖", "风味", "果粒", "果味", "黄桃", "草莓", "芒果", "蓝莓", "甜", "糖"]
# round68：plain 单品要求下的调味/混合词（风味酸奶、爆珠、果粒等不得当 plain 单品）
FLAVOR_MIX_TERMS = ["果味", "风味", "西柚", "脐橙", "草莓", "黄桃", "芒果", "蓝莓",
                    "爆珠", "燕麦", "坚果", "巧克力", "香草", "果粒", "椰果", "啵啵",
                    "果汁", "果酱", "混合"]
# round68：全麦证据分层——标题「全麦/全谷物」= title_claim；仅「黑麦/杂粮」等
# 不得自动满足全麦要求（review_required）。
WHOLE_WHEAT_TERMS = ["全麦", "全谷物"]
OTHER_GRAIN_TERMS = ["黑麦", "裸麦", "杂粮", "多谷物", "粗粮", "燕麦"]
WHITE_BREAD_TERMS = ["白吐司", "牛奶吐司", "奶油面包", "甜面包", "蛋糕", "夹心"]


def load_profiles(path=None):
    p = path or os.path.join(DATA, "product-acceptance-profiles.json")
    return json.load(open(p, encoding="utf-8")).get("profiles", {})


def _hit(name, terms):
    return next((t for t in terms if t in name), None)


def _attribute_hit(name, terms):
    """属性词命中（round69）：紧跟「味」的属性词是风味声明，不算原料证据
    （如「全麦味」「杂粮味」）；其余情况返回首个命中词。"""
    for t in terms:
        start = 0
        while True:
            idx = name.find(t, start)
            if idx < 0:
                break
            if name[idx + len(t):idx + len(t) + 1] != "味":
                return t
            start = idx + 1
    return None


def _species_hit(name, species):
    """物种词命中（排除 牛奶/奶油/牛油果 等误伤上下文）。"""
    terms = SPECIES_TERMS.get(species, [species])
    exceptions = SPECIES_TERM_EXCEPTIONS.get(species, [])
    for t in terms:
        start = 0
        while True:
            idx = name.find(t, start)
            if idx < 0:
                break
            covered = False
            for e in exceptions:
                e_start = name.find(e)
                while e_start >= 0:
                    if e_start <= idx < e_start + len(e):
                        covered = True
                        break
                    e_start = name.find(e, e_start + 1)
                if covered:
                    break
            if not covered:
                return t
            start = idx + 1
    return None


def _base_decision(name):
    """非食品与页面推荐词：直接 rejected。"""
    hit = _hit(name, NON_FOOD_TERMS)
    if hit and len(name) <= 6:
        return "rejected", "non_food_product", "页面推荐词/非商品名"
    return None, None, None


_PROMO_BRACKET = re.compile(r"【[^】]*】")


def _ev(identity=None, composition=None, processing=None, attribute=None, level=None):
    """统一四维证据结构（round69）：identity / composition / processing / attribute_evidence。"""
    e = {
        "identity": identity or {"status": "unknown"},
        "composition": composition or {"status": "unknown"},
        "processing": processing or {"status": "unknown"},
        "attribute_evidence": attribute or {},
    }
    if level:
        e["evidence_level"] = level
    return e


def evaluate_candidate(name, profile):
    """通用商品门禁（round69）：身份 → 结构 → 加工 → 附加属性证据 四维统一判定。

    返回 (decision, evidence, rejection_reasons)；profile 为空时返回 review_required。
    判定器不按品类硬编码分支：品类差异全部来自结构化验收档案。
    先剥离【】促销前缀（如「【红烧很香】」），避免促销语误伤形态判断。
    """
    name = _PROMO_BRACKET.sub(" ", str(name or "")).strip()
    if not profile:
        return "review_required", _ev(identity={"status": "unknown", "note": "no_profile"}), \
            ["insufficient_identity_evidence"]

    d, reason, note = _base_decision(name)
    if d:
        return d, _ev(identity={"status": "non_food", "note": note}), [reason]

    # 兼容两种传入层级：外层概念档案（含 acceptance_profile 键）或验收条件本体。
    ap = profile.get("acceptance_profile") if "acceptance_profile" in profile else profile
    ap = ap or {}

    # ── 1) identity：大品类 / 物种 / 部位 ──────────────────────────────
    identity = {"status": "unknown", "category": None, "species": None, "cut": None}
    req_cats = ap.get("required_category") or []
    cat_ok = None
    for cat in req_cats:
        hit = _hit(name, CATEGORY_TERMS.get(cat, [cat]))
        if hit:
            cat_ok = {"category": cat, "hit": hit}
            break
    if req_cats and not cat_ok:
        return "review_required", _ev(identity=identity), ["insufficient_identity_evidence"]
    identity["category"] = cat_ok

    species = ap.get("species")
    if species:
        conflict = [s for s in SPECIES_TERMS if s != species and _species_hit(name, s)]
        if conflict:
            identity["status"] = "conflict"
            identity["species"] = {"conflict": conflict}
            return "rejected", _ev(identity=identity), ["species_conflict"]
        hit = _species_hit(name, species)
        if not hit:
            identity["species"] = {"status": "not_explicit"}
            return "review_required", _ev(identity=identity), ["insufficient_identity_evidence"]
        identity["species"] = {"hit": hit}

    cut = ap.get("animal_cut")
    if cut:
        hit = _hit(name, [cut])
        if not hit:
            identity["cut"] = {"status": "not_explicit"}
            return "review_required", _ev(identity=identity), ["insufficient_identity_evidence"]
        identity["cut"] = {"hit": hit}

    identity["status"] = "matched"

    # ── 2) composition：复合食品 / 预制菜 / 零食 / 混合产品 ─────────────
    comp = _hit(name, COMPOSITE_TERMS)
    if comp:
        return "rejected", _ev(identity=identity,
                               composition={"status": "composite_food", "hit": comp}), \
            ["composite_food"]
    prep = _hit(name, COMPOSITION_PREPARED_TERMS)
    if prep:
        return "rejected", _ev(identity=identity,
                               composition={"status": "prepared_dish", "hit": prep}), \
            ["prepared_dish"]
    snack = _hit(name, SNACK_TERMS)
    if snack:
        return "rejected", _ev(identity=identity,
                               composition={"status": "snack", "hit": snack}), \
            ["snack_product"]
    composition = {"status": "single_ingredient"}
    if "plain_single_product" in (ap.get("accepted_composition") or []):
        fm = _hit(name, FLAVOR_MIX_TERMS)
        if fm:
            return "rejected", _ev(identity=identity,
                                   composition={"status": "mixed_product", "hit": fm}), \
                ["flavored_product", "mixed_composition"]

    # ── 3) processing：加工状态与菜单用途 ──────────────────────────────
    proc = None
    if _hit(name, FRIED_TERMS):
        proc = "fried"
    elif _hit(name, SEASONED_TERMS):
        proc = "seasoned"
    elif _hit(name, READY_TO_EAT_TERMS):
        proc = "ready_to_eat"
    excluded_proc = set(ap.get("excluded_processing") or [])
    if proc and proc in excluded_proc:
        return "rejected", _ev(identity=identity, composition=composition,
                               processing={"status": "excluded", "hit": proc}), \
            ["wrong_processing_state"]
    processing = {"status": "ok", "hit": proc} if proc else {"status": "ok"}

    # ── 4) attribute_evidence：附加属性证据（标题声明 ≠ 完整验证）──────
    attribute = {}
    level = None
    if ap.get("sweetening_requirement") == "no_added_sugar":
        no_sugar = _attribute_hit(name, NO_SUGAR_TERMS)
        sugar = _hit(name, SUGAR_PRESENT_TERMS)
        if no_sugar:
            attribute["no_added_sugar"] = "title_claim"
            level = "title_claim"
        elif sugar:
            attribute["no_added_sugar"] = "sweetened"
            return "rejected", _ev(identity=identity, composition=composition,
                                   processing=processing, attribute=attribute), \
                ["requirement_not_verified"]
        else:
            attribute["no_added_sugar"] = "unknown"
            return "review_required", _ev(identity=identity, composition=composition,
                                          processing=processing, attribute=attribute), \
                ["requirement_not_verified"]

    if ap.get("whole_grain_requirement") == "whole_grain":
        hit = _attribute_hit(name, WHOLE_WHEAT_TERMS)
        other = _attribute_hit(name, OTHER_GRAIN_TERMS)
        white = _hit(name, WHITE_BREAD_TERMS)
        if hit:
            attribute["whole_grain"] = "title_claim"
            level = level or "title_claim"
        elif white:
            attribute["whole_grain"] = "not_whole_grain"
            return "rejected", _ev(identity=identity, composition=composition,
                                   processing=processing, attribute=attribute), \
                ["requirement_not_verified"]
        elif other:
            attribute["whole_grain"] = "other_grain"
            return "review_required", _ev(identity=identity, composition=composition,
                                          processing=processing, attribute=attribute), \
                ["requirement_not_verified"]
        else:
            attribute["whole_grain"] = "unknown"
            return "review_required", _ev(identity=identity, composition=composition,
                                          processing=processing, attribute=attribute), \
                ["requirement_not_verified"]

    return "accepted", _ev(identity=identity, composition=composition, processing=processing,
                           attribute=attribute, level=level), []
