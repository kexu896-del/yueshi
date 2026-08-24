# 输出契约（结构化字段定义）

## initial_basket（初步食材篮子，步骤 6 产出；曾用名 weekly_basket）

> 三态数据契约：`initial_basket`（系统生成）→ 用户预选 → `locked_basket`（`status=locked`，`user_reviewed=true`）；用户未回复时转为 `provisional_locked_basket`（`status=provisional_locked`，`user_reviewed=false`）。菜谱检索原则上只能使用 `locked_basket`/`provisional_locked_basket` 中的核心食材。

```json
{
  "week": "2026-08-27 ~ 2026-09-02",
  "proteins": ["鸡腿", "鸡蛋", "虾", "豆腐"],
  "vegetables": ["菠菜", "西兰花", "冬瓜", "菌菇"],
  "carbohydrates": ["红薯", "糙米"],
  "flavor_bases": ["咸鲜", "咖喱", "蒜香"]
}
```

生成依据（按优先级）：周期阶段与营养边界 → 所在地普遍可获得性 → 预算 → 当季（`data/seasonal-foods.json`）→ 烹饪时间 → 包装规格（`data/package-rules.json`）→ 保存期。酮生物日 carbohydrates 可为空。

## locked_basket（锁定食材篮子，预选后的产出，步骤 8）

```json
{
  "basket_id": "",
  "status": "locked | provisional_locked",
  "generated_at": "",
  "user_reviewed": true,
  "protein": [],
  "vegetables": [],
  "carbohydrates": [],
  "flavor_bases": [],
  "optional": [],
  "removed_items": [],
  "replacements": [{"from": "", "to": ""}],
  "user_added_items": [],
  "permanent_dislikes": [],
  "week_only_dislikes": [],
  "selection_mode": "user_reviewed | bypassed",
  "allowed_pantry_items": [],
  "allowed_optional_garnishes": [],
  "approved_low_frequency_condiments": [],
  "nutrition_feasibility": "pass",
  "recipe_feasibility": "pass",
  "package_feasibility": "pass",
  "budget_feasibility": "pass",
  "notes": []
}
```

规则：
- `status=provisional_locked` 当且仅当用户显式跳过预选（"都可以/直接生成/跳过"、原请求要求直接生成、不支持多轮的调用模式、fallback 默认篮子）；此时 `user_reviewed=false`、`selection_mode=bypassed`，不记录任何永久偏好，每种核心食材保留缺货替代项。正常多轮场景：输出预选列表后当前回合停止，下一回合回复后再锁定
- 篮子之外允许例外仅限：①已确认家庭库存；②基础调味料白名单；③可完全省略的装饰性配料；④用户同意的一种低频调味料；⑤已复核的缺货平替。新鲜蔬菜/新鲜香草/新蛋白质/新主食/单菜特殊配料不得作为默认例外
- 单项食材字段见 `data/ingredient-catalog.json`（normalized_name / aliases / seasonality / search_keyword / expected_package / perishability / minimum_meal_uses / substitutes / preference_status / recipe_support）
- 偏好与安全分离：preference_status（favorite/acceptable/neutral/dislike_this_week/permanent_dislike）≠ restriction_status（allergy/medical_exclusion/religious_exclusion/ethical_exclusion），后者永不进入候选
- 后续菜谱检索、菜单、采购清单只能使用锁定篮子核心食材；例外仅家庭基础调味、可省略装饰、用户同意的 1 种低频调料、已有库存
- 未在菜单中使用的锁定食材不得进入采购清单

## 采购三对象（每种食材都拆成三层）

```yaml
required:                # 计划需求：菜单真正需要多少
  ingredient: 西兰花
  quantity: 450g
purchase:                # 购买建议：用户实际应买多少
  search_keyword: 西兰花 500g
  package: 500g
  package_count: 1
  expected_leftover: 50g
  substitutes: [菜花, 紫甘蓝]
offer:                   # 参考价与可获取时间（无数据时字段留空，不生成数字）
  channel: 菜场
  source_type: market_public_data     # official_api / market_public_data / city_range / none
  source_name: 南京市商务局
  published_at: 2026-08-19
  normalized_unit: 元/500g
  reference_low: null
  reference_high: null
  estimated_purchase_cost: null       # = package_count × 单包装价格，按购买规格算
  availability: unknown               # available/low_stock/unavailable/not_listed/unknown
  confidence: medium                  # high/medium/low/unavailable
  checked_at: null
```

## 采购清单字段

