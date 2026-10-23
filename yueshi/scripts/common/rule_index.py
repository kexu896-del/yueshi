#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""稳定规则 ID 注册表解析（round78）

唯一人工维护源：references/rule-index.md（Markdown 表格，ID 只增不改）。
本模块把它解析为结构化注册表，供测试与维护工具按 ID 断言，不再用正则扫表：

    from rule_index import load_registry, rule_ids
    reg = load_registry()        # [{rule_id, topic, rule, owners, deprecated}]
    ids = rule_ids()             # {"SAFETY-001", ...}

约定：
- owners 从「细则位置」列的 `反引号路径` 提取；
- 行内文本包含 deprecated（不区分大小写）即标记 deprecated；
- 解析失败（缺表格/缺列）抛 ValueError，不静默跳过。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PATH = os.path.join(ROOT, "references", "rule-index.md")

_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]*\d{3}$")
_OWNER_RE = re.compile(r"`([^`]+)`")


def load_registry(path=None):
    """解析规则索引表；返回按表内顺序排列的规则字典列表。"""
    p = path or DEFAULT_PATH
    with open(p, encoding="utf-8") as f:
        lines = f.read().splitlines()
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        rid = cells[0]
        if rid in ("规则 ID", "") or set(rid) <= {"-", ":"}:
            continue
        if not _ID_RE.match(rid):
            continue
        owners = _OWNER_RE.findall(cells[3])
        rows.append({
            "rule_id": rid,
            "topic": cells[1],
            "rule": cells[2],
            "owners": owners,
            "deprecated": "deprecated" in s.lower(),
        })
    if not rows:
        raise ValueError("rule-index.md 未解析到任何规则行：%s" % p)
    return rows


def rule_ids(path=None):
    return {r["rule_id"] for r in load_registry(path)}


def get(rule_id, path=None):
    for r in load_registry(path):
        if r["rule_id"] == rule_id:
            return r
    return None
