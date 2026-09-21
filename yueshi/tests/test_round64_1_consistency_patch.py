# -*- coding: utf-8 -*-
"""round64.1 回归：文档一致性 / 模式字段边界 / 人工覆写闭环 / 漏斗闭合 / 发布不变量。"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []


def need(path, needle, label):
    if needle not in (ROOT / path).read_text(encoding="utf-8"):
        fails.append(f"{label}：{path} 缺少「{needle}」")


def deny(path, needle, label):
    if needle in (ROOT / path).read_text(encoding="utf-8"):
        fails.append(f"{label}：{path} 不应出现「{needle}」")


def run(script, *a):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *a],
                          capture_output=True, text=True)


sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts/common"))

# ---------- 1. 文档一致性 ----------
rm = (ROOT / "README.md").read_text(encoding="utf-8")
# test_readme_key_items_are_ordered_children
for i, name in enumerate(("基本情况", "避开事项", "周期情况", "吃饭做饭",
                          "菜系口味", "预算库存", "做法选择", "输出格式"), 1):
    if f"\n  {i}. **{name}**" not in rm:
        fails.append(f"文档：关键八项第 {i} 项「{name}」非有序子列表")
# test_male_route_does_not_offer_internal_mode_choice
for p in ("references/safety-rules.md", "SKILL.md"):
    deny(p, "两种模式任选", "文档-男性路线")
need("references/safety-rules.md", "不要求用户选择内部饮食模式", "文档-男性路线")
# test_skill_provider_choice_occurs_at_basket_review
need("SKILL.md", "食材预选环节明确选择 `use_helper`", "文档-Provider 时点")
need("references/price-provider-policy.md", "食材预选环节", "文档-Provider 时点")
need("README.md", "食材预选环节明确选择", "文档-Provider 时点")
# test_build_chain_documentation_includes_auditor
need("MAINTENANCE.md", "recipe_classifier.py` → `recipe_fingerprint_builder.py` → `recipe_library_auditor.py` → `recipe_release_gate.py",
     "文档-构建链")
need("MAINTENANCE.md", "正式生产链组件", "文档-组件命名")

# ---------- 2. 加载器元数据头契约（test_skill_metadata_header_matches_loader_contract） ----------
sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n", sk, re.S)
if not m:
    fails.append("元数据头：缺 --- 区块")
else:
    fm = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M))
    for k in ("name", "version", "description"):
        if not fm.get(k):
            fails.append(f"元数据头：缺 {k}")
    if fm.get("name") != "yueshi":
        fails.append("元数据头：name ≠ yueshi")
    if not re.fullmatch(r"yueshi-\d+\.\d+\.\d+(-rc\d*)?", fm.get("version", "")):
        fails.append("元数据头：version 不符合加载器契约 yueshi-X.Y.Z")
    # 与打包加载器同源：release_pack 按行首 version: 解析
    rp = (ROOT / "scripts/release_pack.py").read_text(encoding="utf-8")
    if 'line.startswith("version:")' not in rp:
        fails.append("元数据头：release_pack 加载器解析逻辑变更，契约测试需同步")

# ---------- 3. 模式字段边界 ----------
from mode_schedule import FORBIDDEN_USER_MODE_FIELDS, reject_user_mode_fields  # noqa: E402
# test_user_diet_mode_field_is_rejected / test_user_mode_schedule_is_rejected
out = reject_user_mode_fields({"diet_mode": "keto", "mode_schedule": {},
                               "nutrition_mode": "x", "budget": 300})
if any(k in out for k in ("diet_mode", "mode_schedule", "nutrition_mode")):
    fails.append("模式字段：内部字段未被拒绝")
# test_plan_mode / meal_plan_mode / preparation_mode 不被误删
legit = {"plan_mode": "solo", "meal_plan_mode": "planned",
         "preparation_mode": "quick_self_prepare", "source_mode": "x"}
if reject_user_mode_fields(legit) != legit:
    fails.append("模式字段：合法 mode 字段被误删")
if not FORBIDDEN_USER_MODE_FIELDS.isdisjoint(legit):
    fails.append("模式字段：拒绝集合与合法字段交集非空")
# test_system_mode_schedule_is_allowed
from mode_schedule import load_mode_schedule, mode_schedule_hash  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    p = pathlib.Path(td) / "ms.json"
    p.write_text(json.dumps({
        "mode_schedule": {"2026-09-15": "hormone_balance", "2026-09-16": "keto_biologic"},
        "mode_summary": {"keto_days": 1, "hormone_days": 1}}), encoding="utf-8")
    data, h = load_mode_schedule(str(p))
    if not h or data["mode_summary"]["keto_days"] != 1:
        fails.append("模式字段：系统派生 mode_schedule 未正常加载")
# test_cycle_fact_change_invalidates_mode_schedule（周期事实变化 → 旧推算失效 → 重算哈希必变）
a = {"mode_schedule": {"2026-09-15": "keto_biologic"},
     "mode_summary": {"keto_days": 1, "hormone_days": 0}}
b = {"mode_schedule": {"2026-09-15": "hormone_balance"},
     "mode_summary": {"keto_days": 0, "hormone_days": 1}}
if mode_schedule_hash(a) == mode_schedule_hash(b):
    fails.append("模式字段：周期事实变化后哈希未失效")

# ---------- 4. 人工覆写闭环 ----------
OV = ROOT / "data/audit/review-overrides.json"
ov_bak = OV.read_bytes()
MF = ROOT / "data/library-manifest.json"
mf_bak = MF.read_bytes()
GATE_OK_NOTE = "round64_1-test-restore"
try:
    ov = json.loads(ov_bak.decode("utf-8"))
    # test_approved_override_is_in_artifact_hashes
    rel = json.loads(mf_bak.decode("utf-8"))["release"]
    if "review_overrides" not in (rel.get("artifact_hashes") or {}):
        fails.append("覆写：review-overrides.json 未纳入 artifact_hashes")
    for o in ov["overrides"]:
        for f in ("source_recipe_hash", "taxonomy_bundle_hash",
                  "ingredient_catalog_hash", "reason_code"):
            if not o.get(f):
                fails.append(f"覆写：{o.get('recipe_id')} 缺绑定字段 {f}")
        if o.get("status") == "pending_reclassify":
            fails.append("覆写：仍存在语义模糊的 pending_reclassify")
    # test_unapproved_override_blocks_release
    ov2 = json.loads(ov_bak.decode("utf-8"))
    ov2["overrides"].append({
        "recipe_id": "htc-001", "field_name": "dish_category",
        "previous_value": "composite_meal", "approved_value": "main_dish",
        "reason_code": "test", "status": "review_required",
        "reviewer": "t", "reviewed_at": "2026-09-15T00:00:00",
        "source_recipe_hash": "sha256:x", "taxonomy_bundle_hash": "sha256:x",
        "ingredient_catalog_hash": "sha256:x"})
    OV.write_text(json.dumps(ov2, ensure_ascii=False), encoding="utf-8")
    r = run("recipe_release_gate.py")
    if "override_review_required" not in r.stdout:
        fails.append(f"覆写：未审核覆写未阻断 release：{r.stdout[:100]}")
    # test_resolved_override_matches_classifier_output（分类器已一致 → 自动转 resolved）
    ov3 = json.loads(ov_bak.decode("utf-8"))
    cls = json.loads((ROOT / "data/recipe-classification.json").read_text(encoding="utf-8"))
    rec = {x["id"]: x for x in cls["records"]}
    o0 = ov3["overrides"][0]
    cur = rec[o0["recipe_id"]][o0["field_name"]]
    o0["approved_value"] = cur  # 构造"分类器已输出批准值"
    OV.write_text(json.dumps(ov3, ensure_ascii=False), encoding="utf-8")
    r = run("recipe_release_gate.py")
    ov4 = json.loads(OV.read_text(encoding="utf-8"))
    if ov4["overrides"][0]["status"] != "resolved_in_classifier":
        fails.append("覆写：分类器一致后未转 resolved_in_classifier")
    # test_override_becomes_stale_after_taxonomy_change
    tax = ROOT / "data/taxonomy/dish-categories.json"
    tax_bak = tax.read_bytes()
    try:
        t = json.loads(tax_bak.decode("utf-8"))
        t["taxonomy_version"] = "9.9.9-stale-test"
        tax.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
        r = run("recipe_release_gate.py")
        if "taxonomy_drift" not in r.stdout and "override_stale" not in r.stdout:
            fails.append(f"覆写：taxonomy 变化未触发阻断：{r.stdout[:100]}")
    finally:
        tax.write_bytes(tax_bak)
finally:
    OV.write_bytes(ov_bak)
    MF.write_bytes(mf_bak)
# 恢复现场：重跑门禁回到 approved
r = run("recipe_release_gate.py", "--approve", "--approved-by", GATE_OK_NOTE)
if '"release_status": "approved"' not in r.stdout:
    fails.append(f"覆写：恢复后门禁未回 approved：{r.stdout[:120]}")

# ---------- 5. 候选漏斗闭合 ----------
aud = json.loads((ROOT / "data/audit/latest-audit.json").read_text(encoding="utf-8"))
eff = aud["effective_candidate_coverage"]
bk = eff["active_time_buckets"]
# test_time_buckets_are_exhaustive_and_mutually_exclusive
if not bk.get("mutually_exclusive") or not bk.get("closure_ok"):
    fails.append("漏斗：时间桶不互斥或不闭合")
if bk["quick_le_15"] + bk["regular_gt_15_le_30"] + bk["slow_gt_30"] \
        + bk["time_unknown"] != eff["after_exact_dedup"]:
    fails.append("漏斗：时间桶总和 ≠ 去重后正餐数")
# test_duplicate_analysis_counts_reconcile
da = eff["exact_duplicate_analysis"]
if da["retained_count"] != da["input_count"] - da["duplicate_record_count"] \
        + da["duplicate_group_count"]:
    fails.append("漏斗：精确重复分析不闭合（keep_first 口径）")
if da.get("canonical_selection_policy") != "keep_first":
    fails.append("漏斗：缺 canonical_selection_policy")
# test_protein_family_coverage_uses_effective_candidates
pfc = eff.get("protein_family_coverage") or {}
if not pfc or sum(v["total"] for v in pfc.values()) != eff["after_exact_dedup"]:
    fails.append("漏斗：蛋白族切片总数与去重正餐数不符")
for k, v in pfc.items():
    for f in ("diversity_fingerprints", "solo_quick", "solo_regular",
              "household_regular", "common_equipment", "price_resolvable"):
        if f not in v:
            fails.append(f"漏斗：{k} 切片缺 {f}")
            break

# ---------- 6. 发布不变量 ----------
invp = ROOT / "data/release-invariants.json"
if not invp.exists():
    fails.append("不变量：release-invariants.json 不存在（须由打包入口生成）")
else:
    inv = json.loads(invp.read_text(encoding="utf-8"))
    # test_release_invariants_match_manifest_build_id
    rel = json.loads(MF.read_text(encoding="utf-8"))["release"]
    if inv["build_id"] != rel["build_id"]:
        fails.append("不变量：build_id 与 manifest 不一致")
    # 当前硬不变量全部满足
    for k, v in inv["hard_expectations"].items():
        if inv["invariants"].get(k) != v:
            fails.append(f"不变量：{k}={inv['invariants'].get(k)}，期望 {v}")
    # test_release_summary_is_not_machine_gate_input
    sm = (ROOT / "reports/release-summary.md").read_text(encoding="utf-8")
    if "机器门禁以 data/release-invariants.json 为准" not in sm:
        fails.append("不变量：release-summary.md 未声明非门禁输入")
    gate_src = (ROOT / "scripts/recipe_release_gate.py").read_text(encoding="utf-8")
    if "release-summary" in gate_src:
        fails.append("不变量：release gate 不应读取展示摘要")
    # test_false_hard_invariant_blocks_package_release
    rp_src = (ROOT / "scripts/release_pack.py").read_text(encoding="utf-8")
    if 'hard_fails.append("release_invariants")' not in rp_src:
        fails.append("不变量：硬不变量失败未接入打包硬门禁")
    # 生成时点早于打包（不变量须随包发布）
    if rp_src.index("build_release_invariants(") > rp_src.index("build_zip(out)"):
        fails.append("不变量：生成晚于打包，无法随包发布")

# ---------- 汇总 ----------
if fails:
    print("round64.1 回归失败：")
    for f in fails:
        print(" ✗", f)
    sys.exit(1)
print("round64.1 回归全部通过（文档一致 / 字段边界 / 覆写闭环 / 漏斗闭合 / 发布不变量）")
