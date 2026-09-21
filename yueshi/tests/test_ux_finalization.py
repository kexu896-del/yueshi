# -*- coding: utf-8 -*-
# round 71 验收：用户体验最终收口（yueshi-1.4.3-ux-final）——
# README 普通用户化与维护文档拆分 / 价格方式 A/B 两选项 / 使用过程用户动作化 /
# 问卷一轮补问四区块与条件显示 / 对话暂停点单一动作 / 早餐语义规则句 /
# 输出格式信息深度核对（round56 已覆盖）。
# 纯文本静态断言，仅用标准库。
import io
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


RM = read("README.md")
MT = read("MAINTENANCE.md")
Q = read("references/questionnaire.md")
OP = read("references/output-policy.md")


def test_breakfast_self_cook_does_not_imply_quick():
    # §3.4 规则句：未说明时间限制时不得仅凭"自己做"或"简单解决"写入 quick_self_prepare
    assert "不得仅凭" in Q and "写入 `quick_self_prepare`" in Q
    # round65 语义仍在：简单解决不推断快手/免开火/固定时长
    assert "不得推断为快手、免开火或固定时长" in Q
    assert "缺时间条件不得强制写入 quick_self_prepare" in Q


def test_questionnaire_template_uses_self_cook_example():
    # 问卷模板示例第 4 行使用"工作日早餐自己做"
    assert "工作日早餐自己做" in Q
    tpl = Q.split("## 问卷模板")[1].split("## 必填与默认值")[0]
    assert "工作日早餐自己做" in tpl
    assert "自己简单解决" not in tpl, "模板默认示例不得使用「自己简单解决」"


def test_missing_inputs_are_grouped_in_one_prompt():
    # §6.2 一轮补问四区块
    for heading in ("### 这周为谁安排", "### 哪些餐需要安排",
                    "### 做饭与采购", "### 最终文件"):
        assert heading in Q, f"一轮补问缺区块：{heading}"
    assert "整段回复，不要求逐格填写" in Q


def test_questionnaire_hides_non_applicable_cycle_fields():
    # §6.3 条件显示六条
    for rule in ("不适用周期路线时，不显示周期问题",
                 "未选择叮咚时，不显示查价助手操作",
                 "单人计划不显示家庭成员配置",
                 "选择公开参考价格时，不解释 JSON 回传",
                 "用户没有硬预算时，只询问大致范围和可否少量超出",
                 "用户已明确某项事实时，不重复询问"):
        assert rule in Q, f"条件显示缺规则：{rule}"


def test_estimate_price_choice_hides_helper_instructions():
    # §6.3：公开参考价格路径不解释 JSON 回传（规则落问卷）
    assert "选择公开参考价格时，不解释 JSON 回传" in Q


def test_helper_choice_shows_one_required_action():
    # §5.2 等待查价暂停话术
    assert "请用叮咚查价助手打开这份查价清单，完成后上传价格结果。" in Q


def test_preselection_message_has_single_primary_action():
    # §5.2 食材预选暂停话术 + 信息不足合并补问话术
    assert "请回复不想要的编号；都可以就回复" in Q
    assert "还需要补充以下几项，请一次回复即可" in Q
    assert "不要在同一暂停消息中解释完整内部流程、状态名称或下一阶段算法" in Q


def test_readme_has_natural_language_intro():
    # §6.1 引导语
    assert "不需要逐项填写，按平常说话的方式描述即可" in RM
    assert "缺少的信息，月食会合并成一轮询问" in RM


def test_readme_price_ab_options():
    # §4 价格方式 A/B 两选项
    assert "**A. 使用叮咚查价助手**" in RM
    assert "**B. 使用公开参考价格**" in RM
    assert "如果本周还没有选择，月食会在食材预选时一并询问，不会自行默认" in RM
    # 价格方式为八项之外的独立章节，且位于八项之后
    assert RM.index("## 本周采购价格方式") > RM.index("  8. **输出格式**")


def test_readme_no_internal_price_terms():
    # 用户端不展示内部状态词
    for term in ("use_helper", "use_estimate", "pending", "request_id",
                 "awaiting_price_result", "price_result_received",
                 "opt_out_after_query", "dingdong_price_choice"):
        assert term not in RM, f"README 出现内部词：{term}"


def test_readme_user_flow_is_action_based():
    # §5.1 使用过程五步用户动作
    for step in ("描述实际情况", "删除不想要的食材", "月食生成菜单并检查营养",
                 "选择叮咚时，完成一次查价", "获取最终计划"):
        assert step in RM, f"使用过程缺步骤：{step}"
    assert "## 用户可见的状态流程" not in RM
    assert "收集信息 → 食材预选 → 生成菜单" not in RM


def test_user_readme_does_not_require_running_scripts():
    # 维护者脚本命令块不在 README；明确普通使用不需要运行脚本
    assert "basket_builder.py --meals-per-day" not in RM
    assert "macros_calculator.py" not in RM
    assert "普通使用不需要运行脚本" in RM


def test_maintenance_content_is_separated_or_labeled():
    # MAINTENANCE.md 存在、有面向声明，并承接命令块与目录
    assert "面向开发、维护者和其他 AI；普通用户无需阅读或运行其中命令" in MT
    assert "basket_builder.py --meals-per-day" in MT
    assert "先读 `CHANGELOG.md`" in MT
    assert "## 给维护者 / 其他 AI" in MT and "## 目录" in MT
    # README 不再保留维护者章节，末尾为维护与开发指针块
    assert "## 给维护者 / 其他 AI" not in RM and "\n## 目录" not in RM
    assert "## 维护与开发" in RM
    for p in ("`SKILL.md`", "`CHANGELOG.md`", "`developer/maintenance-map.md`",
              "`MAINTENANCE.md`"):
        assert p in RM, f"维护与开发指针缺：{p}"


def test_readme_keeps_user_sections():
    # §7.2 保留：这是什么 / 叮咚查价助手使用说明 / 各格式差异 / 安全声明
    for h in ("## 这是什么", "## 使用前需要提供的信息", "## 使用过程",
              "## 本周采购价格方式", "### 叮咚查价助手使用说明",
              "## 各格式差异", "## 安全声明"):
        assert h in RM, f"README 缺保留章节：{h}"


def test_pdf_uses_compact_information_level():
    # §9 核对：PDF 固定不展示映射模块（round56 定稿已覆盖）
    assert "PDF 固定不展示" in OP


def test_html_word_markdown_keep_detailed_appendices():
    # §9 核对：HTML/Word/Markdown 保留详细附录（round56 定稿已覆盖）
    assert "HTML 默认完整保留" in OP and "Word 默认保留" in OP and "Markdown 默认保留" in OP


if __name__ == "__main__":
    import sys
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
