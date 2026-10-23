#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品形态匹配门（round65）：主端 validator / 合并层 / 叮咚助手共用同一份
ingredient-catalog.json + product-form-dictionary.json。

判定优先级（规则 ID：FORM-001）：ingredient_id → 部位 → 生鲜/加工形态 →
预制许可 → 包装 → 价格。形态门只负责"部位 + 形态 + 预制"三段：

  verdict:
    exact     —— 标题命中 exact_terms 且未命中任何排除形态
    eligible  —— 未命中排除形态（allowed_forms 为空或识别形态 ⊆ allowed）
    rejected  —— 命中 excluded_states / 识别出 restrictive 形态且不在 allowed_forms
"""
import json, os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

# round73：否定前缀守卫适用的加工状态形态（唯一来源 data/commodity-vocabulary.json）
try:
    _VOCAB = json.load(open(os.path.join(DATA, "commodity-vocabulary.json"), encoding="utf-8"))
    NEGATION_GUARD_FORMS = tuple(_VOCAB.get("processing_state_forms") or [])
except OSError:
    NEGATION_GUARD_FORMS = ("marinated", "cooked", "cured", "sashimi",
                            "fried", "breaded", "ready_to_eat", "cooked_snack")


def load_catalog(path=None):
    return json.load(open(path or os.path.join(DATA, "ingredient-catalog.json"), encoding="utf-8"))


def load_dictionary(path=None):
    return json.load(open(path or os.path.join(DATA, "product-form-dictionary.json"), encoding="utf-8"))


def _negated(name, idx, prefixes):
    """命中位置前两字符内带否定前缀（免/无/不含/未/去）。"""
    window = name[max(0, idx - 2):idx]
    return any(window.endswith(p) for p in prefixes)


def detect_forms(title, dictionary=None):
    """从商品标题识别形态集合。

    round73 与主词典「规则」及助手端对齐：
    - 否定前缀守卫只作用于加工状态形态（NEGATION_GUARD_FORMS），窗口为前两字符；
    - cut_pieces 的「块」前一字为「整」时归 whole，不归 cut_pieces。
    """
    dictionary = dictionary or load_dictionary()
    prefixes = tuple(dictionary.get("negation_prefixes") or ["免", "无", "不含", "未", "去"])
    found = set()
    for form, spec in dictionary.get("forms", {}).items():
        for kw in spec.get("keywords", []):
            if not kw:
                continue
            start = 0
            hit = False
            while True:
                i = title.find(kw, start)
                if i < 0:
                    break
                if form in NEGATION_GUARD_FORMS and _negated(title, i, prefixes):
                    start = i + 1
                    continue
                if form == "cut_pieces" and title[max(0, i - 1):i] == "整":
                    start = i + 1
                    continue
                hit = True
                break
            if hit:
                found.add(form)
                break
    return found


def restrictive_forms(dictionary=None):
    dictionary = dictionary or load_dictionary()
    return {f for f, s in dictionary.get("forms", {}).items() if s.get("restrictive")}


def match_product(ingredient_id, title, forms=None, catalog=None, dictionary=None):
    """对单个商品标题执行形态门。forms 可传预先识别的形态集合。"""
    catalog = catalog or load_catalog()
    dictionary = dictionary or load_dictionary()
    item = (catalog.get("items") or {}).get(ingredient_id)
    qp = (item or {}).get("query_profile") or {}
    forms = detect_forms(title, dictionary) if forms is None else set(forms)
    excluded = set(qp.get("excluded_states") or [])
    allowed = set(qp.get("allowed_forms") or [])
    hit_excluded = sorted(forms & excluded)
    if hit_excluded:
        return {"verdict": "rejected", "reason_code": "excluded_form",
                "detail": "命中排除形态：%s" % "/".join(hit_excluded),
                "matched_forms": sorted(forms)}
    restr = restrictive_forms(dictionary)
    hit_restrictive = sorted(f for f in forms & restr if allowed and f not in allowed)
    if hit_restrictive:
        return {"verdict": "rejected", "reason_code": "form_not_allowed",
                "detail": "限制形态不在允许清单：%s" % "/".join(hit_restrictive),
                "matched_forms": sorted(forms)}
    req_cat = qp.get("required_category")
    if req_cat and allowed and req_cat not in allowed and not (forms & allowed):
        return {"verdict": "rejected", "reason_code": "required_category_missing",
                "detail": "需要部位/类别 %s，未命中允许形态" % req_cat,
                "matched_forms": sorted(forms)}
    exact_terms = [t for t in (qp.get("exact_terms") or []) if t]
    if any(t and t in title for t in exact_terms):
        return {"verdict": "exact", "reason_code": None, "detail": "",
                "matched_forms": sorted(forms)}
    return {"verdict": "eligible", "reason_code": None, "detail": "",
            "matched_forms": sorted(forms)}


def filter_candidates(ingredient_id, candidates, catalog=None, dictionary=None):
    """批量过滤：candidates 为 [{title/product_name, ...}]，返回带 verdict 的列表。"""
    out = []
    for c in candidates:
        title = c.get("product_name") or c.get("title") or ""
        r = match_product(ingredient_id, title, catalog=catalog, dictionary=dictionary)
        c = dict(c)
        c["form_match"] = r["verdict"]
        if r["reason_code"]:
            c["form_reject_reason"] = r["reason_code"]
        out.append(c)
    return out
