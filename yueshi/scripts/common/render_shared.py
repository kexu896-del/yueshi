#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨格式渲染共享组件（round74）

四个格式渲染器（HTML/PDF/Markdown/Word）共用的事实性辅助函数与常量；
不包含任何门禁逻辑（门禁统一在 scripts/render_gates.py）。

round74 起这些函数使用公开名（display_price / window_no_fasting /
normalize_provider_name），render_plan 保留旧下划线别名以兼容既有调用。
"""
import json
import os
import re
import unicodedata

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
CAFETERIA_TEMPLATES_PATH = os.path.join(DATA, "cafeteria-meal-templates.json")

CATEGORY_ORDER = ["肉蛋水产与豆制品", "蔬菜与菌菇", "谷物薯类与主食",
                  "乳品与油脂", "水果", "调味与干货", "其他"]

ESTIMATE_PRICE_BASIS = ("category_estimate", "historical_estimate")


def clean(text):
    text = unicodedata.normalize("NFC", str(text))
    for ch in ["\u00ad", "\ufeff", "\u200b"]:
        text = text.replace(ch, "")
    return text


def display_price(item):
    """按 price_basis 渲染价格：库存食材显示"库存"并附参考价（预算双口径，round39）；
    direct_public_price 原样；估算层缺"约"前缀时补上。"""
    price = (item.get("reference_price") or "").strip()
    if item.get("purchase_status") == "from_inventory":
        if price and not price.startswith("0元"):
            return f"库存（参考 {price}）"
        return "库存"
    if price.startswith("0元"):
        return "库存"
    if item.get("price_basis") in ESTIMATE_PRICE_BASIS and price and not price.startswith("约"):
        return "约" + price
    return price


def window_no_fasting(window):
    """每日卡片标题行不得出现“禁食/空腹”：只保留进食窗口部分。"""
    w = re.split(r"[·;；]", str(window))[0].strip()
    w = re.sub(r"禁食[^·;；]*", "", w).strip()
    return w


def normalize_provider_name(name: str) -> str:
    """叮咚商品名标点规范化（方案 §5.2/§六）：内部括号改为逗号，
    避免「猪里脊（新鲜猪大里脊（去筋膜））」嵌套括号；外层只保留一个（叮咚：…）。"""
    out = (name.replace("（", "，").replace("）", "")
           .replace("(", "，").replace(")", ""))
    return out.strip("，, ·、")


def load_cafeteria_templates():
    try:
        with open(CAFETERIA_TEMPLATES_PATH, encoding="utf-8") as f:
            return json.load(f)["templates"]
    except OSError:
        return {}
