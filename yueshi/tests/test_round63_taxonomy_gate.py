# -*- coding: utf-8 -*-
"""round63 回归：一级菜谱类型 / 蛋白族拆分 / 指纹三层拆分 / 验收报告 / 发布门禁 / SKILL 规则索引。"""
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


CLS = json.loads((ROOT / "data/recipe-classification.json").read_text(encoding="utf-8"))
FP = json.loads((ROOT / "data/recipe-fingerprints.json").read_text(encoding="utf-8"))
MF = json.loads((ROOT / "data/library-manifest.json").read_text(encoding="utf-8"))
TAX = json.loads((ROOT / "data/taxonomy/dish-categories.json").read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in CLS["records"]}

# ---------- 1. taxonomy 与 dish_category 覆盖 ----------
enum = set(TAX["dish_category_enum"])
if len(enum) != 10:
    fails.append(f"dish_category 枚举应为 10 项，实际 {len(enum)}")
main_ok = set(TAX["allowed_for_main_meal"])
if main_ok != {"main_dish", "staple", "soup", "side", "composite_meal"}:
    fails.append(f"allowed_for_main_meal 不符：{main_ok}")
prod = [r for r in CLS["records"] if not r.get("excluded_from_production")]
bad_cat = [r["id"] for r in prod
           if r.get("dish_category") not in enum]
if bad_cat:
    fails.append(f"生产菜谱存在非法/缺失 dish_category：{bad_cat[:5]}")

# ---------- 2. 分类回归样本（不得误判） ----------
def cat_of(rid):
    return by_id.get(rid, {}).get("dish_category"), by_id.get(rid, {}).get("primary_protein_family")

# 甜点/饮品/调味品/小食 不得带肉蛋白，不进正餐池
no_flesh = {"dessert", "beverage", "sauce_or_condiment", "snack"}
flesh = {"poultry", "pork", "beef", "lamb", "fish", "shellfish", "other_protein"}
for r in prod:
    if r["dish_category"] in no_flesh and r.get("primary_protein_family") in flesh:
        fails.append(f"严重误标：{r['id']} {r.get('name')} {r['dish_category']}→{r['primary_protein_family']}")

# 名称含肉但类型为甜点/饮品的，不得因名词进正餐池
for r in CLS["records"]:
    if r["dish_category"] in no_flesh and r["dish_category"] in main_ok:
        fails.append(f"非正餐类型误入正餐池：{r['id']}")

# 蛋白族字段拆分存在
for r in prod[:1] + prod:
    for k in ("primary_ingredient_family", "primary_protein_family",
              "secondary_protein_families", "classification_method",
              "classification_confidence", "classification_evidence"):
        if k not in r:
            fails.append(f"{r['id']} 缺字段 {k}")
            break
    else:
        continue
    break

# ---------- 3. 指纹三层拆分 ----------
for rec in FP["fingerprints"]:
    for k in ("exact_fingerprint", "diversity_fingerprint", "semantic_cluster_key"):
        if not rec.get(k):
            fails.append(f"{rec.get('id')} 指纹缺 {k}")
            break
    else:
        dv = rec["diversity_fingerprint"].split("|")
        if len(dv) != 5:
            fails.append(f"{rec['id']} diversity_fingerprint 维度数 {len(dv)}≠5")
        continue
    break
if FP["stats"]["exact_duplicate_recipes"] != 0:
    fails.append(f"精确重复应已清零，实际 {FP['stats']['exact_duplicate_recipes']}")
# build_id 三方一致
if not (CLS["build_id"] == FP["build_id"] == MF["release"]["build_id"]):
    fails.append("classification / fingerprints / manifest release 的 build_id 不一致")

# ---------- 4. 验收报告 ----------
aud = json.loads((ROOT / "data/audit/latest-audit.json").read_text(encoding="utf-8"))
if aud.get("audit_status") not in ("passed", "passed_with_warnings", "failed"):
    fails.append(f"audit_status 非法：{aud.get('audit_status')}")
for k in ("blocking_issues", "warnings", "quality_metrics", "comparison_with_previous"):
    if k not in aud:
        fails.append(f"验收报告缺字段 {k}")
