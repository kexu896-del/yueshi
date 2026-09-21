# -*- coding: utf-8 -*-
"""round67 最终验收（2026-09-18）：早餐语义 / README 结构 / 模式名称 / 固定查价回归。

对应《月食yueshi-1.4.3最终验收改进方案》§3/§4/§5/§9/§10。
"""
import json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import run_price_regression as rpr  # noqa: E402
import visible_messages as vm  # noqa: E402

fails = []
runtime = open(os.path.join(ROOT, "references", "runtime-rules.md"), encoding="utf-8").read()
questionnaire = open(os.path.join(ROOT, "references", "questionnaire.md"), encoding="utf-8").read()
rule_index = open(os.path.join(ROOT, "references", "rule-index.md"), encoding="utf-8").read()
readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()

# ---------- §3 早餐语义（6 项） ----------
# 1. 自己做 → planned
if "| 自己做 / 自己解决（无时间或做法条件） | planned |" not in runtime:
    fails.append("test_breakfast_self_cook_maps_to_planned：自己做未映射 planned")
if "不得附带 `quick_self_prepare`" not in runtime and "不附带 `quick_self_prepare`" not in runtime:
    fails.append("test_breakfast_self_cook_maps_to_planned：缺不附带 quick 的规则")

# 2. 计入营养与采购
if "计入菜单、营养和采购" not in runtime:
    fails.append("test_breakfast_self_cook_includes_nutrition_and_procurement：缺计入声明")

# 3. 自己做不推断快手
if "不得仅凭" not in runtime or "推断难度" not in runtime:
    fails.append("test_breakfast_self_cook_does_not_imply_quick：缺不得推断难度规则")
if "默认映射为 **planned + quick_self_prepare**" in runtime:
    fails.append("test_breakfast_self_cook_does_not_imply_quick：仍存在旧默认映射")

# 4. 简单不推断免开火
if "preparation_preference=simple" not in runtime:
    fails.append("test_simple_breakfast_does_not_imply_no_cook：简单未记为偏好")
if "不得推断为快手、免开火或固定时长" not in questionnaire:
    fails.append("test_simple_breakfast_does_not_imply_no_cook：问卷缺禁止推断")

# 5. 时间上限需要明确输入
if "早上只有几分钟 / 明确给出时间上限 | planned | quick_self_prepare" not in runtime:
    fails.append("test_breakfast_time_limit_requires_explicit_input：时间证据映射缺失")
if "缺时间条件不得强制写入 quick_self_prepare" not in questionnaire:
    fails.append("test_breakfast_time_limit_requires_explicit_input：问卷缺时间条件要求")

# 6. 简单不降级 guidance_only
if "不得降级为 `guidance_only`" not in runtime:
    fails.append("test_simple_breakfast_does_not_downgrade_to_guidance_only：缺降级禁止")
if "默认 planned + quick_self_prepare" in rule_index:
    fails.append("test_simple_breakfast_does_not_downgrade_to_guidance_only：规则索引仍含旧映射")

# ---------- §4 README 结构（3 项） ----------
m = re.search(r"- \*\*关键八项\*\*：\n((?:  [1-8]\..*\n){8})", readme)
if not m:
    fails.append("test_readme_key_items_are_nested_ordered_list：八项未形成有序子列表（两级缩进）")
else:
    nums = re.findall(r"^  (\d)\. ", m.group(1), re.M)
    if nums != [str(i) for i in range(1, 9)]:
        fails.append("test_readme_key_items_are_nested_ordered_list：编号顺序异常 %s" % nums)
if "\n## 本周采购价格方式" not in readme:
    fails.append("test_price_choice_is_outside_key_eight：价格方式未作为八项之外的独立章节")
if re.search(r"^  9\. ", readme, re.M):
    fails.append("test_readme_markdown_structure_renders_correctly：出现第 9 项")
price_pos = readme.find("## 本周采购价格方式")
items_pos = readme.find("  8. **输出格式**")
if price_pos < items_pos:
    fails.append("test_readme_markdown_structure_renders_correctly：价格方式位于八项之前")
