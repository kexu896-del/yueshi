# -*- coding: utf-8 -*-
"""round60 回归：早餐语义 / 模式一致性(M11) / 删除反馈四档 / 指纹去重与 D01–D07 / 时令证据链 S01–S04。"""
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


# ---------- 1. 早餐语义（P0-1）----------
need("references/runtime-rules.md", "餐次语义映射表（round60 定稿：简单解决 ≠ 不计划、不采购）", "P0-1")
need("references/runtime-rules.md", "quick_self_prepare", "P0-1")
need("references/runtime-rules.md", "不得路由为 guidance_only", "P0-1")
need("references/runtime-rules.md", "只有\"只给原则/不用安排/不纳入这份计划\"类明确表达才允许 guidance_only", "P0-1")
need("references/questionnaire.md", "自己简单解决", "P0-1")
need("workflows/procurement-flow.md", "B01", "P0-1")
need("workflows/procurement-flow.md", "简单、快手、随便做\"不是合法降级理由", "P0-1")
need("SKILL.md", "同样不等于\"不做这餐\"", "P0-1")
need("SKILL.md", "B01. [auto_fix] planned 且 include_in_procurement=true", "P0-1")
need("references/nutrition-routing.md", "必须计入营养计算", "P0-1")

# ---------- 2. 模式一致性（P0-2 / M11）----------
need("references/runtime-rules.md", "模式参数唯一来源（round60 定稿）", "M11")
need("references/output-policy.md", "mode_schedule_mismatch", "M11")
need("workflows/planning-flow.md", "4.5 | 冻结模式计划（round60）", "M11")
need("SKILL.md", "mode_schedule.json", "M11")

MS = {"plan_id": "t", "mode_schedule": {f"2026-09-{d}": "hormone_balance" for d in range(12, 19)},
      "mode_summary": {"keto_days": 0, "hormone_days": 7}}
with tempfile.TemporaryDirectory() as td:
    msp = pathlib.Path(td) / "ms.json"
    msp.write_text(json.dumps(MS, ensure_ascii=False), encoding="utf-8")

    def run(script, *a):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *a],
                              capture_output=True, text=True)

    # 2a. basket_builder 读取 mode_schedule，hash 出现在输出中
    r = run("basket_builder.py", "--meals-per-day", "1", "--mode-schedule", str(msp),
            "--month", "9", "--budget-tier", "economy", "--seed", "202637")
    if r.returncode != 0:
        fails.append(f"M11：basket_builder --mode-schedule 运行失败 {r.stderr[:200]}")
    else:
        head = r.stdout.split("\n\n")[0]
        try:
            doc = json.loads(head)
            if "mode_schedule_hash" not in doc or doc["mode_summary"]["hormone_days"] != 7:
                fails.append("M11：basket_builder 输出缺 mode_schedule_hash / mode_summary 错误")
            if not doc.get("season_status"):
                fails.append("S02：basket_builder 输出缺 season_status")
        except Exception as e:
            fails.append(f"M11：basket_builder JSON 输出解析失败 {e}")

    # 2b. 手写冲突参数 → M11 失败关闭
    r = run("basket_builder.py", "--meals-per-day", "1", "--mode-schedule", str(msp),
            "--keto-days", "7", "--month", "9")
    if r.returncode == 0 or "mode_schedule_mismatch" not in (r.stderr + r.stdout):
        fails.append("M11：冲突 --keto-days 未失败关闭")

    # 2c. recipe_ranker：--mode-schedule 生效、--mode 冲突失败
    r = run("recipe_ranker.py", "--basket", "鸡腿,鸡蛋,菠菜,西兰花", "--mode-schedule", str(msp),
            "--max-minutes", "25", "--audit-report", str(pathlib.Path(td) / "audit.json"))
    if r.returncode != 0:
        fails.append(f"M11：recipe_ranker --mode-schedule 运行失败 {r.stderr[:200]}")
    else:
        audit = json.loads((pathlib.Path(td) / "audit.json").read_text(encoding="utf-8"))
        if audit["candidate_count_after_dedup"] > audit["candidate_count_before_dedup"]:
            fails.append("P1-1：指纹去重计数异常")
        if audit["candidate_count_after_dedup"] == audit["candidate_count_before_dedup"]:
            fails.append("P1-1：指纹去重未生效（前后计数相同）")
        if audit["mode_schedule_hash"] is None or audit["cuisine_count"] is not None:
            fails.append("P1-3：审计字段缺失或未按 null 约定")
    r = run("recipe_ranker.py", "--basket", "鸡腿", "--mode", "keto", "--mode-schedule", str(msp))
    if r.returncode == 0 or "mode_schedule_mismatch" not in (r.stderr + r.stdout):
        fails.append("M11：冲突 --mode keto 未失败关闭")

    # 2d. mode_summary 与逐日不一致 → invalid/mismatch
    bad = dict(MS)
    bad["mode_summary"] = {"keto_days": 7, "hormone_days": 0}
    bp = pathlib.Path(td) / "bad.json"
    bp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    r = run("basket_builder.py", "--mode-schedule", str(bp))
    if r.returncode == 0 or "mode_schedule" not in (r.stderr + r.stdout):
        fails.append("M11：mode_summary 不一致未失败关闭")

