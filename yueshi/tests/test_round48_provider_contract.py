#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round48：价格数据契约 1.2 回归（放弃地址读取 + 正式/诊断分离 + 效率门禁）。

覆盖：
1. Schema 1.2：schema_version const "1.2"；地址字段（delivery_area /
   delivery_area_label / address_confirmed_by_user / address_unconfirmed）
   全部移除；delivery_context_confirmed_by_user 存在；候选不含
   raw_field_names / image_url；query_result 不含 diagnostics；
2. price-query Schema 移除 delivery_area_expected；
3. golden 样例 1.2 全量通过；delivery_context_confirmed_by_user=false →
   P02_DELIVERY_CONTEXT_UNCONFIRMED；
4. 路由器：snapshot meta 含 delivery_context_confirmed_by_user、不含地址字段；
   DIRECT_PRICE_REQUIRED_FIELDS 不含 delivery_area_label；
5. 契约文档：1.2 版本头、不读取地址、效率门禁（≥3 合格即停 / product_id 去重）、
   价格失败不重跑菜单；SKILL/output-policy 文本同步 "1.2"。
"""
import json
import os
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


class TestSchema12(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(_read("schemas/price-result.schema.json"))
        self.qschema = json.loads(_read("schemas/price-query.schema.json"))

    def test_version_const_12(self):
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "1.2")

    def test_address_fields_removed(self):
        props = self.schema["properties"]
        for gone in ("delivery_area", "delivery_area_label",
                     "address_confirmed_by_user"):
            self.assertNotIn(gone, props, gone)
        self.assertIn("delivery_context_confirmed_by_user", props)
        enum = self.schema["definitions"]["query_result"]["properties"]["status"]["enum"]
        self.assertNotIn("address_unconfirmed", enum)

    def test_candidate_slimmed(self):
        cand = self.schema["definitions"]["product_candidate"]["properties"]
        for gone in ("raw_field_names", "image_url", "delivery_area_label"):
            self.assertNotIn(gone, cand, gone)
        qr = self.schema["definitions"]["query_result"]["properties"]
        self.assertNotIn("diagnostics", qr)

    def test_query_schema_no_area_expected(self):
        self.assertNotIn("delivery_area_expected", self.qschema["properties"])


class TestValidator12(unittest.TestCase):
    def setUp(self):
        import price_result_validator as prv
        self.prv = prv
        self.result_path = os.path.join(BASE, "data", "golden", "price-result-sample.json")
        self.query_path = os.path.join(BASE, "data", "golden", "price-query-sample.json")

    def _golden(self):
        return json.loads(_read("data/golden/price-result-sample.json"))

    def test_price_data_version_12(self):
        self.assertEqual(self.prv.PRICE_DATA_VERSION, "1.2")

    def test_golden_passes(self):
        report = self.prv.validate_result(
            self.result_path, request_id="weekly-plan-2026-08-26-sample",
            query_path=self.query_path)
        self.assertFalse(report["rejected"], report.get("errors"))
        self.assertEqual(report["provider_status"], "success")
        self.assertEqual(report.get("candidate_violations"), {})
        self.assertTrue(report["delivery_context_confirmed_by_user"])

    def test_unconfirmed_context_flagged(self):
        result = self._golden()
        result["delivery_context_confirmed_by_user"] = False
        path = _write_tmp(result)
        try:
            report = self.prv.validate_result(
                path, request_id=result["request_id"], query_path=self.query_path)
            violations = [v for vs in report["candidate_violations"].values() for v in vs]
            self.assertIn("P02_DELIVERY_CONTEXT_UNCONFIRMED", violations)
        finally:
            os.unlink(path)


class TestRouter12(unittest.TestCase):
    def setUp(self):
        import price_provider_router as ppr
        self.ppr = ppr

    def test_required_fields_no_address(self):
        self.assertNotIn("delivery_area_label", self.ppr.DIRECT_PRICE_REQUIRED_FIELDS)

    def test_unconfirmed_context_caps_limited(self):
        good = {
            "product_id": "p-1", "product_name": "北豆腐 400g/盒",
            "package_text": "400g/盒", "reference_grams": 400,
            "listed_price_yuan": 4.29,
            "observed_at": "2026-08-26T08:28:00+08:00",
            "availability": "available", "provider": "dingdong_web",
            "data_source": "network_response", "parse_warnings": [],
            "eligible_for_purchase": True,
        }
        self.assertEqual(self.ppr.assign_price_basis(good, False),
                         "direct_public_price_limited")

    def test_snapshot_meta_context_field(self):
        batch = json.loads(_read("data/golden/price-result-sample.json"))
        meta = self.ppr.build_price_snapshot_meta(batch, "sha256:x", "1.3.0")
        self.assertEqual(meta["result_schema_version"], "1.2")
        self.assertTrue(meta["delivery_context_confirmed_by_user"])
        for gone in ("delivery_area_label", "delivery_area_source",
                     "delivery_area_verified"):
            self.assertNotIn(gone, meta, gone)


class TestPolicyText12(unittest.TestCase):
    def setUp(self):
        self.policy = _read("references/price-provider-policy.md")

    def test_version_12_header(self):
        self.assertIn("price_provider_policy_version = 1.2", self.policy)
        self.assertIn('price_data_version = "1.2"', self.policy)

    def test_no_address_reading(self):
        self.assertIn("不读取、不保存、不验证具体收货地址", self.policy)
        self.assertIn("delivery_context_confirmed_by_user", self.policy)
        # 地址证据分级整节已删除
        self.assertNotIn("配送区域证据分级", self.policy)
        self.assertNotIn("delivery_area_source", self.policy)

    def test_efficiency_gates(self):
        self.assertIn("≥3 个合格候选即停止", self.policy)
        self.assertIn("product_id 去重", self.policy)

    def test_price_failure_no_rerun(self):
        self.assertIn("价格失败不得迫使整份菜谱重新生成", self.policy)
        self.assertIn("最多触发一次轻量回退", self.policy)

    def test_formal_diagnostics_split(self):
        self.assertIn("不进正式结果", self.policy)
        self.assertIn("price-diagnostics.json", self.policy)

    def test_skill_and_output_policy_version_text(self):
        self.assertIn('当前 "1.2"', _read("SKILL.md"))
        self.assertIn('当前 "1.2"', _read("references/output-policy.md"))


if __name__ == "__main__":
    unittest.main()
