# -*- coding: utf-8 -*-
# round 72 验收：早餐"自己做"语义修正（MEAL-STATE-001 定稿，yueshi-1.4.3-ux-final 冻结）——
# 删除"自己简单解决默认映射为 quick_self_prepare"旧规则；SKILL 入口摘要与
# runtime-rules 正式 owner 规则一致；早餐模板路由不反推难度字段、不作排除依据；
# 历史 breakfast_mode 仅按 schema 映射为 meal_plan_mode。
# 覆盖方案 §3.6 七个必测场景 + §7 第二步实现确认（静态断言 + 构建脚本行为）。
import hashlib
import io
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RR = read("references/runtime-rules.md")
Q = read("references/questionnaire.md")
PF = read("workflows/procurement-flow.md")
NR = read("references/nutrition-routing.md")
RI = read("references/rule-index.md")
MM = read("developer/migration-map.md")
TPL = json.loads(read("data/breakfast-templates.json"))


def test_breakfast_self_cook_maps_to_planned():
    # §3.6-1：自己做 → planned
    assert "| 自己做 / 自己解决（无时间或做法条件） | planned |" in RR
    for doc in (SK, RR):
        assert '"工作日早餐自己做"映射为 `planned`' in doc


def test_breakfast_self_cook_includes_nutrition():
    # §3.6-2：计入营养
    for doc in (SK, RR):
        assert "计入菜单、营养和采购" in doc
    assert "必须计入营养计算" in NR
    # 模板库数据层：每个模板恒为 include_in_nutrition=true
    for t in TPL["templates"]:
        assert t["include_in_nutrition"] is True, t["template_id"]


def test_breakfast_self_cook_includes_procurement():
    # §3.6-3：计入采购（B01 硬约束 + 模板 include_in_procurement）
    assert "B01. [auto_fix] planned 且 include_in_procurement=true" in SK
    assert "B01" in PF
    for t in TPL["templates"]:
        assert t["include_in_procurement"] is True, t["template_id"]


def test_breakfast_self_cook_does_not_imply_quick():
    # §3.6-4：无时间限制不产生 quick_self_prepare；旧默认映射已删除
    for doc in (SK, RR):
        assert "默认映射为 `planned` + `preparation_mode = quick_self_prepare`" not in doc
        assert "默认 planned + quick_self_prepare" not in doc
        assert '不得仅凭"自己做"或"简单解决"写入 `quick_self_prepare`' in doc
    assert "给快手搭配" not in SK  # 旧摘要残留
    assert "默认 planned + quick_self_prepare" not in RI


def test_simple_breakfast_does_not_imply_no_cook():
    # §3.6-5："简单"只是偏好，不自动等于免开火/固定时长
    assert "preparation_preference=simple；不推断时长与免开火" in RR
    assert "不得推断为快手、免开火或固定时长" in Q
    assert "`no_cook_allowed` 和 `advance_prep_allowed` 分别记录，不相互替代" in RR


def test_breakfast_time_limit_requires_explicit_input():
    # §3.6-6：时间上限需用户明确输入；用户明确提出快手要求时仍正常路由
    assert "早上只有几分钟 / 明确给出时间上限 | planned | quick_self_prepare" in RR
    assert "早餐大概几分钟" in Q
    assert "时间证据" in Q and "quick_self_prepare" in Q


def test_simple_breakfast_does_not_downgrade_to_guidance_only():
    # §3.6-7：简单餐次不降级
    for doc in (SK, RR):
        assert "不得降级为 `guidance_only`" in doc
        assert '只有"只给原则/不用安排/不纳入这份计划"类明确表达才允许' in doc


def test_skill_summary_matches_owner_rules():
    # §3.5：入口摘要与正式 owner 规则一致（五条规则句两边同有）
    for sentence in ('"工作日早餐自己做"映射为 `planned`',
                     '同样不等于"不做这餐"，不得降级为 `guidance_only`',
                     "是否属于快手、免开火或提前备餐，应根据用户明确提供的时间和做法条件",
                     '不得仅凭"自己做"或"简单解决"写入 `quick_self_prepare`',
                     "分别记录，不相互替代"):
        assert sentence in SK, f"SKILL 缺：{sentence}"
        assert sentence in RR, f"runtime-rules 缺：{sentence}"


def test_breakfast_templates_not_excluded_without_quick():
    # §7：无 quick 标记的 planned 早餐不被模板库排除；模板路由不回写难度字段
    assert "模板库仅作可选菜品来源、不作排除依据" in RR
    assert "选择模板不回写 `quick_self_prepare` 等难度字段" in RR
    assert len(TPL["templates"]) == 22
    cats = {t["category"] for t in TPL["templates"]}
    assert len(cats) == 10  # 十类覆盖


def test_breakfast_templates_builder_reproducible():
    # §7：模板构建脚本可运行且幂等（重建不改变已发布数据文件）
    path = os.path.join(BASE, "data", "breakfast-templates.json")
    before = hashlib.sha256(open(path, "rb").read()).hexdigest()
    r = subprocess.run([sys.executable,
                        os.path.join(BASE, "scripts", "build_breakfast_templates.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    after = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert before == after, "重建早餐模板库改变了数据文件（非幂等）"


def test_legacy_breakfast_mode_schema_mapping_only():
    # §3.5：历史字段迁移——breakfast_mode 仅按 schema 映射为 meal_plan_mode
    assert "历史数据中的 `breakfast_mode` 仅按 schema 映射为 `meal_plan_mode`" in RR
    assert "breakfast_mode" in MM and "meal_plan_mode" in MM


if __name__ == "__main__":
    mod = sys.modules[__name__]
    fails = 0
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
