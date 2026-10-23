#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round79 助手稳定性回归：
1. 配送确认不落盘、不跨任务复用（导入即清、prepare 门禁、单次消费）；
2. 网页被关闭（TargetClosedError）时批量收尾转人话，不崩线程；
3. 关闭入口吞错（页面/浏览器已被关掉时静默收尾）。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import app  # noqa: E402
import gui  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# 1a. 确认状态不持久化：旧 settings.json 里的 delivery_confirmed 读取时被抹掉
with tempfile.TemporaryDirectory() as td:
    sf = Path(td) / "settings.json"
    sf.write_text(json.dumps({"window_geometry": "1x1+0+0",
                              "delivery_confirmed": True}),
                  encoding="utf-8")
    original = gui.SETTINGS_FILE
    gui.SETTINGS_FILE = sf
    try:
        st = gui.load_settings()
    finally:
        gui.SETTINGS_FILE = original
    check("delivery_confirmed" not in st,
          "settings 不得读回 delivery_confirmed")
    check(json.loads(sf.read_text(encoding="utf-8")).get(
        "delivery_confirmed") is None, "旧确认应被迁移抹掉")

# 1b. 任务状态机：导入即清、必须 prepare 后确认、确认只用一次、回等待页恢复按钮
gui_src = Path(__file__).parent.parent.joinpath(
    "src", "gui.py").read_text(encoding="utf-8")
adopt = gui_src[gui_src.index("def _adopt"):gui_src.index("def click_start_query")]
check('"delivery_confirmed": False' in adopt and '"prepared": False' in adopt,
      "导入时应重置确认与 prepared")
click = gui_src[gui_src.index("def click_start_query"):
                gui_src.index("def _session_worker")]
check('not job.get("prepared")' in click, "未完成准备时不得允许确认开始")
start = gui_src[gui_src.index("def _do_start_query"):
                gui_src.index("def _toggle_detail")]
check('job.get("prepared")' in start, "开始前应校验 prepared")
check('job["delivery_confirmed"] = False' in start, "确认必须在开始时消费")
wait = gui_src[gui_src.index("def _show_wait"):
               gui_src.index("def _log_internal")]
check('btn_start.configure(state="normal")' in wait,
      "回到等待页应恢复开始按钮")

# 2. 批量收尾遇到 TargetClosedError → BrowserSessionLost（线程不崩）
from playwright._impl._errors import TargetClosedError  # noqa: E402


class FakePage:
    def is_closed(self):
        return False


calls = {"n": 0}


def fake_collect(**kwargs):
    calls["n"] += 1
    raise TargetClosedError(
        "Target page, context or browser has been closed")


class FakeItem:
    query = "测试"


class FakeBatch:
    items = [FakeItem()]


original_collect = app.collect_one_query
app.collect_one_query = fake_collect
try:
    try:
        app.execute_batch(FakePage(), None, FakeBatch())
        check(False, "网页关闭应抛 BrowserSessionLost")
    except app.BrowserSessionLost:
        pass
finally:
    app.collect_one_query = original_collect
check(calls["n"] == 1, "应实际调用一次查询")

# 3. 关闭入口吞错：页面/浏览器已被关掉时静默收尾


class BadPage:
    def remove_listener(self, *args):
        raise RuntimeError("closed")


class BadContext:
    def close(self):
        raise RuntimeError("closed")


class BadPlaywright:
    def stop(self):
        raise RuntimeError("closed")


class BadCollector:
    @staticmethod
    def handle_response(response):
        return None


app.close_browser_session(
    (BadPlaywright(), BadContext(), BadPage(), BadCollector()))
check(True, "")

if fails:
    for f_ in fails:
        print("FAIL:", f_)
    sys.exit(1)
print("round79 助手稳定性回归：全部通过")
