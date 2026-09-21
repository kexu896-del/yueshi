# -*- coding: utf-8 -*-
# round 38：调整直接更新 meal.ingredients；禁止旁路字段；冻结后禁止修改
import os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import nutrition_adjuster as na

TARGETS = {"energy_kcal": {"min": 700, "max": 1300},
           "protein_g": {"floor": 40, "min": 55, "max": 90, "medical_limit": None},
           "net_carbs_g": {"min": 60, "max": 140},
           "fat_g": {"min": 20, "max": 55}, "confidence": "high"}

CTX = {"locked_basket": ["虾", "鸡蛋（全蛋）", "白米饭（熟）", "菠菜", "鸡胸肉",
                         "北豆腐", "特级初榨橄榄油"],
       "inventory": [], "approved_substitutions": [],
       "mode": "balanced", "meal_types": {"lunch", "dinner"}}


def _meals_low_protein():
    # 蛋白/能量/脂肪偏低的一天：约 398kcal、蛋白 33.7g、脂肪 2.4g
    return [{"meal_id": "d1", "meal_type": "dinner",
             "ingredients": [{"ingredient_id": "白米饭（熟）", "display_name": "白米饭",
                              "amount": 200.0, "unit": "g", "source": "planned"},
                             {"ingredient_id": "菠菜", "display_name": "菠菜",
                              "amount": 200.0, "unit": "g", "source": "planned"},
                             {"ingredient_id": "鸡胸肉", "display_name": "鸡胸肉",
                              "amount": 100.0, "unit": "g", "source": "planned"}]}]


def test_gap_vector_complete():
    gap = na.compute_gap({"energy_kcal": 500, "protein_g": 20, "net_carbs_g": 90,
                          "fat_g": 10}, TARGETS)
    for m in ("energy_kcal", "protein_g", "net_carbs_g", "fat_g"):
        assert m in gap, m
    assert gap["adjustment_required"] is True
    assert gap["protein_g"]["delta_to_target"] > 0  # 低于下限记正数


def test_adjustment_updates_meal_ingredients():
    meals = _meals_low_protein()
    log = na.adjust_day(meals, TARGETS, dict(CTX), date_str="2026-09-01")
    all_ids = [ing["ingredient_id"] for m in meals for ing in m["ingredients"]]
    # 蛋白缺口应通过虾/鸡蛋增量收口
    assert "虾" in all_ids or "鸡蛋（全蛋）" in all_ids
    assert log["passed"] is True
    # 就地更新：带 adjustment_reason 标记
    changed = [ing for m in meals for ing in m["ingredients"] if ing.get("adjustment_reason")]
    assert changed, "meal.ingredients 未被更新"
    # 禁止旁路字段
    for m in meals:
        for banned in ("extra_foods", "render_ingredients", "protein_additions", "calorie_additions"):
            assert banned not in m, banned


def test_no_adjustment_when_in_band():
    meals = [{"meal_id": "d1", "meal_type": "dinner",
              "ingredients": [{"ingredient_id": "白米饭（熟）", "display_name": "白米饭",
                               "amount": 300.0, "unit": "g", "source": "planned"},
                              {"ingredient_id": "鸡胸肉", "display_name": "鸡胸肉",
                               "amount": 250.0, "unit": "g", "source": "planned"},
                              {"ingredient_id": "双低菜籽油", "display_name": "菜籽油",
                               "amount": 30.0, "unit": "g", "source": "planned"},
                              {"ingredient_id": "鸡蛋（全蛋）", "display_name": "鸡蛋",
                               "amount": 150.0, "unit": "g", "source": "planned"}]}]
    before = [[dict(i) for i in m["ingredients"]] for m in meals]
    log = na.adjust_day(meals, TARGETS, dict(CTX))
    assert log["result"] == "no_adjustment_needed" and log["passed"] is True
    assert meals[0]["ingredients"] == before[0]  # 达标时不得新增或改动食材行


def test_frozen_plan_rejected():
    meals = _meals_low_protein()
    ctx = dict(CTX, frozen=True)
    try:
        na.adjust_day(meals, TARGETS, ctx)
        raised = False
    except SystemExit:
        raised = True
    assert raised, "冻结后仍允许调整"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
