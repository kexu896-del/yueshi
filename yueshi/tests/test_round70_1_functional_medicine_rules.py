# -*- coding: utf-8 -*-
"""round70.1（2026-09-21）：功能医学五书 A 级 84 条规则库落地。

断言：
- 注册表完整性：84 条、每书条数 14/17/23/14/16、id 唯一、字段与枚举合法；
- 数值门禁：numeric_policy=reference_only、规则不含生产参数字段、自动提示不含阈值/剂量/检验值；
- 选择器：确定性、tip_key 去重、协议/安全/监测/数值类永不进入自动提示、情境标签按需生效；
- 用户表达门禁：全部自动提示通过 render_plan 禁用词与内部表达检查；
- 集成：选中提示并入 golden 计划后渲染校验通过（执行提醒 ≤5 条）。
"""
import copy, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import functional_medicine_rules as fmr  # noqa: E402
import render_plan as rp  # noqa: E402

fails = []

# ---------- 1) 注册表完整性 ----------
reg = fmr.load_registry()
rules = reg.get("rules") or []
if len(rules) != 84:
    fails.append("规则总数应为 84，实际 %d" % len(rules))
counts = {}
for r in rules:
    counts[r["book"]] = counts.get(r["book"], 0) + 1
expected_counts = {"deep-nutrition": 14, "good-energy": 17, "the-disease-delusion": 23,
                   "why-we-get-sick": 14, "beat-autoimmune": 16}
if counts != expected_counts:
    fails.append("每书条数不符：%s" % counts)
ids = [r["rule_id"] for r in rules]
if len(ids) != len(set(ids)):
    fails.append("rule_id 存在重复")
errors = fmr.validate_registry(reg)
if errors:
    fails.append("validate_registry 失败：%s" % errors[:3])

# ---------- 2) 数值门禁 ----------
if reg.get("numeric_policy") != "reference_only":
    fails.append("numeric_policy 应为 reference_only")
for r in rules:
    if "parameter_id" in r or "effective_parameter_id" in r:
        fails.append("%s 含生产参数字段" % r["rule_id"])
auto_rules = [r for r in rules if r["auto_tip"]]
if not auto_rules:
    fails.append("无任何 auto_tip 规则")
for r in auto_rules:
    text = r["tip_text"]
    for pat in fmr.TIP_BANNED_PATTERNS:
        import re as _re
        if _re.search(pat, text):
            fails.append("%s 自动提示含数值型主张：%s" % (r["rule_id"], text))

# 数值型规则必须留在非自动层
for rid in ("FM-DN-04", "FM-WW-02", "FM-WW-03", "FM-WW-14"):
    rule = next((x for x in rules if x["rule_id"] == rid), None)
    if not rule or rule["auto_tip"]:
        fails.append("%s 属数值型主张，必须 auto_tip=false" % rid)

# ---------- 3) 选择器 ----------
t1 = fmr.select_tips("keto_biologic")
t2 = fmr.select_tips("keto_biologic")
if t1 != t2:
    fails.append("select_tips 非确定性")
keys = [x["tip_key"] for x in t1]
if len(keys) != len(set(keys)):
    fails.append("select_tips 未按 tip_key 去重")
for banned_id in ("FM-BA-01", "FM-DD-15", "FM-BA-16", "FM-DN-10", "FM-DN-11",
                  "FM-WW-11", "FM-WW-12", "FM-WW-13", "FM-WW-14", "FM-BA-15"):
    if any(x["rule_id"] == banned_id for x in t1):
        fails.append("协议/安全/监测类规则不得进入自动提示：%s" % banned_id)
if any(x["category"] == "monitoring" for x in t1):
    fails.append("monitoring 类不得进入自动提示")
# 情境标签：无情境不出现，给情境才出现
plain = fmr.select_tips("keto_biologic")
if any(x["rule_id"] in ("FM-DD-12", "FM-DD-18") for x in plain):
    fails.append("情境专属规则在无情境时被选中")
with_ctx = fmr.select_tips("keto_biologic", ["menopause", "vegetarian"])
if not any(x["rule_id"] == "FM-DD-18" for x in with_ctx):
    fails.append("menopause 情境未启用 FM-DD-18")
if not any(x["rule_id"] == "FM-DD-12" for x in with_ctx):
    fails.append("vegetarian 情境未启用 FM-DD-12")
# 限制条数
if len(fmr.select_tips("keto_biologic", limit=2)) != 2:
    fails.append("limit 参数未生效")

# ---------- 4) 用户表达门禁 ----------
for r in auto_rules:
    text = r["tip_text"]
    for phrase in rp.BANNED_USER_FACING_PHRASES:
        if phrase in text:
            fails.append("%s 提示含禁用表达 %s：%s" % (r["rule_id"], phrase, text))
    for term in rp.BANNED_TITLE_TERMS:
        if term in text:
            fails.append("%s 提示含内部术语 %s：%s" % (r["rule_id"], term, text))

# 反向探针：坏规则必须被 validate_registry 拦下
bad = copy.deepcopy(reg)
bad["rules"].append({"rule_id": "FM-XX-99", "book": "good-energy", "category": "food_selection",
                     "applies_to": ["*"], "auto_tip": True, "tip_key": "bad",
                     "tip_text": "每天补充 5mg 叶酸", "note": "探针"})
probe = fmr.validate_registry(bad)
if not any("数值型主张" in e for e in probe):
    fails.append("数值型提示未被校验拦截")
bad2 = copy.deepcopy(reg)
bad2["rules"].append({"rule_id": "FM-XX-98", "book": "good-energy", "category": "food_selection",
                      "applies_to": ["*"], "auto_tip": True, "tip_key": "bad2",
                      "tip_text": "热量补偿加餐说明在这里", "note": "探针"})
probe2 = fmr.validate_registry(bad2)
if not any("内部表达" in e for e in probe2):
    fails.append("内部表达提示未被校验拦截")
bad3 = copy.deepcopy(reg)
bad3["rules"].append({"rule_id": "FM-XX-97", "book": "good-energy", "category": "food_selection",
                      "applies_to": ["*"], "auto_tip": True, "tip_key": "bad3",
                      "tip_text": "正常长度的一条提示文案", "note": "探针",
                      "parameter_id": "fm_x"})
probe3 = fmr.validate_registry(bad3)
if not any("生产参数字段" in e for e in probe3):
    fails.append("生产参数字段未被校验拦截")

# ---------- 5) 集成：提示并入计划后渲染通过 ----------
plan = json.loads(open(os.path.join(ROOT, "data/golden/golden-sample-plan.json"),
                       encoding="utf-8").read())
picked = fmr.select_tips("hormone_balance", limit=1)
plan["execution_tips"] = list(plan.get("execution_tips") or []) + [picked[0]["tip_text"]]
if len(plan["execution_tips"]) > 5:
    fails.append("并入后执行提醒超过 5 条")
html = rp.render_document(plan, fmt="html")
errs = rp.validate_html(html, plan)
if errs:
    fails.append("并入功能医学提示后渲染校验失败：%s" % errs[:2])
if picked[0]["tip_text"] not in html:
    fails.append("选中提示未出现在渲染结果中")

# ---------- 6) CLI 校验入口 ----------
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
r = subprocess.run([sys.executable, "-X", "utf8",
                    os.path.join(ROOT, "scripts", "functional_medicine_rules.py"), "--validate"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
if r.returncode != 0:
    fails.append("CLI --validate 未通过：%s" % (r.stdout or r.stderr)[-200:])

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round70.1 功能医学规则库（84 条）+ 选择器 + 门禁全部通过")
