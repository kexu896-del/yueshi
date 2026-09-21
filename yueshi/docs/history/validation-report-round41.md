# round41 验证报告

## 新增测试

tests/test_round41_household_flow.py：10 组 54 断言，全部通过。

- t01 新文件 6 件存在
- t02 版本号 1.1.0-rc + 6 个触发词在 frontmatter
- t03 13 步分支句 / 完整性门禁 plan_mode 扩展 / 检查项 12–17
- t04 禁用词 7 项抽查 + 显示转换 5 项
- t05 合并器：base 冻结不改、缺席成员份量移除、参与者收缩、attendance 置 not_participating、effective_meta 记录、leftover 引用挂起（用用户 golden 样例跑通）
- t06 ratio_split 缺席重归一 Σ=100、缺席成员剔除
- t07 present_confirmed 只关 uncertain、shopping_delta 减采购 1000→700
- t08 两件 golden 样例过 schema；引用校验器 CLI 可运行
- t09 household_components：份量块显示"盛取方式"且无内部术语；三本账行 4 列齐；成员营养块独立行
- t10 schema 逐字段 not 修复未回退（防 (1) 版缺陷回流）

## 全量回归

39 个测试文件全部通过（pass=39 fail=0）。

唯一失败-修复：test_round37_stable_release.py 断言旧定版号 1.0.0，按草案 §1 升版要求更新为 1.1.0-rc（属预期联动，非回归）。

## 草案合并后自查（草案末尾三项）

- SKILL 引用到的每个家庭文件都存在且可读 ✅（workflows/household-planning-flow.md、references/household-runtime-rules.md、scripts/household_override_merger.py、scripts/household_components.py、schemas/household/）
- 家庭模式执行不再出现"摘要引用超前" ✅（household_components.py 为真实可运行模块，t09 验证）
- solo 路径与 golden sample 无回归 ✅（test_golden_sample、test_round39_consistency 等 39 文件全绿）

## 已知边界

- 统一渲染器消费 effective_plan 全链路、迁移映射、性能基线仍属 RC2-6，未冻结。
- 合并器仅做结构与分配层；营养/采购金额重算接口留给 household_nutrition_validator（草案既定分工）。
