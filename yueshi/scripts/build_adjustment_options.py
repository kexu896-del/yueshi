#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 data/foods-table.json 生成统一营养调整候选表（候选数据唯一事实源生成器）。

nutrition_delta 一律由 foods-table 的 per_100g 数值按增量克数计算，禁止手填。
输出：data/nutrition-adjustment-options.json
用法：python scripts/build_adjustment_options.py
"""
import json, os, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# 候选定义（不含营养数值；营养 delta 由 foods-table 计算注入）
# 字段对应《统一营养调整候选表模板》第三节
CANDIDATES = [
    # protein_low_fat：蛋白低、热量只需小幅提高
    dict(adjustment_id="protein_low_fat_shrimp_30g", food="虾", action="increase", inc=30,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=2, max_total=60, pkg="none", struct="compatible", priority=90),
    dict(adjustment_id="protein_low_fat_chicken_breast_30g", food="鸡胸肉", action="increase", inc=30,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain", "muscle_gain"],
         max_steps=2, max_total=60, pkg="none", struct="compatible", priority=88),
    dict(adjustment_id="protein_low_fat_cod_50g", food="鳕鱼", action="increase", inc=50,
         meals=["lunch", "dinner"], scope=["locked_basket", "approved_substitution"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=50, pkg="none", struct="compatible", priority=82),
    # protein_energy：蛋白与热量同时偏低
    dict(adjustment_id="protein_energy_egg_50g", food="鸡蛋（全蛋）", action="increase", inc=50,
         meals=["breakfast", "lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain", "muscle_gain"],
         max_steps=2, max_total=100, pkg="none", struct="compatible", priority=92),
    dict(adjustment_id="protein_energy_beidoufu_100g", food="北豆腐", action="increase", inc=100,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=100, pkg="improves", struct="compatible", priority=85),
    dict(adjustment_id="protein_energy_greek_yogurt_100g", food="无糖希腊酸奶", action="increase", inc=100,
         meals=["breakfast", "snack"], scope=["locked_basket", "inventory"],
         modes=["balanced", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=100, pkg="none", struct="compatible", priority=80),
    dict(adjustment_id="protein_energy_milk_250ml", food="全脂牛奶", action="increase", inc=250,
         meals=["breakfast"], scope=["locked_basket", "inventory"],
         modes=["balanced", "hormone_balance"], goals=["maintain", "muscle_gain"],
         max_steps=1, max_total=250, pkg="none", struct="compatible", priority=70),
    # energy_carb：热量低且碳水仍有空间
    dict(adjustment_id="energy_carb_rice_50g", food="白米饭（熟）", action="increase", inc=50,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "hormone_balance"], goals=["maintain", "muscle_gain"],
         max_steps=1, max_total=50, pkg="none", struct="compatible", priority=75),
    dict(adjustment_id="energy_carb_sweetpotato_100g", food="红薯", action="increase", inc=100,
         meals=["breakfast", "lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "hormone_balance"], goals=["maintain"],
         max_steps=1, max_total=100, pkg="none", struct="compatible", priority=72),
    dict(adjustment_id="energy_carb_corn_50g", food="鲜玉米", action="increase", inc=50,
         meals=["breakfast", "lunch"], scope=["locked_basket", "inventory"],
         modes=["balanced", "hormone_balance"], goals=["maintain"],
         max_steps=1, max_total=50, pkg="none", struct="compatible", priority=68),
    # energy_fat：热量低且脂肪偏低
    dict(adjustment_id="energy_fat_walnut_10g", food="核桃", action="increase", inc=10,
         meals=["breakfast", "snack"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["maintain"],
         max_steps=2, max_total=20, pkg="none", struct="compatible", priority=78),
    dict(adjustment_id="energy_fat_olive_oil_5g", food="特级初榨橄榄油", action="increase", inc=5,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=5, pkg="none", struct="compatible", priority=65),
    dict(adjustment_id="energy_fat_avocado_50g", food="牛油果", action="increase", inc=50,
         meals=["breakfast", "lunch"], scope=["locked_basket", "approved_substitution"],
         modes=["balanced", "keto", "hormone_balance"], goals=["maintain"],
         max_steps=1, max_total=50, pkg="worsens", struct="compatible", priority=55),
    # carb_reduce：净碳水超限（先减份量最大的可调整主食）
    dict(adjustment_id="carb_reduce_rice_50g", food="白米饭（熟）", action="decrease", inc=50,
         meals=["lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=2, max_total=100, pkg="none", struct="compatible", priority=90),
    dict(adjustment_id="carb_reduce_sweetpotato_100g", food="红薯", action="decrease", inc=100,
         meals=["breakfast", "lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=100, pkg="none", struct="compatible", priority=80),
    dict(adjustment_id="carb_reduce_bread_30g", food="全麦面包", action="decrease", inc=30,
         meals=["breakfast"], scope=["locked_basket"],
         modes=["balanced", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=30, pkg="none", struct="compatible", priority=75),
    # fat_reduce：脂肪超限（先减额外油脂/肥肉/坚果）
    dict(adjustment_id="fat_reduce_oil_5g", food="双低菜籽油", action="decrease", inc=5,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss"],
         max_steps=2, max_total=10, pkg="none", struct="compatible", priority=90),
    dict(adjustment_id="fat_reduce_walnut_10g", food="核桃", action="decrease", inc=10,
         meals=["breakfast", "snack"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=10, pkg="none", struct="compatible", priority=78),
    dict(adjustment_id="fat_reduce_porkbelly_30g", food="猪五花（生）", action="decrease", inc=30,
         meals=["lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=30, pkg="none", struct="compatible", priority=85),
    # energy_reduce：总能量超上限
    dict(adjustment_id="energy_reduce_oil_5g", food="双低菜籽油", action="decrease", inc=5,
         meals=["lunch", "dinner"], scope=["locked_basket", "inventory"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=5, pkg="none", struct="compatible", priority=82),
    dict(adjustment_id="energy_reduce_rice_50g", food="白米饭（熟）", action="decrease", inc=50,
         meals=["lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "hormone_balance"], goals=["weight_loss"],
         max_steps=1, max_total=50, pkg="none", struct="compatible", priority=70),
    # package_use：营养合格前提下改善包装利用
    dict(adjustment_id="package_use_beidoufu_100g", food="北豆腐", action="increase", inc=100,
         meals=["lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=100, pkg="improves", struct="compatible", priority=60),
    dict(adjustment_id="package_use_spinach_100g", food="菠菜", action="increase", inc=100,
         meals=["lunch", "dinner"], scope=["locked_basket"],
         modes=["balanced", "keto", "hormone_balance"], goals=["weight_loss", "maintain"],
         max_steps=1, max_total=100, pkg="improves", struct="compatible", priority=62),
]


def build():
    ft = json.load(open(os.path.join(BASE, "data/foods-table.json"), encoding="utf-8"))
    foods = ft["foods"]
    options = []
    for c in CANDIDATES:
        if c["food"] not in foods:
            print(f"[跳过] foods-table 无食材：{c['food']}", file=sys.stderr)
            continue
        f = foods[c["food"]]
        k = c["inc"] / 100.0
        sign = -1 if c["action"] in ("decrease", "remove") else 1
        delta = {"energy_kcal": round(f["kcal"] * k * sign, 1),
                 "protein_g": round(f["protein"] * k * sign, 1),
                 "net_carbs_g": round(f["net_carbs"] * k * sign, 1),
                 "fat_g": round(f["fat"] * k * sign, 1)}
        options.append({
            "adjustment_id": c["adjustment_id"],
            "ingredient_id": c["food"],
            "display_name": c["food"],
            "adjustment_action": c["action"],
            "increment_value": c["inc"],
            "increment_unit": "g",
            "nutrition_delta": delta,
            "suitable_meals": c["meals"],
            "source_scope": c["scope"],
            "mode_tags": c["modes"],
            "goal_tags": c["goals"],
            "restriction_tags": [],
            "max_steps_per_day": c["max_steps"],
            "max_total_change": c["max_total"],
            "package_impact": c["pkg"],
            "meal_structure_impact": c["struct"],
            "requires_recipe_change": False,
            "requires_user_confirmation": False,
            "priority": c["priority"],
            "enabled": True,
            "version": "1.0",
        })
    doc = {"schema_version": "1.0",
           "data_version": "2026-08-24",
           "generated_from_foods_table_version": "references/foods-table.md（per 100g 可食部）",
           "updated_at": "2026-08-24",
           "options": options}
    out = os.path.join(BASE, "data/nutrition-adjustment-options.json")
    json.dump(doc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已生成 {out}（{len(options)} 条候选）")


if __name__ == "__main__":
    build()
