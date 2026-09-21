#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mode_schedule 唯一来源加载器（round60 / M11 模式一致性门禁）。

周期模式决策在生成链路最前端冻结为 mode_schedule.json：

    {
      "plan_id": "2026-09-12-ff1795c8",
      "mode_schedule": {"2026-09-12": "hormone_balance", ...},
      "mode_summary": {"keto_days": 0, "hormone_days": 7}
    }

下游脚本（basket_builder / recipe_ranker / 营养求解）一律以
--mode-schedule 读取同一文件；本模块 fail-closed：
  - 文件缺失 / JSON 损坏 → SystemExit(mode_schedule_invalid)
  - mode_summary 与逐日 schedule 重算结果不一致 → SystemExit(mode_schedule_mismatch)
  - 出现未知模式名 → SystemExit(mode_schedule_invalid)
mode_schedule_hash = 规范化 JSON 的 SHA-256 前 16 位，用于 M11 跨脚本比对。
"""
import hashlib
import json

KNOWN_MODES = {"keto_biologic", "hormone_balance", "keto", "hormone"}
MODE_ALIAS = {"keto": "keto_biologic", "hormone": "hormone_balance"}

# MODE-INPUT-001（round64/64.1）：内部饮食安排不是问卷项。使用**明确拒绝集合**
# （精确匹配，禁止按字段名包含 "mode" 模糊匹配——plan_mode / meal_plan_mode /
# preparation_mode / source_mode 是合法字段，不得误删）。
FORBIDDEN_USER_MODE_FIELDS = {
    "mode", "mode_choice", "diet_mode", "nutrition_mode",
    "protocol_choice", "ketobiotic_or_hormone_feasting",
    "mode_schedule", "mode_summary",
}
# 向后兼容别名（round64 测试引用）
USER_MODE_FIELDS = FORBIDDEN_USER_MODE_FIELDS


def reject_user_mode_fields(payload):
    """外部用户原始输入不得携带内部饮食安排赋值字段（MODE-INPUT-001）。
    仅清除 FORBIDDEN_USER_MODE_FIELDS 精确命中的字段；plan_mode、
    meal_plan_mode、preparation_mode、source_mode 等合法字段原样保留。
    返回清除后的副本；发现违规字段时记录于 __rejected_mode_fields。"""
    if not isinstance(payload, dict):
        return payload
    bad = sorted(k for k in payload if k in FORBIDDEN_USER_MODE_FIELDS)
    out = {k: v for k, v in payload.items() if k not in FORBIDDEN_USER_MODE_FIELDS}
    if bad:
        out["__rejected_mode_fields"] = bad
    return out


def canonical_mode(name):
    if name not in KNOWN_MODES:
        raise SystemExit(f"mode_schedule_invalid: 未知模式 {name!r}")
    return MODE_ALIAS.get(name, name)


def mode_schedule_hash(data):
    blob = json.dumps(
        {"mode_schedule": data["mode_schedule"], "mode_summary": data["mode_summary"]},
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def summarize(schedule):
    keto = sum(1 for v in schedule.values() if canonical_mode(v) == "keto_biologic")
    return {"keto_days": keto, "hormone_days": len(schedule) - keto}


def load_mode_schedule(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"mode_schedule_invalid: 无法读取 {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("mode_schedule"), dict) \
            or not data["mode_schedule"]:
        raise SystemExit("mode_schedule_invalid: 缺逐日 mode_schedule")
    schedule = {d: canonical_mode(v) for d, v in data["mode_schedule"].items()}
    recomputed = summarize(schedule)
    declared = data.get("mode_summary") or recomputed
    if declared != recomputed:
        raise SystemExit(
            f"mode_schedule_mismatch: mode_summary {declared} 与逐日重算 {recomputed} 不一致")
    out = dict(data)
    out["mode_schedule"] = schedule
    out["mode_summary"] = recomputed
    return out, mode_schedule_hash(out)
