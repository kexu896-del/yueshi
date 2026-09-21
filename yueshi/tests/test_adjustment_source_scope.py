# -*- coding: utf-8 -*-
# round 38：调整来源只允许 locked_basket / inventory / approved_substitution
import os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import nutrition_adjuster as na


def _ctx(**kw):
    ctx = {"locked_basket": ["虾", "鸡蛋（全蛋）", "白米饭（熟）"],
           "inventory": ["全脂牛奶"], "approved_substitutions": ["鳕鱼"],
           "mode": "balanced", "meal_types": {"lunch", "dinner"}}
    ctx.update(kw)
    return ctx


def test_unknown_ingredient_excluded():
    cands = na.filter_candidates(na.load_options(), _ctx())
    ids = {o["ingredient_id"] for o in cands}
    allowed = {"虾", "鸡蛋（全蛋）", "白米饭（熟）", "全脂牛奶", "鳕鱼"}
    assert ids <= allowed, ids - allowed
    assert "牛油果" not in ids  # 不在任何来源范围内


def test_scope_membership_respected():
    # 鳕鱼的候选 scope 含 approved_substitution，且在批准平替中 → 可用
    cands = na.filter_candidates(na.load_options(), _ctx())
    assert any(o["ingredient_id"] == "鳕鱼" for o in cands)
    # 从批准平替移除后 → 鳕鱼候选被剔除
    cands2 = na.filter_candidates(na.load_options(), _ctx(approved_substitutions=[]))
    assert not any(o["ingredient_id"] == "鳕鱼" for o in cands2)


def test_mode_and_meal_filter():
    # keto 模式：hormone_only 候选（如牛奶 increase）不适用
    cands = na.filter_candidates(na.load_options(), _ctx(mode="keto"))
    assert not any(o["adjustment_id"] == "protein_energy_milk_250ml" for o in cands)
    # 早餐餐次上下文：只留适用于 breakfast 的候选
    cands = na.filter_candidates(na.load_options(), _ctx(meal_types={"breakfast"}))
    assert all("breakfast" in o["suitable_meals"] for o in cands)


def test_disabled_candidates_filtered():
    opts = na.load_options()
    for o in opts:
        if o["ingredient_id"] == "虾":
            o["enabled"] = False
    cands = na.filter_candidates(opts, _ctx())
    assert not any(o["ingredient_id"] == "虾" for o in cands)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
