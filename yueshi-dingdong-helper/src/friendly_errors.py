# -*- coding: utf-8 -*-
"""内部错误码 → 用户操作建议（方案 §8.3 自然语言错误提示）。

界面只显示操作建议；内部错误码与异常原文只写日志（logs/last-error.txt），
不弹给用户。映射缺失时一律返回通用建议，绝不把原始错误码暴露到界面。
"""

# 已登记的内部错误码 → 用户文案
ERROR_MESSAGES = {
    # 月食侧契约/上下文错误（方案 §8.3 原文）
    "request_id mismatch": (
        "这份价格结果不是本次计划生成的，请重新使用本周的查价清单。"),
    "all_candidates_rejected": (
        "有些食材没有找到足够可靠的商品，月食会改用参考价格估算。"),
    "delivery_context_missing": (
        "当前网页还没有确认配送区域，请先在叮咚页面中完成确认。"),
    # 助手端常见错误
    "browser_unavailable": (
        "未能打开浏览器。请先安装 Microsoft Edge 或 Chrome 后重试。"),
    "save_failed": "结果文件保存失败，请换一个文件夹重试。",
    "export_failed": "诊断信息导出失败，请重试。",
    "internal_error": (
        "本次查询未完成。请重试，或在「设置与帮助」中导出诊断信息。"),
}

# 映射缺失时的通用建议（不得回退为原始错误码或异常原文）
GENERIC_MESSAGE = (
    "本次操作没有完成，请重试；仍然不行可在「设置与帮助」中导出诊断信息。")


def friendly_error(code) -> str:
    """把内部错误码翻译成用户操作建议；未知/空码一律返回通用建议。"""
    if not isinstance(code, str):
        return GENERIC_MESSAGE
    return ERROR_MESSAGES.get(code.strip(), GENERIC_MESSAGE)
