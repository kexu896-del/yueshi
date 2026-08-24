#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round28：周期协议启用（用户指示取消证据门禁）、01 本周阶段章节、安全筛查保留。"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import render_plan as rp
BASE = os.path.join(HERE, "..")


def test_cycle_protocol_active():
    out = subprocess.run(
        [sys.executable, os.path.join(BASE, "scripts", "macros_calculator.py"),
         "--cycle", "--last-period", "2026-07-31", "--cycle-len", "30"],
        capture_output=True, text=True)
    assert "cycle_confidence: high" in out.stdout, out.stderr
    assert "经前一周" in out.stdout


def test_evidence_gate_removed_but_safety_kept():
    sk = open(os.path.join(BASE, "SKILL.md"), encoding="utf-8").read() + "".join(open(os.path.join(BASE, p), encoding="utf-8").read() for p in ("references/runtime-rules.md", "references/nutrition-routing.md", "references/output-policy.md"))
    assert "external_evidence_reviewed: true`。未完成" not in sk, "旧证据门禁段落应删除"
    assert "方可进入计划计算" in sk and "CHANGELOG" in sk, "周期协议执行口径缺失（round32 起改为『进入计算+安全约束』口径）"
    for kw in ["抗凝药物", "进食障碍史", "妊娠或哺乳期", "BMI < 18.5", "缺铁性贫血服用铁剂不属于禁食禁忌"]:
        assert kw in sk, f"安全筛查缺: {kw}"


def test_stage_overview_section():
    plan = {
        "plan_meta": {"plan_schema_version": "1", "skill_version": "2026-08-24", "runtime_rules_version": "2026-08-24", "nutrition_rules_version": "2026-08-24", "output_policy_version": "2026-08-24", "recipe_manifest_version": "2026-08", "effective_parameters_version": "2026-08-21", "price_data_version": "2026-08-24"},
    "plan": {"date_range": "2026-08-22 至 2026-08-28", "subtitle": "t",
                 "include_recipe_steps": False, "stats": {}},
        "profile": {},
        "stage_overview": {"current": "经前一周（周期第23–29天）", "strategy": "平衡激素 · 12h",
                           "weeks": [{"time": "本周", "stage": "经前一周", "plan": "平衡激素"},
                                     {"time": "下周", "stage": "月经期", "plan": "能量期"},
                                     {"time": "下下周", "stage": "卵泡期", "plan": "能量期"}],
                           "note": "以出血日为准"},
        "shopping": {"items": [{"ingredient": "虾", "category": "肉蛋水产与豆制品",
                                "required_quantity": "300g", "acceptable_package": "300g/袋",
                                "reference_price": "约26元/袋", "substitutes": [],
                                "leftover_action": "0剩余"}], "total": "约 ¥26"},
        "days": [{"label": "周一 8月24日", "window": "进食 07:30–19:30",
                  "meals": [{"time": "19:00", "status": "在家", "name": "晚餐", "dishes": "x"}],
                  "nutrition_line": "n", "advice": ""}],
        "disclaimer": "d",
    }
    html = rp.render_document(plan)
    i_stage = html.find("<h2>本周阶段</h2>")
    assert i_stage > -1 and i_stage < html.find("<h2>采购清单</h2>"), "01 本周阶段在采购清单之前"
    assert "当前周期位置" in html and "下下周" in html
    assert not rp.validate_html(html, plan)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"PASS {f.__name__}")
    print(f"{len(fns)}/{len(fns)} round28 测试通过")
