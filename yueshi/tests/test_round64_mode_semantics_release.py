# -*- coding: utf-8 -*-
"""round64 回归：模式推算职责纠偏 / 文档真实性 / 发布链防旁路 / 抽样可复现 / 金丝雀。"""
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

# ---------- 1. 问卷不暴露内部模式（test_questionnaire_does_not_expose_internal_mode） ----------
for p in ("references/questionnaire.md", "README.md"):
    for term in ("酮生物", "平衡激素", "keto_biologic", "hormone_balance"):
        deny(p, term, "P0-问卷")
need("README.md", "由月食据此推算本周安排", "P0-问卷")
need("README.md", "是否接受一锅餐、提前备餐、剩余复用和免开火组合", "P0-做法选择")

# ---------- 2. 用户输入内部模式被拒绝（test_user_mode_input_is_rejected） ----------
from mode_schedule import reject_user_mode_fields  # noqa: E402
out = reject_user_mode_fields({"mode": "keto", "budget": 300,
                               "mode_schedule": {"2026-09-15": "keto"}})
if "mode" in out or "mode_schedule" in out:
    fails.append("P0：用户模式字段未被清除")
if out.get("__rejected_mode_fields") != ["mode", "mode_schedule"]:
    fails.append(f"P0：拒绝记录异常 {out.get('__rejected_mode_fields')}")
if reject_user_mode_fields({"budget": 300}) != {"budget": 300}:
    fails.append("P0：合法 payload 被误改")

# ---------- 3. 推算/冻结规则登记（MODE-DERIVE / MODE-FREEZE） ----------
need("references/nutrition-routing.md", "MODE-DERIVE-001", "P0-规则")
need("references/runtime-rules.md", "MODE-INPUT-001", "P0-规则")
need("references/runtime-rules.md", "MODE-FREEZE-001", "P0-规则")
need("references/rule-index.md", "MODE-INPUT-001", "P0-规则索引")
need("references/rule-index.md", "MODE-DERIVE-001", "P0-规则索引")
need("references/rule-index.md", "MODE-FREEZE-001", "P0-规则索引")

# ---------- 4. 周期事实变化触发重新推算（哈希变化；test_cycle_fact_change_recomputes_mode） ----------
from mode_schedule import mode_schedule_hash  # noqa: E402
s1 = {"mode_schedule": {"2026-09-15": "hormone_balance"},
      "mode_summary": {"keto_days": 0, "hormone_days": 1}}
s2 = {"mode_schedule": {"2026-09-15": "keto_biologic"},
      "mode_summary": {"keto_days": 1, "hormone_days": 0}}
if mode_schedule_hash(s1) == mode_schedule_hash(s2):
    fails.append("P0：周期事实变化后 mode_schedule_hash 未变化")

# ---------- 5. 哈希不一致失败关闭（test_mode_schedule_hash_mismatch_fails_closed） ----------
from mode_schedule import load_mode_schedule  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    bad = pathlib.Path(td) / "ms.json"
    bad.write_text(json.dumps({"mode_schedule": {"2026-09-15": "keto"},
                               "mode_summary": {"keto_days": 0, "hormone_days": 1}}),
                   encoding="utf-8")
    try:
        load_mode_schedule(str(bad))
        fails.append("P0：mode_summary 不一致未触发失败关闭")
    except SystemExit as e:
        if "mode_schedule_mismatch" not in str(e):
            fails.append(f"P0：错误码异常 {e}")

# ---------- 6. README 关键八项层级（test_readme_key_items_nested_correctly） ----------
rm = (ROOT / "README.md").read_text(encoding="utf-8")
for i, name in enumerate(("基本情况", "避开事项", "周期情况", "吃饭做饭",
                          "菜系口味", "预算库存", "做法选择", "输出格式"), 1):
    if f"\n  {i}. **{name}**" not in rm:
        fails.append(f"P0-README：关键八项第 {i} 项「{name}」未作为有序子列表（两级缩进）")
need("README.md", "只有在本次计划的食材预选环节明确选择", "I-叮咚时点")

