# -*- coding: utf-8 -*-
"""round68（2026-09-18）：模式营养语义回归。

对应《月食yueshi-1.4.3营养语义与最终验收改进方案》§6/§7/§12：
- 两种模式均有结构化目标（热量/安全线/净碳水/蛋白四字段/脂肪下限）；
- 目标来自 approved 参数（source_rule_id 可追溯）；
- 目标进入每日目标编译、篮子、ranker（模式约束差异真实存在）；
- 渲染器不定义目标；安全规则优先；模式显示名与内部枚举一致；
- 新手保守策略有文档依据。
"""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import run_mode_semantics_regression as msr  # noqa: E402
import visible_messages as vm  # noqa: E402

fails = []
with tempfile.TemporaryDirectory() as td:
    report, path = msr.run_regression(td)
    if not os.path.exists(path):
        fails.append("mode-semantics-regression.json 未生成")

# 1) 交叉检查
for k, v in report["cross_mode_checks"].items():
    if not v:
        fails.append("交叉检查未通过：%s" % k)

# 2) 两种模式结构化目标与来源
fx = {f["mode"]: f for f in report["fixtures"]}
if fx.get("hormone_balance", {}).get("display_name") != "平衡激素模式":
    fails.append("hormone_balance 显示名错误")
if fx.get("keto_biologic", {}).get("display_name") != "酮生物模式":
    fails.append("keto_biologic 显示名错误")
required_target_keys = ("calories_target_kcal", "calorie_safety_floor_kcal",
                        "net_carb_max_g", "protein_safety_floor_g",
                        "protein_individual_target_g", "protein_tolerance_upper_g",
                        "fat_min_energy_pct")
for mode, f in fx.items():
    if f.get("validation") != "passed":
        fails.append("%s 目标校验未通过：%s" % (mode, f.get("validation_errors")))
    if not f.get("source_rule_ids"):
        fails.append("%s 缺参数来源" % mode)
    missing = [k for k in required_target_keys if k not in (f.get("targets") or {})]
    if missing:
        fails.append("%s 目标缺字段：%s" % (mode, missing))

# 3) 预期差异
h = report["targets"]["hormone"]
k = report["targets"]["keto"]
if not k["net_carb_max_g"] < h["net_carb_max_g"]:
    fails.append("酮生物净碳水上限应低于平衡激素")
if not k["fat_min_energy_pct"] > h["fat_min_energy_pct"]:
    fails.append("酮生物脂肪下限应高于平衡激素")
if k["protein_book_reference_g"] == h["protein_book_reference_g"]:
    fails.append("两模式蛋白参考值应不同")

# 4) 参数可追溯：来源规则对应的参数均为 approved
params = json.load(open(os.path.join(ROOT, "data", "effective-parameters.json"),
                        encoding="utf-8"))["parameters"]
approved_rules = {p["source_rule_id"] for p in params
                  if p.get("audit_status") == "approved"}
for mode, f in fx.items():
    for rid in f["source_rule_ids"]:
        if rid not in approved_rules:
            fails.append("%s 来源规则未 approved：%s" % (mode, rid))

# 5) 目标进入篮子与 ranker（约束差异）
if fx["hormone_balance"]["basket_summary"]["carbohydrates"] == \
        fx["keto_biologic"]["basket_summary"]["carbohydrates"]:
    fails.append("两模式篮子碳水约束无差异")
if fx["hormone_balance"]["ranker"]["mode_label"] != "hormone":
    fails.append("hormone ranker 模式标签错误")
if fx["keto_biologic"]["ranker"]["mode_label"] != "keto":
    fails.append("keto ranker 模式标签错误")

# 6) 安全优先与保守策略文档
if not h["calorie_safety_floor_kcal"] > 0 or not h["protein_safety_floor_g"] <= h["protein_individual_target_g"]:
    fails.append("安全线/蛋白地板数值异常")
runtime = open(os.path.join(ROOT, "references", "runtime-rules.md"), encoding="utf-8").read()
if "更保守" not in runtime:
    fails.append("缺保守参数规则（runtime-rules）")
safety = open(os.path.join(ROOT, "references", "safety-rules.md"), encoding="utf-8").read()
if "热量不低于安全线" not in safety or "蛋白质不低于安全下限" not in safety:
    fails.append("安全规则优先级声明缺失")

# 7) 显示映射一致性
rules = vm.load_mode_display()
if vm.mode_display("hormone_balance", rules)["display_name"] != "平衡激素模式":
    fails.append("显示映射：hormone_balance")
if vm.mode_display("keto_biologic", rules)["display_name"] != "酮生物模式":
    fails.append("显示映射：keto_biologic")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round68 模式营养语义回归全部通过")
print("cross:", json.dumps(report["cross_mode_checks"], ensure_ascii=False))
