#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round49：回传链路与 Provider 结果缺失路由（发布失败评审 §七）。

覆盖：
1. SKILL.md 含回传链路说明（月食生成清单 → 用户本机查价 → 上传回对话）；
2. 结果缺失路由：未上传有效结果不得声称已取得叮咚直采价；
   强制实时价 → user_input_required；价格失败只回退价格层；
3. Provider 返回字段不含具体收货地址；
4. policy §4.1 存在且与 SKILL 摘要一致；
5. 路由函数行为：unavailable/invalid_result 降级不判 fatal（回归）。
"""
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))


def _read(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


class TestHandoffText(unittest.TestCase):
    def setUp(self):
        self.skill = _read("SKILL.md")
        self.policy = _read("references/price-provider-policy.md")

    def test_handoff_chain_documented(self):
        # round57：SKILL 只保留清单生成点；回传链路与结果文件名完整表述在 policy
        self.assertIn("月食-查价清单.json", self.skill)
        for needle in ("月食-叮咚价格结果.json", "上传回对话", "没有自动上传通道"):
            self.assertIn(needle, self.policy, needle)

    def test_missing_result_routing(self):
        self.assertIn("user_input_required", self.skill)
        self.assertIn("结果缺失路由", self.policy)
        self.assertIn("不得声称已取得叮咚直采价", self.policy)

    def test_price_failure_price_layer_only(self):
        # round57：失败回退完整表述移至 policy
        self.assertIn("价格失败只回退价格层", self.policy)
        self.assertIn("不重新执行食材预选、菜单装配和营养全流程", self.policy)

    def test_no_address_return(self):
        # round57：地址边界完整表述移至 policy（不读取、不保存、不验证具体收货地址）
        self.assertIn("不读取、不保存、不验证具体收货地址", self.policy)
        self.assertIn("delivery_context_confirmed_by_user", self.policy)


class TestRouterBehavior(unittest.TestCase):
    def setUp(self):
        import price_provider_router as ppr
        self.ppr = ppr

    def test_missing_result_never_fatal(self):
        # 结果缺失/损坏对应 unavailable / invalid_result：降级，不判 fatal
        for status in ("unavailable", "invalid_result"):
            mapped = self.ppr.map_provider_status(status)
            self.assertEqual(mapped["gate_result"], "auto_fix")
            self.assertEqual(mapped["fallback"], "category_estimate")
        # 用户强制实时价 + 需操作 → user_input_required
        mapped = self.ppr.map_provider_status("user_action_required", True)
        self.assertEqual(mapped["gate_result"], "user_input_required")


if __name__ == "__main__":
    unittest.main()
