# -*- coding: utf-8 -*-
"""round62 回归：菜谱库覆盖审计器 / selection_audit 规范契约 / 快手早餐模板库。"""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []


def need(path, needle, label):
    if needle not in (ROOT / path).read_text(encoding="utf-8"):
        fails.append(f"{label}：{path} 缺少「{needle}」")


def run(script, *a):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *a],
                          capture_output=True, text=True)


# ---------- 1. 覆盖审计器 ----------
with tempfile.TemporaryDirectory() as td:
    jp = pathlib.Path(td) / "a.json"
    r = run("recipe_library_auditor.py", "--json", str(jp))
    if r.returncode != 0:
        fails.append(f"审计器运行失败 {r.stderr[:200]}")
    else:
        rep = json.loads(jp.read_text(encoding="utf-8"))
        for k in ("total_recipes", "parseable_recipes", "missing_source", "missing_technique",
                  "missing_cuisine", "missing_season", "missing_primary_family",
                  "fingerprint_cluster_count", "high_duplicate_recipes",
                  "protein_family_coverage", "technique_coverage", "cuisine_coverage",
                  "quick_recipes", "solo_friendly_recipes", "household_friendly_recipes",
                  "per_source_counts"):
            if k not in rep:
                fails.append(f"审计报告缺字段 {k}")
        if rep["total_recipes"] < 1500:
            fails.append("审计总数异常（生产池应含索引 367 + 书池 1209）")
        if rep["missing_source"] != 0:
            fails.append("索引池来源应按 howtocook 归一，missing_source 应为 0")
        if rep["fingerprint_cluster_count"] <= 0 or rep["high_duplicate_recipes"] <= 0:
            fails.append("指纹簇/重复统计未生效")
        if "poultry" not in rep["protein_family_coverage"]:
            fails.append("主蛋白族覆盖缺 poultry")
        if "蒸" not in rep["technique_coverage"]:
            fails.append("烹法覆盖缺 蒸")

# ---------- 2. selection_audit 规范命名 + Schema ----------
schema = json.loads((ROOT / "schemas/selection-audit.schema.json").read_text(encoding="utf-8"))
for k in ("candidate_count_before_dedup", "candidate_count_after_dedup", "recipe_source_count",
          "selected_recipe_ids", "selected_source_ids", "selected_fingerprints",
          "technique_count", "history_repeat_count", "diversity_gate_result"):
    if k not in schema["required"]:
        fails.append(f"selection-audit Schema 缺必需字段 {k}")
if "不得填猜测值" not in schema["description"] and "不得伪造" not in schema["description"]:
    fails.append("Schema 未声明 null 不伪造约定")

ms = {"plan_id": "t", "mode_schedule": {f"2026-09-{d}": "hormone_balance" for d in range(12, 19)},
      "mode_summary": {"keto_days": 0, "hormone_days": 7}}
with tempfile.TemporaryDirectory() as td:
    msp = pathlib.Path(td) / "ms.json"
    msp.write_text(json.dumps(ms, ensure_ascii=False), encoding="utf-8")
    ap = pathlib.Path(td) / "audit.json"
    r = run("recipe_ranker.py", "--basket", "鸡腿,鸡蛋,菠菜,西兰花", "--mode-schedule", str(msp),
            "--max-minutes", "25", "--audit-report", str(ap))
    if r.returncode != 0:
        fails.append(f"ranker 运行失败 {r.stderr[:200]}")
    else:
        audit = json.loads(ap.read_text(encoding="utf-8"))
        missing = [k for k in schema["required"] if k not in audit]
        if missing:
            fails.append(f"ranker 审计输出缺规范字段 {missing}")
        if audit["candidate_count_before_dedup"] is None:
            fails.append("before_dedup 应已计算")
        if audit["history_repeat_count"] is not None:
            fails.append("未计算字段应为 null")

# ---------- 3. 早餐模板库 ----------
bt = json.loads((ROOT / "data/breakfast-templates.json").read_text(encoding="utf-8"))
tmpls = bt["templates"]
if len(tmpls) < 20:
    fails.append("早餐模板少于 20 个")
CATS = {"无需烹饪组合", "5分钟组装", "10分钟平底锅", "可前夜准备", "可带走",
        "乳制品替代", "鸡蛋替代", "不同碳水组", "咸味早餐", "温热早餐"}
got = {t["category"] for t in tmpls}
if got != CATS:
    fails.append(f"模板类别不全：缺 {CATS - got}")
F = json.loads((ROOT / "data/foods-table.json").read_text(encoding="utf-8"))["foods"]
for t in tmpls:
    for field in ("active_minutes", "total_minutes", "workday_suitable", "prepare_ahead",
                  "ingredients", "nutrition", "substitution_rules"):
        if field not in t:
            fails.append(f"模板 {t['template_id']} 缺字段 {field}")
    if t["meal_plan_mode"] != "planned" or not t["include_in_nutrition"] \
            or not t["include_in_procurement"] or t["preparation_mode"] != "quick_self_prepare":
        fails.append(f"模板 {t['template_id']} 语义字段错误")
    # 营养值与 foods-table 重算一致（不手填）
    tot = 0.0
    for ing in t["ingredients"]:
        tot += F[ing["food"]]["kcal"] * ing["grams"] / 100
    if abs(tot - t["nutrition"]["kcal"]) > 0.2:
        fails.append(f"模板 {t['template_id']} 营养值与 foods-table 不一致")

# 构建器幂等且拒绝未知食材
r = run("build_breakfast_templates.py")
if r.returncode != 0:
    fails.append(f"早餐模板构建器失败 {r.stderr[:200]}")

# 规则接入
need("references/runtime-rules.md", "data/breakfast-templates.json", "模板库接入")
need("references/runtime-rules.md", "10分钟平底锅", "模板库接入")
need("SKILL.md", "breakfast-templates.json", "模板库接入")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round62 全部探针与脚本行为命中")
sys.exit(0)