| 字段 | 说明 |
|---|---|
| `ingredient` | 食材标准名 |
| `purchase_name` | 常用购买名称（口语化+规格，如"冰鲜鸡腿 400g"） |
| `required_quantity` | 菜单实际需求量（g/ml/个） |
| `acceptable_package` | 常见购买规格（`data/package-rules.json`） |
| `reference_price` | 参考价（有可靠来源时；无则留空不虚构） |
| `substitutes` | 平替列表（`data/substitutions.json`） |
| `leftover_action` | 剩余去向或储存方式 |
| `estimated_purchase_cost` | 预计支出（按购买包装数 × 单包装价格；内部预算用） |
| `price_confidence` | high / medium / low / unavailable（内部字段，不进用户文件） |

**用户可见采购表只显示**：食材｜需要量｜建议购买规格｜参考价｜平替（剩余去向）。价格说明只保留"逐项具体参考价 + 合计"，无可靠价格时加一行"部分食材暂无可靠参考价，未计入预算总额"；不出现任何"实价/成交价为准"字样。

## 采购清单汇总字段（shopping_aggregator.py 输出）

`food, required_quantity, package_quantity, planned_use, expected_leftover, leftover_action`
（实际需求量 / 建议购买规格 / 计划用途分布 / 预计剩余量 / 剩余去向或储存方式）

## recipe_fingerprint（菜谱指纹，多样性校验用）

`{protein, vegetable, method, flavor, structure, texture}`——六维；相邻两顿相同维 ≤4（相似度≤70%）。
书籍来源菜谱的统一记录格式（含 source_type / extraction_type / canonical_recipe_family）见 `references/book-recipe-extraction.md`。

## weekly_feedback（下周迭代输入，存 `diet-plans/weekly_feedback.md`）

```yaml
week: 2026-08-27 ~ 2026-09-02
liked_recipes: [咖喱鸡腿南瓜锅]
disliked_recipes: [白灼虾]
unavailable_ingredients: [羽衣甘蓝]
actual_cooking_time: {鸡腿西兰花焖锅: 35}   # 分钟，用于修正估计
leftovers: [希腊酸奶半盒, 胡萝卜2根]
# 食材预选反馈（下周预选时读取）
permanent_dislikes: []        # 用户明确"以后不要"的食材
week_only_dislikes: []        # 仅本周删除的食材（默认，下周自动恢复候选）
neutral_ingredients: []
favorite_ingredients: []
accepted_substitutions: []    # 用户接受的替换（from→to）
rejected_substitutions: []
```

偏好沉淀写入 `diet-plans/user-ingredient-preferences.json`（permanent_dislikes / preference_status / restrictions）。

## 打卡 CSV（已停用）

每日打卡、计划与打卡偏差对比已取消；本契约不再使用，仅保留此说明。


## transient_user_recipe（用户临时菜谱记录，仅限当前计划）

```yaml
name: 用户常吃菜名
record_status: transient_approved
scope: current_plan_only        # 不写入生产池，计划结束后失效
checks_passed:                  # 10 项检查全部通过才可标记 transient_approved
  - name_ingredients_confirmed  # 菜名与食材经用户确认
  - ingredient_normalized
  - allergen_medical_checked
  - locked_basket_compliant     # 核心食材须在锁定清单内；否则不自动采购，提示预选追加或记 next_week_candidate
  - one_serving_grams
  - oil_seasoning_estimated
  - nutrition_recalculated
  - time_equipment_feasible
  - package_leftover_planned
  - fingerprint_dedup_vs_pool
next_week_candidate: false      # 核心食材不在 locked_basket 时为 true
```


## recipe_instruction（做法字段，仅中饭/晚饭稍复杂菜式）

```yaml
recipe_instruction:
  include_for_complex_lunch_dinner: true | false   # 由问卷第 4 项决定
  steps: []                 # 分步做法
  preparation_notes: []     # 要点/提前处理
  heat_or_temperature: ""   # 火力或温度阶段
  doneness_signal: ""       # 熟度/收汁/口感判断
  advance_prep: ""          # 可提前备餐部分
```

- 用户选择"需要"时，所有符合条件（步骤≥4/腌制/焯水后焖烧/预调酱汁/多火力阶段/熟度判断/非直观电器程序）的中饭和晚饭必须在最终文件显示"做法"小节；内部有步骤但未渲染 = 验收失败。

## 日期口径（统一）

