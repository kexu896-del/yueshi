#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round46：外部价格 Provider 契约回归。

覆盖：
1. 新文件齐备（policy / 两份 Schema / 两个脚本 / golden 样例）；
2. SKILL.md 摘要、版本号、门禁映射与哈希职责表述；
3. price_result_validator：golden 样例通过；损坏文件/request_id 不匹配 → invalid_result（退出码 3）；
   P02–P07 候选级违例检出；
4. price_provider_router：状态映射不扩大 fatal 枚举；price_basis 收紧条件；
   provider 与 price_basis 分离；ordinary_payable_price 不用会员价；
5. 性能基线包含 price_gate 节点且 login_wait 口径分离说明存在。
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


class TestFilesExist(unittest.TestCase):
    def test_new_files_present(self):
        for rel in (
            "references/price-provider-policy.md",
            "schemas/price-query.schema.json",
            "schemas/price-result.schema.json",
            "scripts/price_result_validator.py",
            "scripts/price_provider_router.py",
            "data/golden/price-query-sample.json",
            "data/golden/price-result-sample.json",
        ):
            self.assertTrue(os.path.exists(os.path.join(BASE, rel)), rel)

    def test_schemas_are_valid_draft07(self):
        import jsonschema
        for rel in ("schemas/price-query.schema.json", "schemas/price-result.schema.json"):
            schema = json.loads(_read(rel))
            jsonschema.Draft7Validator.check_schema(schema)


class TestSkillEntry(unittest.TestCase):
    def setUp(self):
        self.skill = _read("SKILL.md")
        self.policy = _read("references/price-provider-policy.md")
        self.runtime = _read("references/runtime-rules.md")
        self.output = _read("references/output-policy.md")

    def test_version_bumped(self):
        # 与 frontmatter 同源动态断言（round43 T01 先例）：semver 且不低于 1.2.0
        import re
        m = re.search(r"^version: yueshi-(\d+)\.(\d+)\.(\d+)(-\S+)?$", self.skill, re.M)
        self.assertIsNotNone(m, "frontmatter version 缺失")
        self.assertGreaterEqual((int(m.group(1)), int(m.group(2))), (1, 2))

    def test_skill_summary_block(self):
        # round57：SKILL Provider 摘要缩短为指针版，权限边界完整表述移至 policy §1
        for needle in ("外部价格 Provider", "new_purchase_amount > 0",
                       "user_input_required", "references/price-provider-policy.md"):
            self.assertIn(needle, self.skill, needle)
        for needle in ("不具有", "修改菜单", "恢复用户删除食材",
                       "加入购物车、提交订单、支付"):
            self.assertIn(needle, self.policy, needle)

    def test_policy_core_contracts(self):
        for needle in ("price_provider_priority", "dingdong_web_direct",
                       "direct_public_price_limited", "P01", "P08",
                       "price_snapshot_meta", "price_result_hash",
                       "login_wait_ms", "普通应付价"):
            self.assertIn(needle, self.policy, needle)
        # 性能硬边界：契约 1.1 起为 ≤3 查询词（分层召回）、5 候选
        self.assertIn("最多查询 3 个查询词", self.policy)
        self.assertIn("最多保留 5 个候选", self.policy)

    def test_hash_responsibility_separation(self):
        for needle in ("rules_bundle_hash", "pipeline_bundle_hash",
                       "price_result_hash", "price_data_version"):
            self.assertIn(needle, self.skill, needle)
        # price_data_version 唯一含义：价格数据契约版本
        self.assertIn("价格数据契约版本", self.skill)

    def test_g06_scope_limit(self):
        self.assertIn("不得编价", self.skill)
        self.assertIn("会员价当普通价", self.skill)
        self.assertIn("G06 自动修复范围限定", self.policy)

    def test_no_fatal_enum_expansion(self):
        # fatal_reason 仍为 7 枚举，不新增 Provider 类 fatal
        for forbidden in ("provider_unavailable", "login_failed", "price_fetch_failed"):
            self.assertNotIn(forbidden, self.skill)
            self.assertNotIn(forbidden, self.runtime)


