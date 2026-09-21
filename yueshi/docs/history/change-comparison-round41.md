# round41 变更对照（SKILL 联动修订 · 家庭模式接入入口）

依据：《SKILL联动修订草案》+ household-planning-flow.md + household-runtime-rules.md + household_override_merger.py + household_reference_validator.py（草案版）+ golden 样例 2 件 + 重传 schema 5 件。

## 草案逐条落实

| 草案条目 | 落实 | 位置 |
|---|---|---|
| §1 版本 1.0.0→1.1.0-rc + CHANGELOG | ✅ 已改 frontmatter；CHANGELOG 追加 round41 条目 | SKILL.md / CHANGELOG.md |
| §2 description 触发词 6 个 | ✅ 全部追加 | SKILL.md frontmatter |
| §3 完整性门禁按 plan_mode 扩展 | ✅ 检查项 1 扩展：shared_* 追加校验家庭规则/流程/schemas，缺失→fatal(core_rule_file_missing)，不降级 solo | SKILL.md 检查项 1 |
| §4 固定执行顺序补家庭分支 | ✅ 15 步说明后补 13 步分支句（不得逐成员各跑一遍） | SKILL.md 固定执行顺序 |
| §5 渲染架构补家庭组件 | ✅ 渲染器分工追加 merger + household_components.py + 渲染前置顺序；household_components.py 为新建真实模块（非超前引用） | SKILL.md 渲染架构 / scripts/ |
| §6 术语门禁补家庭词表 | ✅ 禁用词 +11、显示转换 +8 | SKILL.md 术语门禁 |
| §7 入口门禁家庭检查项 | ✅ 追加第 12–17 项（仅 shared_* 执行）；"引用校验器 7 项"按实际写为"全部检查项" | SKILL.md 检查项 12–17 |
| §8 locked_basket 分级复查 | ✅ 草案确认维持现状，无需改 | — |

## 新入库文件

| 文件 | 来源 | 处理 |
|---|---|---|
| workflows/household-planning-flow.md | 用户草案 | 原样入库，状态行改为"已并入（round41）" |
| references/household-runtime-rules.md | 用户草案 | 同上 |
| scripts/household_override_merger.py | 用户草案 | 原样入库（结构+分配层合并器，营养/金额重算留接口） |
| scripts/household_components.py | 本轮新建 | 成员营养块/份量块/三本账行 HTML 组件，消除草案 §5 的超前引用 |
| data/golden/household/samples/golden-*.json | 用户样例 | 原样入库；占位哈希在测试侧按"缺省跳过"口径处理 |

## 与草案/用户输入的两处偏差（已向你说明）

1. **校验器不替换**：草案版 household_reference_validator.py 的 13 项检查已全部被 round40 正式版覆盖（且正式版按餐次粒度输出、与 schema check 枚举一一对应、含 check 完整性）；置信度联动维持生成器自检 `ratio_split_confidence_ok`。正式版保留。
2. **重传 schema 存在回退缺陷，未采用**：(1) 版 shared-definitions 与 bundle 把 round40 修好的逐字段 `not` 退回为多字段 `not: {required: [action, leftover_plan_id]}`——Draft-07 下该写法只在多字段**同时**出现时才拦截，external_meal 只带 leftover_plan_id 会漏检。正式版保持修复态，test_round41 t10 锁定防回归。其余 3 件 schema 与现版完全一致。

## 版本号联动

- test_round37_stable_release.py 的定版断言由 `yueshi-1.0.0` 更新为 `yueshi-1.1.0-rc`（草案 §1 要求"版本必须跟着走"）。