用户未指定日期：`start_date = request_date + 1 天`，一周 = 连续 7 天（不默认自然周），两周 = 连续 14 天；用户指定自然周或开始日期时按用户要求。日期同步到标题、每日菜单、预算说明、采购清单与文件名。

## 输出路由

`output_format: pdf | html | md | docx`（可多选）——用户选择一种时只交付该一种；未指定默认 Markdown；用户要求多种时可同时交付。中间文件写 tmp，不作为附件。


## plan.json（渲染唯一定稿输入）

```yaml
plan:
  date_range: "2026-08-22 至 2026-08-28"
  subtitle: 阶段与模式一句话
  include_recipe_steps: true | false   # 问卷必选项，无默认值；false 时渲染器不输出做法
  stats: {阶段, 模式, 预算}
  moon_phases: []                       # 7 天月相
profile: {性别, 年龄, 目标, ...}
shopping:
  items: [{ingredient, category, required_quantity, acceptable_package, reference_price, substitutes, leftover_action}]
  # category 必填，取值：肉蛋水产与豆制品 / 蔬菜与菌菇 / 谷物薯类与主食 / 乳品与油脂 / 水果 / 调味与干货 / 其他
  # reference_price 必填（硬门禁）：有来源价用来源价；无来源价用 data/price-estimates.json 同类估算（如"约26元/袋"）
  # meal_allocation 建议填：食材↔菜谱对照（如"周六午140g · 周三晚160g"），网页折叠、打印展开
  total: "约 ¥163（估算口径，实际以购买时为准）"
  price_note: "参考价为当地近期同类公开行情估算，非实时报价"
prep:                      # 备餐任务节（必填）
  purchase_day: {label: "周六 8/22", tasks: [采购执行, 分装冷冻, ...]}
  prep_day: {label: "周日 8/23", tasks: [腌制, 预蒸, ...]}
  leftover_verification: [{ingredient, purchase_vs_use, result}]   # ≥3 项 0 剩余/去向验证
wisdom: {paragraphs: ["段1 周期+禁食+碳水逻辑", "段2 时令+蛋白+体质适配", "段3 操作提示+下周预告"]}  # 3 段自然叙述，无小标题
execution_tips: []         # 执行提示：3-6 条一句话（用药间隔/外食口径/清库存/下周衔接）
# profile 仅内部计算使用，渲染层不输出"本周档案"章节；days[].window 只写进食窗口，不含"禁食/空腹"字样
days:
  - label: 周一 8/22
    window: 进食 08:00-19:00 · 禁食 13h
    meals: [{time, status, name, dishes, grams, recipe_instruction?}]   # time/status 为独立字段
    nutrition_line: 净碳水/蛋白/脂肪一行
    advice: ""             # 仅当天有特殊事项（解冻/腌制/剩菜/外食/跨阶段/备餐衔接）才写
disclaimer: 免责声明文本
```

校验通过后才进入渲染；渲染阶段不得改动其中任何业务数据。
# 输出契约（结构化字段定义）

## initial_basket（初步食材篮子，步骤 6 产出；曾用名 weekly_basket）

> 三态数据契约：`initial_basket`（系统生成）→ 用户预选 → `locked_basket`（`status=locked`，`user_reviewed=true`）；用户未回复时转为 `provisional_locked_basket`（`status=provisional_locked`，`user_reviewed=false`）。菜谱检索原则上只能使用 `locked_basket`/`provisional_locked_basket` 中的核心食材。

```json
{
  "week": "2026-08-27 ~ 2026-09-02",
  "proteins": ["鸡腿", "鸡蛋", "虾", "豆腐"],
  "vegetables": ["菠菜", "西兰花", "冬瓜", "菌菇"],
  "carbohydrates": ["红薯", "糙米"],
  "flavor_bases": ["咸鲜", "咖喱", "蒜香"]
}
```

生成依据（按优先级）：周期阶段与营养边界 → 所在地普遍可获得性 → 预算 → 当季（`data/seasonal-foods.json`）→ 烹饪时间 → 包装规格（`data/package-rules.json`）→ 保存期。酮生物日 carbohydrates 可为空。

## locked_basket（锁定食材篮子，预选后的产出，步骤 8）

