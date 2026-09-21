#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""蛋白质候选角色与冷却（round65，数据：data/protein-candidate-roles.json）

- candidate_role：staple（家常主力）/ rotation（轮换）/ exploratory（探索型）。
- 核心槽位：total 5、minimum_staple 3、maximum_exploratory 1；不强制水产占位。
- exploratory 进入核心需满足 exploratory_core_requires_any 任一条件。
- candidate_suppression：首次从核心删除 → 冷却 4 周（可作替代）；8 周内第二次删除
  → 冷却 8 周且不可作替代；permanent_dislike 硬排除；用户点名要求可覆盖冷却。
"""
import json, os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def load_rules(path=None):
    p = path or os.path.join(DATA, "protein-candidate-roles.json")
    return json.load(open(p, encoding="utf-8"))


def candidate_role(name, rules=None):
    """返回 staple / rotation / exploratory；未登记默认 rotation。"""
    rules = rules or load_rules()
    for role in rules["candidate_role_enum"]:
        if name in rules["roles"].get(role, []):
            return role
    return "rotation"


def suppression_state(name, prefs, current_week, rules=None):
    """根据核心删除历史计算冷却状态。

    prefs 字段：
      core_deletion_history: {name: [删除发生的周编号, ...]}
      explicit_requests: [本周用户点名要求的食材]
      permanent_dislikes: 由预选器既有逻辑处理（硬排除）
    返回 {suppress_from_core, allow_as_alternative, cooldown_weeks, reason_code}。"""
    rules = rules or load_rules()
    sup = rules["candidate_suppression"]
    if name in (prefs.get("explicit_requests") or []):
        if sup.get("explicit_user_request_overrides_suppression", True):
            return {"suppress_from_core": False, "allow_as_alternative": True,
                    "cooldown_weeks": 0, "reason_code": "explicit_user_request"}
    hist = sorted((prefs.get("core_deletion_history") or {}).get(name, []))
    if not hist:
        return {"suppress_from_core": False, "allow_as_alternative": True,
                "cooldown_weeks": 0, "reason_code": None}
    last = hist[-1]
    first_rule = sup["first_core_deletion"]
    window = sup["second_deletion_within_weeks"]
    if len(hist) >= 2 and hist[-1] - hist[-2] <= window:
        rule = sup["second_deletion"]
        reason = "repeat_deletion_cooldown"
    else:
        rule = first_rule
        reason = "first_deletion_cooldown"
    if current_week - last < rule["cooldown_weeks"]:
        return {"suppress_from_core": rule["suppress_from_core"],
                "allow_as_alternative": rule["allow_as_alternative"],
                "cooldown_weeks": rule["cooldown_weeks"] - (current_week - last),
                "reason_code": reason}
    return {"suppress_from_core": False, "allow_as_alternative": True,
            "cooldown_weeks": 0, "reason_code": None}


def exploratory_allowed(name, prefs, staple_count, rules=None):
    """探索型食材是否允许进入核心候选。"""
    rules = rules or load_rules()
    flags = set(prefs.get("exploratory_signals") or [])
    if "user_open_to_exploration" in flags or "explicit_user_request" in flags:
        return True
    if "positive_personal_history" in flags and \
            name in (prefs.get("positive_history") or []):
        return True
    slots = rules["slots"]
    if staple_count < slots["minimum_staple"]:
        return "staple_candidate_shortage" in rules["exploratory_core_requires_any"]
    return False


def enforce_protein_slots(entries, prefs=None, current_week=0, rules=None):
    """对蛋白质候选层执行角色槽位与冷却约束（原地过滤，返回被移出名单）。

    entries：build_candidates 蛋白质层列表（每项含 normalized_name）。
    规则：冷却中的食材不进核心（按 allow_as_alternative 决定是否可作替代展示）；
    staple 不足 minimum_staple 时优先保留 staple；exploratory 至多 maximum_exploratory
    且需满足准入条件；未登记食材按 rotation 处理。"""
    rules = rules or load_rules()
    prefs = prefs or {}
    slots = rules["slots"]
    kept, moved = [], []
    for e in entries:
        name = e["normalized_name"]
        e["candidate_role"] = candidate_role(name, rules)
        st = suppression_state(name, prefs, current_week, rules)
        e["candidate_suppression"] = st
        if st["suppress_from_core"]:
            e["suppressed_from_core"] = True
            if st["allow_as_alternative"]:
                moved.append((name, st["reason_code"], "alternative_only"))
            else:
                moved.append((name, st["reason_code"], "suppressed"))
            continue
        kept.append(e)
    staple = [e for e in kept if e["candidate_role"] == "staple"]
    # exploratory 准入与额度
    expl = [e for e in kept if e["candidate_role"] == "exploratory"]
    allowed_expl = []
    for e in expl:
        if len(allowed_expl) >= slots["maximum_exploratory"]:
            e["suppressed_from_core"] = True
            moved.append((e["normalized_name"], "exploratory_slot_limit", "suppressed"))
            continue
        if exploratory_allowed(e["normalized_name"], prefs, len(staple), rules):
            allowed_expl.append(e)
        else:
            e["suppressed_from_core"] = True
            moved.append((e["normalized_name"], "exploratory_not_authorized", "suppressed"))
    kept = [e for e in kept if not e.get("suppressed_from_core")]
    kept.sort(key=lambda x: -x.get("score", 0))
    if len(kept) > slots["total"]:
        # 裁剪时优先保住 staple 达到 minimum_staple
        staples_kept = [e for e in kept if e["candidate_role"] == "staple"]
        others = [e for e in kept if e["candidate_role"] != "staple"]
        final = staples_kept[:max(slots["minimum_staple"], slots["total"] - len(others))]
        final += others[:slots["total"] - len(final)]
        kept = final
    return kept, moved
