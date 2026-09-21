#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成结构化快手早餐模板库 data/breakfast-templates.json（round62 第三优先）。

模板食材与克数在此文件维护；营养值一律由 data/foods-table.json 实时计算写入，
**禁止手填营养数字**（无foods-table条目的食材直接失败，不允许估算）。

模板字段：活跃操作时间 / 总时间 / 是否适合工作日 / 是否可提前准备 /
食材和克数 / 营养数据 / 采购归属 / 替换规则。
"""
import collections
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# (id, 名称, 类别, 活跃分钟, 总分钟, 适合工作日, 可前夜准备, [(食材, 克数)], [替换规则])
TEMPLATES = [
    ("bt-nocook-01", "酸奶燕麦杯", "无需烹饪组合", 3, 3, True, True,
     [("无糖希腊酸奶", 200), ("燕麦片（生）", 30), ("香蕉", 80), ("核桃", 10)],
     ["希腊酸奶 ↔ 无糖酸奶（普通）", "香蕉 ↔ 苹果", "核桃 ↔ 无糖花生酱 10g"]),
    ("bt-nocook-02", "牛奶燕麦香蕉碗", "无需烹饪组合", 3, 5, True, False,
     [("全脂牛奶", 250), ("燕麦片（生）", 40), ("香蕉", 100)],
     ["全脂牛奶 ↔ 无糖豆浆", "香蕉 ↔ 蓝莓 60g"]),
    ("bt-nocook-03", "牛油果全麦吐司", "无需烹饪组合", 5, 5, True, False,
     [("全麦面包", 60), ("牛油果", 70), ["鸡蛋（全蛋）", 55]],
     ["牛油果 ↔ 无糖花生酱 15g", "鸡蛋 ↔ 切达奶酪 20g"]),
    ("bt-asm5-01", "奶酪鸡蛋三明治", "5分钟组装", 5, 5, True, False,
     [("全麦面包", 60), ("切达奶酪", 20), ("鸡蛋（全蛋）", 55), ("黄瓜", 60)],
     ["切达奶酪 ↔ 牛油果 50g", "黄瓜 ↔ 番茄 80g"]),
    ("bt-asm5-02", "豆浆燕麦坚果杯", "5分钟组装", 4, 4, True, True,
     [("无糖豆浆", 300), ("燕麦片（生）", 35), ("核桃", 10), ("黑芝麻", 5)],
     ["无糖豆浆 ↔ 全脂牛奶", "核桃 ↔ 南瓜籽 10g"]),
    ("bt-pan10-01", "番茄炒蛋配全麦面包", "10分钟平底锅", 8, 10, True, False,
     [("鸡蛋（全蛋）", 110), ("番茄", 150), ("全麦面包", 50), ("特级初榨橄榄油", 5)],
     ["番茄 ↔ 黄瓜 100g", "全麦面包 ↔ 蒸红薯 120g"]),
    ("bt-pan10-02", "黄瓜炒蛋配玉米", "10分钟平底锅", 8, 10, True, False,
     [("鸡蛋（全蛋）", 110), ("黄瓜", 120), ("鲜玉米", 120), ("特级初榨橄榄油", 5)],
     ["鲜玉米 ↔ 全麦面包 50g", "黄瓜 ↔ 番茄 150g"]),
    ("bt-pan10-03", "香煎鸡胸牛油果盘", "10分钟平底锅", 9, 12, True, False,
     [("鸡胸肉", 80), ("牛油果", 60), ("番茄", 100), ("特级初榨橄榄油", 5)],
     ["鸡胸肉 ↔ 水煮蛋 2 枚（前夜准备）"]),
    ("bt-prep-01", "隔夜燕麦杯", "可前夜准备", 5, 5, True, True,
     [("全脂牛奶", 200), ("燕麦片（生）", 40), ("无糖希腊酸奶", 100), ("蓝莓", 50)],
     ["蓝莓 ↔ 香蕉 80g", "希腊酸奶 ↔ 无糖酸奶（普通）"]),
    ("bt-prep-02", "前夜水煮蛋玉米盒", "可前夜准备", 3, 3, True, True,
     [("鸡蛋（全蛋）", 110), ("鲜玉米", 150), ("无糖豆浆", 250)],
     ["鲜玉米 ↔ 蒸山药 120g", "无糖豆浆 ↔ 全脂牛奶 250ml"]),
    ("bt-go-01", "花生酱香蕉卷饼", "可带走", 5, 5, True, False,
     [("全麦面包", 70), ("无糖花生酱", 16), ("香蕉", 80)],
     ["无糖花生酱 ↔ 切达奶酪 20g", "香蕉 ↔ 苹果 100g"]),
    ("bt-go-02", "鸡蛋黄瓜三明治", "可带走", 6, 6, True, True,
     [("全麦面包", 70), ("鸡蛋（全蛋）", 55), ("黄瓜", 60), ("切达奶酪", 15)],
     ["切达奶酪 ↔ 无糖花生酱 12g"]),
    ("bt-nodairy-01", "豆浆燕麦蛋组合", "乳制品替代", 4, 6, True, True,
     [("无糖豆浆", 300), ("燕麦片（生）", 35), ("鸡蛋（全蛋）", 55)],
     ["无糖豆浆 ↔ 燕麦奶（无添加糖）", "燕麦 ↔ 小米（生）25g 煮粥"]),
    ("bt-nodairy-02", "豆浆红薯蛋盘", "乳制品替代", 5, 12, True, True,
     [("无糖豆浆", 300), ("红薯", 150), ("鸡蛋（全蛋）", 55)],
     ["红薯 ↔ 鲜玉米 150g"]),
    ("bt-noegg-01", "豆浆豆腐燕麦碗", "鸡蛋替代", 5, 8, True, False,
     [("无糖豆浆", 250), ("内酯豆腐", 120), ("燕麦片（生）", 35), ("黑芝麻", 5)],
     ["内酯豆腐 ↔ 北豆腐 100g", "黑芝麻 ↔ 核桃 10g"]),
    ("bt-noegg-02", "鸡胸牛油果吐司", "鸡蛋替代", 6, 8, True, True,
     [("鸡胸肉", 70), ("牛油果", 60), ("全麦面包", 60)],
     ["鸡胸肉 ↔ 内酯豆腐 150g", "牛油果 ↔ 无糖花生酱 15g"]),
    ("bt-carb-01", "蒸红薯酸奶盘", "不同碳水组", 3, 15, True, True,
     [("红薯", 180), ("无糖希腊酸奶", 150), ("鸡蛋（全蛋）", 55)],
     ["红薯 ↔ 蒸山药 150g / 鲜玉米 150g / 南瓜 200g"]),
    ("bt-carb-02", "小米粥配蛋", "不同碳水组", 3, 20, True, True,
     [("小米（生）", 30), ("鸡蛋（全蛋）", 55), ("黄瓜", 80)],
     ["小米 ↔ 燕麦片（生）30g", "黄瓜 ↔ 番茄 100g"]),
    ("bt-savory-01", "咸豆浆豆腐脑风", "咸味早餐", 5, 8, True, False,
     [("无糖豆浆", 300), ("内酯豆腐", 150), ("黑芝麻", 5)],
     ["内酯豆腐 ↔ 北豆腐 120g"]),
    ("bt-savory-02", "番茄鸡蛋咸燕麦", "咸味早餐", 8, 10, True, False,
     [("燕麦片（生）", 35), ("鸡蛋（全蛋）", 55), ("番茄", 120), ("特级初榨橄榄油", 3)],
     ["番茄 ↔ 黄瓜 100g"]),
    ("bt-warm-01", "热牛奶燕麦蛋", "温热早餐", 5, 8, True, False,
     [("牛奶（加热）", 250), ("燕麦片（生）", 40), ("鸡蛋（全蛋）", 55)],
     ["牛奶（加热）↔ 无糖豆浆（加热）", "燕麦 ↔ 小米（生）30g"]),
    ("bt-warm-02", "蒸南瓜山药蛋盘", "温热早餐", 5, 15, True, True,
     [("南瓜", 200), ("山药", 100), ("鸡蛋（全蛋）", 55)],
     ["南瓜 ↔ 红薯 150g", "山药 ↔ 鲜玉米 120g"]),
]


def main():
    foods = json.load(open(os.path.join(DATA, "foods-table.json"), encoding="utf-8"))["foods"]
    out = collections.OrderedDict()
    out["version"] = "1.0.0"
    out["说明"] = ("结构化快手早餐模板库（round62）。全部模板语义为 meal_plan_mode=planned + "
                 "preparation_mode=quick_self_prepare，include_in_nutrition / include_in_procurement "
                 "恒为 true（B01/B02：不得因快手降级为 guidance_only）。营养值由 "
                 "scripts/build_breakfast_templates.py 依据 foods-table.json 计算，禁止手填。")
    templates = []
    for tid, name, cat, act, tot, workday, prep, items, subs in TEMPLATES:
        nut = {"net_carbs": 0.0, "protein": 0.0, "fat": 0.0, "kcal": 0.0}
        ings = []
        for food, g in items:
            if food not in foods:
                raise SystemExit(f"breakfast_template_error: {tid} 食材「{food}」不在 foods-table，禁止估算")
            f = foods[food]
            for k in nut:
                nut[k] += f[k] * g / 100
            ings.append({"food": food, "grams": g})
        templates.append(collections.OrderedDict([
            ("template_id", tid), ("name", name), ("category", cat),
            ("meal_plan_mode", "planned"), ("preparation_mode", "quick_self_prepare"),
            ("include_in_nutrition", True), ("include_in_procurement", True),
            ("active_minutes", act), ("total_minutes", tot),
            ("workday_suitable", workday), ("prepare_ahead", prep),
            ("ingredients", ings),
            ("nutrition", {k: round(v, 1) for k, v in nut.items()}),
            ("substitution_rules", subs),
        ]))
    out["templates"] = templates
    path = os.path.join(DATA, "breakfast-templates.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    cats = collections.Counter(t["category"] for t in templates)
    print(f"已生成 {path}：{len(templates)} 个模板，类别覆盖 {dict(cats)}")


if __name__ == "__main__":
    main()
