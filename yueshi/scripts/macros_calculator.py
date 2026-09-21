#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
饮食计划营养素计算 + 周期阶段 + 食谱校验脚本（纯标准库）

用法：
  # 1) 计算营养素目标
  python macros_calculator.py --sex f --age 32 --height 165 --weight 55 \
      --activity 1.4 --goal lose --mode keto

  # 2) 女性周期阶段与断食窗口
  python macros_calculator.py --cycle --last-period 2026-08-10 --cycle-len 28

  # 3) 校验一周食谱（CSV 列见下方 --check 说明）
  python macros_calculator.py --check meals.csv --sex f --age 32 --height 165 \
      --weight 55 --activity 1.4 --goal maintain --mode keto

规则（与 SKILL.md 硬规则一致）：
  酮生物饮食：净碳水 <=50g/日；蛋白质 <=75g/日；脂肪供能 >=60%
  平衡激素饮食：净碳水 <=150g/日；蛋白质 <=50g/日；脂肪按需
"""

import argparse, csv, json, os, sys
from datetime import date

# 强制 UTF-8 输出，避免 Windows 终端 GBK/UTF-8 乱码
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KETO_CARB_CAP = 50.0
KETO_PROTEIN_CAP = 75.0
KETO_FAT_PCT_MIN = 0.60
HORMONE_CARB_CAP = 150.0
HORMONE_PROTEIN_CAP = 50.0
PROTEIN_TOLERANCE_PCT = 20.0  # 个体目标容差带（由 effective-parameters 统一管理取值）

# ── effective production parameters（单一事实源：data/effective-parameters.json）──
# 失败关闭：只有 source_verified=true 且 audit_status=approved 的参数才覆盖内置值；
# 未批准参数打印降级提示（调用方应转一般均衡饮食方案并告知用户）。
_EFFECTIVE = {}
_APPROVED = {}


def load_effective_parameters():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "effective-parameters.json")
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except OSError:
        print("[警告] 未找到 effective-parameters.json：书籍协议参数未核证，使用脚本内置保守值", file=sys.stderr)
        return
    plist = doc.get("parameters", [])
    if isinstance(plist, dict):  # 兼容旧 schema
        plist = [dict(parameter_id=k, **v) for k, v in plist.items()]
    p = {}
    for item in plist:
        pid = item.get("parameter_id")
        if pid in p:
            print(f"[降级] 参数 {pid} 重复定义，拒绝取值", file=sys.stderr)
            continue
        p[pid] = item

    def approved(name, unit=None):
        item = p.get(name)
        if item is None or item.get("value") is None:
            return False
        if not item.get("source_rule_id"):  # 失败关闭第 8 条：source_rule_id 为空
            print(f"[降级] 参数 {name} 缺少 source_rule_id，无法追溯，拒绝取值", file=sys.stderr)
            return False
        if item.get("source_verified") is not True or item.get("audit_status") != "approved":
            return False
        if unit and item.get("unit") != unit:
            print(f"[降级] 参数 {name} 单位不匹配（期望 {unit}）", file=sys.stderr)
            return False
        _APPROVED[name] = True
        return True

    mapping = {
        "keto_net_carb_cap_g": ("KETO_CARB_CAP", float, "g/day"),
        "keto_protein_reference_cap_g": ("KETO_PROTEIN_CAP", float, "g/day"),
        "keto_fat_energy_min_pct": ("KETO_FAT_PCT_MIN", lambda v: float(v) / 100.0, "pct_energy"),
        "hormone_net_carb_cap_g": ("HORMONE_CARB_CAP", float, "g/day"),
        "hormone_protein_reference_cap_g": ("HORMONE_PROTEIN_CAP", float, "g/day"),
        "protein_tolerance_pct": ("PROTEIN_TOLERANCE_PCT", float, "pct"),
    }
    for name, (const, conv, unit) in mapping.items():
        if approved(name, unit):
            globals()[const] = conv(p[name]["value"])
        else:
            print(f"[降级] 参数 {name} 未完成来源核证（非 approved），不进入生产计算", file=sys.stderr)
    approved("cycle_phases", "cycle_day_range")  # 周期阶段参数登记（门禁同上）
    approved("manifestation_fasting_cap_h", "hours")
    approved("nurture_fasting", "flag")
    _EFFECTIVE.update(p)



load_effective_parameters()


def fasting_window(last_meal_end, fasting_hours):
    """断食窗口闭合计算。
    next_eating_start = last_meal_end + fasting_hours；进食窗口 = 24 - 禁食时长。
    返回 (next_eating_start 'HH:MM', eating_window_hours, next_day 0/1)。"""
    hh, mm = map(int, last_meal_end.split(":"))
    total = hh * 60 + mm + int(round(fasting_hours * 60))
    start = total % 1440
    return f"{start // 60:02d}:{start % 60:02d}", 24 - fasting_hours, (1 if total >= 1440 else 0)


ACTIVITY = {"1.2": "久坐", "1.375": "轻度活动", "1.55": "中度活动",
            "1.725": "高强度活动", "1.9": "极高强度"}

GOAL_ADJ = {"lose": -0.18, "maintain": 0.0, "bulk": 0.10, "heal": 0.0}

PROTEIN_PER_KG = {"lose": 1.2, "maintain": 1.0, "bulk": 1.4, "heal": 1.0}


def bmr_mifflin(sex, weight, height, age):
    if sex.lower().startswith("m"):
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161


def calc_targets(sex, age, height, weight, activity, goal, mode):
    bmr = bmr_mifflin(sex, weight, height, age)
    tdee = bmr * activity
    cal = tdee * (1 + GOAL_ADJ[goal])
    floor = bmr * 1.1
    if cal < floor:
        cal = floor
    mode = mode.lower()
    if mode == "keto":
        carb_cap, protein_cap = KETO_CARB_CAP, KETO_PROTEIN_CAP
    else:
        carb_cap, protein_cap = HORMONE_CARB_CAP, HORMONE_PROTEIN_CAP
    # 蛋白质四字段：safety_floor / individual_target / book_reference（仅提示，不作硬上限）/ medical_limit（医嘱，默认 None）
    floor_factor = {"lose": 1.0, "maintain": 0.8, "bulk": 1.2, "heal": 1.0}[goal]
    protein_safety_floor = weight * floor_factor
    protein_individual_target = weight * PROTEIN_PER_KG[goal]
    protein = max(protein_safety_floor, protein_individual_target)
    protein_book_reference = protein_cap          # 原书参考值，只提示偏离
    protein_medical_limit = None                  # 医嘱上限，无则略高于个体目标不自动失败
    protein_tolerance = protein_individual_target * (1 + PROTEIN_TOLERANCE_PCT / 100)
    overridden = protein > protein_book_reference
    # 净碳水：取上限（实际规划留 10% 余量更好，见输出提示）
    carb = carb_cap
    # 剩余热量给脂肪
    fat = (cal - protein * 4 - carb * 4) / 9.0
    if fat < 0:
        fat = 0.0
    fat_pct = (fat * 9) / cal * 100 if cal > 0 else 0
    return dict(bmr=bmr, tdee=tdee, calories=cal, protein=protein,
                carbs=carb, fat=fat, fat_pct=fat_pct,
                carb_cap=carb_cap, protein_cap=protein_cap,
                protein_safety_floor_g=protein_safety_floor,
                protein_individual_target_g=protein_individual_target,
                protein_book_reference_g=protein_book_reference,
                protein_medical_limit_g=protein_medical_limit,
                protein_tolerance_g=protein_tolerance,
                protein_floor=protein_safety_floor, overridden=overridden)


def print_targets(r):
    print("【营养素目标】")
    print(f"BMR : {r['bmr']:.0f} kcal（Mifflin-St Jeor）")
    print(f"TDEE: {r['tdee']:.0f} kcal")
    print(f"目标热量: {r['calories']:.0f} kcal/日")
    print(f"净碳水: ≤{r['carb_cap']:.0f} g/日（规划建议 {r['carbs']*0.9:.0f} g 留余量）")
    print(f"蛋白质: 安全下限 {r['protein_safety_floor_g']:.0f} g/日；个体目标 {r['protein_individual_target_g']:.0f} g/日（容差带上限 {r['protein_tolerance_g']:.0f} g；书中参考 {r['protein_book_reference_g']:.0f} g 仅提示）")
    if r["overridden"]:
        print("⚠ 安全下限高于书中模式上限，已按个体需要覆盖（书中 50g/75g 仅作原书参数展示）。")
    print(f"脂肪  : {r['fat']:.0f} g/日（供能 {r['fat_pct']:.0f}%）")
    if r["fat_pct"] < 60 and r["carb_cap"] == KETO_CARB_CAP:
        print("⚠ 脂肪供能不足 60%！酮生物模式需上调脂肪或下调热量目标。")
    print()
    print("【提示】")
    print("· 生成食谱时逐日留 5~10% 余量，避免满打满算（酱油/香料也含微量碳水）。")
    print("· 减重目标热量已含 −18% 赤字；如一周后精力明显下降，回调 5%。")


def cycle_phase(last_period, cycle_len, on_date=None):
    """周期阶段判定。cycle_phases 通过 source_verified + approved + source_rule_id 门禁
    即按原书阶段执行（变更历史见 CHANGELOG.md 与
    维护区参数构建报告（路径见 developer/maintenance-map.md））；未通过时整体降级为单一温和模式，cycle_confidence: low。"""
    d = on_date or date.today()
    delta = (d - last_period).days
    day = delta % cycle_len + 1
    if not _APPROVED.get("cycle_phases"):
        print("[降级] 周期阶段参数未通过 approved 门禁：本周不启用精细周期切换，"
              "使用单一温和模式，不安排延长禁食（cycle_confidence: low）", file=sys.stderr)
        return day, "单一温和模式（周期协议降级）", "禁食按安全分级 L0 起步范围执行（skill_safety_policy，见 safety-rules.md）",             "一般均衡饮食：天然食材、足量蛋白质与蔬菜", "hormone", "low"
    cp = _EFFECTIVE.get("cycle_phases", {}).get("value", {})
    p1_end = cp.get("power1", [1, 10])[1]
    p2_end = cp.get("manifestation", [11, 15])[1]
    p3_end = cp.get("power2", [16, 19])[1]
    if day <= p1_end:
        phase = "能量期（月经期+月经后一周）"
        fast = "禁食按 L0/L1 分级执行（分级时长为 skill_safety_policy 参数，见 safety-rules.md）"
        food = "酮生物饮食：绿叶蔬菜+优质脂肪；发酵食物、十字花科支持雌激素代谢"
        mode = "keto"
    elif day <= p2_end:
        phase = "排卵期"
        cap = _EFFECTIVE.get("manifestation_fasting_cap_h", {}).get("value", 15)
        fast = f"禁食按 L0/L1 执行，本阶段协议上限 {cap}h；与安全分级冲突时取更保守者"
        food = "平衡激素饮食：十字花科、苦味绿叶菜、芝麻亚麻籽、发酵食物、三文鱼、浆果"
        mode = "hormone"
    elif day <= p3_end:
        phase = "能量期下半场（排卵后低谷）"
        fast = "禁食按 L0/L1 分级执行（分级时长为 skill_safety_policy 参数，见 safety-rules.md）"
        food = "酮生物饮食：绿叶蔬菜+优质脂肪"
        mode = "keto"
    else:
        phase = "经前一周"
        fast = "本阶段原书协议不安排禁食（nurture_fasting，approved 参数）"
        food = "平衡激素饮食：土豆、红薯、南瓜、扁豆黑豆、柑橘/热带水果、南瓜籽、糙米藜麦"
        mode = "hormone"
    return day, phase, fast, food, mode, "high"


def print_cycle(last_period, cycle_len):
    day, phase, fast, food, mode, conf = cycle_phase(last_period, cycle_len)
    print(f"cycle_confidence: {conf}")
    print(f"今天是周期第 {day} 天（按 {cycle_len} 天周期，自 {last_period} 起）")
    print(f"阶段：{phase}")
    print(f"断食窗口：{fast}")
    if mode == "keto":
        print(f"饮食模式：酮生物（净碳水≤{KETO_CARB_CAP:.0f}g/蛋白参考≤{KETO_PROTEIN_CAP:.0f}g/脂肪供能≥{KETO_FAT_PCT_MIN*100:.0f}%，参数来自 effective-parameters.json）")
    else:
        print(f"饮食模式：平衡激素饮食（净碳水≤{HORMONE_CARB_CAP:.0f}g/蛋白参考≤{HORMONE_PROTEIN_CAP:.0f}g/脂肪按需，参数来自 effective-parameters.json）")
    print(f"食物侧重：{food}")
    print("注：以实际出血日重置第 1 天；周期不规律者仅作参考，不推断排卵；")
    print("    禁食安全分级：L0=12-14h 默认；L1=上限16h 仅限有经验健康成年人；>24h 需医疗监督（L2），本工具不生成方案。")


def check_week(csv_path, r):
    """CSV 列: date, meal, food, grams, net_carbs_per100, protein_per100, fat_per100, kcal_per100"""
    days = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            g = float(row["grams"])
            nc = float(row["net_carbs_per100"]) * g / 100
            p = float(row["protein_per100"]) * g / 100
            ft = float(row["fat_per100"]) * g / 100
            kc = float(row["kcal_per100"]) * g / 100
            d = row["date"]
            days.setdefault(d, dict(nc=0, p=0, f=0, kcal=0))
            days[d]["nc"] += nc
            days[d]["p"] += p
            days[d]["f"] += ft
            days[d]["kcal"] += kc
    print("【一周食谱校验】")
    print(f"{'日期':<12}{'净碳水':>7}{'蛋白':>7}{'脂肪':>7}{'热量':>8}  判定")
    ok = True
    for d in sorted(days):
        x = days[d]
        fat_pct = x["f"] * 9 / x["kcal"] * 100 if x["kcal"] else 0
        problems = []
        notes = []
        if x["nc"] > r["carb_cap"]:
            problems.append(f"碳水超 {x['nc']-r['carb_cap']:.0f}g")
        med = r.get("protein_medical_limit_g")
        if med is not None and x["p"] > med:
            problems.append(f"蛋白超医嘱上限 {x['p']-med:.0f}g")
        elif x["p"] > r["protein_tolerance_g"]:
            problems.append(f"蛋白超个体目标容差带 {x['p']-r['protein_tolerance_g']:.0f}g")
        elif x["p"] > r["protein_book_reference_g"]:
            notes.append(f"蛋白高于书中参考 {x['p']-r['protein_book_reference_g']:.0f}g（仅提示）")
        if x["p"] < r["protein_safety_floor_g"]:
            problems.append(f"蛋白低于安全下限 {r['protein_safety_floor_g']-x['p']:.0f}g")
        if r["carb_cap"] == KETO_CARB_CAP and fat_pct < 60:
            problems.append(f"脂肪供能仅 {fat_pct:.0f}%")
        if problems:
            ok = False
            verdict = "；".join(problems)
        elif notes:
            verdict = "合规（" + "；".join(notes) + "）"
        else:
            verdict = "合规"
        print(f"{d:<12}{x['nc']:>6.0f}g{x['p']:>6.0f}g{x['f']:>6.0f}g"
              f"{x['kcal']:>7.0f}  {verdict}")
    if ok:
        print("✓ 全部合规")
    else:
        print("✗ 存在超标项，调整食材克数后重新校验")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sex", choices=["m", "f"])
    ap.add_argument("--age", type=int)
    ap.add_argument("--height", type=float, help="cm")
    ap.add_argument("--weight", type=float, help="kg")
    ap.add_argument("--activity", type=float, default=1.4)
    ap.add_argument("--goal", choices=["lose", "maintain", "bulk", "heal"], default="lose")
    ap.add_argument("--mode", choices=["keto", "hormone"], default="keto")
    ap.add_argument("--cycle", action="store_true", help="女性周期阶段查询")
    ap.add_argument("--last-period", help="上次月经开始日 YYYY-MM-DD")
    ap.add_argument("--cycle-len", type=int, default=28)
    ap.add_argument("--check", help="校验 CSV 食谱文件路径")
    args = ap.parse_args()

    if args.cycle:
        if not args.last_period:
            print("需要 --last-period YYYY-MM-DD")
            sys.exit(1)
        lp = date.fromisoformat(args.last_period)
        print_cycle(lp, args.cycle_len)
        return

    need = [args.sex, args.age, args.height, args.weight]
    if any(v is None for v in need):
        print("示例：python macros_calculator.py --sex f --age 32 --height 165 "
              "--weight 55 --activity 1.4 --goal maintain --mode keto")
        sys.exit(1)

    r = calc_targets(args.sex, args.age, args.height, args.weight,
                     args.activity, args.goal, args.mode)
    print_targets(r)
    if args.check:
        print()
        check_week(args.check, r)


if __name__ == "__main__":
    main()
