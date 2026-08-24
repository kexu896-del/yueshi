# 书籍菜谱提取流程（EPUB → 统一菜谱库）

> 目标：把 EPUB 书籍变成**可参与食材篮子、营养计算和多样性排序的数据**，而不是把原菜谱整段搬进库。
> 核心原则：区分"读取菜谱"和"建立可用菜谱库"；宁缺毋滥，不虚构书中不存在的内容。

## 三类提取结果（防止把原则当菜谱）

| 类型 | 判定标准 | 去向 |
|---|---|---|
| `explicit_recipe` | 书中有明确菜名 + 食材表 + 份量 + 步骤 | 菜谱候选池（改造后） |
| `meal_pattern` | 只有食物组合/餐盘建议（如"某阶段可选鱼类、十字花科、牛油果"） | 可据以生成新菜，标记 `book_pattern_derived`，**不得称为书中原菜谱** |
| `technique_note` | 可迁移技法（无完整菜谱） | 技法库，不单独成菜 |
| `flavor_template` | 可迁移味型/酱汁结构 | 味型库（flavor-bases.json 候选） |
| `ingredient_culture_note` | 物产、时令、地域、名称、食俗 | 文化索引，**不进菜谱池** |
| `service_or_eating_context` | 上桌、搭配、场合、进食方式 | 文化索引，**不进菜谱池** |
| `historical_recipe_lead` | 散文/历史中的菜谱线索 | 待核验队列，须由另一份可执行菜谱来源交叉验证 |
| `protocol_rule` | 只有饮食原则（如"经前增加天然复合碳水"） | 规则库（cycle-protocol.md），**不进菜谱池** |

## 七步提取流程

1. **解析目录，不整本丢给 AI**：先读 EPUB 目录，锁定可能含食谱的章节（Recipes / Meal Plan / Menu / Breakfast / Lunch / Dinner / Snacks / Appendix / 食谱 / 菜单 / 一周计划）。长文本整本总结容易遗漏、混写、把理论当菜谱。
2. **逐章节提取**：每次只处理一个章节，输出三类记录；**章节中没有明确菜谱时，不得自行补写菜名、克数或步骤**。
3. **保留来源定位**：至少记录书名、EPUB 章节标题、内部文件名、菜谱标题、来源类型——不存全文，但要能回查。
4. **规范化食材名称**（与平替分开两步）：如 salmon fillet → 三文鱼柳、leafy greens → 绿叶菜；然后再建大陆市场平替（三文鱼→鲭鱼/带鱼/鲈鱼）。提取时不直接替换，保证可追溯。
5. **菜谱适配**：多人份 → 一人份或两餐份；国外食材 → 本地常见食材；操作 → 20 至 30 分钟、现有厨具可完成、适合具体模式。产出是"改造版"，标记 `book_adapted`，不再表述成原书原方。
6. **重新计算营养**：不信书中热量。按实际生重、实际用油、实际份数、替换后的食材、去增的主食重算（用 `references/foods-table.md` + `scripts/macros_calculator.py --check`）。
7. **进入统一索引**：与 HowToCook 共用同一套字段（见下），最终统一候选池来源包括：HowToCook 来源 / 书籍明确菜谱改造 / 书籍组合建议生成 / 本地家常菜 / 用户喜欢菜。

## 书籍菜谱记录格式

```yaml
id: book_001
name: 番茄香草烤鱼
source_type: book_adapted          # book_adapted / book_pattern_derived
source_book: 某书
source_location: 第6章或EPUB章节名
extraction_type: explicit_recipe   # explicit_recipe / meal_pattern / technique_note / flavor_template / ingredient_culture_note / service_or_eating_context / historical_recipe_lead / protocol_rule
core_ingredients: [白肉鱼, 番茄]
methods: [烤]
structure: 蛋白质加蔬菜
flavors: [番茄, 香草]
original_servings: 4
adapted_servings: 1
active_minutes: 15
total_minutes: 35
mode_fit: {keto_biologic: high, hormone_balance: high}
required_modifications: [不使用额外糖, 按个人份量重新计算用油]
nutrition_status: recalculation_required
copyright_status: transformed_summary   # 只存改造后的摘要，不存原文
canonical_recipe_family: tomato_baked_fish
```

## 来源配额（柔性观察指标，不凌驾于锁定篮子/安全/包装/时间/偏好/营养；无法满足时允许偏离并记录原因）

```
weekly_source_mix:
  howtocook_adapted: 30 至 50%
  book_explicit_adapted: 20 至 30%
  book_pattern_derived: 10 至 20%
  local_home_cooking: 20 至 30%
  user_favorites: 1 至 2 道
```

一周 7 顿自炊晚餐示例：2 道 HowToCook 改造 + 2 道书籍菜谱改造 + 1 道组合原则生成 + 1 道本地家常菜 + 1 道清库存菜。

## 菜谱家族去重（canonical_recipe_family）

多本书常有"名字不同、结构相同"的菜（牛油果鸡蛋沙拉 / 鸡蛋牛油果碗 / 绿色早餐碗）。去重顺序：菜名标准化 → 核心食材标准化 → 烹法和结构指纹 → 判断同一菜谱家族。同一家族保留信息最完整、最适合本地采购的一条，其余作为变体。

## 排序原则

书籍来源**不自动获得更高权重**。所有候选菜统一评分：所在地普遍可获得性 + 包装利用率 + 烹饪时间 + 用户口味 + 周期模式适配 + 菜谱多样性 + 营养重算结果。书籍食谱常见问题（食材难买、特殊调料多、多人份、耗时长、口味不本地化）都要在评分中自然扣分。

## 新增六书（2026-08-21 精读批次，状态：待批准）

Chinese Homestyle / The Woks of Life / Chinese Soul Food 三本英文中餐书候选在各自 book-extraction 目录 explicit-recipes.jsonl（preliminary_decision=candidate），统一标 Chinese_American_home_cooking，不冒充地方原方。《吃货辞典》《姑苏食话》只产文化/物产/时令索引，explicit_recipe=0。Coconut & Sambal 新版（指纹 158ec08ff63d3f6d）独立进 Southeast_Asian_Indonesian 来源，不参与中餐配额；旧不可用版本不计数。

**正式入池前必须**：人工审 book-extraction/proposed-new-recipes.jsonl（18 条缺口填补提案）与 duplicate-merge-plan.json（16 个同名/同构家族）；未批准前不得把新书候选合并进 data/book-recipes.json，也不得用文化散文线索补齐菜谱。
