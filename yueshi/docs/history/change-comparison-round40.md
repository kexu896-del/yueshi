# round 40 变更对照（依据《月食家庭版v0.3 RC2修改意见整合》+ 5 份 schema）

## RC2-1/2（用户已完成）
- 5 份 schema 原样入库 schemas/household/；**唯一改动**：修正 `not:{required:[多字段]}` 的 Draft-07 语义缺陷（多字段同时出现才拦截 → 拆为逐字段 not），否则 external_meal 单带 leftover_plan_id、present_confirmed 单带 action 均会漏检。shared-definitions 与 bundle 同步修补，负向测试已锁定。

## RC2-3 校验器（scripts/household_reference_validator.py）
| 文档要求 | 落点 | 状态 |
|---|---|---|
| 集合校验 | PRIMARY_COUNT_EQUALS_ONE / MEMBER_ID_UNIQUE / 参与者⊆成员 | ✅ |
| 比例校验 | RATIO_SET_EQUALS_PARTICIPANTS / Σmin≤100≤Σmax / selected_pct Σ=100 | ✅ |
| 引用校验 | 餐次/份量/override/leftover/condiment 成员与餐次引用 | ✅ |
| 状态分支 | 由 schema if/then 承担（absent 必填 action；external_meal 禁 action/leftover、采购后才禁 delta；present_confirmed 全禁），测试逐项锁定 | ✅ |
| 剩余归属 | leftover member 引用 + source_meal 绑定校验 | ✅ |
| check 完整性 | 生成器 13 项 + 脚本 13 项各恰好一次（CHECK_ID_COMPLETENESS） | ✅ |
| L3 gate（P1-8） | L3 除 schema 要求 override 外，脚本校验 gate 满足分锅条件 | ✅ |

## RC2-4 Skill 联动
| 文档要求 | 落点 | 状态 |
|---|---|---|
| 4 种 plan_mode 路由 + 触发/追问/退出 | SKILL.md 主线路由第 6 条重写；安全冲突直接进 split_safety_required | ✅ |
| 家庭信息一轮合并问卷 | runtime-rules「家庭模式」 | ✅ |
| 计算节奏（检索一次/批处理/一次求解/两轮/局部重算） | runtime-rules「家庭模式」 | ✅ |
| locked_basket 门禁分级 | SKILL.md 门禁第 3 条区分用户待确认 vs 生成器失败 | ✅ |
| 渲染容量（>3 人摘要页+成员附页） | SKILL.md 路由 + household_layout_gate 引用 | ✅ |

## RC2-5 8 组 golden cases
全部通过 bundle Schema + 跨引用校验器（双人同量/双人不同量/三人不同量/安全分锅/采购前缺席/采购后外食/uncertain 关闭/三人缺席重分配）。

## 冻结前 11 项清单
test_household_rc2.py 逐项覆盖（含 5 个负向用例）。第 10 项（计算节奏）为流程约束，文档层面落于 runtime-rules；渲染门禁项属 RC2-6（渲染器适配 household schema 尚未做，本轮按文档顺序只到 RC2-5）。

## 测试
- 新增 18 项（12 + 6）全绿；全量 39 个测试文件通过。
