# 迁移映射（v0.3 RC2 / 1.1.0 → 旧家庭产物）

> 状态：round43 新增 · RC2-6 迁移映射。
> 原则：**迁移器负责旧版转新版；正式 Schema 不为兼容旧字段重新放宽 additionalProperties。**
> 本文件不参与用户计划决策（同 maintenance-map 定位）。

## 1. 字段迁移

| 旧字段 | 新位置 | 说明 |
|---|---|---|
| `plan_meta.mode` | `plan_mode`（顶层） | 取值 solo / shared_uniform / shared_meal_personalized / split_safety_required |
| `portion_ratio`（单数） | `portion_ratios[]`（数组） | 每成员 pct_min/pct_max/selected_pct |
| `weight_basis` | `quantity.canonical_basis` | raw / edible / cooked |
| `attendance_overrides_applied` | `effective_meta.applied_override_ids` | 只存在 effective 层，禁止写回 base |
| `shared_meal.mode` | `meal_plan_mode` | planned / guidance_only / excluded（单人版同口径） |
| `breakfast_mode` 等历史同义字段 | `meal_plan_mode` | 仅按 schema 映射，不再并存 |

## 2. 文件迁移

| 旧形态 | 新形态 |
|---|---|
| 旧单文件家庭 plan | 三层：`base_plan.json`（冻结）+ `overrides_YYYYMMDD.json`（独立 patch）+ `effective_plan.json`（运行时派生物，非权威源，不作为下次生成输入） |
| 渲染直读 base | 渲染只读 validated effective_plan；无 override 走 identity merge |

## 3. 行为迁移

| 旧行为 | 新行为 |
|---|---|
| 家庭渲染直接读取 base | 家庭渲染只读取校验通过的 effective_plan |
| `shared_*` 前缀判断 | `household_plan_modes` 集合判断（含 split_safety_required） |
| 逐成员各跑一遍 15 步 | 家庭 13 步：单次检索、单次装配、批量营养、≤2 轮全局微调 |
| 缺席重建整周 | 缺席只合并 patch 并局部重算；整周重建记 audit warning 并回滚 |
| 调试字段塞进产物（_note 等） | 调试信息进 stderr / 结构化日志 / merge_report，产物过 additionalProperties:false |

## 4. 拒绝策略

| 场景 | 策略 |
|---|---|
| 旧字段出现在正式 base/overrides/effective | **明确失败**（additionalProperties:false），由迁移器先行转换 |
| 旧单文件家庭 plan 直接渲染 | **禁止**；先拆分三层并过 Schema |
| 迁移后写回旧格式 | **禁止**；新版只写三层契约 |
| 迁移器无法确定的字段 | 不猜不伪造：标记未迁移项并停止，交人工确认 |
| 旧版 plan_schema_version 渲染 | 版本门禁明确失败（plan_schema_mismatch），不静默兼容 |