class TestValidator(unittest.TestCase):
    def setUp(self):
        import price_result_validator as prv
        self.prv = prv
        self.result_path = os.path.join(BASE, "data", "golden", "price-result-sample.json")
        self.query_path = os.path.join(BASE, "data", "golden", "price-query-sample.json")

    def test_golden_passes(self):
        report = self.prv.validate_result(
            self.result_path,
            request_id="weekly-plan-2026-08-26-sample",
            query_path=self.query_path,
        )
        self.assertFalse(report["rejected"], report.get("errors"))
        self.assertEqual(report["provider_status"], "success")
        self.assertEqual(report.get("candidate_violations"), {})
        self.assertTrue(report["result_hash"].startswith("sha256:"))

    def test_corrupted_file_invalid_result(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            f.write("{not json")
            bad = f.name
        try:
            report = self.prv.validate_result(bad)
            self.assertEqual(report["provider_status"], "invalid_result")
            self.assertTrue(report["rejected"])
        finally:
            os.unlink(bad)

    def test_request_id_mismatch_p08(self):
        report = self.prv.validate_result(self.result_path, request_id="other-batch")
        self.assertEqual(report["provider_status"], "invalid_result")
        self.assertIn("P08", report["errors"][0])

    def test_candidate_gates(self):
        result = json.loads(_read("data/golden/price-result-sample.json"))
        cand = result["results"][0]["candidates"][0]
        # P06 售罄
        cand["availability"] = "sold_out"
        # P07 排除词
        cand["product_name"] = "黑椒腌制里脊 400g"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
            path = f.name
        try:
            report = self.prv.validate_result(
                path, request_id=result["request_id"], query_path=self.query_path)
            violations = [v for vs in report["candidate_violations"].values() for v in vs]
            self.assertIn("P06_SOLD_OUT", violations)
            self.assertIn("P07_EXCLUDED_TERM", violations)
        finally:
            os.unlink(path)

    def test_cli_exit_codes(self):
        script = os.path.join(SCRIPTS, "price_result_validator.py")
        ok = subprocess.run([sys.executable, script, self.result_path,
                             "--request-id", "weekly-plan-2026-08-26-sample",
                             "--query", self.query_path], capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr.decode())
        bad = subprocess.run([sys.executable, script, self.result_path,
                              "--request-id", "nope"], capture_output=True)
        self.assertEqual(bad.returncode, 3)


class TestRouter(unittest.TestCase):
    def setUp(self):
        import price_provider_router as ppr
        self.ppr = ppr

    def test_status_mapping_no_new_fatal(self):
        for status in self.ppr.PROVIDER_STATUSES:
            for forced in (False, True):
                mapped = self.ppr.map_provider_status(status, forced)
                self.assertIn(mapped["gate_result"],
                              ("auto_fix", "user_input_required", "success"))
                self.assertNotEqual(mapped["gate_result"], "fatal", status)
        # 用户强制实时价 + 需用户操作 → user_input_required
        mapped = self.ppr.map_provider_status("user_action_required", True)
        self.assertEqual(mapped["gate_result"], "user_input_required")
        # 未强制 → 允许降级
        mapped = self.ppr.map_provider_status("user_action_required", False)
        self.assertEqual(mapped["gate_result"], "auto_fix")
        # invalid_result 不得记为 corrupted_plan_json
        mapped = self.ppr.map_provider_status("invalid_result")
        self.assertNotIn("corrupted_plan_json", json.dumps(mapped, ensure_ascii=False))

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            self.ppr.map_provider_status("exploded")

    def test_price_basis_tightening(self):
        good = {
            "product_id": "p-1", "product_name": "北豆腐 400g/盒",
            "package_text": "400g/盒",
            "reference_grams": 400, "listed_price_yuan": 4.29,
            "observed_at": "2026-08-26T08:28:00+08:00",
            "delivery_area_label": "南京市鼓楼区某小区",
            "availability": "available", "provider": "dingdong_web",
            "data_source": "network_response", "parse_warnings": [],
            "eligible_for_purchase": True,
        }
        self.assertEqual(self.ppr.assign_price_basis(good, True), "direct_public_price")
        # 地址未确认 → limited
        self.assertEqual(self.ppr.assign_price_basis(good, False),
                         "direct_public_price_limited")
        # 规格解析失败 → limited
        no_spec = dict(good, reference_grams=None,
                       parse_warnings=["PACKAGE_WEIGHT_UNRESOLVED"])
        self.assertEqual(self.ppr.assign_price_basis(no_spec, True),
                         "direct_public_price_limited")
        # 无价格 → 拒绝赋值
        with self.assertRaises(ValueError):
            self.ppr.assign_price_basis(dict(good, listed_price_yuan=None), True)

    def test_ordinary_payable_price(self):
        member_only = {"listed_price_yuan": 3.99, "price_type": "member",
                       "member_price_yuan": 3.99, "regular_price_yuan": None}
        self.assertIsNone(self.ppr.ordinary_payable_price(member_only))
        regular = {"regular_price_yuan": 4.29, "price_type": "regular"}
        self.assertEqual(self.ppr.ordinary_payable_price(regular), 4.29)

    def test_snapshot_meta_builder(self):
        batch = json.loads(_read("data/golden/price-result-sample.json"))
        meta = self.ppr.build_price_snapshot_meta(batch, "sha256:x", "0.1.0")
        # 契约 1.2（round48）：配送会话确认字段替代地址字段
        for field in ("provider", "provider_version", "result_schema_version",
                      "delivery_context_confirmed_by_user", "observed_at",
                      "source_mode", "request_id", "result_hash"):
            self.assertIn(field, meta, field)


class TestPerfBaseline(unittest.TestCase):
    def test_price_gate_node_documented(self):
        src = _read("scripts/perf_baseline.py")
        self.assertIn("price_gate_validate", src)
        self.assertIn("login_wait_ms", src)  # 用户等待与自动执行分开的口径说明

    def test_pipeline_components_include_price_scripts(self):
        import render_plan
        for comp in ("scripts/price_result_validator.py",
                     "scripts/price_provider_router.py"):
            self.assertIn(comp, render_plan.PIPELINE_COMPONENTS)


if __name__ == "__main__":
    unittest.main()
