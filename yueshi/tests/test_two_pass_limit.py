# -*- coding: utf-8 -*-
# round 38：营养计算最多两轮；第二轮只小幅收口；两轮后返回换菜/失败原因
import os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import nutrition_adjuster as na

TARGETS = {"energy_kcal": {"min": 1400, "max": 1700},
           "protein_g": {"floor": 45, "min": 55, "max": 90, "medical_limit": None},
           "net_carbs_g": {"min": 80, "max": 150},
           "fat_g": {"min": 35, "max": 65}, "confidence": "high"}

CTX = {"locked_basket": ["虾", "鸡蛋（全蛋）", "白米饭（熟）", "菠菜", "核桃"],
       "inventory": [], "approved_substitutions": [],
       "mode": "balanced", "meal_types": {"lunch", "dinner"}}


def test_max_rounds_hard_capped():
    try:
        na.adjust_day([], TARGETS, dict(CTX), max_rounds=3)
        raised = False
    except ValueError:
        raised = True
    assert raised, "max_rounds 超过 2 未被拒绝"


def test_at_most_two_rounds_recorded():
    # 候选极少（只有一步菠菜增量）→ 差额无法在两轮内修完 → 必须停在两轮并给出结论
    meals = [{"meal_id": "d1", "meal_type": "dinner",
              "ingredients": [{"ingredient_id": "菠菜", "display_name": "菠菜",
                               "amount": 100.0, "unit": "g", "source": "planned"}]}]
    ctx = dict(CTX, locked_basket=["菠菜"])
    log = na.adjust_day(meals, TARGETS, ctx, date_str="2026-09-02")
    assert len(log["rounds"]) <= 2, len(log["rounds"])
    if not log["passed"]:
        assert log["result"] in ("local_recipe_swap", "failed_safety_violation"), log["result"]
        assert log["reason"]


def test_second_round_small_steps_only():
    meals = [{"meal_id": "d1", "meal_type": "dinner",
              "ingredients": [{"ingredient_id": "白米饭（熟）", "display_name": "白米饭",
                               "amount": 150.0, "unit": "g", "source": "planned"},
                              {"ingredient_id": "菠菜", "display_name": "菠菜",
                               "amount": 200.0, "unit": "g", "source": "planned"}]}]
    log = na.adjust_day(meals, TARGETS, dict(CTX))
    if len(log["rounds"]) == 2:
        r2 = log["rounds"][1]
        counts = {}
        for s in r2["selected_adjustments"]:
            counts[s["adjustment_id"]] = counts.get(s["adjustment_id"], 0) + 1
        assert all(v <= na.ROUND2_STEP_LIMIT for v in counts.values()), counts


def test_no_runtime_search():
    # 调整器全文不得包含网络/搜索调用（来源受控：只用候选表与本地食材表）
    src = open(os.path.join(BASE, "scripts", "nutrition_adjuster.py"), encoding="utf-8").read()
    for banned in ("requests", "urllib", "web_search", "http://", "https://api"):
        assert banned not in src, banned


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
