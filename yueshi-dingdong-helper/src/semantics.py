#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品语义门禁（round67 起；round73 单一来源化）

与月食 scripts/common/product_semantics.py 同规则：词表唯一来源为内嵌快照
semantics-snapshot.json（由月食 scripts/export_helper_semantics.py 从主库导出），
本文件只持有判定逻辑。

- 名称命中只用于召回；验收条件由 acceptance_profile 决定；
- 三态：accepted / rejected / review_required；证据不足一律 review_required；
- 维护原因类别，不维护具体商品全称。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SNAP_PATH = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) \
    / "semantics-snapshot.json"
with open(_SNAP_PATH, encoding="utf-8") as _f:
    _SNAP = json.load(_f)
_VOCAB = _SNAP["commodity_vocabulary"]

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

_PROMO_BRACKET = re.compile(r"【[^】]*】")


def _hit(name: str, terms) -> str | None:
    return next((t for t in terms if t in name), None)


def _attribute_hit(name: str, terms) -> str | None:
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


def _species_hit(name: str, species: str) -> str | None:
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


def evaluate_candidate(name: str, acceptance_profile: dict | None):
    """通用商品门禁（round69）：身份 → 结构 → 加工 → 附加属性证据 四维统一判定。

    返回 (decision, evidence, rejection_reasons)；acceptance_profile 为空 → review_required。
    判定器不按品类硬编码分支：品类差异全部来自结构化验收档案。
    """
    name = _PROMO_BRACKET.sub(" ", str(name or "")).strip()
    if not acceptance_profile:
        return "review_required", _ev(identity={"status": "unknown", "note": "no_profile"}), \
            ["insufficient_identity_evidence"]

    hit = _hit(name, NON_FOOD_TERMS)
    if hit and len(name) <= 6:
        return "rejected", _ev(identity={"status": "non_food", "note": "页面推荐词/非商品名"}), \
            ["non_food_product"]

    # round73：与技能侧契约对齐——兼容外层概念档案（含 acceptance_profile 键）或验收条件本体。
    ap = acceptance_profile.get("acceptance_profile") \
        if isinstance(acceptance_profile, dict) and "acceptance_profile" in acceptance_profile \
        else acceptance_profile
    ap = ap or {}

    # ── 1) identity：大品类 / 物种 / 部位 ──────────────────────────────
    identity = {"status": "unknown", "category": None, "species": None, "cut": None}
    req_cats = ap.get("required_category") or []
    cat_ok = None
    for cat in req_cats:
        h = _hit(name, CATEGORY_TERMS.get(cat, [cat]))
        if h:
            cat_ok = {"category": cat, "hit": h}
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
        h = _species_hit(name, species)
        if not h:
            identity["species"] = {"status": "not_explicit"}
            return "review_required", _ev(identity=identity), ["insufficient_identity_evidence"]
        identity["species"] = {"hit": h}

    cut = ap.get("animal_cut")
    if cut:
        h = _hit(name, [cut])
        if not h:
            identity["cut"] = {"status": "not_explicit"}
            return "review_required", _ev(identity=identity), ["insufficient_identity_evidence"]
        identity["cut"] = {"hit": h}

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
        # round73：与技能侧一致使用 _attribute_hit——「全麦味」是风味声明，不算全麦证据
        h = _attribute_hit(name, WHOLE_WHEAT_TERMS)
        other = _attribute_hit(name, OTHER_GRAIN_TERMS)
        white = _hit(name, WHITE_BREAD_TERMS)
        if h:
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
