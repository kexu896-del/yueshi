# -*- coding: utf-8 -*-
# round 57 验收：v1.3.0 封版前一致性收口——
# P0-1 营养管线冻结时机分支化（查价前不冻结最终 plan.json）；
# P0-2 启用叮咚时价格契约纳入规则完整性门禁；
# P1-3 Provider 摘要缩短为指针版（详细表述在 price-provider-policy.md）；
# P1-4 README 章节重排；P1-5 PDF=hidden 固定规则无旧多模式残留；
# P1-6 P09 价格元数据一致性门禁；P2-7 术语门禁扩充；P2-8 README 依赖表述。
import io, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RM = read("README.md")
RR = read("references/runtime-rules.md")
PF = read("workflows/planning-flow.md")
OP = read("references/output-policy.md")
PP = read("references/price-provider-policy.md")
RP = read("scripts/render_plan.py")


def test_freeze_timing_p0():
    # 营养管线：复核后只形成稳定快照；启用叮咚时查价合并后才冻结最终 plan.json
    nut = re.search(r"- \*\*营养管线\*\*：(.*?)\n", SK).group(1)
    assert "稳定快照" in nut and "menu_snapshot_hash" in nut
    assert "才冻结最终 plan.json" in nut
    assert "查价前任何阶段不得冻结最终 plan.json" in nut
    assert "未启用外部查价时" in nut and "启用叮咚查价时" in nut
    # 禁止出现旧的"复核→冻结→渲染"直线口径
    assert "最终复核 → **冻结 plan.json** → 渲染" not in SK
    # planning-flow 步骤 12 同样不提前冻结
    assert "不在本步冻结最终 plan.json" in PF
    assert "未冻结" in PF


def test_integrity_gate_dingdong_extension_p0():
    assert "启用叮咚查价时的追加完整性检查" in SK
    assert "references/price-provider-policy.md" in SK
    assert "schemas/price-query.schema.json" in SK
    assert "schemas/price-result.schema.json" in SK
    assert "scripts/price_result_migrator.py" in SK
    assert "core_rule_file_missing" in SK
    for detail in ("price_provider_contract_missing", "price_query_schema_missing",
                   "price_result_schema_missing", "price_result_migrator_missing"):
        assert detail in SK, detail
    assert "不得伪装成叮咚直采价" in SK
    assert "未启用叮咚时，价格契约文件缺失不影响普通估价流程" in SK


def test_provider_summary_shortened():
    # SKILL 摘要保留关键指针
    for needle in ("外部价格 Provider", "new_purchase_amount > 0",
                   "月食-查价清单.json", "awaiting_price_result",
                   "再冻结最终 plan.json", "PDF 不展示",
                   "references/price-provider-policy.md"):
        assert needle in SK, needle
    # 细节表述移出 SKILL、落在 policy
    for moved in ("没有自动上传通道", "月食-叮咚价格结果.json",
                  "不读取、不保存、不验证具体收货地址",
                  "价格失败只回退价格层",
                  "不重新执行食材预选、菜单装配和营养全流程",
                  "加入购物车、提交订单、支付"):
        assert moved not in SK, f"细节仍留在 SKILL: {moved}"
        assert moved in PP, f"policy 缺: {moved}"
    # 摘要长度收敛（不超过 700 字）
    bullet = re.search(r"- \*\*外部价格 Provider\*\*：(.*?)\n", SK).group(1)
    assert len(bullet) <= 700, len(bullet)


MT = read("MAINTENANCE.md")


def test_readme_structure():
    # round71：README 为纯普通用户向，维护者内容迁入 MAINTENANCE.md
    order = ["## 这是什么", "## 使用前需要提供的信息", "## 使用过程",
             "## 本周采购价格方式", "## 使用叮咚查价时", "## 各格式差异",
             "## 维护与开发", "## 安全声明"]
    pos = [RM.index(h) for h in order]
    assert pos == sorted(pos), "README 章节顺序不符"
    # 叮咚与格式说明是独立 H2，不再是安全声明子项
    assert "### 使用叮咚查价时" not in RM and "### 对应菜单及用量" not in RM
    # 维护者章节已迁出 README
    assert "## 给维护者 / 其他 AI" not in RM and "## 目录" not in RM
    assert "关键八项" in RM
    assert "单人 15 步" in MT and "家庭 13 步" in MT
    # scripts 依赖表述核对后不绝对化冲突（chromium 为非 Python 依赖已注明）
    assert "全部为纯 Python 标准库" in MT and "Chromium" in MT


def test_pdf_hidden_fixed_no_legacy():
    # 旧多模式口径已清除
    assert "PDF 按版面评估选" not in OP
    assert "[meal_usage_map]" not in RP  # 评估日志代码已删
    # 固定配置写死
    assert "{html: full, docx: full, markdown: full, pdf: hidden}" in OP
    assert "不再支持 auto/full/summary" in OP


def test_p09_consistency_gate():
    assert "## 7. 采购门禁 P01–P09" in PP
    assert "P09（round57 新增：价格元数据一致性门禁）" in PP
    assert "price_snapshot_meta.provider" in PP
    assert "result_schema_version" in PP
    assert "不自动选择其中一个值" in PP
    assert "预算卡、采购表和价格说明必须引用同一 `price_result_hash`" in PP
    # 汇总处同步 P01–P09
    assert "P01–P09" in OP and "P01–P09" in RR
    assert "P01–P09 采购门禁（含价格元数据一致性 P09）" in SK
    # validator 执行组件口径保持 P01–P08 + 注明 P09 在合并/渲染侧
    assert "P09 一致性门禁在价格合并/渲染侧执行" in read("developer/maintenance-map.md")


def test_terminology_gate_expanded():
    for term in ("awaiting_price_result", "price_result_received",
                 "opt_out_after_query", "dingdong_helper_opt_in",
                 "menu_snapshot_hash", "nutrition_snapshot_hash",
                 "shopping_demand_hash", "price_result_hash",
                 "migration_log", "provider_product_name",
                 "shopping_meal_usage_map"):
        assert f'"{term}"' in RP, f"BANNED_TITLE_TERMS 缺 {term}"
        assert term in OP, f"术语门禁策略缺 {term}"
    for conv in ("awaiting_price_result → 等待叮咚价格结果",
                 "price_result_received → 已读取价格结果",
                 "opt_out_after_query → 已改用参考价格估算",
                 "migration_log → 文件兼容处理记录"):
        assert conv in OP, conv


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fails = 0
    for name in dir(mod):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