# ---------- 7. SKILL front matter 与残句（test_skill_front_matter_is_valid / no_trailing_dup） ----------
sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n", sk, re.S)
if not m:
    fails.append("P0-SKILL：缺 YAML front matter")
else:
    fm = m.group(1)
    if not re.search(r"^name:\s*yueshi\s*$", fm, re.M):
        fails.append("P0-SKILL：front matter 缺 name")
    if not re.search(r"^version:\s*yueshi-\d+\.\d+\.\d+(-rc\d*)?$", fm, re.M):
        fails.append("P0-SKILL：version 不符合加载器契约 yueshi-X.Y.Z")
lines = [l for l in sk.strip().splitlines() if l.strip()]
if len(lines) >= 2 and lines[-1].strip() == lines[-2].strip():
    fails.append("P0-SKILL：文件末尾存在重复残句")
if sk.count("代替正规治疗的建议。") != 1:
    fails.append("P0-SKILL：残句「代替正规治疗的建议。」未清干净")
# 标题层级连续
prev = 0
for l in sk.splitlines():
    hm = re.match(r"^(#+)\s", l)
    if hm:
        lvl = len(hm.group(1))
        if prev and lvl > prev + 1:
            fails.append(f"P0-SKILL：标题层级跳级 {prev}→{lvl}：{l[:30]}")
            break
        prev = lvl

# ---------- 8. 规则 ID 单一 owner / SKILL 只引用已登记 ID ----------
ri = (ROOT / "references/rule-index.md").read_text(encoding="utf-8")
reg_ids = re.findall(r"^\| ([A-Z]+(?:-[A-Z]+)*-\d{3}) \|", ri, re.M)
if len(reg_ids) != len(set(reg_ids)):
    fails.append("P1-规则索引：规则 ID 重复")
for rid in re.findall(r"[A-Z]+(?:-[A-Z]+)*-\d{3}", sk):
    if rid not in reg_ids:
        fails.append(f"P1-规则索引：SKILL.md 引用了未登记规则 {rid}")

# ---------- 9. 发布链防旁路 ----------
import recipe_ranker as rr  # noqa: E402
ok, reason = rr.verify_release_integrity()
if not ok:
    fails.append(f"P1：当前 approved 库完整性校验应通过，实际 {reason}")

mf_path = ROOT / "data/library-manifest.json"
ri_path = ROOT / "data/recipe-index.json"
mf_bak = mf_path.read_bytes()
ri_bak = ri_path.read_bytes()
try:
    # 9a. 手工把 blocked 改为 approved（artifact_hashes 保留真实值也会因状态来源
    #     非 gate 而不可信——此处模拟“手工放行但未重跑 gate”无哈希场景）
    mf = json.loads(mf_bak.decode("utf-8"))
    rel = dict(mf["release"])
    rel["release_status"] = "approved"
    rel.pop("artifact_hashes", None)
    mf["release"] = rel
    mf_path.write_text(json.dumps(mf, ensure_ascii=False), encoding="utf-8")
    ok, reason = rr.verify_release_integrity()
    if ok:
        fails.append("P1：缺 artifact_hashes 的手工 approved 未被拒绝")

    # 9b. approved 后修改一条菜谱（同 build_id 不同内容哈希）
    mf_path.write_bytes(mf_bak)
    idx = json.loads(ri_bak.decode("utf-8"))
    idx[0]["name"] = str(idx[0].get("name", "x")) + "-tampered"
    ri_path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    ok, reason = rr.verify_release_integrity()
    if ok or "artifact_hash_mismatch" not in reason:
        fails.append(f"P1：批准后篡改菜谱未被拒绝（{ok} {reason}）")
    ri_path.write_bytes(ri_bak)
    ok, reason = rr.verify_release_integrity()
    if not ok:
        fails.append("P1：恢复后完整性校验应通过")
finally:
    mf_path.write_bytes(mf_bak)
    ri_path.write_bytes(ri_bak)

