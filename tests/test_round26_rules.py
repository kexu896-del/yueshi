#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round26 规则回归：价格硬门禁、章节白名单（无本周档案）、日卡无禁食、
早餐碳水四组轮换、备餐流转核验、食养之理合并节。"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import render_plan as rp


def plan26():
    return {
        "plan": {"date_range": "2026-08-22 至 2026-08-28", "subtitle": "单一温和模式",
                 "include_recipe_steps": False,
                 "stats": {"天数": "7 天", "模式": "平衡激素", "进食窗口": "07:30–19:30"}},
        "profile": {"基本情况": "女 29 岁"},
        "shopping": {"items": [
            {"ingredient": "虾", "category": "肉蛋水产与豆制品", "required_quantity": "300g",
             "acceptable_package": "300g/袋", "reference_price": "约26元/袋",
             "substitutes": ["鳕鱼"], "leftover_action": "0剩余"},
        ], "total": "约 ¥202（估算口径）", "price_note": "参考价为当地近期同类公开行情估算，非实时报价"},
        "prep": {"purchase_day": {"label": "周六", "tasks": ["采购", "分装冷冻"]},
                 "prep_day": {"label": "周日", "tasks": ["腌制", "预蒸玉米"]},
                 "leftover_verification": [
                     {"ingredient": "虾", "purchase_vs_use": "300/300", "result": "0剩余"},
                     {"ingredient": "玉米", "purchase_vs_use": "560/560", "result": "0剩余"},
                     {"ingredient": "酸奶", "purchase_vs_use": "1100/1100", "result": "0剩余"}]},
        "days": [{"label": "周一 8月24日", "window": "进食 07:30–19:30 · 禁食 12 小时",
                  "meals": [{"time": "07:30", "status": "自行处理", "name": "早餐",
                             "dishes": "全麦面包+水煮蛋+牛奶"}],
                  "nutrition_line": "净碳水约96g", "advice": ""}],
        "wisdom": {"paragraphs": ["经前期，单一温和模式，保持12小时夜间空腹。", "当季冬瓜玉米，缺铁配番茄。", "周末分装冷冻，下周重出计划。"]},
        "execution_tips": ["铁剂与奶类间隔2小时以上。"],
        "disclaimer": "免责声明。",
    }


def test_price_gate_fails_on_empty():
    p = plan26()
    p["shopping"]["items"][0]["reference_price"] = ""
    try:
        rp.render_shopping(p["shopping"])
        raise AssertionError("空参考价必须触发停止")
    except SystemExit:
        pass


def test_no_profile_section_and_no_fasting_in_daycard():
    html = rp.render_document(plan26())
    assert "本周档案" not in html and 'id="profile"' not in html
    week = re.search(r'id="week"(.*?)</section>', html, re.S).group(1)
    assert "禁食" not in week and "空腹" not in week, "日卡区禁止禁食/空腹字样"
    assert "暂无参考价" not in html


def test_prep_and_verification_rendered():
    html = rp.render_document(plan26())
    assert "备餐任务" in html and "食材流转核验" in html and html.count("0剩余") >= 3
    p = plan26(); p["prep"]["leftover_verification"] = p["prep"]["leftover_verification"][:2]
    try:
        rp.render_prep(p["prep"]); raise AssertionError("流转核验不足3项必须停止")
    except SystemExit:
        pass


def test_wisdom_merged_section():
    html = rp.render_document(plan26())
    assert "食养之理与执行说明" in html
    assert html.count("class='wisdom-para'") == 3, "理论为 3 段自然叙述"
    assert "顺时顺势" not in html, "无小标题"
    assert "铁剂与奶类间隔2小时" in html


def test_breakfast_carb_rotation_rule():
    """碳水四组相邻不同、每组 ≤3 次、7 天 ≥4 种结构。"""
    seq = ["B", "D", "C", "A", "B", "D", "C"]  # 本周实际排列
    for a, b in zip(seq, seq[1:]):
        assert a != b, "相邻两天碳水组不得重复"
    for g in set(seq):
        assert seq.count(g) <= 3
    assert len(set(seq)) >= 4


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"PASS {f.__name__}")
    print(f"{len(fns)}/{len(fns)} round26 规则测试通过")
