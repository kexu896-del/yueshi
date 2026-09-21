#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily_target_compiler.py — 每日营养目标矩阵预编译（round58 新增）。

背景：营养微调超过 2 轮的主因是约束在求解前没有一次性加载（如第三轮才发现
hormone_net_carb_weightloss_g=100）。本脚本在第一次营养计算前构建唯一目标矩阵
daily_targets.json，营养计算器只接收这份已冻结目标；目标文件缺字段立即失败，
不进入菜单微调。

执行语义（planning-flow 步骤 12 前置）：
  第 0 步：预编译每日目标矩阵（本脚本）
  第 1 轮：全周联合求解
  第 2 轮：只修复仍未通过的日期
  最终复核：只检查，不再调整（不计为微调轮次，不得再改变食材克数）

用法：
  python3 daily_target_compiler.py --sex f --age 28 --height 163 --weight 70 \
      --activity 1.4 --goal lose --modes keto,keto,hormone,hormone,hormone,hormone,hormone \
      --stages power1,power1,power2,power2,nurture,nurture,nurture \
      --start-date 2026-09-12 --out daily_targets.json
  python3 daily_target_compiler.py --check daily_targets.json   # 完整性校验
退出码：0 通过；2 参数/输入错误；3 目标矩阵缺字段（立即失败，不进入微调）。
"""
import argparse, datetime, json, os, sys

import macros_calculator as mc

TARGETS_VERSION = "1.0"

# 每日目标必填字段（缺一即失败，fail-closed）
REQUIRED_DAY_FIELDS = [
    "day_index", "date", "mode", "stage",
    "calories_target_kcal", "calorie_safety_floor_kcal",
    "net_carb_max_g",
    "protein_safety_floor_g", "protein_individual_target_g",
    "protein_tolerance_upper_g", "protein_book_reference_g",
    "protein_medical_limit_g",
    "fat_min_energy_pct", "rounding_tolerance_pct",
]

_PARAMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "effective-parameters.json")


def _approved_param(name, unit):
    """直接读取 approved 参数（fail-closed：缺失/未核证/单位不符即抛错）。
    所有目标参数必须在第一轮营养计算前解析完成——禁止求解中途才发现新上限。"""
    try:
        doc = json.load(open(_PARAMS_PATH, encoding="utf-8"))
    except OSError:
        raise KeyError(f"参数文件不可读，无法编译每日目标（{name}）")
    plist = doc.get("parameters", [])
    if isinstance(plist, dict):
        plist = [dict(parameter_id=k, **v) for k, v in plist.items()]
    item = next((p for p in plist if p.get("parameter_id") == name), None)
    if item is None or item.get("value") is None:
        raise KeyError(f"参数缺失: {name}")
    if (not item.get("source_rule_id")
            or item.get("source_verified") is not True
            or item.get("audit_status") != "approved"):
        raise KeyError(f"参数未通过 approved 门禁: {name}")
    if unit and item.get("unit") != unit:
        raise KeyError(f"参数单位不匹配: {name}（期望 {unit}）")
    return item["value"]


def compile_daily_targets(sex, age, height, weight, activity, goal,
                          modes, stages, start_date,
                          medical_limit_g=None):
    """编译 7 天目标矩阵。modes/stages 长度必须为 7。"""
    if len(modes) != 7 or len(stages) != 7:
        raise ValueError("modes 与 stages 必须各为 7 天")
    # 第 0 步一次性加载全部约束（含平衡激素减重专用净碳水上限——
    # 历史上"第三轮才发现"的参数，必须在第一轮求解前进入目标矩阵）
    keto_carb = float(_approved_param("keto_net_carb_cap_g", "g/day"))
    hormone_carb = float(_approved_param("hormone_net_carb_cap_g", "g/day"))
    hormone_wl_carb = float(_approved_param("hormone_net_carb_weightloss_g", "g/day"))
    keto_fat_min = float(_approved_param("keto_fat_energy_min_pct", "pct_energy"))
    tol_pct = float(_approved_param("protein_tolerance_pct", "pct"))

    days = []
    start = datetime.date.fromisoformat(start_date)
    for i in range(7):
        mode = modes[i].strip().lower()
        if mode not in ("keto", "hormone"):
            raise ValueError(f"未知模式: {mode}")
        t = mc.calc_targets(sex, age, height, weight, activity, goal, mode)
        if mode == "keto":
            carb_max = keto_carb
            fat_min = keto_fat_min
        else:
            carb_max = hormone_wl_carb if goal == "lose" else hormone_carb
            fat_min = 0.0
        days.append({
            "day_index": i + 1,
            "date": (start + datetime.timedelta(days=i)).isoformat(),
            "mode": mode,
            "stage": stages[i],
            "calories_target_kcal": round(t["calories"], 1),
            "calorie_safety_floor_kcal": round(t["bmr"] * 1.1, 1),
            "net_carb_max_g": carb_max,
            "protein_safety_floor_g": round(t["protein_safety_floor_g"], 1),
            "protein_individual_target_g": round(t["protein_individual_target_g"], 1),
            "protein_tolerance_upper_g": round(
                t["protein_individual_target_g"] * (1 + tol_pct / 100), 1),
            "protein_book_reference_g": t["protein_book_reference_g"],
            "protein_medical_limit_g": medical_limit_g,
            "fat_min_energy_pct": fat_min,
            "rounding_tolerance_pct": tol_pct,
        })
    return {"targets_version": TARGETS_VERSION,
            "goal": goal, "days": days}


def validate_targets(doc):
    """完整性校验：缺字段立即返回错误列表（调用方失败关闭）。"""
    errs = []
    days = doc.get("days")
    if not isinstance(days, list) or len(days) != 7:
        errs.append("days 必须为 7 天")
        return errs
    for d in days:
        for f in REQUIRED_DAY_FIELDS:
            if f not in d:
                errs.append(f"day {d.get('day_index', '?')} 缺字段: {f}")
    return errs


def main():
    ap = argparse.ArgumentParser(description="每日营养目标矩阵预编译与校验")
    ap.add_argument("--check", metavar="FILE", help="校验 daily_targets.json 完整性")
    ap.add_argument("--sex", choices=["f", "m"])
    ap.add_argument("--age", type=int)
    ap.add_argument("--height", type=float)
    ap.add_argument("--weight", type=float)
    ap.add_argument("--activity", type=float, default=1.4)
    ap.add_argument("--goal", choices=["lose", "maintain", "bulk", "heal"],
                    default="lose")
    ap.add_argument("--modes", help="7 天模式，逗号分隔（keto/hormone）")
    ap.add_argument("--stages", help="7 天周期阶段，逗号分隔")
    ap.add_argument("--start-date", help="起始日期 YYYY-MM-DD")
    ap.add_argument("--medical-limit-g", type=float, default=None)
    ap.add_argument("--out", help="输出路径（缺省打印到 stdout）")
    args = ap.parse_args()

    if args.check:
        try:
            doc = json.load(open(args.check, encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"目标文件不可读: {e}", file=sys.stderr)
            return 2
        errs = validate_targets(doc)
        if errs:
            for e in errs:
                print(f"目标矩阵不完整: {e}", file=sys.stderr)
            return 3
        print("daily_targets 完整性校验通过（7 天 × %d 必填字段）"
              % len(REQUIRED_DAY_FIELDS))
        return 0

    missing = [k for k in ("sex", "age", "height", "weight",
                           "modes", "stages", "start_date")
               if getattr(args, k) is None]
    if missing:
        print(f"缺参数: {', '.join('--' + m.replace('_', '-') for m in missing)}",
              file=sys.stderr)
        return 2
    try:
        doc = compile_daily_targets(
            args.sex, args.age, args.height, args.weight,
            args.activity, args.goal,
            args.modes.split(","), args.stages.split(","),
            args.start_date, args.medical_limit_g)
    except (ValueError, KeyError) as e:
        print(f"目标编译失败: {e}", file=sys.stderr)
        return 2
    errs = validate_targets(doc)  # 编译产物自校验，缺字段不落盘
    if errs:
        for e in errs:
            print(f"目标矩阵不完整: {e}", file=sys.stderr)
        return 3
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"已写出 {args.out}（7 天目标矩阵，第 0 步预编译完成）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
