#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round45：成品口径修正（151g/大米生熟/非做饭日文案/包装优先级）+ 速度优化
（局部重装配 / 联合求解器 / 先求解后渲染 / 缓存）。"""
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


def _plan(**kw):
    plan = json.loads(read("data/golden/golden-sample-plan.json"))
    if "shopping_items" in kw:
        plan["shopping"]["items"] = kw["shopping_items"]
    return plan


def _render(plan):
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "p.json"), os.path.join(td, "o.html")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "render_html.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        if r.returncode == 0:
            return 0, open(op, encoding="utf-8").read()
        return r.returncode, r.stderr + r.stdout


def _shop_item(name, **extra):
    it = {"ingredient": name, "amount": "1kg", "reference_price": "约¥10",
          "spec": "1kg/袋", "note": ""}
    it.update(extra)
    return it


FIXTURE = [
    {"ingredient_id": "rice", "name": "白米饭",
     "per_100g": {"energy": 116, "carbs": 25.9, "protein": 2.6, "fat": 0.3},
     "grams": {"primary": 300, "secondary": 420}, "adjustable": True, "min_g": 80, "max_g": 500},
    {"ingredient_id": "chicken", "name": "鸡肉",
     "per_100g": {"energy": 167, "carbs": 0, "protein": 19.3, "fat": 9.4},
     "grams": {"primary": 130, "secondary": 130}, "adjustable": False},
    {"ingredient_id": "tofu", "name": "豆腐",
     "per_100g": {"energy": 82, "carbs": 3.0, "protein": 8.1, "fat": 3.7},
     "grams": {"primary": 150, "secondary": 150}, "adjustable": True, "min_g": 50, "max_g": 350},
    {"ingredient_id": "oil", "name": "油脂",
     "per_100g": {"energy": 884, "carbs": 0, "protein": 0, "fat": 100},
     "grams": {"primary": 25, "secondary": 30}, "adjustable": True, "min_g": 10, "max_g": 50},
]
TARGETS = [
    {"member_id": "primary", "targets": {"energy_min": 800, "energy_max": 1000,
                                         "carbs_max": 60, "protein_min": 45,
                                         "fat_min": 25, "fat_max": 45}},
    {"member_id": "secondary", "targets": {"energy_min": 1000, "energy_max": 1200,
                                           "carbs_max": 80, "protein_min": 55,
                                           "fat_min": 30, "fat_max": 55}},
]


def _doc():
    return {"members": json.loads(json.dumps(TARGETS)),
            "ingredients": json.loads(json.dumps(FIXTURE))}


def t01_solver_joint_solve():
    from household_portion_solver import solve
    r = solve(_doc())
    check("t01a 一次联合求解 optimal", r["status"] == "optimal")
    t = r["totals"]
    check("t01b 全员碳水达标", t["primary"]["carbs"] <= 60 and t["secondary"]["carbs"] <= 80)
    check("t01c 全员蛋白达标", t["primary"]["protein"] >= 45 and t["secondary"]["protein"] >= 55)
    check("t01d 全员热量在区间内",
          800 <= t["primary"]["energy"] <= 1000 and 1000 <= t["secondary"]["energy"] <= 1200)
    check("t01e 全员脂肪在区间内",
          25 <= t["primary"]["fat"] <= 45 and 30 <= t["secondary"]["fat"] <= 55)
    grams = json.dumps(r["grams"])
    check("t01f locked 食材不进调整输出", "chicken" not in grams)
    check("t01g 改动非零且最小化目标记录", r["objective_l1_g"] > 0 and r["adjustments"])


def t02_solver_infeasible_and_cli():
    from household_portion_solver import solve
    doc = _doc()
    doc["members"][0]["targets"]["carbs_max"] = 10  # 不可达
    r = solve(doc)
    check("t02a infeasible 明确返回", r["status"] == "infeasible")
    with tempfile.TemporaryDirectory() as d:
        ip, op = os.path.join(d, "i.json"), os.path.join(d, "o.json")
        json.dump(_doc(), open(ip, "w", encoding="utf-8"))
        r1 = subprocess.run([sys.executable,
                             os.path.join(BASE, "scripts", "household_portion_solver.py"),
                             ip, "-o", op], capture_output=True, text=True)
        check("t02b CLI optimal exit 0", r1.returncode == 0 and os.path.exists(op))
        doc["members"][0]["targets"]["carbs_max"] = 10
        json.dump(doc, open(ip, "w", encoding="utf-8"))
        r2 = subprocess.run([sys.executable,
                             os.path.join(BASE, "scripts", "household_portion_solver.py"), ip],
                            capture_output=True, text=True)
        check("t02c CLI infeasible exit 3", r2.returncode == 3)


def t03_rice_caliber_gate():
    bad = _plan(shopping_items=[_shop_item("大米", note="约2.5kg")])
    rc, out = _render(bad)
    check("t03a 熟重生重混用被拦截", rc != 0 and "生米口径" in out, out[-200:])
    bad2 = _plan(shopping_items=[_shop_item("大米", note="需取用生米约1000g")])
    rc, out = _render(bad2)
    check("t03b 缺熟米饭对应量被拦截", rc != 0 and "熟米饭" in out, out[-200:])
    good = _plan(shopping_items=[_shop_item("大米", note="需取用生米约1000g（对应熟米饭约2300g）")])
    rc, out = _render(good)
    check("t03c 双行标注通过", rc == 0, out[-200:])


def t04_excluded_day_copy_gate():
    plan = _plan()
    plan["days"][0]["advice"] = "今天无人在家吃饭，三餐自行解决。"
    rc, out = _render(plan)
    check("t04a 旧文案被拦截", rc != 0 and "三餐自行解决" in out, out[-200:])
    op = read("references/output-policy.md")
    check("t04b 标准文案入 output-policy",
          "今天不在家用餐，本计划不安排菜单，也不计入本周采购与营养合计" in op)


def t05_tolerance_and_packaging_rules():
    nr = read("references/nutrition-routing.md")
    check("t05a 取整浮动判定口径", "≤0.9g" in nr and "rounding tolerance" in nr)
    check("t05b 显示口径写约区间", "个别日期因食材取整允许约 1g 浮动" in nr)
    check("t05c 禁止内外口径不一致", "内部通过、可见页面也必须看起来达标" in nr)
    rr = read("references/runtime-rules.md")
    check("t05d 包装消耗优先级", "包装消耗优先级" in rr and "散装称重" in rr)
    check("t05e 米类生熟口径规则", "米类生熟口径" in rr and "禁止以熟饭重充当生米" in rr)


def t06_speed_rules():
    pf = read("workflows/household-planning-flow.md")
    check("t06a 局部重装配模式", "schedule_and_ingredient_patch" in pf and "不重跑完整 13 步" in pf)
    check("t06b 局部管线七步", "锁定篮子过滤 → 做饭日菜单重装配 → 份量联合求解" in pf)
    check("t06c 一次联合求解纪律", "household_portion_solver.py" in pf and "试克数" in pf)
    check("t06d 先求解再渲染", "只渲染一次" in pf and "禁止渲染后再调营养与采购" in pf)
    check("t06e 不变数据哈希缓存", "哈希直接复用" in pf)


if __name__ == "__main__":
    for fn in (t01_solver_joint_solve, t02_solver_infeasible_and_cli,
               t03_rice_caliber_gate, t04_excluded_day_copy_gate,
               t05_tolerance_and_packaging_rules, t06_speed_rules):
        fn()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)
