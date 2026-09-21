#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成家庭版 v0.3 RC2 的 8 组 golden cases（RC2-5）。

输出 data/golden/household/case-NN-*.json（base 计划；含 overrides 的案例另出 *-overrides.json）。
所有案例必须通过 bundle Schema 与 household_reference_validator 跨引用校验。
"""
import json, os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "golden", "household")
os.makedirs(BASE, exist_ok=True)

META = {"build_id": "golden-hh-2026.08", "plan_schema_version": "v0.3-rc2",
        "rules_bundle_hash": "", "skill_version": "g", "runtime_rules_version": "g",
        "nutrition_rules_version": "g", "output_policy_version": "g",
        "recipe_manifest_version": "g", "effective_parameters_version": "g",
        "price_data_version": "g", "generated_at": "2026-08-25T09:00:00Z"}

TARGET_F = {"calories_kcal": 1500, "net_carbs_g": 120, "protein_floor_g": 55, "protein_target_g": 70}
TARGET_M = {"calories_kcal": 2100, "net_carbs_g": 200, "protein_floor_g": 75, "protein_target_g": 95}
TARGET_G = {"calories_kcal": 1600, "net_carbs_g": 150, "protein_floor_g": 60, "protein_target_g": 75}


def member(mid, label, primary, target, **kw):
    m = {"member_id": mid, "display_label": label, "precision_level": "exact",
         "goal": kw.pop("goal", "maintain"), "restrictions": kw.pop("restrictions", []),
         "is_primary": primary, "sex": kw.pop("sex", "f"), "age_years": kw.pop("age", 30),
         "height_cm": kw.pop("h", 165), "weight_kg": kw.pop("w", 55),
         "activity_factor": 1.375, "nutrition_target": target}
    m.update(kw)
    return m


def qty(v, u, g):
    return {"display_value": v, "display_unit": u, "canonical_grams": g, "canonical_basis": "raw"}


GATE_OK = {"same_pot_allowed": True, "separate_before_seasoning": False,
           "separate_cookware_required": False, "cross_contact_risk": "low", "blocking_reasons": []}
GATE_SPLIT = {"same_pot_allowed": False, "separate_before_seasoning": True,
              "separate_cookware_required": True, "cross_contact_risk": "high",
              "blocking_reasons": ["花生过敏"]}

LAYOUT = {"one_ingredient_per_shopping_row": True, "shopping_row_height": "auto",
          "ingredient_word_break": "keep_all", "nutrition_member_block_count_max_pdf": 3,
          "portion_note_max_lines": 2, "visible_font_min_pt": 8.5,
          "no_fixed_row_height": True, "disclaimer_separate": True}

GEN_CHECKS = [{"check_id": c, "status": "pass"} for c in [
    "total_equals_portions_plus_loss", "member_nutrition_uses_member_portions",
    "purchase_matches_household_usage", "one_ingredient_per_shopping_row",
    "ratio_split_confidence_ok", "breakfast_portions_present",
    "portion_method_required", "reuse_dates_match_meals",
    "seasoning_strategy_resolved", "no_internal_terms_in_visible_text",
    "override_merge_consistent", "leftover_destination_resolved",
    "nutrition_transfer_consistent"]]


def meal(mid, parts, portions, method, title="番茄炒蛋+米饭", date="2026-09-01",
         ratios=None, deviation=None, seasoning=None, gate=None, attendance=None):
    m = {"meal_id": mid, "date": date, "meal_type": "dinner", "title": title,
         "household_ingredients": [
             {"ingredient_id": "鸡蛋", "quantity": qty(4, "枚", 200)},
             {"ingredient_id": "番茄", "quantity": qty(2, "个", 300)}],
         "participant_member_ids": parts, "member_portions": portions,
         "portion_method": method}
    if ratios:
        m["portion_ratios"] = ratios
        m["portion_note"] = "按比例盛取"
    if deviation:
        m["portion_deviation"] = deviation
    if seasoning:
        m["seasoning_strategy"] = seasoning
    if gate:
        m["cooking_gate_override"] = gate
    if attendance:
        m["attendance_plan"] = attendance
    return m


def portion(mid, grams):
    return {"member_id": mid,
            "items": [{"ingredient_id": "鸡蛋", "quantity": qty(grams // 2, "g", grams // 2)},
                      {"ingredient_id": "番茄", "quantity": qty(grams - grams // 2, "g", grams - grams // 2)}]}


def ratios(spec):
    return [{"member_id": mid, "pct_min": lo, "pct_max": hi, "selected_pct": sel}
            for mid, lo, hi, sel in spec]


DEV = {"allowed": True, "expected_range_pct": 10, "reason": "手工盛取误差",
       "affects_nutrition_confidence": True}

SHOPPING = [{"ingredient_id": "鸡蛋", "household_required_amount": qty(14, "枚", 700),
             "recommended_package": "10枚/盒 ×1", "price_basis": "direct_public_price",
             "new_purchase_cost": 12.0}]


def plan(mode, members, meals, **kw):
    p = {"plan_meta": dict(META, build_id=kw.pop("build_id", META["build_id"])),
         "plan_mode": mode, "members": members, "shared_meals": meals,
         "shopping": SHOPPING, "household_default_cooking_gate": kw.pop("gate", GATE_OK),
         "household_validation": {"checks": [dict(c) for c in GEN_CHECKS]},
         "household_layout_gate": dict(LAYOUT)}
    p.update(kw)
    return p


def save(name, doc):
    json.dump(doc, open(os.path.join(BASE, name), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("生成", name)


def build():
    A = member("m_a", "减重份", True, TARGET_F, goal="weight_loss")
    B = member("m_b", "维持份", False, TARGET_M, sex="m", age=32, h=176, w=72)
    C = member("m_c", "调理份", False, TARGET_G, goal="health_conditioning", age=28, w=58)

    # 1 双人同量
    save("case-01-two-equal.base.json",
         plan("shared_uniform", [A, B],
              [meal("d1", ["m_a", "m_b"], [portion("m_a", 250), portion("m_b", 250)], "equal_split")],
              build_id="golden-hh-01"))
    # 2 双人不同量（ratio_split 60/40）
    save("case-02-two-ratio.base.json",
         plan("shared_meal_personalized", [A, B],
              [meal("d1", ["m_a", "m_b"], [portion("m_a", 300), portion("m_b", 200)],
                    "ratio_split", ratios=ratios([("m_a", 55, 65, 60), ("m_b", 35, 45, 40)]),
                    deviation=dict(DEV))],
              build_id="golden-hh-02"))
    # 3 三人不同量（Σmin≤100≤Σmax，selected=100）
    save("case-03-three-ratio.base.json",
         plan("shared_meal_personalized", [A, B, C],
              [meal("d1", ["m_a", "m_b", "m_c"],
                    [portion("m_a", 250), portion("m_b", 300), portion("m_c", 200)],
                    "ratio_split",
                    ratios=ratios([("m_a", 30, 40, 33), ("m_b", 35, 45, 40), ("m_c", 22, 32, 27)]),
                    deviation=dict(DEV))],
              build_id="golden-hh-03"))
    # 4 安全分锅（L3 + gate 覆盖 + split_safety_required）
    l3 = {"level": "L3_separate", "shared_base_profile": "light",
          "separate_reason": "m_b 花生过敏，交叉接触风险高", "affects_member_nutrition": False}
    Bx = member("m_b", "维持份", False, TARGET_M, sex="m", age=32, h=176, w=72,
                restrictions=["花生过敏"])
    save("case-04-safety-split.base.json",
         plan("split_safety_required", [A, Bx],
              [meal("d1", ["m_a", "m_b"], [portion("m_a", 250), portion("m_b", 250)],
                    "separate_cookware", seasoning=l3, gate=dict(GATE_SPLIT))],
              build_id="golden-hh-04", gate=dict(GATE_SPLIT)))
    # 5 采购前缺席（absent + before_shopping + shopping_delta reduce_purchase）
    base5 = plan("shared_meal_personalized", [A, B],
                 [meal("d1", ["m_a", "m_b"], [portion("m_a", 250), portion("m_b", 250)],
                       "equal_split")],
                 build_id="golden-hh-05")
    save("case-05-absent-before-shopping.base.json", base5)
    save("case-05-absent-before-shopping.overrides.json",
         {"base_build_id": "golden-hh-05", "override_batch_id": "ov-05",
          "overrides": [{"override_id": "ov-05-1", "date": "2026-09-01", "meal_id": "d1",
                         "member_id": "m_b", "status": "absent", "known_at": "before_shopping",
                         "action": "reduce_batch",
                         "shopping_delta": [{"ingredient_id": "鸡蛋", "direction": "reduce",
                                             "grams": 100, "destination": "reduce_purchase"}]}]})
    # 6 采购后外食（external_meal + after_shopping：无 action/leftover/delta）
    save("case-06-external-after-shopping.base.json",
         plan("shared_uniform", [A, B],
              [meal("d1", ["m_a", "m_b"], [portion("m_a", 250), portion("m_b", 250)], "equal_split")],
              build_id="golden-hh-06"))
    save("case-06-external-after-shopping.overrides.json",
         {"base_build_id": "golden-hh-06", "override_batch_id": "ov-06",
          "overrides": [{"override_id": "ov-06-1", "date": "2026-09-01", "meal_id": "d1",
                         "member_id": "m_a", "status": "external_meal",
                         "known_at": "after_shopping"}]})
    # 7 uncertain 关闭（base 悬置 + present_confirmed）
    base7 = plan("shared_meal_personalized", [A, B],
                 [meal("d1", ["m_a", "m_b"], [portion("m_a", 250), portion("m_b", 250)],
                       "equal_split", attendance={"m_a": "expected", "m_b": "uncertain"})],
                 build_id="golden-hh-07")
    save("case-07-uncertain-close.base.json", base7)
    save("case-07-uncertain-close.overrides.json",
         {"base_build_id": "golden-hh-07", "override_batch_id": "ov-07",
          "overrides": [{"override_id": "ov-07-1", "date": "2026-09-01", "meal_id": "d1",
                         "member_id": "m_b", "status": "present_confirmed",
                         "known_at": "before_cooking"}],
          "pending_resolutions": [{"resolution_id": "pr-07-1", "meal_id": "d1",
                                   "member_id": "m_b", "deadline": "2026-09-01T12:00:00Z",
                                   "auto_resolve": "keep_plan", "status": "resolved"}]})
    # 8 三人缺席重分配（一人 absent；合并器负责重归一，此处校验 base+override 合法）
    save("case-08-three-absent-redistribute.base.json",
         plan("shared_meal_personalized", [A, B, C],
              [meal("d1", ["m_a", "m_b", "m_c"],
                    [portion("m_a", 250), portion("m_b", 300), portion("m_c", 200)],
                    "ratio_split",
                    ratios=ratios([("m_a", 30, 40, 33), ("m_b", 35, 45, 40), ("m_c", 22, 32, 27)]),
                    deviation=dict(DEV))],
              build_id="golden-hh-08"))
    save("case-08-three-absent-redistribute.overrides.json",
         {"base_build_id": "golden-hh-08", "override_batch_id": "ov-08",
          "overrides": [{"override_id": "ov-08-1", "date": "2026-09-01", "meal_id": "d1",
                         "member_id": "m_c", "status": "absent", "known_at": "before_cooking",
                         "action": "keep_batch_for_leftover"}]})


if __name__ == "__main__":
    build()
