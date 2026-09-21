# -*- coding: utf-8 -*-
# round 38：统一营养调整候选表 schema 与数据一致性
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

DOC = json.load(open(os.path.join(BASE, "data/nutrition-adjustment-options.json"), encoding="utf-8"))
SCHEMA = json.load(open(os.path.join(BASE, "schemas/nutrition-adjustment-options.schema.json"),
                        encoding="utf-8"))
FOODS = json.load(open(os.path.join(BASE, "data/foods-table.json"), encoding="utf-8"))["foods"]


def test_schema_valid():
    import jsonschema
    jsonschema.validate(DOC, SCHEMA)


def test_header_fields():
    for k in ("schema_version", "data_version", "generated_from_foods_table_version",
              "updated_at", "options"):
        assert k in DOC, k
    assert len(DOC["options"]) >= 15


def test_nutrition_delta_from_foods_table():
    # 所有候选营养增量必须由 foods-table per_100g 数值推算，不得手填
    for o in DOC["options"]:
        f = FOODS[o["ingredient_id"]]
        sign = -1 if o["adjustment_action"] in ("decrease", "remove") else 1
        k = o["increment_value"] / 100.0 * sign
        assert abs(o["nutrition_delta"]["energy_kcal"] - round(f["kcal"] * k, 1)) < 0.11, o["adjustment_id"]
        assert abs(o["nutrition_delta"]["protein_g"] - round(f["protein"] * k, 1)) < 0.11, o["adjustment_id"]
        assert abs(o["nutrition_delta"]["net_carbs_g"] - round(f["net_carbs"] * k, 1)) < 0.11, o["adjustment_id"]
        assert abs(o["nutrition_delta"]["fat_g"] - round(f["fat"] * k, 1)) < 0.11, o["adjustment_id"]


def test_categories_covered():
    for cat in ("protein_low_fat", "protein_energy", "energy_carb", "energy_fat",
                "carb_reduce", "fat_reduce", "energy_reduce", "package_use"):
        assert any(o["adjustment_id"].startswith(cat) for o in DOC["options"]), cat


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
