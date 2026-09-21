# -*- coding: utf-8 -*-
"""round61 回归：封版一致性（README 参数口径 / fatal_reason 枚举 / B 门禁降级 /
D01 统一与适用范围 / 时令条件完整性 / 助手交付口径 / 文档静态检查）。"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []


def read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def need(path, needle, label):
    if needle not in read(path):
        fails.append(f"{label}：{path} 缺少「{needle}」")


# ---------- 1. README 文档静态检查（P0-1 / P2-11）----------
readme = read("README.md")
for banned in ("--mode keto", "--mode hormone", "--keto-days", "--hormone-days"):
    if banned in readme:
        fails.append(f"README 仍含废弃模式参数示例「{banned}」")
if "367" in readme:
    fails.append("README 仍手写菜谱数量")
need("MAINTENANCE.md", "以 data/library-manifest.json 为准", "P1-菜谱数")
need("MAINTENANCE.md", "--mode-schedule mode_schedule.json", "P0-1")

# ---------- 2. fatal_reason 枚举（P0-2）----------
need("SKILL.md", "mode_schedule_mismatch", "P0-2")
need("SKILL.md", "core_rule_file_missing / safety_route_unresolvable / plan_schema_mismatch / "
     "rules_bundle_mismatch / corrupted_plan_json / mode_schedule_mismatch / "
     "auto_fix_retry_exhausted / renderer_retry_exhausted", "P0-2")

# ---------- 3. B01/B02 改 auto_fix（P0-3）----------
need("SKILL.md", "B01. [auto_fix]", "P0-3")
need("SKILL.md", "B02. [auto_fix]", "P0-3")
need("workflows/procurement-flow.md", "B01 [auto_fix]", "P0-3")
need("workflows/procurement-flow.md", "恢复为 planned", "P0-3")
need("workflows/procurement-flow.md", "auto_fix_retry_exhausted", "P0-3")
need("workflows/procurement-flow.md", "meal_semantic_audit", "P0-3")
if "B01. [fatal]" in read("SKILL.md") or "B01**：" in read("workflows/procurement-flow.md").replace("[auto_fix]", ""):
    fails.append("P0-3：B01 旧 fatal/无级别定义仍残留")

# ---------- 4. D01 统一与适用范围（P1-1）----------
need("workflows/planning-flow.md", "同一主蛋白最多出现 2 次，并且烹法或主风味必须不同", "P1-1")
need("workflows/planning-flow.md", "=1 餐时不执行 D01–D05", "P1-1")
need("workflows/planning-flow.md", "早餐基础食材", "P1-1")
need("workflows/planning-flow.md", "多样性不得凌驾的条件", "P1-1")
need("workflows/planning-flow.md", "D06", "P1-1")
for path in ("references/runtime-rules.md", "SKILL.md", "references/sample-days.md",
             "workflows/planning-flow.md"):
    for line in read(path).splitlines():
        if "同一主食材一周" in line and "≤3" in line \
                and "不再使用" not in line and "替代旧" not in line:
            fails.append(f"P1-1：旧「≤3 次」规则仍残留于 {path}（非否定语境）")

# diversity_checker D01 行为：同一主蛋白 3 次 → 违规
with tempfile.TemporaryDirectory() as td:
    csvp = pathlib.Path(td) / "m.csv"
    csvp.write_text(
        "date,meal,dish,protein,vegetable,method,flavor,structure,texture\n"
        "2026-09-12,晚餐,焖鸡腿,鸡腿,洋葱,焖,酱香,炖煮,软\n"
        "2026-09-14,晚餐,咖喱鸡腿,鸡腿,土豆,焖,咖喱,炖煮,软\n"
        "2026-09-16,晚餐,烤鸡腿,鸡腿,西兰花,烤,黑椒,烤制,嫩\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/diversity_checker.py"), str(csvp)],
                       capture_output=True, text=True)
    if "D01" not in r.stdout or ">2 次上限" not in r.stdout:
        fails.append("P1-1：diversity_checker 未按 D01 识别主蛋白 3 次重复")

# ---------- 5. 时令条件完整性（P1-2）----------
need("SKILL.md", "时令条件检查（规则 ID：SEASON-001）", "P1-2")
need("SKILL.md", "seasonal_data_unavailable", "P1-2")
need("SKILL.md", "不得凭月份常识补写当季结论", "P1-2")
need("workflows/planning-flow.md", "season_status` + `source_rule_id` 四要素", "P1-2")
need("workflows/planning-flow.md", "只能证明月份进入流程", "P1-2")
need("workflows/planning-flow.md", "时令数据缺失降级（round61，G01 条件完整性）", "P1-2")

# ---------- 6. 助手交付口径（P1-3）----------
need("MAINTENANCE.md", "当前过渡交付方式为完整文件夹分发", "P1-3")
need("MAINTENANCE.md", "dev/DEVELOPMENT.md", "P1-3")

# ---------- 7. 执行审计字段（P2-10）----------
need("workflows/planning-flow.md", "meal_semantic_audit", "P2-10")
need("workflows/planning-flow.md", "mode_consistency_audit", "P2-10")
need("workflows/planning-flow.md", "diversity_gate_result", "P2-10")
need("workflows/planning-flow.md", "不得填猜测值", "P2-10")

# ---------- 8. 非 fatal 状态分类（12.2）----------
need("SKILL.md", "meal_mode_invalid_downgrade", "12.2")
need("SKILL.md", "diversity_gate_failed", "12.2")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round61 全部探针与脚本行为命中")
sys.exit(0)
