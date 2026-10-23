#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速模式索引生成（round76）

两份轻量索引此前是"无生成脚本的孤儿产物"（停留 2026-08-21，快速模式读旧数据）。
本脚本从生产菜谱池重新派生，并作为构建链（scripts/build_library.py）的末步骤：

- data/recipe-production-index.json —— 快速模式初筛（只读本文件，不打开菜谱正文）
- data/ingredient-recipe-inverted.json —— ingredient → recipe 倒排索引

字段映射（与历史产物逐字段核对一致）：
  HowToCook（recipe-index.json）：name=original_name / source_id="howtocook" /
    mode_fit=adaptability / equipment 原样 / estimated_active_minutes 原样
  书籍（book-recipes.json）：name=name / source_id="book_pool_11books" /
    mode_fit=mode_fit / equipment=[] / estimated_active_minutes=active_minutes

版本口径：production_pool_version / build_version = library-manifest release.build_id。
不在索引内嵌 manifest 字节哈希：门禁的常规审批重放会改写 approved_at/approved_by（测试运行时
也会），字节级绑定会造成"虚假过期"；manifest 与产物的一致性由 scripts/build_library.py --check
的 artifact_hashes 校验负责，索引新鲜度由本脚本的内容重建比对负责。

用法：
  python scripts/build_quick_indices.py            # 写入 data/
  python scripts/build_quick_indices.py --out DIR  # 写入指定目录（测试/密封）
  python scripts/build_quick_indices.py --check    # 校验已提交文件与当前池一致
"""
import argparse
import json
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
DATA = os.path.join(ROOT, "data")

PROD_FILE = "recipe-production-index.json"
INVERTED_FILE = "ingredient-recipe-inverted.json"

PROD_PURPOSE = "轻量菜谱检索索引：快速模式只读本文件初筛，入选后再打开完整菜谱记录"
INVERTED_PURPOSE = "ingredient→recipe 倒排索引：快速模式候选检索，不扫描菜谱正文"


def _load(rel):
    with open(os.path.join(DATA, rel), encoding="utf-8") as f:
        return json.load(f)


def _build_id(manifest_path=None):
    p = manifest_path or os.path.join(DATA, "library-manifest.json")
    with open(p, encoding="utf-8") as f:
        mf = json.load(f)
    return ((mf.get("release") or {}).get("build_id")) or "unknown"


def _entry_howtocook(r):
    return {
        "id": r["id"],
        "name": r.get("original_name") or r.get("name"),
        "source_id": "howtocook",
        "core_ingredients": r.get("core_ingredients") or [],
        "methods": r.get("methods") or [],
        "flavors": r.get("flavors") or [],
        "structure": r.get("structure"),
        "estimated_active_minutes": r.get("estimated_active_minutes"),
        "equipment": r.get("equipment") or [],
        "mode_fit": r.get("adaptability") or {},
    }


def _entry_book(r):
    return {
        "id": r["id"],
        "name": r.get("name") or r.get("original_name"),
        "source_id": "book_pool_11books",
        "core_ingredients": r.get("core_ingredients") or [],
        "methods": r.get("methods") or [],
        "flavors": r.get("flavors") or [],
        "structure": r.get("structure"),
        "estimated_active_minutes": r.get("active_minutes"),
        "equipment": [],
        "mode_fit": r.get("mode_fit") or {},
    }


def build_documents(manifest_path=None):
    """返回 (生产索引文档, 倒排索引文档)；顺序 = HowToCook 全量 → 书籍全量。"""
    build_id = _build_id(manifest_path)
    index = _load("recipe-index.json")
    books = (_load("book-recipes.json") or {}).get("recipes") or []
    entries = [_entry_howtocook(r) for r in index] + [_entry_book(r) for r in books]
    prod = {
        "purpose": PROD_PURPOSE,
        "generated_from": ["data/recipe-index.json", "data/book-recipes.json"],
        "production_pool_version": build_id,
        "record_count": len(entries),
        "recipes": entries,
    }
    inverted = {}
    for e in entries:
        for ing in e.get("core_ingredients") or []:
            inverted.setdefault(ing, []).append(e["id"])
    inv = {
        "purpose": INVERTED_PURPOSE,
        "count": len(inverted),
        "index": inverted,
        "build_version": build_id,
    }
    return prod, inv


def render(doc):
    return json.dumps(doc, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="快速模式索引生成（round76）")
    ap.add_argument("--out", default=None, help="输出目录（默认 data/）")
    ap.add_argument("--check", action="store_true", help="校验已提交文件是否与当前池一致")
    args = ap.parse_args()
    prod, inv = build_documents()
    pairs = [(PROD_FILE, render(prod)), (INVERTED_FILE, render(inv))]
    if args.check:
        bad = []
        for name, text in pairs:
            p = os.path.join(DATA, name)
            if not os.path.exists(p):
                bad.append("%s 不存在" % name)
                continue
            with open(p, encoding="utf-8") as f:
                if f.read() != text:
                    bad.append("%s 陈旧（池或 manifest 已变，请重跑 build_quick_indices.py）" % name)
        if bad:
            for b in bad:
                print("FAIL: " + b)
            return 1
        print("OK: 快速索引新鲜 | 记录 %d | 食材 %d" % (prod["record_count"], inv["count"]))
        return 0
    out_dir = args.out or DATA
    os.makedirs(out_dir, exist_ok=True)
    for name, text in pairs:
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(text)
    print("快速索引已写入：%s | 记录 %d | 食材 %d | build_id=%s" % (
        out_dir, prod["record_count"], inv["count"], prod["production_pool_version"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
