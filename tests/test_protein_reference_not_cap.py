#!/usr/bin/env python3
# 收口轮 P1-2：book_reference 只提示不作硬上限；容差带与医嘱上限生效；安全下限兜底
import csv, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALC = os.path.join(ROOT, "scripts", "macros_calculator.py")
BASE = ["--sex", "f", "--age", "32", "--height", "165", "--weight", "55",
        "--goal", "lose", "--mode", "hormone"]
# 该画像：安全下限 55g、个体目标 66g、容差带上限 ~79g、书中参考 50g


def run_check(day_protein):
    td = tempfile.mkdtemp()
    fp = os.path.join(td, "week.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "meal", "food", "grams", "net_carbs_per100",
                    "protein_per100", "fat_per100", "kcal_per100"])
        # 单日一餐，蛋白=day_protein（protein_per100=100 → grams 即蛋白克数）
        w.writerow(["2026-08-22", "晚餐", "测试食材", day_protein, 10, 100, 10, 500])
    r = subprocess.run([sys.executable, CALC] + BASE + ["--check", fp],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    return r.stdout


# 1) 蛋白 60g：高于书中参考 50g，但低于个体目标容差带 → 合规，且只出现"仅提示"
out = run_check(60)
assert "✓ 全部合规" in out, out
assert "仅提示" in out, out
assert "蛋白超" not in out, out

# 2) 蛋白 90g：超容差带 ~79g → 不合规
out = run_check(90)
assert "✗" in out and "容差带" in out, out

# 3) 蛋白 40g：低于安全下限 55g → 不合规
out = run_check(40)
assert "✗" in out and "安全下限" in out, out

print("PASS")