# ---------- 10. taxonomy / 目录漂移 → release gate 拒绝 ----------
tax_path = ROOT / "data/taxonomy/dish-categories.json"
tax_bak = tax_path.read_bytes()
try:
    t = json.loads(tax_bak.decode("utf-8"))
    t["taxonomy_version"] = "9.9.9-drift-test"
    tax_path.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    r = run("recipe_release_gate.py")
    if '"release_status": "blocked"' not in r.stdout or "taxonomy_drift" not in r.stdout:
        fails.append(f"P1：taxonomy 漂移未阻断：{r.stdout[:100]}")
finally:
    tax_path.write_bytes(tax_bak)
# 恢复后重过门禁（保持 approved 与哈希一致）
r = run("recipe_release_gate.py", "--approve", "--approved-by", "round64-test-restore")
if '"release_status": "approved"' not in r.stdout:
    fails.append(f"P1：恢复后门禁应 approved：{r.stdout[:100]}")

# ---------- 11. 抽样可复现（test_audit_sampling_is_reproducible） ----------
hr = json.loads((ROOT / "data/audit/human-review.json").read_text(encoding="utf-8"))
sp = hr.get("sampling") or {}
if sp.get("random_seed") != 63 or sp.get("strategy") != "stratified_plus_risk_based" \
        or not sp.get("population_build_id"):
    fails.append("P1：抽样缺 seed/strategy/population_build_id")
acc = hr.get("accuracy") or {}
for f in ("dish_category", "primary_ingredient_family",
          "primary_protein_family", "overall"):
    if f not in acc:
        fails.append(f"P1：缺分字段准确率 {f}")
if hr.get("sample_split", {}).get("risk", 0) < 1:
    fails.append("P1：风险样本未单独记录")
rv = hr.get("review") or {}
for f in ("correct", "incorrect", "ambiguous", "unresolved",
          "reviewer_count", "disagreement_count"):
    if f not in rv:
        fails.append(f"P1：复核结果缺字段 {f}")
ov = json.loads((ROOT / "data/audit/review-overrides.json").read_text(encoding="utf-8"))
for o in ov.get("overrides", []):
    for f in ("previous_value", "approved_value", "reason_code",
              "reviewer", "reviewed_at"):
        if f not in o:
            fails.append(f"P1：人工覆写缺字段 {f}")

# ---------- 12. 有效候选覆盖（P2） ----------
aud = json.loads((ROOT / "data/audit/latest-audit.json").read_text(encoding="utf-8"))
eff = aud.get("effective_candidate_coverage")
if not eff or eff.get("main_meal_pool", 0) < 1000:
    fails.append("P2：有效候选覆盖缺失或异常")
if eff and "distinct_diversity_fingerprints_by_protein_family" not in eff:
    fails.append("P2：缺各蛋白族独立多样性指纹数")

# ---------- 13. 端到端金丝雀（可执行部分） ----------
# 13a. 单人参考价：approved 库可读、候选非空
r = run("recipe_ranker.py", "--basket", "鸡腿,鸡蛋,菠菜", "--mode", "hormone", "--limit", "5")
if r.returncode != 0 or "候选" not in r.stdout:
    fails.append(f"E2E-单人：ranker 金丝雀失败 {r.stderr[:80]}")
# 13b. 菜谱库被篡改：manifest approved 但内容哈希改变 → ranker 拒绝（不缓存不补全）
try:
    idx = json.loads(ri_bak.decode("utf-8"))
    idx[1]["category"] = "篡改"
    ri_path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    r = run("recipe_ranker.py", "--basket", "鸡腿", "--mode", "hormone")
    if r.returncode == 0 or "release_integrity_failed" not in (r.stderr + r.stdout):
        fails.append("E2E-篡改：ranker 未拒绝被篡改的 approved 库")
finally:
    ri_path.write_bytes(ri_bak)

# ---------- 汇总 ----------
if fails:
    print("round64 回归失败：")
    for f in fails:
        print(" ✗", f)
    sys.exit(1)
print("round64 回归全部通过（模式纠偏 / 文档 lint / 发布链防旁路 / 抽样可复现 / 金丝雀）")
