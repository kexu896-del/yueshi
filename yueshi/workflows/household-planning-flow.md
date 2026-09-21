# 家庭模式执行流程（household-planning-flow）

> 状态：已并入（round41）· 配套 `references/household-runtime-rules.md` 与 `schemas/` RC2。
> 适用：`plan_mode` = `shared_uniform` / `shared_meal_personalized` / `split_safety_required`。solo 继续走 `workflows/planning-flow.md`，两者不互相改造。
> 总原则：**单次检索、单次装配、批量营养、≤2 轮全局微调、缺席只合并 patch**。

## 13 步固定顺序

1. **plan_mode 前置识别**：开始生成前确认四类模式之一。多人不静默降级 solo；`split_safety_required`（安全冲突）直接进入，不追问降级。
2. **家庭安全筛查**：逐成员登记过敏原/医嘱/宗教限制；任一成员有慢病用药 → 仅医嘱范围内适配；安全排除项在共锅判定前完成，之后不可恢复。
3. **家庭信息一轮追问**（与"关键八项"合并为同一轮）：成员清单、共同餐次、默认共锅策略、份量精度、谁做饭+时间上限；答不出按默认值（共锅、档位份量）。
4. **成员营养目标批量计算**（脚本）：只对 precision_level=exact 的成员计算；portion_band 成员用档位。绝经/更年期减重成员蛋白 floor ≥1.1g/kg、钙来源 ≥1 份/日。
5. **共锅安全判定**：生成 `household_default_cooking_gate`；安全冲突成员/餐次标记 `split_safety_required`（分锅或该餐不共享）。
6. **菜谱检索（只运行一次）**：候选过滤 = 渠道可购 → 成员安全交集 → 共锅结构（structure_grade：high 清炖蒸焖烩/一锅主菜+独立主食优先；low 重酱混匀降权；forbidden 三锅并行排除）→ 多样性指纹（对家庭总量计算）。
7. **household_ingredients**：按家庭下锅总量填写每餐（quantity + canonical_grams + canonical_basis）。
8. **portion_seed → 初始 member_portions**：先按种子倍率（如 staple 1.5 / protein 1.15）形成初始分配；每餐声明 `portion_method`；早餐同样拆分。
9. **批量计算成员 nutrition_gap**：同时算全部精算成员的营养差额向量，不逐个成员跑管线。
10. **个人可分离组件调整（≤2 轮）**：主食份量 → 肉块/豆腐/蛋 → 牛奶/酸奶/加餐 → 后置油脂 → 个人小配菜；**不重建共享菜**。两轮后仍不达标：标记该共享菜不适合当前成员组合，再做局部换菜（并回步骤 6 只重算该菜）。
11. **不变量校验 → 冻结 base_plan.json**：
    - 每餐 household 总量 = Σ member_portions + 损耗/剩余；
    - participant_member_ids = member_portions 成员集合（not_participating 不得进入）；
    - ratio_split：portion_ratios 必填、区间覆盖整锅、selected_pct Σ=100、置信度联动；
    - 引用校验器 7 项 + check 完整性（household_reference_validator.py）。
    全部通过后写 plan_meta（plan_schema_version=const "v0.3-rc2"）并冻结，之后不再人工改数。
12. **反向汇总采购（三本账）**：一行一食材；household_required / inventory_used / new_purchase（按包装取整）；条件采购独立字段；库存显示参考价；双口径预算（新购 / 含库存）。
13. **渲染**：无论有无 patch 都经 `household_override_merger` 产出 effective_plan（无 patch 走 identity merge，effective_meta.applied_override_ids 为空）→ effective Schema 校验 → 统一渲染；渲染器只读校验通过的 effective_plan。成员营养块独立行；>3 人摘要页+附页；随后走入口级最终门禁（家庭检查项）。

## 缺席/变化子流程（patch 管线，不回到第 1 步）

1. 用户报告变化 → 只追问一轮（采购是否完成 + 剩余去向），答不出按可保存默认值。
2. 写 `overrides_YYYYMMDD.json`：absent（known_at 四时机 + action）/ external_meal（不计家庭账、无 leftover、无 transfer；before_shopping 可 reduce_purchase）/ present_confirmed（关闭 uncertain）。
3. 合并（household_override_merger）局部重算：
   - 受影响 meal 的 household_ingredients；
   - 该餐 member_portions（3 人缺席时 selected_pct 重新归一）；
   - 当日成员营养；
   - 采购差量（shopping_delta）与 leftover_plan。
4. **不**重跑菜谱检索、不重建整周、不改未受影响日期、不改 plan_mode。若发生整周重建 → audit warning + 回滚局部重算。

## 计划期不确定（uncertain）子流程

1. `attendance_plan=uncertain` 的餐：份量计入采购、选菜优先可保存结构（structure_grade 偏好）。
2. 生成 `pending_attendance_resolution`（deadline + auto_resolve）。
3. 到期未确认 → 按 auto_resolve 处理（confirm_absent → 走 patch 子流程；keep_plan → 保持）。

## 局部重装配模式（change_scope=schedule_and_ingredient_patch，round45）

用户仅修改 cooking_days / excluded_days / excluded_ingredients（预算、库存、人员、目标、口味、输出格式不变）时，**不重跑完整 13 步**，只执行：

> 锁定篮子过滤 → 做饭日菜单重装配 → 份量联合求解 → 营养批量校验 → 采购反向汇总 → 备餐日期派生 → effective_plan 渲染。

跳过：安全信息重新采集、成员营养目标重算、预算与库存重新询问、完整食材预选、与修改无关的规则加载与候选解析。其余字段变化仍走完整 13 步；无法判定时按完整流程处理，不猜。

## 求解与渲染纪律（round45）

- **份量一次联合求解**：禁止模型逐项"试克数→跑脚本→再改"。可调整食材（主食/可分离蛋白/乳品/油脂）连同成员约束一次交 `scripts/household_portion_solver.py` 联合求解（L1 最小改动）；模型只决定哪些食材允许调整、哪些必须保留、哪些菜式不可替换；求解 infeasible 时才局部换菜。
- **先求解，再统一渲染**：菜单装配 → 营养求解一次 → 采购聚合 → 全门禁 → 冻结 plan.json → 只渲染一次；仅纯排版问题允许重渲染，禁止渲染后再调营养与采购。
- **不变数据哈希缓存**：成员营养目标、库存、预算、地区价格、菜谱候选索引、食品营养表、单位换算表未变化时按哈希直接复用，仅新日程与排除食材参与重装配。

## 完成标准

- 模式从未从单人版"后置改造"而来；
- 每位精算成员有独立营养目标与 member_portions；
- 每餐家庭总量与成员分量之和一致；
- 混合菜有明确 portion_method 与置信度；
- 个人热量不足只调个人可分离组件；
- 安全冲突自动分锅或停止共享菜；
- 采购一行一食材、三本账分离、量与菜单一致；
- 备餐建议与 meal_id/日期一致；
- 缺席只局部重算，不重建整周。
