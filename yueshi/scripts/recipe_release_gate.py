#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱库生产准入门禁（round63 工作流 F）。

唯一允许写 library-manifest.json release 块的脚本；审计失败时不得手工改状态绕过。

判定：
  - 读取 recipe_library_auditor.py 的审计 JSON（--audit，默认先跑审计）；
  - 有 blocking_issues → release_status = blocked；
  - 有 warnings 无 blocking → review_required（可经 --approve 人工确认后升 approved，
    人工确认必须给 --approved-by 留痕）；
  - 无 blocking 且无 warnings → approved；
  - 阈值与指标同时写入 manifest.quality_thresholds / quality_metrics，构建 ID 三件套
    （审计报告、manifest、菜谱分类/指纹）必须一致，不一致即 blocked。

round64 起 manifest.release 同时冻结全部生产产物内容哈希（artifact_hashes）；
ranker 启动时同时校验 approved 状态、build ID 与内容哈希，任一不一致即拒绝读取生产库。
taxonomy 或食材目录变更后必须重跑「分类器 → 指纹 → 审计 → 门禁」完整链路，
否则 artifact_hashes 失配，release gate 拒绝、ranker 拒绝。

用法：
  python scripts/recipe_release_gate.py                 # 判定并写 manifest
  python scripts/recipe_release_gate.py --approve --approved-by 张三   # 人工放行警告项
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(BASE, "data")
MANIFEST = os.path.join(DATA, "library-manifest.json")

# 纳入发布冻结的生产产物（相对 data/ 的路径；taxonomy_bundle 为 taxonomy 目录合并哈希）
ARTIFACT_FILES = {
    "recipe_index": "recipe-index.json",
    "book_recipes": "book-recipes.json",
    "classification_output": "recipe-classification.json",
    "fingerprints": "recipe-fingerprints.json",
    "audit_data": "audit/latest-audit.json",
    "ingredient_catalog": "ingredient-catalog.json",
    "review_overrides": "audit/review-overrides.json",
}


