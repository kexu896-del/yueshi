# 稳定规则 ID 索引

跨版本不变的规则标识。ID 只增不改：规则内容演进时 ID 不变、细则位置可迁移；规则废止时标记 `deprecated` 并保留条目，不删除不复用。

| 规则 ID | 主题 | 一句话规则 | 细则位置 |
|---|---|---|---|
| SAFETY-001 | 安全硬门槛 | 安全、过敏原、热量安全线、蛋白质基础需要、医嘱必须全部满足，不为便利让步 | `references/safety-rules.md` |
| MEAL-STATE-001 | 餐次状态 | "自己简单解决"≠"不做这餐"：默认 planned（不推断快手）；只有明确"不纳入计划"才允许 guidance_only；时间/免开火/提前备餐条件分别记录 | `references/runtime-rules.md` |
| PROCUREMENT-001 | 预选闭环 | 先篮子后菜谱；"都可以吃"=accepted_batch 不是跳过；删除食材不进篮子/菜谱/采购 | `references/runtime-rules.md` |
| PRICE-001 | 价格三层 | direct_public_price / category_estimate / historical_estimate；空价=渲染门禁失败；不可用则替换同功能食材 | `references/runtime-rules.md`、`references/price-provider-policy.md` |
| HOUSEHOLD-001 | 家庭模式 | plan_mode 按集合成员判定 household_plan_modes，禁止字符串前缀匹配；多人不静默降级 solo | `references/household-runtime-rules.md`、`workflows/household-planning-flow.md` |
| MODE-001 | 模式参数一致性（总规则） | 周期模式决策后冻结 mode_schedule.json，下游脚本只读该文件，不一致即 M11 失败关闭；细分边界见 MODE-INPUT-001 / MODE-DERIVE-001 / MODE-FREEZE-001 | `references/runtime-rules.md`、`scripts/common/mode_schedule.py` |
| MODE-INPUT-001 | 用户输入边界 | 用户不得直接选择内部饮食模式（酮生物 / 平衡激素），只提供周期与生活事实；问卷不出现内部模式枚举；用户 payload 携带 mode_schedule/mode 选择字段时拒绝或清除 | `references/runtime-rules.md` |
| MODE-DERIVE-001 | 系统推算 | 逐日模式由系统按周期事实、安全筛查、断食经验与作息推算；安全冲突采用更保守参数；推算失败进入缺信息追问或保守降级，不转嫁为用户选模式；结果须可追溯至已批准参数 | `references/nutrition-routing.md` |
| MODE-FREEZE-001 | 冻结与只读 | 推算完成后冻结 mode_schedule 及 mode_schedule_hash，下游组件只读；用户纠正周期事实后重新推算而非手工改模式结果 | `references/runtime-rules.md` |
| DIVERSITY-001 | 多样性证据链 | 候选先按多样性指纹去重再参与 D01–D07 整周多样性硬门禁；跨周重复惩罚进入评分 | `workflows/planning-flow.md`、`scripts/diversity_checker.py` |
| SEASON-001 | 时令条件 | "当季/时令"声称必须有 region + month + source_rule_id；数据缺失时停止使用当季表述或转 user_input_required | `data/seasonal-produce-cn.json`、`references/runtime-rules.md` |
| OUTPUT-001 | 输出契约 | plan.json 是唯一中间件，禁止手写 HTML；章节白名单固定顺序；渲染只读校验通过的 plan | `references/output-policy.md` |
| MEAL-SELFCOOK-001 | 自炊与快手分离 | "自己做"只登记 planned + home + self 事实；quick_self_prepare / 15 分钟 / 免开火需用户明确时间或做法证据，否则合并追问 | `references/runtime-rules.md`、`references/questionnaire.md` |
| ROLE-001 | 蛋白候选角色 | 核心候选默认 staple 为主（≥3/5），exploratory ≤1 且需准入条件；不强制水产占位；核心删除触发 4/8 周冷却 | `data/protein-candidate-roles.json`、`scripts/common/candidate_roles.py` |
| FORM-001 | 商品形态门 | 匹配优先级 ingredient_id → 部位 → 生鲜/加工形态 → 预制许可 → 包装 → 价格；命中排除形态即拒绝；validator / 合并层 / 叮咚助手共用 ingredient-catalog.json + product-form-dictionary.json | `scripts/common/product_forms.py`、`scripts/price_result_validator.py`、`data/product-form-dictionary.json` |
| BUDGET-001 | 预算三态 | budget_type = hard_cap / preferred_target / flexible_target + allowed_overrun_pct；只有金额没有类型视为信息缺失；hard_cap 超支未经用户批准不得定稿 | `references/runtime-rules.md`、`scripts/shopping_aggregator.py` |
| CHANGE-001 | 商品变更日志 | provider_suggestion → final_selection 逐条记录 selection_change_reason_codes；纠错（correction）与包装优化（packaging_optimization）分开统计 | `scripts/common/selection_change_log.py` |
| SELECT-001 | 预选确认强制交互 | 候选清单必须展示并等待用户明确回复后才能锁定；执行方不得自行整批接受或跳过；本周已删除食材不再出现；selection_mode 留痕 applied/bypassed/provisional，provisional 禁止进入正式生成 | `workflows/planning-flow.md`、`scripts/ingredient_preselector.py` |
