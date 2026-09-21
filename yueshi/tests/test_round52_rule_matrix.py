#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round52：通用食材库与匹配质量分层（两份改进方案）。

覆盖：
1. data/product-form-dictionary.json 主库结构（版本、否定前缀、restrictive 标记）；
2. data/ingredient-catalog.json 有 catalog_version，上海青/鸡腿/鸡蛋有 query_profile；
3. price-query / price-result 契约增补字段存在且向后兼容（golden 样例仍通过校验）；
4. 词典与 helper 快照一致性声明（FORM_DICTIONARY_VERSION 见 CHANGELOG/policy）；
5. CHANGELOG 最新条目以「用户指示」开头（既有门禁口径回归）。
"""
import json
import os
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import jsonschema  # noqa: E402


def _load(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return json.load(f)


def _read(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


class TestFormDictionary(unittest.TestCase):
    def setUp(self):
        self.dic = _load("data/product-form-dictionary.json")

    def test_version_and_negation(self):
        self.assertEqual(self.dic["form_dictionary_version"], "1.4.0")
        for neg in ("免", "无", "未"):
            self.assertIn(neg, self.dic["negation_prefixes"])

    def test_required_forms_present(self):
        forms = self.dic["forms"]
        for form in ("diced", "cut_pieces", "marinated", "cooked",
                     "whole_leg", "drumstick", "whole", "filled", "ball"):
            self.assertIn(form, forms, form)
            self.assertTrue(forms[form]["keywords"], form)
            self.assertIn("restrictive", forms[form], form)

    def test_cut_pieces_restrictive(self):
        # 「块」必须限制性且不得自动等同整腿（方案 §四）
        self.assertTrue(self.dic["forms"]["cut_pieces"]["restrictive"])
        self.assertIn("块", self.dic["forms"]["cut_pieces"]["keywords"])


class TestCatalogProfiles(unittest.TestCase):
    def setUp(self):
        self.cat = _load("data/ingredient-catalog.json")

    def test_catalog_version(self):
        self.assertEqual(self.cat["catalog_version"], "1.6.0")

    def test_query_profiles(self):
        for name in ("上海青", "鸡腿", "鸡蛋"):
            prof = self.cat["items"][name].get("query_profile")
            self.assertIsNotNone(prof, name)
            for key in ("primary_query", "exact_terms", "aliases",
                        "broad_terms", "category_substitution_allowed"):
                self.assertIn(key, prof, f"{name}.{key}")
        # 上海青：宽泛「青菜」只能在 broad_terms，不得混入 exact/aliases
        prof = self.cat["items"]["上海青"]["query_profile"]
        self.assertIn("青菜", prof["broad_terms"])
        self.assertNotIn("青菜", prof["exact_terms"])
        self.assertNotIn("青菜", prof["aliases"])
        # 鸡腿：allowed_forms 只含整件形态
        self.assertEqual(
            set(self.cat["items"]["鸡腿"]["query_profile"]["allowed_forms"]),
            {"whole_leg", "drumstick"})


class TestContractAdditions(unittest.TestCase):
    def test_query_schema_new_fields(self):
        schema = _load("schemas/price-query.schema.json")
        root_props = schema["properties"]
        self.assertIn("catalog_version", root_props)
        self.assertIn("form_dictionary_version", root_props)
        item_props = schema["definitions"]["query_item"]["properties"]
        for key in ("exact_terms", "broad_terms",
                    "category_substitution_allowed"):
            self.assertIn(key, item_props, key)

    def test_result_schema_new_fields(self):
        schema = _load("schemas/price-result.schema.json")
        root_props = schema["properties"]
        self.assertIn("catalog_version", root_props)
        cand_props = schema["definitions"]["product_candidate"]["properties"]
        for key in ("match_quality", "product_form", "form_match"):
            self.assertIn(key, cand_props, key)
        result_props = schema["definitions"]["query_result"]["properties"]
        for key in ("substitution_notice", "dictionary_suggestions"):
            self.assertIn(key, result_props, key)
        sug_props = schema["definitions"]["suggested_purchase"]["properties"]
        for key in ("total_count_text", "package_text", "match_quality"):
            self.assertIn(key, sug_props, key)
        # 结果瘦身：候选不再必填 observed_at / data_source
        required = schema["definitions"]["product_candidate"]["required"]
        self.assertNotIn("observed_at", required)
        self.assertNotIn("data_source", required)

    def test_match_quality_enum(self):
        schema = _load("schemas/price-result.schema.json")
        enum = schema["definitions"]["product_candidate"][
            "properties"]["match_quality"]["enum"]
        for q in ("exact", "alias", "category_fallback", "low_confidence"):
            self.assertIn(q, enum)

    def test_golden_samples_still_valid(self):
        """向后兼容：既有 golden 样例在新契约下仍通过校验。"""
        query_schema = _load("schemas/price-query.schema.json")
        result_schema = _load("schemas/price-result.schema.json")
        sample_q = _load("data/golden/price-query-sample.json")
        sample_r = _load("data/golden/price-result-sample.json")
        jsonschema.validate(sample_q, query_schema)
        jsonschema.validate(sample_r, result_schema)

    def test_new_fields_accepted(self):
        """新字段的完整样例通过校验（匹配质量 + 替代提示 + 枚数）。"""
        result_schema = _load("schemas/price-result.schema.json")
        sample = _load("data/golden/price-result-sample.json")
        sample["catalog_version"] = "1.1.0"
        sample["form_dictionary_version"] = "1.1.0"
        ok = next(r for r in sample["results"] if r["status"] == "success")
        if ok["candidates"]:
            ok["candidates"][0]["match_quality"] = "category_fallback"
            ok["candidates"][0]["product_form"] = "fresh"
            ok["candidates"][0]["form_match"] = "acceptable"
        ok["substitution_notice"] = "同类候选，非精确命中"
        ok["dictionary_suggestions"] = [{
            "ingredient_id": ok["ingredient_id"],
            "type": "new_alias", "value": "青菜",
            "evidence_count": 2, "example_products": ["高原青菜 500g"]}]
        if ok.get("suggested_purchase"):
            ok["suggested_purchase"]["total_count_text"] = "12枚"
            ok["suggested_purchase"]["package_text"] = "660g"
            ok["suggested_purchase"]["match_quality"] = "exact"
        jsonschema.validate(sample, result_schema)


class TestDocsConsistency(unittest.TestCase):
    def test_policy_mentions_round52(self):
        policy = _read("references/price-provider-policy.md")
        for needle in ("category_fallback", "substitution_notice",
                       "dictionary_suggestions", "change_reason",
                       "form_dictionary_version"):
            self.assertIn(needle, policy, needle)

    def test_changelog_latest_entry(self):
        head = _read("CHANGELOG.md")
        latest = [ln for ln in head.splitlines() if ln.startswith("## ")][0]
        self.assertTrue(latest.startswith("## 用户指示"), latest)
        self.assertIn("round ", latest)
        # round 52 条目必须仍在历史记录中
        self.assertIn("round 52", head)


if __name__ == "__main__":
    unittest.main()
