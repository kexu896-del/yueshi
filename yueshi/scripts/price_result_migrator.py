#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
price_result_migrator.py —— 月食-叮咚价格结果.json 版本迁移器（round54 新增，round55 G13 定稿）。

用途：把可明确识别的受支持旧版结果文件迁移到当前契约版本（"1.2"）。
规则（price-provider-policy.md §4.2 / G13）：
- 只允许本脚本做版本升级，禁止人工编辑结果 JSON；
- `provider` 只有在旧文件来源可唯一确认时才可补齐（含
  delivery_context_confirmed_by_user 字段判定为 dingdong_web）；
- `schema_version` 只能按已知旧结构映射，不能直接填最新版；
- 每次迁移必须写 migration_log：source_schema_version / target_schema_version /
  fields_added / migrator_version / revalidation_passed / migrated_at；
- 迁移后重新执行 Schema 校验，revalidation_passed=false 即失败；
- 版本无法识别（连旧结构都对不上）即 price_result_invalid，不修补、报错退出。

用法：
    python scripts/price_result_migrator.py --input old.json --output new.json
"""
import argparse, io, json, os
from datetime import datetime, timezone, timedelta

MIGRATOR_VERSION = "1.0"
CURRENT_SCHEMA_VERSION = "1.2"
RESULT_SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "schemas", "price-result.schema.json")


def _detect_legacy(doc):
    """识别受支持旧版。返回 (legacy_version, provider_hint)；无法识别返回 None。

    已知旧结构：1.0/1.1 均含 results[].candidates[]（product_name+listed_price_yuan）
    与批次级 started_at/completed_at；含 delivery_context_confirmed_by_user
    可唯一确认来源为 dingdong_web。
    """
    results = doc.get("results")
    if not isinstance(results, list) or not results:
        return None
    cand0 = (results[0].get("candidates") or [{}])[0]
    if "product_name" not in cand0 and "listed_price_yuan" not in cand0:
        return None
    if "started_at" not in doc and "completed_at" not in doc:
        return None
    provider_hint = "dingdong_web" if "delivery_context_confirmed_by_user" in doc else None
    declared = str(doc.get("schema_version") or "")
    legacy = declared if declared in ("1.0", "1.1") else "legacy-1.1"
    return legacy, provider_hint


def _revalidate(doc):
    """迁移后重新执行同一 Schema 校验；jsonschema 不可用时做根级必填兜底。"""
    try:
        import jsonschema
        schema = json.load(io.open(RESULT_SCHEMA, encoding="utf-8"))
        jsonschema.validate(doc, schema)
        return True
    except ImportError:
        return all(doc.get(k) for k in ("schema_version", "provider", "request_id"))
    except Exception:
        return False


def migrate(doc):
    """返回迁移后的 doc；无法识别或校验失败时抛 SystemExit。"""
    if str(doc.get("schema_version")) == CURRENT_SCHEMA_VERSION:
        raise SystemExit("结果文件已是当前契约版本 %s，无需迁移。" % CURRENT_SCHEMA_VERSION)
    detected = _detect_legacy(doc)
    if detected is None:
        raise SystemExit(
            "price_result_invalid：字段缺失且版本无法识别，禁止人工放行/修补；"
            "请回本机「月食叮咚查价助手」重新导出。")
    legacy_version, provider_hint = detected
    fields_added = []
    if not doc.get("schema_version"):
        # 只能按已知旧结构映射版本号，不直接填最新版
        doc["schema_version"] = legacy_version
        fields_added.append("schema_version")
    if not doc.get("provider"):
        if provider_hint is None:
            raise SystemExit(
                "price_result_invalid：provider 缺失且旧文件来源无法唯一确认，禁止补齐；"
                "请回本机助手重新导出。")
        doc["provider"] = provider_hint
        fields_added.append("provider")
    if not doc.get("request_id"):
        raise SystemExit(
            "price_result_invalid：request_id 缺失无法迁移（必须与本次查价清单一致，"
            "不可推定）；请回本机助手重新导出。")
    # 1.0/1.1 → 1.2 结构清理：候选空值字段移除
    for r in doc.get("results", []):
        for c in r.get("candidates", []):
            for k in ("observed_at", "product_url"):
                if k in c and c[k] is None:
                    del c[k]
    doc["schema_version"] = CURRENT_SCHEMA_VERSION
    passed = _revalidate(doc)
    tz = timezone(timedelta(hours=8))
    doc["migration_log"] = {
        "source_schema_version": legacy_version,
        "target_schema_version": CURRENT_SCHEMA_VERSION,
        "fields_added": fields_added,
        "migrator_version": MIGRATOR_VERSION,
        "revalidation_passed": passed,
        "migrated_at": datetime.now(tz).isoformat(timespec="seconds"),
    }
    if not passed:
        raise SystemExit(
            "price_result_invalid：迁移后重新校验未通过（revalidation_passed=false），"
            "该结果不可用；请回本机助手重新导出。")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    with io.open(a.input, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc = migrate(doc)
    with io.open(a.output, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    log = doc["migration_log"]
    print("迁移完成：%s → %s（补齐字段 %s，重新校验通过）"
          % (log["source_schema_version"], log["target_schema_version"],
             log["fields_added"] or "无"))


if __name__ == "__main__":
    main()