def evaluate_overrides():
    """round64.1 §6：人工覆写闭环。
    在冻结哈希前调用（可能回写状态迁移）：
      - review_required（未审核）→ blocking；
      - applied_pending_rule_fix：绑定的菜谱/taxonomy/目录哈希与当前不一致
        → 自动标记 stale 并 blocking；分类器当前输出已等于批准值
        → 迁移为 resolved_in_classifier（保留审计历史）；
      - stale → blocking；
      - rejected / resolved_in_classifier → 不阻断。
    返回 blocking 列表。"""
    p = os.path.join(DATA, "audit", "review-overrides.json")
    if not os.path.exists(p):
        return []
    ov = json.load(open(p, encoding="utf-8"))
    overrides = ov.get("overrides", [])
    if not overrides:
        return []
    cls = json.load(open(os.path.join(DATA, "recipe-classification.json"),
                         encoding="utf-8"))
    rec = {r["id"]: r for r in cls["records"]}
    cur_tax = sha256_tree(os.path.join(DATA, "taxonomy"))
    cur_cat = sha256_file(os.path.join(DATA, "ingredient-catalog.json"))
    blocking, changed = [], False
    for o in overrides:
        st = o.get("status")
        if st == "review_required":
            blocking.append(f"override_review_required:{o.get('recipe_id')}")
            continue
        if st == "applied_pending_rule_fix":
            r = rec.get(o.get("recipe_id"))
            cur_rec = ("sha256:" + hashlib.sha256(
                json.dumps(r, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()) if r else None
            stale = (cur_rec != o.get("source_recipe_hash")
                     or cur_tax != o.get("taxonomy_bundle_hash")
                     or cur_cat != o.get("ingredient_catalog_hash"))
            # 分类器已能自动得到批准值 → 转 resolved_in_classifier
            if r and r.get(o.get("field_name")) == o.get("approved_value"):
                o["status"] = "resolved_in_classifier"
                o["resolved_note"] = "分类器输出已与批准值一致，覆写归档（历史保留）"
                changed = True
                continue
            if stale:
                o["status"] = "stale"
                o["stale_reason"] = "source/taxonomy/catalog hash 已变化，须重新审核"
                changed = True
                blocking.append(f"override_stale:{o.get('recipe_id')}")
            continue
        if st == "stale":
            # 幂等恢复：记录的绑定哈希与当前一致（净变化为零）→ 解除 stale，
            # 回到 applied_pending_rule_fix；分类器已一致 → resolved
            r = rec.get(o.get("recipe_id"))
            cur_rec = ("sha256:" + hashlib.sha256(
                json.dumps(r, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()) if r else None
            if r and r.get(o.get("field_name")) == o.get("approved_value"):
                o["status"] = "resolved_in_classifier"
                o["resolved_note"] = "分类器输出已与批准值一致，覆写归档（历史保留）"
                changed = True
                continue
            if (cur_rec == o.get("source_recipe_hash")
                    and cur_tax == o.get("taxonomy_bundle_hash")
                    and cur_cat == o.get("ingredient_catalog_hash")):
                o["status"] = "applied_pending_rule_fix"
                o["restored_note"] = "绑定哈希与当前一致（净变化为零），自动解除 stale"
                changed = True
                continue
            blocking.append(f"override_stale:{o.get('recipe_id')}")
    if changed:
        json.dump(ov, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return blocking


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_tree(dirpath):
    h = hashlib.sha256()
    for root, _dirs, files in sorted(os.walk(dirpath)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, dirpath)
            h.update(rel.encode("utf-8"))
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
    return "sha256:" + h.hexdigest()


def compute_artifact_hashes():
    """冻结全部生产产物内容哈希；缺任一产物返回 None（由调用方转 blocking）。"""
    hashes = {}
    for key, rel in ARTIFACT_FILES.items():
        p = os.path.join(DATA, rel)
        if not os.path.exists(p):
            return None, f"artifact_missing:{rel}"
        hashes[key] = sha256_file(p)
    tax_dir = os.path.join(DATA, "taxonomy")
    if not os.path.isdir(tax_dir):
        return None, "artifact_missing:taxonomy/"
    hashes["taxonomy_bundle"] = sha256_tree(tax_dir)
    return hashes, None

QUALITY_THRESHOLDS = {
    "dish_category_coverage": 1.0,
    "primary_ingredient_family_coverage": 0.98,
    "primary_protein_family_coverage": 0.98,
    "classification_sample_accuracy": 0.95,
    "cross_category_cluster_count": 0,
    "severe_protein_mislabel_count": 0,
}


def run_audit():
    out = os.path.join(DATA, "audit", "latest-audit.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run([sys.executable,
                        os.path.join(BASE, "scripts", "recipe_library_auditor.py"),
                        "--json", out], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit("release_gate_error: 审计脚本运行失败")
    return json.load(open(out, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default=None, help="已有审计 JSON；缺省自动重跑审计")
    ap.add_argument("--approve", action="store_true", help="人工放行 warnings（须 --approved-by）")
    ap.add_argument("--approved-by", default=None)
    args = ap.parse_args()

    rep = json.load(open(args.audit, encoding="utf-8")) if args.audit else run_audit()
    if rep.get("audit_status") is None:
        raise SystemExit("release_gate_error: 审计缺少 audit_status（验收层未运行）")

    blocking = rep.get("blocking_issues", [])
    warnings = rep.get("warnings", [])
    metrics = rep.get("quality_metrics", {})
    audit_build = rep.get("build_id")

    # 构建 ID 一致性：审计报告 / 分类 / 指纹必须同一次构建
    for name in ("recipe-classification.json", "recipe-fingerprints.json"):
        p = os.path.join(DATA, name)
        if not os.path.exists(p):
            blocking = sorted(set(blocking) | {f"build_artifact_missing:{name}"})
            continue
        bid = json.load(open(p, encoding="utf-8")).get("build_id")
        if bid != audit_build:
            blocking = sorted(set(blocking) | {f"build_id_mismatch:{name}"})

    # 人工覆写闭环（round64.1，须在冻结哈希前评估：可能回写状态迁移）
    blocking = sorted(set(blocking) | set(evaluate_overrides()))

    # 生产产物内容哈希（round64）：taxonomy/目录/分类/指纹/审计/索引/覆写 全部冻结
    artifact_hashes, hash_err = compute_artifact_hashes()
    if hash_err:
        blocking = sorted(set(blocking) | {hash_err})

    # 漂移检测（round64）：分类产物记录的源哈希必须与当前 taxonomy/目录一致，
    # 否则说明 taxonomy 或食材目录变更后未重新分类
    cls_path = os.path.join(DATA, "recipe-classification.json")
    if os.path.exists(cls_path) and artifact_hashes:
        src = (json.load(open(cls_path, encoding="utf-8")).get("source_hashes") or {})
        for key, label in (("taxonomy_bundle", "taxonomy_drift"),
                           ("ingredient_catalog", "ingredient_catalog_drift")):
            recorded = src.get(key)
            if not recorded:
                blocking = sorted(set(blocking) | {f"source_hash_missing:{key}"})
            elif recorded != artifact_hashes.get(key):
                blocking = sorted(set(blocking) | {label})

    if blocking:
        status = "blocked"
    elif warnings:
        status = "review_required"
        if args.approve:
            if not args.approved_by:
                raise SystemExit("release_gate_error: --approve 必须同时给 --approved-by 留痕")
            status = "approved"
    else:
        status = "approved"

    mf = json.load(open(MANIFEST, encoding="utf-8"))
    mf["release"] = {
        "release_status": status,
        "build_id": audit_build,
        "artifact_hashes": artifact_hashes,
        "quality_thresholds": QUALITY_THRESHOLDS,
        "quality_metrics": metrics,
        "blocking_issues": blocking,
        "warnings": warnings,
        "approved_by": (args.approved_by if args.approve else
                        ("recipe_release_gate.py(auto)" if status == "approved" else None)),
        "approved_at": (datetime.datetime.now().isoformat(timespec="seconds")
                        if status == "approved" else None),
        "gate": "scripts/recipe_release_gate.py",
        "note": "release_status 只能由本脚本依据审计结果写入；审计失败不得手工改状态绕过。"
                "修改菜谱数据、分类器或指纹算法后必须重新审计并重新过门禁。"
                "artifact_hashes 冻结全部生产产物内容哈希；taxonomy 或食材目录变更后"
                "必须重跑完整构建链，否则哈希失配即拒绝。",
    }
    json.dump(mf, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({"release_status": status, "build_id": audit_build,
                      "blocking_issues": blocking, "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
