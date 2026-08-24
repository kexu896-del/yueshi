#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采购清单反向汇总脚本（纯标准库）

输入：餐次明细 CSV（由周计划菜单生成）
  列：date, meal, dish, food, grams, unit, storage, kind
  kind 取值：
    fresh      — 当天现做现吃，采购量 = 需要量
    cook_batch — 一次烹饪多份（如晚餐多做为次日便当），grams 填"本次烹饪总量"
    reuse      — 复用餐次（如次日便当吃前晚剩菜），不计入采购
    pantry     — 家中已有库存（油盐米等），不计入采购，仅在库存表列出
输出：按区域分组的采购汇总 + 食材去向核对 + 校验清单

一人食包装规格适配（可选）：
  --packages packages.csv  真实包装规格表（food,package_quantity,unit）
                           提供后按真实规格取整，不再用粗略规则
  --meals-per-day {1,2,3}  每日自炊餐次，用于一人食食材种类数校验
  --csv-out out.csv        导出五字段明细：
                           food, required_quantity, package_quantity,
                           planned_use, expected_leftover, leftover_action

用法：
  python shopping_aggregator.py meals.csv
  python shopping_aggregator.py --menu meals.csv --packages packages.csv \
      --meals-per-day 1 --csv-out plan.csv --budget 300 --budget-period week