```json
{
  "basket_id": "",
  "status": "locked | provisional_locked",
  "generated_at": "",
  "user_reviewed": true,
  "protein": [],
  "vegetables": [],
  "carbohydrates": [],
  "flavor_bases": [],
  "optional": [],
  "removed_items": [],
  "replacements": [{"from": "", "to": ""}],
  "user_added_items": [],
  "permanent_dislikes": [],
  "week_only_dislikes": [],
  "selection_mode": "user_reviewed | bypassed",
  "allowed_pantry_items": [],
  "allowed_optional_garnishes": [],
  "approved_low_frequency_condiments": [],
  "nutrition_feasibility": "pass",
  "recipe_feasibility": "pass",
  "package_feasibility": "pass",
  "budget_feasibility": "pass",
  "notes": []
}
```

规则：
- `status=provisional_locked` 当且仅当用户显式跳过预选（"都可以/直接生成/跳过"、原请求要求直接生成、不支持多轮的调用模式、fallback 默认篮子）；此时 `user_reviewed=false`、`selection_mode=bypassed`，不记录任何永久偏好，每种核心食材保留缺货替代项。正常多轮场景：输出预选列表后当前回合停止，下一回合回复后再锁定
- 篮子之外允许例外仅限：①已确认家庭库存；②基础调味料白名单；③可完全省略的装饰性配料；④用户同意的一种低频调味料；⑤已复核的缺货平替。新鲜蔬菜/新鲜香草/新蛋白质/新主食/单菜特殊配料不得作为默认例外
- 单项食材字段见 `data/ingredient-catalog.json`（normalized_name / aliases / seasonality / search_keyword / expected_package / perishability / minimum_meal_uses / substitutes / preference_status / recipe_support）
- 偏好与安全分离：preference_status（favorite/acceptable/neutral/dislike_this_week/permanent_dislike）≠ restriction_status（allergy/medical_exclusion/religious_exclusion/ethical_exclusion），后者永不进入候选
- 后续菜谱检索、菜单、采购清单只能使用锁定篮子核心食材；例外仅家庭基础调味、可省略装饰、用户同意的 1 种低频调料、已有库存
- 未在菜单中使用的锁定食材不得进入采购清单

## 采购三对象（每种食材都拆成三层）

```yaml
required:                # 计划需求：菜单真正需要多少
  ingredient: 西兰花
  quantity: 450g
purchase:                # 购买建议：用户实际应买多少
  search_keyword: 西兰花 500g
  package: 500g
  package_count: 1
  expected_leftover: 50g
  substitutes: [菜花, 紫甘蓝]
offer:                   # 参考价与可获取时间（无数据时字段留空，不生成数字）
  channel: 菜场
  source_type: market_public_data     # official_api / market_public_data / city_range / none
  source_name: 南京市商务局
  published_at: 2026-08-19
  normalized_unit: 元/500g
  reference_low: null
  reference_high: null
  estimated_purchase_cost: null       # = package_count × 单包装价格，按购买规格算
  availability: unknown               # available/low_stock/unavailable/not_listed/unknown
  confidence: medium                  # high/medium/low/unavailable
  checked_at: null
```

## 采购清单字段

| 字段 | 说明 |
|---|---|
| `ingredient` | 食材标准名 |
| `purchase_name` | 常用购买名称（口语化+规格，如"冰鲜鸡腿 400g"） |
| `required_quantity` | 菜单实际需求量（g/ml/个） |
| `acceptable_package` | 常见购买规格（`data/package-rules.json`） |
| `reference_price` | 参考价（有可靠来源时；无则留空不虚构） |
| `substitutes` | 平替列表（`data/substitutions.json`） |
| `leftover_action` | 剩余去向或储存方式 |
| `estimated_purchase_cost` | 预计支出（按购买包装数 × 单包装价格；内部预算用） |
| `price_confidence` | high / medium / low / unavailable（内部字段，不进用户文件） |

**用户可见采购表只显示**：食材｜需要量｜建议购买规格｜参考价｜平替（剩余去向）。价格说明只保留"逐项具体参考价 + 合计"，无可靠价格时加一行"部分食材暂无可靠参考价，未计入预算总额"；不出现任何"实价/成交价为准"字样。

## 采购清单汇总字段（shopping_aggregator.py 输出）

`food, required_quantity, package_quantity, planned_use, expected_leftover, leftover_action`
（实际需求量 / 建议购买规格 / 计划用途分布 / 预计剩余量 / 剩余去向或储存方式）

## recipe_fingerprint（菜谱指纹，多样性校验用）

`{protein, vegetable, method, flavor, structure, texture}`——六维；相邻两顿相同维 ≤4（相似度≤70%）。
书籍来源菜谱的统一记录格式（含 source_type / extraction_type / canonical_recipe_family）见 `references/book-recipe-extraction.md`。

