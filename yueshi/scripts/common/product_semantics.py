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


def load_vocabulary(path=None):
    """加载商品语义判定词汇契约（round73）：词表唯一来源 data/commodity-vocabulary.json。"""
    p = path or os.path.join(DATA, "commodity-vocabulary.json")
    return json.load(open(p, encoding="utf-8"))


_VOCAB = load_vocabulary()

DECISIONS = tuple(_VOCAB["decisions"])

REJECTION_REASONS = tuple(_VOCAB["rejection_reasons"])

SPECIES_TERMS = _VOCAB["species_terms"]
# round67.1：物种词误伤守卫——「牛奶/奶油/牛油果/牛油/蜗牛」不是牛肉冲突。
SPECIES_TERM_EXCEPTIONS = _VOCAB["species_term_exceptions"]

CATEGORY_TERMS = _VOCAB["category_terms"]

COMPOSITE_TERMS = _VOCAB["composite_terms"]
# round69：按通用框架维度拆分——预制菜属 composition，调味/即食属 processing。
# （round67.1 已删除裸「卤」：卤水豆腐是凝固工艺不是预制菜。）
COMPOSITION_PREPARED_TERMS = _VOCAB["composition_prepared_terms"]
SNACK_TERMS = _VOCAB["snack_terms"]
FRIED_TERMS = _VOCAB["fried_terms"]
SEASONED_TERMS = _VOCAB["seasoned_terms"]
READY_TO_EAT_TERMS = _VOCAB["ready_to_eat_terms"]
NON_FOOD_TERMS = _VOCAB["non_food_terms"]

NO_SUGAR_TERMS = _VOCAB["no_sugar_terms"]
SUGAR_PRESENT_TERMS = _VOCAB["sugar_present_terms"]
# round68：plain 单品要求下的调味/混合词（风味酸奶、爆珠、果粒等不得当 plain 单品）
FLAVOR_MIX_TERMS = _VOCAB["flavor_mix_terms"]
# round68：全麦证据分层——标题「全麦/全谷物」= title_claim；仅「黑麦/杂粮」等
# 不得自动满足全麦要求（review_required）。
WHOLE_WHEAT_TERMS = _VOCAB["whole_wheat_terms"]
OTHER_GRAIN_TERMS = _VOCAB["other_grain_terms"]
WHITE_BREAD_TERMS = _VOCAB["white_bread_terms"]
# 形态词典否定前缀守卫适用的加工状态形态（与 product-form-dictionary.json 规则一致）
PROCESSING_STATE_FORMS = tuple(_VOCAB["processing_state_forms"])


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


def judge_candidate(candidate, profile, revalidate=False):
    """候选判定唯一入口（round73：合并 purchase_selector._decision_for 与
    run_price_regression._decision_of 两份复评副本）。

    - 助手输出 candidate_decision 时优先采用；
    - revalidate=True 忽略结果内已有判定，用本地当前门禁重评（旧结果复评）；
    - 无概念档案时保守回退：旧字段 form_match/eligible_for_purchase 只作参考。
    """
    decision = (candidate or {}).get("candidate_decision")
    if not revalidate and decision in ("accepted", "rejected", "review_required"):
        return decision, (candidate or {}).get("evidence") or {}, \
            list((candidate or {}).get("rejection_reasons") or [])
    if profile:
        return evaluate_candidate((candidate or {}).get("product_name", ""), profile)
    # 无概念档案：保守回退（旧字段只作参考，形态被拒或未标合格 → review_required）
    if (candidate or {}).get("form_match") == "rejected" \
            or (candidate or {}).get("eligible_for_purchase") is False:
        return "rejected", {}, ["product_form_correction"]
    if (candidate or {}).get("eligible_for_purchase") is True:
        return "accepted", {
            "identity": {"status": "matched", "note": "legacy_eligible"},
            "composition": {"status": "unknown"},
            "processing": {"status": "unknown"},
            "attribute_evidence": {},
        }, []
    return "review_required", {}, ["insufficient_identity_evidence"]
