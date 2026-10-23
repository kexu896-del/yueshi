#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""助手语义快照导出（round73，2026-09-21）

商品语义判定单一来源化：主库数据文件是唯一来源，本脚本把三份主库数据导出为
助手内嵌快照 src/semantics-snapshot.json（随助手分发，构建时刷新）。

- commodity-vocabulary.json  → 判定词表（两侧判定器共用）；
- product-form-dictionary.json → 形态词典（助手形态识别）；
- ingredient-catalog.json     → 目录规则（7 个食材的 query_profile，助手精简清单展开）。

用法：
  python scripts/export_helper_semantics.py               # 写入助手 src/semantics-snapshot.json
  python scripts/export_helper_semantics.py --out <路径>   # 写入指定路径
  python scripts/export_helper_semantics.py --check        # 校验已提交快照是否新鲜（陈旧退出码 1）
"""
import argparse
import hashlib
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL_ROOT, "data")

# 助手侧精简清单展开所需的目录规则食材（与助手 CATALOG_RULES 历史范围一致）
CATALOG_SNAPSHOT_IDS = ["鸡腿", "三文鱼", "玉米", "芹菜", "鸡蛋", "红薯", "猪里脊"]

DEFAULT_OUT = os.path.join(SKILL_ROOT, "..", "yueshi-dingdong-helper", "src",
                           "semantics-snapshot.json")


def _read(rel):
    p = os.path.join(DATA, rel)
    with open(p, encoding="utf-8") as f:
        return f.read()


def build_snapshot():
    vocab_raw = _read("commodity-vocabulary.json")
    forms_raw = _read("product-form-dictionary.json")
    catalog_raw = _read("ingredient-catalog.json")

    vocab = json.loads(vocab_raw)
    forms = json.loads(forms_raw)
    catalog = json.loads(catalog_raw)

    rules = {}
    items = catalog.get("items") or {}
    missing = [iid for iid in CATALOG_SNAPSHOT_IDS if iid not in items]
    if missing:
        raise SystemExit("目录规则快照缺食材：%s" % missing)
    for iid in CATALOG_SNAPSHOT_IDS:
        rules[iid] = items[iid].get("query_profile") or {}

    def sha(raw):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return {
        "snapshot_version": "1.0.0",
        "说明": "商品语义判定单一来源快照（round73）：由月食技能仓 "
                "scripts/export_helper_semantics.py 从主库数据文件生成，禁止手改；"
                "主库改词后必须重跑导出并提升对应主库版本。",
        "generated_by": "scripts/export_helper_semantics.py",
        "commodity_vocabulary": vocab,
        "form_dictionary": {
            "version": forms.get("form_dictionary_version"),
            "negation_prefixes": forms.get("negation_prefixes"),
            "forms": forms.get("forms"),
            "conditional_accept": forms.get("conditional_accept"),
        },
        "catalog": {
            "version": catalog.get("catalog_version"),
            "rules": rules,
        },
        "source_hashes": {
            "commodity_vocabulary": sha(vocab_raw),
            "product_form_dictionary": sha(forms_raw),
            "ingredient_catalog": sha(catalog_raw),
        },
    }


def render(snapshot):
    return json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="助手语义快照导出（round73）")
    ap.add_argument("--out", default=None, help="输出路径（默认助手 src/semantics-snapshot.json）")
    ap.add_argument("--check", action="store_true", help="校验已提交快照是否新鲜")
    args = ap.parse_args()

    snapshot = build_snapshot()
    text = render(snapshot)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    if args.check:
        target = args.out or DEFAULT_OUT
        if not os.path.exists(target):
            print("FAIL: 快照不存在：%s（请运行 export_helper_semantics.py）" % target)
            return 1
        current = open(target, encoding="utf-8").read()
        if current != text:
            print("FAIL: 快照陈旧：%s（主库已变，请重新导出）" % target)
            return 1
        print("OK: 快照新鲜 %s | sha16=%s | 目录 %s / 形态 %s" % (
            target, digest, snapshot["catalog"]["version"],
            snapshot["form_dictionary"]["version"]))
        return 0

    target = args.out or DEFAULT_OUT
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(text)
    print("快照已写入：%s | sha16=%s | 目录 %s / 形态 %s / 词汇 %s | 规则 %d 项" % (
        target, digest, snapshot["catalog"]["version"],
        snapshot["form_dictionary"]["version"],
        snapshot["commodity_vocabulary"].get("vocabulary_version"),
        len(snapshot["catalog"]["rules"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
