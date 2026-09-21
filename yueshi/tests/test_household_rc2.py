# -*- coding: utf-8 -*-
# round 40：家庭版 v0.3 RC2 —— schemas 入库 / 校验器 / 8 组 golden cases / 冻结前 11 项清单
import copy, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import jsonschema
import household_reference_validator as hv

BUNDLE = json.load(open(os.path.join(BASE, "schemas/household/household-schemas.bundle.json"),
                        encoding="utf-8"))
GOLD = os.path.join(BASE, "data/golden/household")


def load(n):
    return json.load(open(os.path.join(GOLD, n), encoding="utf-8"))


def _case(n):
    base = load(f"{n}.base.json")
    ovf = os.path.join(GOLD, f"{n}.overrides.json")
    return base, (json.load(open(ovf, encoding="utf-8")) if os.path.exists(ovf) else None)


CASES = ["case-01-two-equal", "case-02-two-ratio", "case-03-three-ratio",
         "case-04-safety-split", "case-05-absent-before-shopping",
         "case-06-external-after-shopping", "case-07-uncertain-close",
         "case-08-three-absent-redistribute"]


def test_eight_golden_cases_pass():
    for n in CASES:
        base, ov = _case(n)
        jsonschema.validate(base, BUNDLE["base_plan"])
        if ov:
            jsonschema.validate(ov, BUNDLE["overrides"])
        rep = hv.validate_base(base, ov)
        assert not rep.failed, (n, rep.failed)


def test_simple_meal_without_seasoning_passes():
    # 清单 1：省略 seasoning_strategy 的简单餐可过
    base, _ = _case("case-01-two-equal")
    assert "seasoning_strategy" not in base["shared_meals"][0]
    jsonschema.validate(base, BUNDLE["base_plan"])


def test_l3_requires_gate_consistency():
    # 清单 1b：L3 必须有 cooking_gate_override（schema）且 gate 满足分锅条件（脚本）
    base, _ = _case("case-04-safety-split")
    bad = copy.deepcopy(base)
    del bad["shared_meals"][0]["cooking_gate_override"]
    try:
        jsonschema.validate(bad, BUNDLE["base_plan"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "L3 缺 cooking_gate_override 未被 schema 拦截"
    bad2 = copy.deepcopy(base)
    bad2["shared_meals"][0]["cooking_gate_override"]["same_pot_allowed"] = True
    bad2["shared_meals"][0]["cooking_gate_override"]["separate_cookware_required"] = False
    rep = hv.validate_base(bad2)
    assert rep.failed, "L3 gate 不一致未被脚本拦截"


def test_selected_pct_sum_100():
    # 清单 2：三人比例 selected_pct 合计必须严格 100
    base, _ = _case("case-03-three-ratio")
    bad = copy.deepcopy(base)
    bad["shared_meals"][0]["portion_ratios"][0]["selected_pct"] = 30
    rep = hv.validate_base(bad)
    assert any(r["check_id"] == "SELECTED_PCT_SUM_EQUALS_100" and r["status"] == "fail"
               for r in rep.results)


def test_base_rejects_effective_fields():
    # 清单 3：base 出现 effective_meta / overrides 字段即失败
    base, _ = _case("case-01-two-equal")
    for k in ("effective_meta", "attendance_overrides"):
        bad = copy.deepcopy(base)
        bad[k] = {}
        try:
            jsonschema.validate(bad, BUNDLE["base_plan"])
            raised = False
        except jsonschema.ValidationError:
            raised = True
        assert raised, k


def test_override_status_branches():
    # 清单 4：absent 必填 action；present_confirmed 禁止 action/shopping_delta
    _, ov5 = _case("case-05-absent-before-shopping")
    bad = copy.deepcopy(ov5)
    del bad["overrides"][0]["action"]
    try:
        jsonschema.validate(bad, BUNDLE["overrides"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "absent 缺 action 未被拦截"
    _, ov7 = _case("case-07-uncertain-close")
    bad2 = copy.deepcopy(ov7)
    bad2["overrides"][0]["action"] = "reduce_batch"
    try:
        jsonschema.validate(bad2, BUNDLE["overrides"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "present_confirmed 带 action 未被拦截"


def test_canonical_single_truth():
    # 清单 5：quantity 之外不得出现第二个 canonical_grams（strict schema 报错）
    base, _ = _case("case-01-two-equal")
    bad = copy.deepcopy(base)
    bad["shared_meals"][0]["household_ingredients"][0]["canonical_grams"] = 200
    try:
        jsonschema.validate(bad, BUNDLE["base_plan"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "ingredient_amount 出现游离 canonical_grams 未被拦截"


def test_not_participating_excluded():
    # 清单 6：not_participating 不得进入 participants / member_portions
    base, _ = _case("case-01-two-equal")
    bad = copy.deepcopy(base)
    bad["shared_meals"][0]["attendance_plan"] = {"m_a": "expected", "m_b": "not_participating"}
    rep = hv.validate_base(bad)
    assert any(r["check_id"] == "NOT_PARTICIPATING_EXCLUDED_FROM_PORTIONS"
               and r["status"] == "fail" for r in rep.results)


def test_external_meal_no_leftover():
    # 清单 7：external_meal 禁止 leftover_plan_id；采购后禁止 shopping_delta
    _, ov6 = _case("case-06-external-after-shopping")
    bad = copy.deepcopy(ov6)
    bad["overrides"][0]["leftover_plan_id"] = "lp-1"
    try:
        jsonschema.validate(bad, BUNDLE["overrides"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "external_meal 带 leftover_plan_id 未被拦截"
    bad2 = copy.deepcopy(ov6)
    bad2["overrides"][0]["shopping_delta"] = [{"ingredient_id": "鸡蛋", "direction": "reduce",
                                               "grams": 100, "destination": "reduce_purchase"}]
    try:
        jsonschema.validate(bad2, BUNDLE["overrides"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "after_shopping 的 external_meal 带 shopping_delta 未被拦截"


def test_numeric_bounds_and_unique_ids():
    # 清单 8：负克数与重复成员 ID 均被拦截
    base, _ = _case("case-01-two-equal")
    bad = copy.deepcopy(base)
    bad["shared_meals"][0]["household_ingredients"][0]["quantity"]["canonical_grams"] = -5
    try:
        jsonschema.validate(bad, BUNDLE["base_plan"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised
    bad2 = copy.deepcopy(base)
    bad2["members"].append(dict(bad2["members"][0]))
    try:
        jsonschema.validate(bad2, BUNDLE["base_plan"])  # schema 不查重复 → 脚本查
    except jsonschema.ValidationError:
        pass
    rep = hv.validate_base(bad2)
    assert any(r["check_id"] == "MEMBER_ID_UNIQUE" and r["status"] == "fail" for r in rep.results)


def test_legacy_fields_rejected():
    # 清单 9：旧字段在 strict schema 下报错
    base, _ = _case("case-01-two-equal")
    bad = copy.deepcopy(base)
    bad["members"][0]["portion_ratio"] = 0.6  # v0.3 RC 旧字段
    try:
        jsonschema.validate(bad, BUNDLE["base_plan"])
        raised = False
    except jsonschema.ValidationError:
        raised = True
    assert raised, "旧字段 portion_ratio 未被 strict schema 拦截"


def test_cli_exit_codes(tmp_path=None):
    import subprocess as sp
    ok = sp.run([sys.executable, os.path.join(BASE, "scripts/household_reference_validator.py"),
                 "--base", os.path.join(GOLD, "case-01-two-equal.base.json")],
                capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
