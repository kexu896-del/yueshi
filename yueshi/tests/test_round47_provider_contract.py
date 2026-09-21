#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round47：查询追溯 + eligible SKU 门槛回归（round48 契约 1.2 下修订）。

round48 契约演进：地址证据分级（§6.1、delivery_area 块、P02_DELIVERY_AREA_UNVERIFIED）
已被「放弃地址读取 + delivery_context_confirmed_by_user」取代，相关断言移除；
版本断言改为与 Schema const 同源（动态），不再硬编码 "1.1"。

仍覆盖：
1. Schema：状态细分枚举、eligible_for_purchase / matched_query 字段、search_terms maxItems=3；
2. golden 样例全量通过；available 但非 eligible → P06_NOT_ELIGIBLE_SKU；
   positive_terms / hard_excluded_terms 相关性对照；CLI 退出码；
3. 路由器：eligible_for_purchase=False → 至多 direct_public_price_limited；
   缺省 eligible 按五要素推算（无 product_id → limited）；
4. 契约文档：§5.1 追溯字段、性能边界 ≤3 词。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
sys.path.insert(0, SCRIPTS)


def _read(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


def _write_tmp(payload):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(payload, f, ensure_ascii=False)
    f.close()
    return f.name


def _schema_const_version():
    schema = json.loads(_read("schemas/price-result.schema.json"))
    return schema["properties"]["schema_version"]["const"]


class TestSchemaTiered(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(_read("schemas/price-result.schema.json"))
        self.qschema = json.loads(_read("schemas/price-query.schema.json"))

    def test_version_matches_validator(self):
        import price_result_validator as prv
        self.assertEqual(_schema_const_version(), prv.PRICE_DATA_VERSION)

    def test_status_enum_refined(self):
        enum = self.schema["definitions"]["query_result"]["properties"]["status"]["enum"]
        for s in ("search_empty", "candidates_filtered", "candidates_unpriced",
                  "candidates_unavailable", "no_match"):
            self.assertIn(s, enum)

    def test_traceability_fields(self):
        qr = self.schema["definitions"]["query_result"]["properties"]
        for f in ("attempted_queries", "matched_query", "match_strategy"):
            self.assertIn(f, qr, f)
        cand = self.schema["definitions"]["product_candidate"]["properties"]
        for f in ("matched_query", "eligible_for_purchase"):
            self.assertIn(f, cand, f)

    def test_query_schema_tiered_terms(self):
        item = self.qschema["definitions"]["query_item"]["properties"]
        self.assertEqual(item["search_terms"]["maxItems"], 3)
        self.assertIn("positive_terms", item)
        self.assertIn("hard_excluded_terms", item)


class TestValidatorGates(unittest.TestCase):
    def setUp(self):
        import price_result_validator as prv
        self.prv = prv
        self.result_path = os.path.join(BASE, "data", "golden", "price-result-sample.json")
        self.query_path = os.path.join(BASE, "data", "golden", "price-query-sample.json")

    def _golden(self):
        return json.loads(_read("data/golden/price-result-sample.json"))

    def test_golden_passes(self):
        report = self.prv.validate_result(
            self.result_path, request_id="weekly-plan-2026-08-26-sample",
            query_path=self.query_path)
        self.assertFalse(report["rejected"], report.get("errors"))
        self.assertEqual(report["provider_status"], "success")
        self.assertEqual(report.get("candidate_violations"), {})
        self.assertEqual(report["price_data_version"], _schema_const_version())

    def test_not_eligible_sku_flagged(self):
        result = self._golden()
        result["results"][0]["candidates"][0]["eligible_for_purchase"] = False
        path = _write_tmp(result)
        try:
            report = self.prv.validate_result(
                path, request_id=result["request_id"], query_path=self.query_path)
            violations = [v for vs in report["candidate_violations"].values() for v in vs]
            self.assertIn("P06_NOT_ELIGIBLE_SKU", violations)
        finally:
            os.unlink(path)

    def test_positive_and_hard_exclude_terms(self):
        result = self._golden()
        cand = result["results"][0]["candidates"][0]
        cand["product_name"] = "黑椒腌制里脊 400g"  # 命中 hard_excluded_terms（黑椒/腌制）
        path = _write_tmp(result)
        try:
            report = self.prv.validate_result(
                path, request_id=result["request_id"], query_path=self.query_path)
            violations = [v for vs in report["candidate_violations"].values() for v in vs]
            self.assertIn("P07_EXCLUDED_TERM", violations)
        finally:
            os.unlink(path)

    def test_cli_golden_exit_0(self):
        script = os.path.join(SCRIPTS, "price_result_validator.py")
        ok = subprocess.run([sys.executable, script, self.result_path,
                             "--request-id", "weekly-plan-2026-08-26-sample",
                             "--query", self.query_path], capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr.decode())


class TestRouterEligible(unittest.TestCase):
    def setUp(self):
        import price_provider_router as ppr
        self.ppr = ppr
        self.good = {
            "product_id": "p-1", "product_name": "北豆腐 400g/盒",
            "package_text": "400g/盒", "reference_grams": 400,
            "listed_price_yuan": 4.29,
            "observed_at": "2026-08-26T08:28:00+08:00",
            "availability": "available", "provider": "dingdong_web",
            "data_source": "network_response", "parse_warnings": [],
            "eligible_for_purchase": True,
        }

    def test_eligible_gate_required(self):
        self.assertEqual(self.ppr.assign_price_basis(self.good, True),
                         "direct_public_price")
        not_eligible = dict(self.good, eligible_for_purchase=False)
        self.assertEqual(self.ppr.assign_price_basis(not_eligible, True),
                         "direct_public_price_limited")

    def test_eligible_fallback_inference(self):
        # 缺省 eligible：按五要素推算；无 product_id（DOM 侦察候选）→ 不合格
        inferred = dict(self.good)
        del inferred["eligible_for_purchase"]
        self.assertEqual(self.ppr.assign_price_basis(inferred, True),
                         "direct_public_price")
        dom_only = dict(inferred, product_id=None)
        self.assertEqual(self.ppr.assign_price_basis(dom_only, True),
                         "direct_public_price_limited")


class TestPolicyTieredText(unittest.TestCase):
    def setUp(self):
        self.policy = _read("references/price-provider-policy.md")

    def test_tiered_recall_section(self):
        for needle in ("attempted_queries", "matched_query", "match_strategy",
                       "search_empty", "candidates_filtered", "candidates_unpriced",
                       "candidates_unavailable"):
            self.assertIn(needle, self.policy, needle)

    def test_perf_boundary_three_terms(self):
        self.assertIn("最多查询 3 个查询词", self.policy)
        self.assertNotIn("1 个主关键词 + 1 个别名", self.policy)


if __name__ == "__main__":
    unittest.main()
