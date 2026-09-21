#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round25 渲染回归：月相单 path、采购品类分组与两列、暂无参考价、
meal grid 结构、rationale/execution_tips 章节、组件黑名单。"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import render_plan as rp


def sample_plan():
    return {
        "plan": {"date_range": "2026-08-22 至 2026-08-28", "subtitle": "测试",
                 "include_recipe_steps": False, "stats": {"天数": "7 天", "模式": "平衡激素", "进食窗口": "07:30–19:30", "预算": "约 ¥231"}},
        "profile": {"基本情况": "女 29 岁"},
        "shopping": {"items": [
            {"ingredient": "虾", "category": "肉蛋水产与豆制品", "required_quantity": "290g",
             "acceptable_package": "300g/袋", "reference_price": "约26元/袋", "substitutes": ["鳕鱼"],
             "leftover_action": "剩余冷冻"},
            {"ingredient": "菠菜", "category": "蔬菜与菌菇", "required_quantity": "330g",
             "acceptable_package": "300g/把", "reference_price": "约 5 元/把", "substitutes": [],
             "leftover_action": "周六日优先吃完"},
        ], "total": "约 ¥31", "price_note": "估算口径"},
        "days": [{"label": "周一 8月24日", "window": "进食 07:30-19:30",
                  "meals": [{"time": "07:30", "status": "自备 · 免煮", "name": "早餐",
                             "dishes": "全麦面包+酸奶", "grams": "约320kcal"}],
                  "nutrition_line": "净碳水约99g", "advice": ""}],
        "wisdom": {"shunshi": "单一温和模式，保持12小时夜间空腹。", "wuwei": "清淡。", "ziran": "当季。"},
        "execution_tips": ["铁剂与奶类间隔2小时。"],
        "disclaimer": "免责声明。",
    }


def test_moon_svg_single_path():
    for illum, waxing in [(0.03, True), (0.25, True), (0.5, True), (0.75, True), (0.97, True),
                          (0.25, False), (0.75, False)]:
        svg = rp._moon_svg(illum, waxing)
        assert svg.count("<path") == 1, f"illum={illum} 亮部必须是单一 path"
        assert svg.count("<ellipse") == 0, "禁止 ellipse 叠加（旧版碎片来源）"
    assert "<path" not in rp._moon_svg(0.01, True)   # 新月无亮部
    assert "<circle" in rp._moon_svg(0.99, True)     # 满月整圆
    # 盈月右亮：外弧 sweep=1；亏月左亮：sweep=0
    assert " 0 0 1 " in rp._moon_svg(0.25, True)
    assert " 0 0 0 " in rp._moon_svg(0.25, False)


def test_shopping_grouping_and_columns():
    html = rp.render_shopping(sample_plan()["shopping"])
    assert 'class="shopping-category"' in html
    assert "肉蛋水产与豆制品" in html and "蔬菜与菌菇" in html
    assert html.find("肉蛋水产与豆制品") < html.find("蔬菜与菌菇"), "按 CATEGORY_ORDER 排序"
    assert "<th>替代</th>" in html and "<th>剩余去向</th>" in html, "替代与剩余去向分两列"
    assert "约26元/袋" in html and "暂无参考价" not in html, "每行必须有价格"
    assert "<td>—</td>" in html, "空替代显示 —"
    assert "平替" not in html


def test_meal_grid_structure():
    html = rp.render_meal_row({"time": "07:30", "status": "在家", "name": "早餐",
                               "dishes": "燕麦粥", "grams": "燕麦35g"}, False)
    assert html.count('class="meal-time"') == 1 and html.count('class="meal-status"') == 1
    assert 'class="grams"' in html, "克数在菜品列内"


def test_rationale_and_tips_rendered():
    html = rp.render_document(sample_plan())
    assert "食养之理与执行说明" in html and "铁剂与奶类间隔2小时" in html
    assert 'id="why"' in html


def test_component_blacklist():
    html = rp.render_document(sample_plan())
    for banned in ["menu_map", "toc-nav", "donut", "ring-chart", "<canvas"]:
        assert banned not in html, f"禁用组件残留: {banned}"
    errs = rp.validate_html(html, sample_plan())
    assert not errs, errs


def test_cafeteria_uses_template_data():
    tpls = {"balanced_standard": {"display": "一荤一半荤两素+米饭",
            "nutrition_estimate": {"net_carbs_g": 32, "protein_g": 18, "fat_g": 14},
            "display_note": "大致区间"}}
    html = rp.render_meal_row({"time": "12:00", "status": "外食", "name": "午餐",
                               "meal_source": "cafeteria", "order_template": "balanced_standard"},
                              False, tpls)
    assert "一荤一半荤两素+米饭" in html and "估算净碳水约32g" in html


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"PASS {f.__name__}")
    print(f"{len(fns)}/{len(fns)} round25 渲染测试通过")
