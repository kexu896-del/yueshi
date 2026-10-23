#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体质食养修饰器（round79）

仅当用户**明确自述**体质（如"我阳虚/怕冷/湿气重"）时启用：

- resolve(text)：自述文本 → 体质键（别名匹配；未知返回 None；特禀走安全路由）；
- bias_for(food, key)：单个食材的软偏置分（+2 相宜清单 / -2 禁忌清单 /
  ±1 性味匹配；未知性味不偏置）；
- recipe_bias(recipe, key)：菜谱级软偏置（名称/主料/烹法的聚合，上限 ±2）；
- user_line(key, applied)：生活化复述（不出现体质判定、辨证、疗效词）。

硬边界（由调用方保证）：安全、过敏、医嘱、营养目标、预算、锁定篮子与最低菜数
永远优先；本模块只改变排序，不改变候选集合与任何计算。
"""
import functools
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

RULES_PATH = os.path.join(DATA, "constitution-food-rules.json")
PROFILES_PATH = os.path.join(DATA, "constitution-profiles.json")
NATURE_PATH = os.path.join(DATA, "food-nature.json")

BAD_TERMS = ("辨证", "证型", "治疗", "治愈", "疗效", "处方", "剂量")


@functools.lru_cache(maxsize=4)
def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_rules(path=None):
    return _load(path or RULES_PATH)


def load_profiles(path=None):
    return (_load(path or PROFILES_PATH).get("constitutions") or {})


def load_nature(path=None):
    return (_load(path or NATURE_PATH).get("items") or {})


def load_inferred(path=None):
    return (_load(path or NATURE_PATH).get("inferred") or {})


def _norm(text):
    return "".join(str(text or "").split())


def resolve(text, rules=None, profiles=None):
    """自述文本 → 体质键。

    规则：体质名（name_zh / textbook_name）是强别名，命中即返回；
    症状别名是弱别名——只命中一个方向才启用；同时命中多个方向（如「又怕冷又怕热」）
    视为歧义，返回 None（不猜测方向）。未知返回 None。
    """
    profiles = profiles or load_profiles()
    t = _norm(text)
    if not t:
        return None
    strong, weak = [], []
    for key, p in profiles.items():
        names = {str(p.get("name_zh") or ""), str(p.get("textbook_name") or "")}
        names.discard("")
        for alias in p.get("aliases") or []:
            (strong if str(alias) in names else weak).append((str(alias), key))
    for alias, key in strong:
        if alias in t:
            return key
    hits = {key for alias, key in weak if alias and alias in t}
    if len(hits) == 1:
        return next(iter(hits))
    return None


def resolve_status(text, rules=None, profiles=None):
    """返回 (key, status)：status ∈ ok / ambiguous / unknown（供调用方给出准确提示）。"""
    profiles = profiles or load_profiles()
    t = _norm(text)
    if not t:
        return None, "unknown"
    strong, weak = [], []
    for key, p in profiles.items():
        names = {str(p.get("name_zh") or ""), str(p.get("textbook_name") or "")}
        names.discard("")
        for alias in p.get("aliases") or []:
            (strong if str(alias) in names else weak).append((str(alias), key))
    for alias, key in strong:
        if alias in t:
            return key, "ok"
    hits = {key for alias, key in weak if alias and alias in t}
    if len(hits) == 1:
        return next(iter(hits)), "ok"
    return None, ("ambiguous" if len(hits) > 1 else "unknown")


def base_food(name, rules=None):
    rules = rules or load_rules()
    aliases = rules.get("base_food_aliases") or {}
    for k in sorted(aliases, key=len, reverse=True):
        if k in name:
            return aliases[k]
    return name


def bias_for(food, key, rules=None, nature=None):
    """返回 (score, tags)。score ∈ {-2..+2}（推断条目 ±0.5）；未知体质/空规则返回 (0, [])。"""
    rules = rules or load_rules()
    nature = nature if nature is not None else load_nature()
    inferred = load_inferred()
    rule = (rules.get("rules") or {}).get(key) or {}
    if not rule or rule.get("safety_route"):
        return 0, []
    base = base_food(food, rules)

    def _hit(terms):
        for t in terms or []:
            # 完整食材名允许包含匹配；基础名（如 鱼/肉）只做精确匹配，避免 鱼→带鱼 误伤
            if any(t in n or n in t for n in (food,)):
                return t
            if base and base != food and t == base:
                return t
        return None

    score, tags = 0, []
    pf = _hit(rule.get("prefer_foods"))
    if pf:
        score += 2
        tags.append("prefer:" + pf)
    af = _hit(rule.get("avoid_foods"))
    if af:
        score -= 2
        tags.append("avoid:" + af)
    item = nature.get(food) or nature.get(base_food(food, rules))
    if item:
        nat = item.get("nature")
        if nat:
            if nat in (rule.get("prefer_natures") or []):
                score += 1
                tags.append("nature:" + nat)
            elif nat in (rule.get("avoid_natures") or []):
                score -= 1
                tags.append("nature_avoid:" + nat)
    else:
        # 类别级推断（round79c）：半权重，只参与性味方向，不冒充教材
        infer = inferred.get(food) or inferred.get(base_food(food, rules))
        if infer:
            w = float(infer.get("weight") or 0.5)
            nat = infer.get("nature")
            if nat in (rule.get("prefer_natures") or []):
                score += w
                tags.append("nature_inferred:" + nat)
            elif nat in (rule.get("avoid_natures") or []):
                score -= w
                tags.append("nature_inferred_avoid:" + nat)
    return max(-2, min(2, score)), tags


def recipe_bias(recipe, key, rules=None, nature=None):
    """菜谱级软偏置：名称/主料/烹法聚合，上限 ±2。"""
    rules = rules or load_rules()
    name = str((recipe or {}).get("original_name") or (recipe or {}).get("name") or "")
    core = (recipe or {}).get("core_ingredients") or []
    methods = (recipe or {}).get("methods") or []
    total, hit = 0, 0
    for food in core:
        s, _ = bias_for(food, key, rules, nature)
        total += s
        hit += 1
    if hit:
        total = total / hit
    text = name + "".join(str(x) for x in methods)
    for pf in ((rules.get("rules") or {}).get(key) or {}).get("prefer_foods") or []:
        if pf in text:
            total += 0.5
            break
    return max(-2, min(2, total))


def recipe_score_bonus(recipe, key, rules=None, nature=None):
    """菜谱级偏置 → 整数分：保留方向（±0.5 也至少记 ±1），避免四舍五入把半权重抹掉。"""
    b = recipe_bias(recipe, key, rules, nature)
    if b >= 1:
        return int(round(b))
    if 0 < b < 1:
        return 1
    if b <= -1:
        return int(round(b))
    if -1 < b < 0:
        return -1
    return 0


def user_line(key, applied, rules=None):
    """生活化复述；applied 为实际被偏置的食材名列表。不输出体质判定。"""
    rules = rules or load_rules()
    trigger = (rules.get("user_trigger") or {}).get(key)
    label = (rules.get("food_group_label") or {}).get(key)
    applied = [a for a in (applied or []) if a]
    if not trigger or not applied:
        return ""
    sample = "、".join(dict.fromkeys(applied))[:40]
    line = "你提到%s，本周多安排了%s这类%s食材。" % (trigger, sample, label or "")
    for bad in BAD_TERMS:
        line = line.replace(bad, "")
    return line


def validate(rules=None, nature=None):
    """数据完整性检查；返回错误列表。"""
    rules = rules or load_rules()
    nature = nature if nature is not None else load_nature()
    errs = []
    for key, rule in (rules.get("rules") or {}).items():
        for f in ("prefer_foods", "avoid_foods", "prefer_natures", "avoid_natures", "cooking"):
            if f not in rule:
                errs.append("%s 缺字段 %s" % (key, f))
        for word in BAD_TERMS:
            blob = json.dumps(rule, ensure_ascii=False)
            if word in blob:
                errs.append("%s 规则含禁用语：%s" % (key, word))
    if len(nature) < 60:
        errs.append("food-nature 条目过少：%d" % len(nature))
    inferred = load_inferred()
    for name, d in inferred.items():
        if name in nature:
            errs.append("%s 同时存在教材条目与推断条目（推断不得覆盖教材）" % name)
        if d.get("basis") != "category_inference":
            errs.append("%s 推断条目 basis 非法" % name)
        if float(d.get("weight") or 0) != 0.5:
            errs.append("%s 推断权重必须为 0.5" % name)
        if d.get("nature") not in ("寒", "凉", "平", "温", "热"):
            errs.append("%s 推断性味非法：%s" % (name, d.get("nature")))
        if not d.get("category"):
            errs.append("%s 推断缺类别" % name)
    return errs