## weekly_feedback（下周迭代输入，存 `diet-plans/weekly_feedback.md`）

```yaml
week: 2026-08-27 ~ 2026-09-02
liked_recipes: [咖喱鸡腿南瓜锅]
disliked_recipes: [白灼虾]
unavailable_ingredients: [羽衣甘蓝]
actual_cooking_time: {鸡腿西兰花焖锅: 35}   # 分钟，用于修正估计
leftovers: [希腊酸奶半盒, 胡萝卜2根]
# 食材预选反馈（下周预选时读取）
permanent_dislikes: []        # 用户明确"以后不要"的食材
week_only_dislikes: []        # 仅本周删除的食材（默认，下周自动恢复候选）
neutral_ingredients: []
favorite_ingredients: []
accepted_substitutions: []    # 用户接受的替换（from→to）
rejected_substitutions: []
```

偏好沉淀写入 `diet-plans/user-ingredient-preferences.json`（permanent_dislikes / preference_status / restrictions）。

## 打卡 CSV（已停用）

每日打卡、计划与打卡偏差对比已取消；本契约不再使用，仅保留此说明。


## transient_user_recipe（用户临时菜谱记录，仅限当前计划）

```yaml
name: 用户常吃菜名
record_status: transient_approved
scope: current_plan_only        # 不写入生产池，计划结束后失效
checks_passed:                  # 10 项检查全部通过才可标记 transient_approved
  - name_ingredients_confirmed  # 菜名与食材经用户确认
  - ingredient_normalized
  - allergen_medical_checked
  - locked_basket_compliant     # 核心食材须在锁定清单内；否则不自动采购，提示预选追加或记 next_week_candidate
  - one_serving_grams
  - oil_seasoning_estimated
  - nutrition_recalculated
  - time_equipment_feasible
  - package_leftover_planned
  - fingerprint_dedup_vs_pool
next_week_candidate: false      # 核心食材不在 locked_basket 时为 true
```


## recipe_instruction（做法字段，仅中饭/晚饭稍复杂菜式）

```yaml
recipe_instruction:
  include_for_complex_lunch_dinner: true | false   # 由问卷第 4 项决定
  steps: []                 # 分步做法
  preparation_notes: []     # 要点/提前处理
  heat_or_temperature: ""   # 火力或温度阶段
  doneness_signal: ""       # 熟度/收汁/口感判断
  advance_prep: ""          # 可提前备餐部分
```

- 用户选择"需要"时，所有符合条件（步骤≥4/腌制/焯水后焖烧/预调酱汁/多火力阶段/熟度判断/非直观电器程序）的中饭和晚饭必须在最终文件显示"做法"小节；内部有步骤但未渲染 = 验收失败。

## 日期口径（统一）

用户未指定日期：`start_date = request_date + 1 天`，一周 = 连续 7 天（不默认自然周），两周 = 连续 14 天；用户指定自然周或开始日期时按用户要求。日期同步到标题、每日菜单、预算说明、采购清单与文件名。

## 输出路由

`output_format: pdf | html | md | docx`（可多选）——用户选择一种时只交付该一种；未指定默认 Markdown；用户要求多种时可同时交付。中间文件写 tmp，不作为附件。


## plan.json（渲染唯一定稿输入）

```yaml
plan:
  date_range: "2026-08-22 至 2026-08-28"
  subtitle: 阶段与模式一句话
  include_recipe_steps: true | false   # 问卷必选项，无默认值；false 时渲染器不输出做法
  stats: {阶段, 模式, 预算}
  moon_phases: []                       # 7 天月相
profile: {性别, 年龄, 目标, ...}
shopping:
  items: [{ingredient, category, required_quantity, acceptable_package, reference_price, substitutes, leftover_action}]
  # category 必填，取值：肉蛋水产与豆制品 / 蔬菜与菌菇 / 谷物薯类与主食 / 乳品与油脂 / 水果 / 调味与干货 / 其他
  # reference_price 必填（硬门禁）：有来源价用来源价；无来源价用 data/price-estimates.json 同类估算（如"约26元/袋"）
  # meal_allocation 建议填：食材↔菜谱对照（如"周六午140g · 周三晚160g"），网页折叠、打印展开
  total: "约 ¥163（估算口径，实际以购买时为准）"
  price_note: "参考价为当地近期同类公开行情估算，非实时报价"
prep:                      # 备餐任务节（必填）
  purchase_day: {label: "周六 8/22", tasks: [采购执行, 分装冷冻, ...]}
  prep_day: {label: "周日 8/23", tasks: [腌制, 预蒸, ...]}
  leftover_verification: [{ingredient, purchase_vs_use, result}]   # ≥3 项 0 剩余/去向验证
wisdom: {paragraphs: ["段1 周期+禁食+碳水逻辑", "段2 时令+蛋白+体质适配", "段3 操作提示+下周预告"]}  # 3 段自然叙述，无小标题
execution_tips: []         # 执行提示：3-6 条一句话（用药间隔/外食口径/清库存/下周衔接）
# profile 仅内部计算使用，渲染层不输出"本周档案"章节；days[].window 只写进食窗口，不含"禁食/空腹"字样
days:
  - label: 周一 8/22
    window: 进食 08:00-19:00 · 禁食 13h
    meals: [{time, status, name, dishes, grams, recipe_instruction?}]   # time/status 为独立字段
    nutrition_line: 净碳水/蛋白/脂肪一行
    advice: ""             # 仅当天有特殊事项（解冻/腌制/剩菜/外食/跨阶段/备餐衔接）才写
disclaimer: 免责声明文本
```