"""

import csv
import json
import os
import sys
from collections import OrderedDict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ZONES = OrderedDict([
    ("vegetable", "蔬菜与菌菇｜本周主要提供体积、纤维和天然碳水"),
    ("protein", "肉蛋与豆制品｜按每餐蛋白质目标反向汇总"),
    ("staple", "谷物、薯类与水果｜主要用于平衡激素饮食日"),
    ("oil_nut", "油脂、坚果与调味｜先检查家中库存"),
])

STOCK_CATEGORY = {
    "叶菜": "vegetable", "瓜茄": "vegetable", "菌菇": "vegetable", "海菜": "vegetable",
    "根茎": "staple", "薯类": "staple", "谷物": "staple", "水果": "staple",
    "肉类": "protein", "禽类": "protein", "水产": "protein", "蛋": "protein",
    "豆制品": "protein",
    "油": "oil_nut", "坚果": "oil_nut", "调味": "oil_nut", "饮品": "oil_nut",
}

# 易腐分级（用于余量去向与"至少两顿"校验）
PERISHABLE_SHORT = {"叶菜", "菌菇", "豆制品"}              # 冷藏 2~3 天
PERISHABLE_FRESH = {"肉类", "禽类", "水产"}                # 冷藏 1~2 天，可分装冷冻
SHELF_OK = {"根茎", "薯类", "谷物", "油", "坚果", "调味", "饮品", "蛋", "干货"}

# 一人食核心食材种类上限（调味料与库存不计入；与 SKILL.md 分层表一致）
KIND_LIMITS = {1: (12, 16), 2: (16, 22), 3: (22, 30)}


def rough_pack(g):
    """无真实规格表时的粗略取整规则。"""
    if g <= 50: return (g, "少量")
    if g <= 100: return (100, "小份")
    if g <= 200: return (200, "1份")
    if g <= 300: return (300, "1份")
    if g <= 500: return (500, "1斤装/半斤")
    return (round(g / 500) * 500, "%d斤装" % round(g / 500))


def main():
    import argparse, json, os
    ap = argparse.ArgumentParser(description="采购清单反向汇总")
    ap.add_argument("--selection-report", default=None, help="预选追溯 JSONL：menu_status=not_selected 的食材不得作为采购数据行")
    ap.add_argument("--menu", default=None, help="餐次明细 CSV（date,meal,dish,food,grams,unit,storage,kind,category）")
    ap.add_argument("--inventory", default=None, help="家中库存 CSV（food）")
    ap.add_argument("--prices", default=None, help="本地价格 CSV（food,price_per_unit,unit）")
    ap.add_argument("--packages", default=None, help="包装规格 CSV（food,package_quantity,unit）")
    ap.add_argument("--meals-per-day", type=int, choices=[1, 2, 3], default=None,
                    help="每日自炊餐次（一人食食材种类校验）")
    ap.add_argument("--csv-out", default=None,
                    help="导出五字段明细 CSV（required/package/planned_use/expected_leftover/leftover_action）")
    ap.add_argument("--budget", type=float, default=None, help="预算金额")
    ap.add_argument("--budget-period", choices=["week", "biweek", "month", "28d", "custom"], default=None)
    ap.add_argument("--period-start", default=None, help="YYYY-MM-DD")
    ap.add_argument("--period-end", default=None, help="YYYY-MM-DD")
    ap.add_argument("--flexibility", type=float, default=0.0, help="允许浮动比例（0/0.05/0.1）")
    ap.add_argument("--search-list", default=None,
                    help="导出采购清单 CSV（ingredient, purchase_name, required_quantity, "
                         "acceptable_package, substitutes）；自动读取 data/package-rules.json "
                         "与 data/substitutions.json")
    args = ap.parse_args()
    path = args.menu or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not path:
        ap.print_help()
        return
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    # 预选闭环：未入选食材不得作为采购数据行（只进内部 selection report / 执行提示一行说明）
    excluded = set()
    if args.selection_report and os.path.exists(args.selection_report):
        for line in open(args.selection_report, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("menu_status") == "not_selected":
                excluded.add(rec.get("ingredient"))
    if excluded:
        rows = [r for r in rows if r.get("food", "").strip() not in excluded]
        print(f"预选未入选食材已从采购表移除：{'、'.join(sorted(excluded))}（去向见 selection report）")
    # 库存扣除
    inventory = set()
    if args.inventory:
        for r in csv.DictReader(open(args.inventory, encoding="utf-8-sig")):
            inventory.add(r.get("food", "").strip())
    # 价格表（food, price_per_unit, unit, confidence[可选 high/medium/low]）
    prices = {}
    if args.prices:
        for r in csv.DictReader(open(args.prices, encoding="utf-8-sig")):
            prices[r.get("food", "").strip()] = (float(r.get("price_per_unit", 0)),
                                                 r.get("unit", "500g"),
                                                 (r.get("confidence") or "medium").strip())

    def price_cost(food, purchased_g, pkg_count):
        """预计支出 = 购买包装数 × 单包装价格；散装按购买克数折算。
        置信度 low/unavailable 不进入预算合计（门禁）。返回 (cost, conf) 或 None。"""
        if food not in prices:
            return None
        price, unit, conf = prices[food]
        if conf in ("low", "unavailable"):
            return None
        if unit in ("500g", "斤"):
            return (price * purchased_g / 500.0, conf)
        if unit in ("kg", "公斤"):
            return (price * purchased_g / 1000.0, conf)
        if unit == "g":
            return (price * purchased_g, conf)
        # 计件包装（盒/个/袋/份）：按包装数计
        return (price * pkg_count, conf)
    # 真实包装规格表
    packages = {}
    if args.packages:
        for r in csv.DictReader(open(args.packages, encoding="utf-8-sig")):
            packages[r.get("food", "").strip()] = (float(r.get("package_quantity", 0)),
                                                   r.get("unit", "g"))

    def pack(food, g):
        """返回 (购买量, 规格说明)；优先真实包装规格（向上取整到整包装）。"""
        if food in packages and packages[food][0] > 0:
            pkg = packages[food][0]
            n = 1
            while pkg * n < g:
                n += 1
            unit = packages[food][1] or "g"
            return (pkg * n, f"{pkg:g}{unit}×{n}")
        return rough_pack(g)

    def pack_count(food, g):
        """购买包装数（预算按包装计）。"""
        if food in packages and packages[food][0] > 0:
            pkg = packages[food][0]
            n = 1
            while pkg * n < g:
                n += 1
            return n
        return 1

    # 汇总：food -> {required, sources, dates, storage, zone, category}
    foods = OrderedDict()
    pantry = OrderedDict()
    for r in rows:
        food = r["food"].strip()
        grams = float(r["grams"])
        kind = (r.get("kind") or "fresh").strip()
        if kind == "pantry" or food in inventory:
            pantry[food] = r.get("storage", "")
            continue
        if kind == "reuse":
            if food in foods:
                foods[food]["sources"].append(f"{r['date']} {r['meal']}(复用)")
                foods[food]["dates"].add(r["date"])
            continue
        if food not in foods:
            foods[food] = {"required": 0.0, "sources": [], "dates": set(),
                           "storage": "", "zone": "oil_nut", "category": ""}
        foods[food]["required"] += grams
        foods[food]["sources"].append(f"{r['date']} {r['meal']}")
        foods[food]["dates"].add(r["date"])
        foods[food]["storage"] = r.get("storage", foods[food]["storage"])
        foods[food]["category"] = r.get("category", foods[food]["category"])
        foods[food]["zone"] = STOCK_CATEGORY.get(r.get("category", ""), foods[food]["zone"])

    def leftover_action(food, d, leftover):
        """余量去向建议。"""
        if leftover <= 0:
            return "无剩余"
        cat = d["category"]
        used_days = len(d["dates"])
        if cat in SHELF_OK:
            return f"剩 {leftover:g}g，{d['storage'] or '常温'}储存，下周续用"
        if used_days >= 2:
            return f"剩 {leftover:g}g，并入最后一餐或清库存餐"
        if cat in PERISHABLE_FRESH:
            return f"剩 {leftover:g}g，分装冷冻或 48h 内安排第二餐；无法消耗则改小包装/冷冻品"
        return f"剩 {leftover:g}g，48h 内安排第二餐；无法消耗则改小包装或不选该食材"

    print("【采购汇总（按区域）】")
    total_kinds = 0
    detail_rows = []  # csv-out 用
    for zone, desc in ZONES.items():
        items = [(f, d) for f, d in foods.items() if d["zone"] == zone]
        if not items:
            continue
        print(f"\n■ {desc}")
        for f, d in items:
            p_, pkg = pack(f, d["required"])
            leftover = p_ - d["required"]
            action = leftover_action(f, d, leftover)
            line = (f"  □ {f}｜需 {d['required']:g}g → 买 {p_:g}g（{pkg}）｜{d['storage'] or '常温'}"
                    f"｜{'、'.join(d['sources'][:3])}")
            if leftover > 0:
                line += f"｜余量 {leftover:g}g → {action}"
            print(line)
            total_kinds += 1
            detail_rows.append({
                "food": f,
                "required_quantity": f"{d['required']:g}",
                "package_quantity": f"{p_:g}",
                "planned_use": "、".join(d["sources"]),
                "expected_leftover": f"{leftover:g}",
                "leftover_action": action,
            })
    print(f"\n共 {total_kinds} 种必买食材")

    if pantry:
        print("\n【家中库存（不买）】" + "、".join(pantry.keys()))

    # 一人食种类数校验（调味料/库存不计入；oil_nut 区视为调味不计入核心食材）
    if args.meals_per_day:
        lo, hi = KIND_LIMITS[args.meals_per_day]
        core = sum(1 for d in foods.values() if d["zone"] != "oil_nut")
        perish = sum(1 for d in foods.values()
                     if d["zone"] == "vegetable" and d["category"] in PERISHABLE_SHORT)
        print(f"\n【一人食校验】每日自炊 {args.meals_per_day} 餐 → 核心食材 {core} 种（建议 {lo}~{hi}）"
              f"；易腐鲜菜 {perish} 种（每日1餐建议 4~6）")
        if core > hi:
            print(f"  ✗ 核心食材超出上限 {hi} 种：合并只用一次的配菜，或改为复用现有食材")
        # 易腐食材"至少两顿"反向校验（按餐次事件计；单份现买水产/冷冻品豁免）
        for f, d in foods.items():
            if d["category"] in PERISHABLE_SHORT | PERISHABLE_FRESH and len(d["sources"]) < 2 \
               and d["zone"] != "oil_nut":
                if d["category"] == "水产" and d["required"] <= 200:
                    print(f"  · 水产「{f}」单份 {d['required']:g}g 现买现吃/冷冻保存，允许只出现 1 次")
                    continue
                print(f"  ✗ 易腐食材「{f}」仅安排 {len(d['sources'])} 顿："
                      f"增至 2 顿、改现买现吃单份，或更换食材")

    # 预算结构
    if args.budget:
        print("\n【预算结构】")
        print(f"  预算金额: ¥{args.budget:g}  周期: {args.budget_period or '未指定'}"
              f"  弹性: ±{args.flexibility*100:.0f}%" if args.flexibility else f"  预算金额: ¥{args.budget:g}  周期: {args.budget_period or '未指定'}")
        est_total = 0.0
        unpriced = []
        for f, d in foods.items():
            p_, _ = pack(f, d["required"])
            pc = price_cost(f, p_, pack_count(f, d["required"]))
            if pc is None:
                unpriced.append(f)
            else:
                est_total += pc[0]
        if not prices:
            print("  预算结构已生成，但缺少当地价格数据。")
            print("  请使用用户录入价格或历史购买价格完成金额校验。")
        else:
            est_total = round(est_total, 1)
            print(f"  本周预计采购金额: ¥{est_total}（按购买包装计算，仅计入 high/medium 置信度价格）")
            if unpriced:
                print(f"  未计入（无价格或置信度不足）: {'、'.join(unpriced)}")
            over = est_total > args.budget * (1 + args.flexibility)
            print(f"  状态: {'预计超出' if over else '预算内'}")
            if over:
                print("  建议：替换高价等价食材（三文鱼→鲭鱼、牛里脊→鸡腿/蛋/豆腐、藜麦→糙米等），不得削减蛋白/热量/蔬菜/过敏原底线。")

    print("\n【食材去向核对】")
    for f, d in foods.items():
        print(f"  {f}｜总需 {d['required']:g}g｜{'、'.join(d['sources'])}")

    print("\n【校验】")
    checks = []
    for f, d in foods.items():
        p_, _ = pack(f, d["required"])
        if p_ < d["required"]:
            checks.append(f"✗ {f} 购买量 {p_:g}g < 需要量 {d['required']:g}g")
    if not checks:
        checks.append("✓ 购买量覆盖需要量；复用餐次未重复采购")
    for c in checks:
        print(" ", c)

    if args.csv_out:
        with open(args.csv_out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["food", "required_quantity", "package_quantity",
                                               "planned_use", "expected_leftover", "leftover_action"])
            w.writeheader()
            w.writerows(detail_rows)
        print(f"\n已导出五字段明细：{args.csv_out}")

    if args.search_list:
        import json, os
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        pkg_rules, subs = {}, {}
        try:
            pkg_rules = json.load(open(os.path.join(base, "package-rules.json"), encoding="utf-8")).get("packages", {})
            subs_all = json.load(open(os.path.join(base, "substitutions.json"), encoding="utf-8"))
            for grp in subs_all.values():
                if isinstance(grp, dict):
                    subs.update(grp)
        except Exception as e:
            print(f"  ! 数据文件读取失败（{e}），搜索词仅按菜单生成")
        rows2 = []
        for f, d in foods.items():
            p_, pkg_desc = pack(f, d["required"])
            rule = pkg_rules.get(f, {})
            pkg_str = f"{rule['package_quantity']:g}{rule.get('unit','g')}" if rule else pkg_desc
            keyword = f"{f} {pkg_str}" if rule else f
            pc = price_cost(f, p_, pack_count(f, d["required"]))
            rows2.append({
                "ingredient": f,
                "search_keyword": keyword,
                "required_quantity": f"{d['required']:g}g",
                "acceptable_package": pkg_str,
                "substitutes": " / ".join(subs.get(f, [])) or "（同类食材任选）",
                "estimated_purchase_cost": f"{pc[0]:.1f}" if pc else "",
                "price_confidence": pc[1] if pc else "unavailable",
            })
        with open(args.search_list, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["ingredient", "search_keyword", "required_quantity",
                                               "acceptable_package", "substitutes",
                                               "estimated_purchase_cost", "price_confidence"])
            w.writeheader()
            w.writerows(rows2)
        print(f"已导出采购清单：{args.search_list}（{len(rows2)} 项；"
              f"可执行率 {sum(1 for r in rows2 if r['search_keyword'])}/{len(rows2)}）")


if __name__ == "__main__":
    main()
