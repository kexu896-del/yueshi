#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食材篮子生成器（两次生成的第一阶段）

按 周期模式天数 / 自炊餐次 / 预算档位 / 当季 生成 weekly_basket 草案 JSON，
供 AI 在此基础上微调（换用户爱吃/忌口的食材）。

用法：
  python basket_builder.py --meals-per-day 1 --keto-days 2 --hormone-days 5 \
      --month 8 --budget-tier standard --seed 202635
输出：weekly_basket JSON（proteins/vegetables/carbohydrates/flavor_bases）+ 校验提示

预算档位：economy（≈300-450元）/ standard（≈450-700元）/ quality（700+元）
"""
import argparse, json, os, random, sys

PROTEIN_POOLS = {
    "economy": ["鸡蛋", "鸡腿", "鸡胸肉", "豆腐", "带鱼", "猪里脊", "蛤蜊"],
    "standard": ["鸡蛋", "鸡腿", "牛里脊", "虾", "三文鱼", "豆腐", "鳕鱼", "牛腩"],
    "quality": ["三文鱼", "牛里脊", "虾", "鳕鱼", "羊排", "鸡蛋", "豆腐", "生蚝"],
}
VEG_BASE = ["菠菜", "西兰花", "大白菜", "黄瓜", "西红柿", "洋葱", "胡萝卜",
            "芹菜", "紫甘蓝", "生菜", "冬瓜", "空心菜", "绿豆芽"]
CARB_POOLS = {
    "economy": ["红薯", "玉米", "糙米", "南瓜", "土豆"],
    "standard": ["红薯", "糙米", "燕麦米", "玉米", "山药", "莲藕"],
    "quality": ["糙米", "藜麦", "山药", "红薯", "玉米"],
}
FAT_POOLS = {"standard": ["核桃", "牛油果"], "quality": ["牛油果", "核桃", "巴旦木"]}

# 一人食分层表（与 SKILL.md 一致；非一人食取 3 餐档）
LAYER = {1: (12, 16), 2: (16, 22), 3: (22, 30)}


def load_json(name):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", name)
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meals-per-day", type=int, choices=[1, 2, 3], default=2)
    ap.add_argument("--keto-days", type=int, default=0)
    ap.add_argument("--hormone-days", type=int, default=7)
    ap.add_argument("--month", type=int, default=0, help="1-12，取当令食材")
    ap.add_argument("--budget-tier", choices=["economy", "standard", "quality"], default="standard")
    ap.add_argument("--seed", type=int, default=0, help="周种子（如 202635），保证周与周篮子不同")
    ap.add_argument("--avoid", default="", help="忌口食材，顿号分隔")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    lo, hi = LAYER[args.meals_per_day]
    avoid = set(filter(None, args.avoid.split("、")))

    seasonal = load_json("seasonal-foods.json").get(f"{args.month}月", []) if args.month else []

    def pick(pool, n, prefer=None):
        pool = [x for x in pool if x not in avoid]
        prefer = [x for x in (prefer or []) if x in pool]
        rest = [x for x in pool if x not in prefer]
        rng.shuffle(rest)
        return (prefer + rest)[:n]

    n_prot = max(3, min(5, lo // 4))
    n_veg = max(4, min(8, lo - n_prot - 2))
    proteins = pick(PROTEIN_POOLS[args.budget_tier], n_prot)
    vegetables = pick(VEG_BASE, n_veg, prefer=[s for s in seasonal if s in VEG_BASE])
    # 当令蔬菜补充（如银耳/百合等非 VEG_BASE 项仅作提示）
    seasonal_extra = [s for s in seasonal if s not in VEG_BASE and s not in avoid][:3]

    carbohydrates = []
    if args.hormone_days > 0:
        carbohydrates = pick(CARB_POOLS[args.budget_tier], 2 if args.hormone_days <= 3 else 3,
                             prefer=[s for s in seasonal if s in ("南瓜", "山药", "莲藕", "红薯", "玉米", "芋头")])

    basket = {
        "proteins": proteins,
        "vegetables": vegetables + [x for x in seasonal_extra if x in ("银耳", "百合")],
        "carbohydrates": carbohydrates,
        "flavor_bases": rng.sample(["咸鲜", "蒜香", "酱香", "咖喱", "酸甜", "黑椒", "清淡", "酸辣"], 4),
        "fat_extras": FAT_POOLS.get(args.budget_tier, []) if args.keto_days > 0 else [],
    }
    total = len(proteins) + len(basket["vegetables"]) + len(carbohydrates) + len(basket["fat_extras"])
    print(json.dumps({"weekly_basket": basket}, ensure_ascii=False, indent=2))

    # 包装规格核对：篮子里的食材必须有已知包装规格，否则提示先确认所在地可获得性
    pkg_rules = load_json("package-rules.json").get("packages", {})
    all_items = proteins + basket["vegetables"] + carbohydrates + basket["fat_extras"]
    no_pkg = [x for x in all_items if x not in pkg_rules]
    if no_pkg:
        print(f"\n! 以下食材无已知包装规格，生成采购清单前需先确认常见购买规格：{'、'.join(no_pkg)}")
    else:
        print("\n✓ 篮子内全部食材均有已知包装规格（data/package-rules.json）")
    print(f"\n篮子共 {total} 种（分层建议 {lo}~{hi}，调味与库存不计）")
    if total > hi:
        print("  ! 超出上限，删减只用一次的食材")
    if args.keto_days and not basket["fat_extras"]:
        print("  ! 酮生物日建议配脂肪来源（牛油果/坚果），economy 档用鸡蛋+烹饪油补足")
    if seasonal:
        print(f"  · 当令参考：{'、'.join(seasonal)}")
    if avoid:
        print(f"  · 已避开忌口：{'、'.join(avoid)}")


if __name__ == "__main__":
    main()