# round71：价格方式为 A/B 两个清晰选项，用户端不暴露内部状态词
for needle in ("**A. 使用叮咚查价助手**", "**B. 使用公开参考价格**", "不会自行默认"):
    if needle not in readme:
        fails.append("test_price_choice_is_outside_key_eight：价格方式缺「%s」" % needle)

# ---------- §5 模式名称（4 项） ----------
rules = vm.load_mode_display()
if (vm.mode_display("hormone_balance", rules) or {}).get("display_name") != "平衡激素模式":
    fails.append("test_hormone_balance_display_name：显示名错误")
if (vm.mode_display("keto_biologic", rules) or {}).get("display_name") != "酮生物模式":
    fails.append("test_keto_biologic_display_name：显示名错误")
for r, ds, fs in os.walk(ROOT):
    if any(s in r for s in ("book-extraction", "__pycache__", ".pytest_cache", "docs", "reports")):
        continue
    for f in fs:
        if not f.endswith((".md", ".py", ".json")) or f in (
                "test_round67_user_expression.py", "test_round67_final_acceptance.py",
                "mode-display.json", "CHANGELOG.md"):
            continue
        if "均衡激素模式" in open(os.path.join(r, f), encoding="utf-8", errors="ignore").read():
            fails.append("test_deprecated_mode_name_absent：%s 含旧称" % f)
if "请选择平衡激素模式" in questionnaire or "请选择酮生物模式" in questionnaire:
    fails.append("test_questionnaire_does_not_offer_mode_selection：问卷出现模式选择")
if "由月食据此推算本周安排" not in questionnaire and "由月食据此推算" not in readme:
    fails.append("test_questionnaire_does_not_offer_mode_selection：缺系统推算表述")

# ---------- §9/§10 固定查价回归（六类食材） ----------
fixture = json.loads(open(os.path.join(ROOT, "data/golden/price-result-round67-sample.json"),
                          encoding="utf-8").read())
with tempfile.TemporaryDirectory() as td:
    summary, report = rpr.run_regression(fixture, None, td, source="fixture")
    if summary["ingredient_count"] != 6:
        fails.append("回归：食材数应为 6，实为 %d" % summary["ingredient_count"])
    if summary["invalid_final_purchase_count"] != 0:
        fails.append("回归：存在无效最终采购 %d 项" % summary["invalid_final_purchase_count"])
    for name in ("price-query-regression.json", "price-result-regression.json",
                 "price-semantic-gate-report.json", "price-regression-summary.md"):
        if not os.path.exists(os.path.join(td, name)):
            fails.append("回归：缺产物 %s" % name)
    by_id = {gi["ingredient_id"]: gi for gi in report["items"]}
    def rej(iid, part):
        return any(part in c["product_name"] for c in by_id[iid]["candidates"]
                   if c["decision"] == "rejected")
    if not rej("猪里脊", "牛小里脊"):
        fails.append("回归：牛小里脊未 rejected")
    if not rej("南瓜", "脆片"):
        fails.append("回归：南瓜脆片未 rejected")
    if not rej("带鱼", "香煎"):
        fails.append("回归：预制带鱼未 rejected")
    if not rej("豆腐", "油豆腐"):
        fails.append("回归：油豆腐未 rejected")
    if by_id["无糖酸奶"]["final_selection"] is not None:
        fails.append("回归：无糖酸奶无候选应回退估价")
    if by_id["无糖酸奶"]["candidates_recalled"] != 0:
        fails.append("回归：无糖酸奶应无候选（fixture）")
    # review_required 不得进入最终采购
    for iid, gi in by_id.items():
        final = gi["final_selection"]
        if final:
            match = next((c for c in gi["candidates"] if c["product_name"] == final), None)
            if not match or match["decision"] != "accepted":
                fails.append("回归：%s 最终采购非 accepted 来源" % iid)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round67 最终验收（早餐/README/模式/固定回归）全部通过")
print("regression summary:", json.dumps(summary, ensure_ascii=False))
