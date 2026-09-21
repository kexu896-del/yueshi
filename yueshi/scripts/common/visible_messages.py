#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户表达转换器（round67，2026-09-18）

计算组件（营养、预算、价格校验）只输出结构化事实，由本模块统一生成用户文案，
避免内部原因码、构建状态和审核语言进入正式用户文件（规则见
references/output-policy.md「用户表达层」）。

约定：
- 可见消息类型：action / explanation / flexibility / caution / price_summary；
- 内部消息类型不得进入正式文件：build_status / algorithm_reason /
  validation_result / correction_trace / scoring_trace / gate_summary / debug_summary。
"""
import json, os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

VISIBLE_MESSAGE_TYPES = ("action", "explanation", "flexibility", "caution", "price_summary")
INTERNAL_MESSAGE_TYPES = ("build_status", "algorithm_reason", "validation_result",
                          "correction_trace", "scoring_trace", "gate_summary", "debug_summary")


def load_mode_display(path=None):
    p = path or os.path.join(DATA, "mode-display.json")
    return json.load(open(p, encoding="utf-8"))


def mode_display(mode_value, rules=None):
    """内部模式枚举 → {display_name, user_note}；未知模式不猜测，返回 None。"""
    rules = rules or load_mode_display()
    item = (rules.get("modes") or {}).get(mode_value)
    if not item:
        return None
    return {"display_name": item["display_name"], "user_note": item["user_note"]}


def snack_line(reason_code, skip_if_external_meal_sufficient=True):
    """可选加餐文案：按饥饿程度决定，不展示内部原因码。"""
    if reason_code in ("calorie_floor_adjustment", "energy_gap"):
        return "下午明显饿时再吃这份加餐；午餐吃得足，可以不吃。"
    if reason_code in ("protein_gap",):
        return "当天正餐蛋白质已较充足，这份加餐按饥饿程度决定是否食用。"
    return "这份加餐按饥饿程度决定是否食用。"


def protein_line(status):
    """蛋白状态文案：above_target_tolerance 不展示内部状态名。"""
    mapping = {
        "above_target_tolerance": "今天的正餐已经有足够蛋白质，可选加餐按饥饿程度决定。",
        "below_target": "今天蛋白质略少，优先把正餐的蛋白质吃完。",
        "within_band": "今天蛋白质安排合适。",
    }
    return mapping.get(status, "")


def budget_summary(target_yuan, tolerance_upper_yuan, estimated_total_yuan):
    """预算摘要：目标预算与允许范围分开说明，不出现内部比例口径。"""
    text = "本周预计采购约 %s 元。预算目标为 %s 元，可接受范围约至 %s 元" % (
        _num(estimated_total_yuan), _num(target_yuan), _num(tolerance_upper_yuan))
    over = float(estimated_total_yuan) - float(tolerance_upper_yuan)
    if over > 0:
        text += "，目前比可接受范围高约 %s 元。" % _num(over)
    else:
        text += "，在可接受范围内。"
    return text


def budget_saving_options(options):
    """节省建议：options = [{"text": ..., "saving_yuan": ...}]，最多两条。"""
    lines = ["如需控制支出，可优先："]
    for i, opt in enumerate(options[:2], 1):
        lines.append("%d. %s，预计节省约 %s 元；" % (i, opt["text"], _num(opt["saving_yuan"])))
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip("；") + "。"
    return "\n".join(lines)


def estimate_note():
    """参考估价说明：全文件只出现一次。"""
    return "酸奶、全麦面包和豆腐暂按当地常见价格估算，购买时以实际价格为准。"


def seasonal_line(has_peak_items=True):
    return ("本周优先安排了适合 9 月购买的蔬菜。" if has_peak_items
            else "本周按常见可购蔬菜安排。")


def price_failure_line():
    """单个食材查价失败降级估算的用户话术（与 round59 口径一致）。"""
    return "叮咚没查到价，已按当地参考价估算"


def _num(v):
    f = float(v)
    return ("%g" % round(f, 2))
