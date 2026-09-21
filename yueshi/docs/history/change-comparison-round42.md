# round42 变更对照（v1.1.0-rc 烟测后修改意见）

依据：《月食家庭版_v1.1.0-rc烟测后修改意见.docx》。3 P0 + 5 P1 + §四契约补强 + §五文字草案 + §六 T01–T08 全部落实。

## P0

| 问题 | 落实 |
|---|---|
| shared_* 漏掉 split_safety_required | SKILL 主线路由第 6 条定义 `household_plan_modes` 集合并声明"禁止前缀匹配"；全文 5 处家庭条件改为集合判定；render_plan.py 新增 HOUSEHOLD_PLAN_MODES 常量；household-runtime-rules.md 同步 |
| 渲染输入名称歧义 | SKILL 渲染架构改写：solo 读校验通过的 plan.json；家庭链路 base+overrides→merger→effective→Schema 校验→统一渲染，渲染器只读校验通过的 effective_plan；统一文件名时总控复制临时构建目录并记录 source_artifact |
| 家庭规则未纳入 rules_bundle_hash | compute_rules_bundle_hash(plan_mode) 家庭模式追加 7 个文件（2 规则 + 5 契约）；SKILL 版本门禁与 output-policy 契约同步说明；T08 验证 |

## P1

| 问题 | 落实 |
|---|---|
| "上限 3 人"与"超 3 人附页"冲突 | 统一为"摘要页最多并排 3 人；成员总数可大于 3 进附页；超 max_members 生成前 user_input_required，不静默截断"（SKILL + runtime-rules + household-runtime-rules 三处） |
| PDF ≤9 页与附页冲突 | 家庭版 = 基础 9 页 + 成员附页预算；SKILL 与 output-policy 均写明"禁止为卡页数降低字号" |
| pending 口径过宽 | H04 改为"仅禁止本次 effective 截止时间前且影响当前输出的 pending"；合并器跳过 merge_status≠applied 的 patch（stderr 记录，源文件保留） |
| 完整性门禁未前置家庭条件 | G01 保留单点定义并写明"生成前即追加校验"；H01–H06 头部注明引用 G01 不重复定义 |
| 检查项编号 | 通用 G01–G11、家庭 H01–H06 |

## §四 契约补强

- 合并器：落盘前 effective Schema 校验（校验器缺失仅警告）、失败不落盘、os.replace 原子写出；T02/T10 负向用例锁定。
- 人数语义：成员主数据不裁剪（T03b 锁定 effective.members 仍 2 人），仅餐次 participant 集合收缩；T04 双向错误模式负向用例。
- leftover 追溯：不向 effective 塞私有字段；经 effective_meta.applied_override_ids → override 源文件追溯（T06c）；渲染若需直接显示剩余安排，由 RC2-6 渲染连线时按契约 leftover_plans 物化，本轮维持不物化（T06a）。

## §六 用例

T01–T08 全部实现于 tests/test_round42_rc2_freeze.py（54 断言，含 T10 原子写出补强）。

## 联动更新（非回归）

- round41 测试：检查项编号 12–17 → H01–H06；合成夹具 merge(validate=False)（落盘前校验由真实 golden 样例 t05 覆盖）。
