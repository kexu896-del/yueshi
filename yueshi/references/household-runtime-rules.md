# 家庭模式运行规则（household-runtime-rules）

> 状态：已并入（round41）· 与 `schemas/` RC2 契约配套 · 待评审后并入 `references/runtime-rules.md` 或作为独立规则文件。
> 适用：`plan_mode` = `shared_uniform` / `shared_meal_personalized` / `split_safety_required`。
> 与单人 runtime-rules 的关系：单人规则为基底（餐次三态、价格三层、预选闭环、采购输出、断食窗口、生成约束全部继承），本文只写家庭增量；冲突时按 SKILL.md 的领域裁决，安全规则永远最高。
> 核心不变量（冻结）：①每餐 `household_ingredients` 总量 = Σ `member_portions` + 可解释损耗/剩余；②个人营养只读 `member_portions`，禁止家庭总量除以人数；③营养一律按 `quantity.canonical_grams` 计算；④数值全部由脚本计算，模型只填决策字段。

## 1. 模式触发与识别

- 用户提及多人共餐（"双人""我们俩""一家人"）或同餐不同量 → 在"关键八项"阶段确认 `plan_mode`。
- `split_safety_required`：任一成员之间存在过敏、严格医嘱、宗教饮食冲突 → **直接进入本模式**，不经追问降级为共锅。
- 多人场景**不静默降级为 solo**：未确认前按 `user_input_required` 处理。
- 家庭摘要页最多并排展示 **3 名成员**；成员总数可大于 3，超出部分渲染为成员附页；超过正式支持的 max_members 时生成前返回 user_input_required，不在渲染阶段静默截断。

## 2. 家庭信息采集（与关键八项合并为同一轮）

一次追问合并（不额外开第二轮；不逐成员反复追问）：

1. 一起吃饭人数与成员代号（如"我/他/孩子"，标明谁是发起人）；
2. 哪些餐一起吃（早/午/晚分别）；
3. 各成员安全限制（过敏原/医嘱/宗教饮食，共锅判定前必须完整）；
4. 默认共锅策略（同意共锅 / 某些餐必须分锅）；
5. 份量精度（精确克数核算 / 食量档位：吃得少·正常·吃得多）；
6. 谁做饭 + 每餐时间上限（新增第 9 问：共享菜复杂度必须受该成员约束）。

- 只对 `precision_level=exact` 的成员收集身高、体重、年龄、活动量；`portion_band` 成员不填。
- 追问只有一轮；答不出按可保存默认值处理（如"都同意共锅""份量按档位"）。

## 3. 成员模型

- `primary` 固定为发起请求的用户（3 人以上摘要以 primary 为对象）。
- `display_label` 为用户可见标签（减重份 / 健康调理份 / 儿童份），不暴露不必要个人资料。
- 绝经/更年期 + 减重成员：蛋白 floor ≥ 1.1g/kg、每日钙来源 ≥ 1 份（牛奶/豆制品），写入该成员 nutrition_target。
- 所有成员限制在共锅判定（第 4 节）之前完成登记，之后不可由预选恢复。

## 4. 共锅安全判定（两级）

- `household_default_cooking_gate`：家庭默认判定；`shared_meal.cooking_gate_override`：单餐覆盖（无覆盖继承默认）。
- 差异处理表：

| 差异类型 | 处理 |
|---|---|
| 减重 vs 维持、食量差异 | 可共锅，调个人主食与蛋白份量 |
| 辣度/酸味/香菜等偏好 | L0 共享基础味 + L1 桌边调味，不另开锅 |
| 低盐/忌辣（非医嘱） | L0 清淡基础味解决；L2 先盛出后补味（仅炒/烩/焖类） |
| 普通主食量差异 | 主食独立分装 |
| 过敏、严格医嘱、宗教冲突、交叉接触风险 | **不得共锅**：`split_safety_required`（分锅/分餐，或该餐不生成共享菜） |

- L3 一致性：`seasoning_strategy.level=L3_separate` 时，对应 gate 必须满足 `same_pot_allowed=false` 或 `separate_cookware_required=true`，语义不得打架。

## 5. 调味四级（seasoning_strategy）

| 级别 | 适用 | 执行 | 增加锅具 |
|---|---|---|---|
| L0 共享基础味 | 普通家庭默认 | 整锅清淡、不过咸、不预先重辣 | 否 |
| L1 桌边调味 | 有人喜辣/重口 | 辣椒油、酱汁、蘸料盛盘后个人添加 | 否 |
| L2 同锅先盛后补味 | 儿童/低盐成员 | 熟后先盛出基础份，原锅补味 30-60 秒（仅炒/烩/焖类） | 否 |
| L3 分锅/分餐 | 过敏/医嘱/宗教/交叉接触 | 独立锅具或不生成共享菜 | 是 |
| not_applicable | 牛奶/水煮蛋/蒸玉米等原味餐 | 不填 | — |

- 普通减重/维持/调理之间不为盐、醋、辣椒碎建立营养分账。
- 共锅油脂默认计入家庭基础菜，按成员实际盛取比例分配。
- 仅高能量桌边加料（辣椒油、芝麻酱）计入个人营养（`affects_member_nutrition=true` 时才记录个人增量）。
- 低盐仅在医嘱或用户明确要求时成为硬约束；普通"口味偏淡"由 L0 解决。

## 6. 分量方法（portion_method）与约束

六类：`exact_split`（分别列克数）/ `component_split`（关键组件克数、汤汁共享）/ `ratio_split`（按重量比例）/ `equal_split`（各半）/ `separate_before_seasoning`（先盛出某成员份）/ `separate_cookware`（分锅）。