校验通过后才进入渲染；渲染阶段不得改动其中任何业务数据。


## preselection_decision（预选语义三档）

```yaml
preselection_decision: accepted_batch | explicitly_wanted | merely_allowed
# accepted_batch：用户对系统展示的整组预选回复"都可以（吃）"——等于接受本周候选组，中高优先级
# explicitly_wanted：用户明确点名"本周想吃"——高优先级
# merely_allowed：只是不忌口、未在本周预选中出现——普通优先级
```

排序权重：explicitly_wanted > accepted_batch > merely_allowed。accepted_batch 食材未入选必须给出真实原因，不得静默消失；覆盖率不凌驾于安全/过敏/医嘱/营养硬门槛，不为凑覆盖率采购只用一次的大包装易腐食材。

## ingredient_selection_result（预选后未使用食材的追溯记录，内部 selection report）

```yaml
ingredient: 蛤蜊
preselection_decision: accepted_batch
menu_status: selected | not_selected
candidate_count: 1
top_candidate: 蛤蜊蒸蛋
rejected_at: diversity_or_package_gate
reason_codes: [lower_rank_after_constraints]
can_swap: true
swap_target_meal: 周日晚餐
```

标准原因码：no_production_recipe / recipe_fingerprint_missing / safety_or_medical_conflict / allergen_conflict / time_limit / equipment_mismatch / package_waste / budget_pressure / nutrition_conflict / duplicate_protein / low_diversity_gain / lower_rank_after_constraints / insufficient_quantity / schedule_mismatch。
每个预选后未使用的食材至少记录一个原因码、候选菜数量、最高分候选、淘汰层、是否存在一键替换方案；原因必须来自 ranker 日志，渲染器不得猜测。

## 食堂/外食餐次（meal 字段扩展）

```yaml
meal_type: lunch
meal_source: cafeteria          # cafeteria=食堂/外食；自炊餐缺省
meal_time: "12:00"
meal_status: 外食 · 区间估算
order_template: balanced_standard   # data/cafeteria-meal-templates.json 的模板 ID
```

食堂模板（点餐结构与营养估算）统一从 `data/cafeteria-meal-templates.json` 读取；估算值进入当天完整营养合计；外食为低置信度时当天只显示"预计接近目标"，不得标"精确达标"；用户文件显示简洁文本，内部日志保留模板 ID 与置信度。

## 采购清单排除规则

最终菜单未使用的食材不得出现在正式采购表数据行；预选后未使用的食材只进入内部 selection report，或在"执行提示"用一行说明（含真实原因与可替换方案）；用户接受替换后须重新汇总购买量、规格、预算与剩余去向。


### 食堂模板 ID 与覆盖（收口轮同步）

- `meal.order_template` 取值仅限 `data/cafeteria-meal-templates.json` 的 `templates` 键（当前：`balanced_standard` / `no_soup`）；HTML 渲染、PDF 转换与营养校验必须读取同一模板对象，不得各自硬编码。
- 用户说明食堂实际情况后允许覆盖默认模板：在 plan.json 该餐次写 `template_override`（`display` 与 `nutrition_estimate{net_carbs_g, protein_g, fat_g, confidence}` 完整四字段），置信度不高于原模板；覆盖记录写入内部日志。
- 低置信度外食日的当日营养行只写"预计接近目标"，不得写精确达标。