qm = aud.get("quality_metrics", {})
if qm.get("dish_category_coverage", 0) < 1.0:
    fails.append("dish_category_coverage < 100%")
if qm.get("severe_protein_mislabel_count", 1) != 0:
    fails.append("存在严重蛋白误标")

# ---------- 5. 发布门禁 ----------
rel = MF.get("release") or {}
if rel.get("release_status") != "approved":
    fails.append(f"manifest release_status={rel.get('release_status')}，应为 approved")
sys.path.insert(0, str(ROOT / "scripts"))
import recipe_ranker as rr  # noqa: E402
if not rr.production_allowed("howtocook"):
    fails.append("approved manifest 下 howtocook 应允许生产")
with tempfile.TemporaryDirectory() as td:
    blocked = dict(MF)
    blocked["release"] = dict(rel, release_status="blocked")
    p = pathlib.Path(td) / "mf.json"
    p.write_text(json.dumps(blocked, ensure_ascii=False), encoding="utf-8")
    old = rr.MANIFEST
    rr.MANIFEST = str(p)
    if rr.production_allowed("howtocook"):
        fails.append("blocked manifest 被拒绝失败")
    rr.MANIFEST = old

# ---------- 6. 多样性指纹接线 ----------
with tempfile.TemporaryDirectory() as td:
    csvp = pathlib.Path(td) / "menu.csv"
    csvp.write_text(
        "date,meal,dish,protein,vegetable,method,flavor,structure,recipe_id\n"
        "2026-09-15,午餐,乡村啤酒鸭,,,,,,htc-001\n"
        "2026-09-16,午餐,某菜,鸡腿,土豆,炖,咸鲜,一锅炖煮,\n"
        "2026-09-17,午餐,某菜2,鸡蛋,菠菜,蒸,清淡,蒸菜,\n",
        encoding="utf-8")
    r = run("diversity_checker.py", str(csvp), "--fingerprints",
            str(ROOT / "data/recipe-fingerprints.json"))
    if "多样性指纹接入：1/3" not in r.stdout:
        fails.append(f"diversity_checker 指纹接线异常：{r.stdout[:120]}")

# ---------- 7. SKILL / README / 规则索引 ----------
need("SKILL.md", "version: yueshi-1.4.3", "G")
sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
for marker in ("round60", "round61", "round62"):
    if marker in sk:
        fails.append(f"SKILL.md 仍含历史轮次标记 {marker}（应迁入 CHANGELOG）")
if len(sk.splitlines()) >= 150:
    fails.append(f"SKILL.md 超 150 行：{len(sk.splitlines())}")
need("README.md", "适用 SKILL 版本：1.4.3", "I")
need("README.md", "## 使用过程", "I")
need("README.md", "获取最终计划", "I")
need("MAINTENANCE.md", "正式生产链组件", "I")
need("MAINTENANCE.md", "只读审计工具", "I")
need("MAINTENANCE.md", "禁止单独运行的内部组件", "I")
ri = (ROOT / "references/rule-index.md").read_text(encoding="utf-8")
for rid in ("SAFETY-001", "MEAL-STATE-001", "PROCUREMENT-001", "PRICE-001",
            "HOUSEHOLD-001", "MODE-001", "DIVERSITY-001", "SEASON-001", "OUTPUT-001"):
    if rid not in ri:
        fails.append(f"rule-index.md 缺稳定规则 ID {rid}")
need("SKILL.md", "references/rule-index.md", "G")

# ---------- 8. 修复清单产物 ----------
for p in ("reports/recipe-unparseable.csv", "reports/recipe-low-confidence.csv",
          "reports/recipe-missing-tags.csv", "reports/recipe-duplicate-review.csv",
          "reports/recipe-library-audit.md"):
    if not (ROOT / p).exists():
        fails.append(f"缺修复清单产物 {p}")

# ---------- 汇总 ----------
if fails:
    print("round63 回归失败：")
    for f in fails:
        print(" ✗", f)
    sys.exit(1)
print(f"round63 回归全部通过（生产菜谱 {len(prod)} 条，build_id {CLS['build_id']}）")