# ---------- 3. 删除反馈四档（P0-3）----------
pref = json.loads((ROOT / "data/ingredient-preference-schema.json").read_text(encoding="utf-8"))
for s in ("persistent_reduce", "temporarily_unavailable"):
    if s not in pref["preference_status"]:
        fails.append(f"P0-3：preference_status 缺 {s}")
need("references/runtime-rules.md", "这周不想吃", "P0-3")
need("references/runtime-rules.md", "本周流程不得恢复该食材", "P0-3")
need("references/runtime-rules.md", "不得读取其他用户个人内容", "P0-3")

with tempfile.TemporaryDirectory() as td:
    basket = {"weekly_basket": {"proteins": ["鸡腿", "猪里脊", "蛤蜊"], "vegetables": ["菠菜", "西兰花"],
                                "carbohydrates": ["南瓜"], "fat_extras": [], "flavor_bases": ["咸鲜"]}}
    bp = pathlib.Path(td) / "b.json"; bp.write_text(json.dumps(basket, ensure_ascii=False), encoding="utf-8")
    prefs = {"preference_status": {"蛤蜊": "persistent_reduce"},
             "history_4w": {"蛤蜊": {"last_week": True, "count_4w": 3}}}
    pp = pathlib.Path(td) / "p.json"; pp.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    cp = pathlib.Path(td) / "c.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/ingredient_preselector.py"),
                        "--build-candidates", "--basket", str(bp), "--month", "9",
                        "--level", "standard", "--meals-per-day", "1",
                        "--preferences", str(pp), "--export-json", str(cp)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fails.append(f"P0-3：preselector 运行失败 {r.stderr[:200]}")
    else:
        cand = json.loads(cp.read_text(encoding="utf-8"))
        clam = next((e for e in cand["layers"]["protein"] if e["display_name"] == "蛤蜊"), None)
        if clam is None:
            fails.append("P0-3：persistent_reduce 被误作硬排除")
        else:
            if "strong_repeat" not in clam["candidate_reason_codes"]:
                fails.append("P1-3：缺 strong_repeat 原因码")
            plain = next(e for e in cand["layers"]["protein"] if e["display_name"] == "鸡腿")
            if clam["score"] >= plain["score"]:
                fails.append("P1-3：历史重复惩罚未降权")

# ---------- 4. 多样性 D01–D07 / 时令 S01–S04 ----------
need("workflows/planning-flow.md", "D01–D07 多样性硬门禁（round60", "D")
need("workflows/planning-flow.md", "相邻自炊餐不得同时为\"快炒＋咸鲜\"组合", "D04")
need("workflows/planning-flow.md", "同一菜谱来源（source_id）不得包揽全部自炊正餐", "D05")
need("workflows/planning-flow.md", "S01–S04 时令门禁（round60）", "S")
need("workflows/planning-flow.md", "找不到审核过的时令数据时不得虚构\"当季\"结论", "S01")
need("scripts/diversity_checker.py", "D04 相邻两顿都是「快炒+咸鲜」", "D04")

# D04 脚本行为：相邻快炒+咸鲜 → 违规
with tempfile.TemporaryDirectory() as td:
    csvp = pathlib.Path(td) / "m.csv"
    csvp.write_text("date,meal,dish,protein,vegetable,method,flavor,structure,texture\n"
                    "2026-09-12,晚餐,洋葱炒鸡蛋,鸡蛋,洋葱,炒,咸鲜,快炒,软\n"
                    "2026-09-13,晚餐,芹菜炒肉丝,猪肉,芹菜,炒,咸鲜,快炒,嫩\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/diversity_checker.py"), str(csvp)],
                       capture_output=True, text=True)
    if "D04" not in r.stdout:
        fails.append("D04：相邻快炒+咸鲜未被识别")

# ---------- 5. 时令证据链数据 ----------
sp = json.loads((ROOT / "data/seasonal-produce-cn.json").read_text(encoding="utf-8"))
if sp["version"] != "1.0.0" or "seasonal-foods.json" not in sp["source"]:
    fails.append("S01：seasonal-produce-cn.json 来源不可追溯")
e9 = sp["months"]["9"][0]
if set(e9) < {"ingredient_id", "season_status", "source_rule_id"} or "seasonal-foods.json#9月" != e9["source_rule_id"]:
    fails.append("S01：时令条目缺 source_rule_id")
need("workflows/planning-flow.md", "data/seasonal-produce-cn.json", "S")
need("SKILL.md", "S01–S04", "S")

# ---------- 6. 目录族标注 ----------
cat = json.loads((ROOT / "data/ingredient-catalog.json").read_text(encoding="utf-8"))
if cat["catalog_version"] != "1.6.0":
    fails.append("目录版本未提升 1.6.0")
if cat["items"]["鸡腿"].get("ingredient_family") != "poultry":
    fails.append("目录缺 ingredient_family 标注")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round60 全部探针与脚本行为命中")
sys.exit(0)
