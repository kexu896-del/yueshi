# -*- coding: utf-8 -*-
"""方案 §8 收口回归：
1. 三个内部错误码映射为方案原文用户文案（§8.3）；
2. 未知/空错误码不暴露原文，一律返回通用建议（§8.3）；
3. 导入后自检三状态文案与主按钮存在（§8.1），完成态主按钮存在（§8.2）；
4. 界面不再向用户暴露异常原文（技术信息/原始错误码）。

用法：python dev\\test_ux_friendly_errors.py
失败即非零退出。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from friendly_errors import ERROR_MESSAGES, GENERIC_MESSAGE, friendly_error  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# 1. 三个错误码 → 方案原文文案（§8.3）
EXPECT = {
    "request_id mismatch":
        "这份价格结果不是本次计划生成的，请重新使用本周的查价清单。",
    "all_candidates_rejected":
        "有些食材没有找到足够可靠的商品，月食会改用参考价格估算。",
    "delivery_context_missing":
        "当前网页还没有确认配送区域，请先在叮咚页面中完成确认。",
}
for code, text in EXPECT.items():
    check(friendly_error(code) == text, f"映射不符: {code}")

# 2. 未知/空/非字符串错误码不暴露原文（§8.3）
for bad in ("some_unknown_error", "", None, 123, ValueError("boom")):
    got = friendly_error(bad)
    check(got == GENERIC_MESSAGE, f"未知码应返回通用建议: {bad!r} -> {got!r}")
    if isinstance(bad, str) and bad.strip():
        check(bad.strip() not in got, f"通用建议不得包含原始错误码: {bad!r}")
# 已知码允许前后空白仍命中；映射文案不得等于通用建议
check(friendly_error("request_id mismatch ") == EXPECT["request_id mismatch"],
      "已知码带空白应仍命中映射")
for code in ERROR_MESSAGES:
    check(ERROR_MESSAGES[code] != GENERIC_MESSAGE, f"映射文案不得等于通用建议: {code}")

# 3. 自检三状态文案与主按钮（§8.1）+ 完成态主按钮（§8.2），静态检查 gui.py
gui_src = Path(__file__).parent.parent.joinpath("src", "gui.py").read_text(
    encoding="utf-8")
for needle in ("✓ 已读取本周查价清单", "✓ 浏览器可以使用",
               "○ 请在叮咚网页中确认配送区域",
               '"开始查询"', '"查价完成"', '"下载结果并返回月食"',
               "下载价格结果后，请将文件上传到月食对话。"):
    check(needle in gui_src, f"gui 缺: {needle}")

# 4. 界面不再向用户暴露异常原文/技术信息（§8.3）
for banned in ("（技术信息：", "showerror(\"保存失败\", str(exc)",
               "showerror(\"导出失败\", str(exc)"):
    check(banned not in gui_src, f"gui 仍暴露原始错误: {banned}")
# 内部错误码必须写日志，不能只弹窗
check("internal-errors.log" in gui_src, "缺内部错误码日志落点")

if fails:
    for f_ in fails:
        print("FAIL:", f_)
    sys.exit(1)
print("方案 §8 收口回归：全部通过")