- **ratio_split**：必填 `portion_ratios`（每成员 pct_min/pct_max）+ `portion_deviation`；`selected_pct` 由脚本生成且 Σ=100，渲染器不得临时猜比例；置信度联动——单成员最大区间宽度 >10pp 不得 high、>20pp 不得 medium；Σmin≤100 且 Σmax≥100。
- 集合不变量：`participant_member_ids` = `member_portions` 的 member_id 集合；`not_participating` 不得进入；`uncertain` 可以进入（份量为暂定，计入采购，选菜优先可保存结构）。
- **早餐同样必须拆分**（鸡蛋、牛奶是可分离关键营养源）。
- 每餐必须有 `portion_method`；混合菜无法精确拆分时，把差异转移到可分离主食、乳品或加餐。
- 初始分配用 `portion_seed`（如 staple 1.5 / protein 1.15），但**不得作为最终份量**；最终份量 = 初始分配 + 个人营养调整器结果。

## 7. 执行节奏（防慢，家庭模式硬性要求）

1. 菜谱检索与共锅装配**只运行一次**（不为每位成员各跑一遍）。
2. 成员营养目标**批量计算**；份量一次性求解。
3. 全局营养微调**最多两轮**；之后冻结 `base_plan.json`。
4. 个人调整顺序：个人主食份量 → 可单独盛取的肉块/豆腐/鸡蛋 → 个人牛奶/酸奶/加餐 → 后置油脂/酱汁 → 个人独立小配菜；**两位成员都无法达标时才换共享菜**。
5. 数值全部脚本算（household_portion_allocator / household_nutrition_validator / household_shopping_aggregator），模型只填决策字段（菜名、portion_method、缺席意图等）。
6. 缺席/变化只合并 patch 并局部重算，见第 9 节。

## 8. 采购三本账

- 采购表**一行一个 ingredient_id**，禁止斜杠合并、禁止"按需"统一量、禁止一个价格代表多食材。
- `household_required_amount`（家庭需求）/ `inventory_used_amount`（库存取用）/ `new_purchase_amount`（新购，按包装规格取整）三本账分离；新购 = 需求 − 库存取用。
- 库存食材显示"库存（参考 X 元/规格）"；本周实际支出只计新购，含库存折算为全口径参考，不与现金预算混淆。
- 条件采购独立字段（`purchase_condition`），禁止塞进食材名称（如"家中库存不足时补买"）。
- 包装量用 `package_quantity`，不与营养 quantity 混用。
- 剩菜按最大食量成员评估（`leftover_attribution`，默认男方足量者）。

## 9. 缺席与变化（三层文件 + patch 管线）

- `base_plan.json` 冻结后**不修改**；缺席/确认变化写入 `overrides_YYYYMMDD.json`；渲染前由 `household_override_merger` 合并出 `effective_plan.json`（派生物，非权威源，不作为下次生成输入）。
- **计划期不确定**：`attendance_plan=uncertain`（份量计入采购、选菜优先可保存结构）+ `pending_attendance_resolution`（deadline + auto_resolve=confirm_absent/keep_plan）。
- **事后变化**（patch 只记录已发生/已确认）：
  - `absent`：按 `known_at` 四时机处理（采购前→减采购；采购后→剩余去向；烹饪前→减量；烹饪后→剩余份转便当/冷冻）；必填 `action`；可选引用 `leftover_plan_id`。
  - `external_meal`：该餐该成员份量不计家庭账、不产生 leftover、不触发 nutrition_transfer；仅 `known_at=before_shopping` 时允许 `shopping_delta`（destination 只能 reduce_purchase）。
  - `present_confirmed`：仅关闭 uncertain；不要求 action，禁止 shopping_delta/leftover_plan_id。
- **局部重算范围**：受影响 meal 的 household_ingredients、该餐 member_portions、当日成员营养、采购差量（shopping_delta）、leftover_plan。**不**重跑菜谱检索、不重建整周、不改未受影响日期、不改 plan_mode。
- 3 人缺席：剩余成员 `selected_pct` 由合并器重新归一化并重算该餐份量。
- 缺席若触发整周重建：记 **audit warning** 并回滚为局部重算路径，不判 fatal。

## 10. 复用链与文案派生

- 复用链（首炖/二炖、泡发、解冻）用 `reuse_chain` 绑定 meal_id 与日期；所有"周几/日期"建议文本由字段派生，禁止手写。
- 用户可见日期必须与 meal 日期一致，不一致视为渲染门禁失败。

## 11. 术语映射（用户可见文字）

内部字段不得进入用户可见文字。家庭模式追加映射：`portion_method`→盛取方式；`external_meal`→外食；`uncertain`→待定；`member_portions`→各人份量；`shared_base`→共享基础味；`leftover_plan`→剩余安排；`attendance_override`→就餐变化；`selected_pct`→实际分配比例。

## 12. 渲染与门禁联动

- 渲染前置：`household_override_merger` 合并 effective_plan（无 override 走 identity merge）→ effective Schema 校验 → 统一渲染管线；成员营养块为独立行组件，禁止超长竖线拼接。
- >3 名成员：PDF 摘要页（目标用户 + 份量档位）+ 成员附页；完整个人明细放网页折叠区或附表。
- 入口门禁追加（plan_mode ∈ household_plan_modes 时）：`household_validation` 检查（总量=分量之和、出席集合、ratio 置信度、leftover 去向、nutrition_transfer 一致、引用校验器全部检查项、check 完整性）随 SKILL.md 入口门禁执行。
