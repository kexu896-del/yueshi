# 规划主流程（固定执行顺序 15 步）

> 默认 `execution_mode: fast`：一次加载 manifest + `data/foods-table.json` + `data/recipe-production-index.json`；候选检索用 **ingredient→recipe 倒排索引**（`data/ingredient-recipe-inverted.json`），不扫描全部菜谱正文；先按 locked_basket 过滤再打开完整菜谱（复杂度判定优先读菜谱元数据 complexity 字段）；用户选"不需要做法"时 recipe_steps 读取数=0，选"需要"时只打开最终入选的 moderate/complex 中饭晚饭完整步骤；营养最多两轮；菜单包装锁定后才算价格；只跑一次采购汇总；只生成用户所选格式；不运行全库提取/去重/审计；耗时记入内部性能日志。`maintenance_audit` 模式需明确要求才运行。

> 每次生成周计划都按此顺序执行，**不得跳步、不得换序**。每步的输入输出见下；任何一步缺信息，按 `workflows/fallback-flow.md` 降级，不猜。

## 执行顺序

| # | 步骤 | 做什么 | 产出 |
|---|---|---|---|
| 1 | 意图识别 | 判断用户要"理论解释"还是"周计划"；要理论就只答理论，不生成计划 | 意图判定 |
| 2 | 安全筛查 | 按 `references/safety-rules.md` 走主线路由；命中红线→停止自动定制，转医嘱范围内适配。**过敏原/医嘱/宗教饮食等安全排除在此登记 restriction_status，后续预选不得恢复** | 安全分支结论 |
| 3 | 关键六项信息 | 按 `references/questionnaire.md` 的一行式模板收集（做法与日期走默认值，输出格式在问卷内可选多种）；已提供的直接复用，缺项走动态追问 | 用户信息卡 |
| 4 | 周期阶段与进食窗口 | 跑 `scripts/macros_calculator.py --cycle`；逐日定阶段/模式/禁食时长（L0/L1 上限内） | 7 天阶段表 |
| 5 | 预算与所在地价格口径 | 采购不再区分线上线下来源；只定所在城市公开价格来源；同时按日期规则定 start_date（默认 request_date+1，连续 7 天） | 价格口径与日期口径 |
| 6 | 初步食材篮子 | 先生成 `initial_basket` 草案（结构见 `references/output-schema.md`）：依据周期阶段、营养边界、所在地普遍可获得性、预算、当季（`data/seasonal-foods.json`）、烹饪时间、包装规格（`data/package-rules.json`）、保存期。**此时还没有菜谱** | 初步食材篮子 |
| 7 | 用户食材预选 | 跑 `scripts/ingredient_preselector.py --build-candidates`：三层展示（本周核心食材 P/V/C 编号 + 本周风味 F + 可选点缀 O），每项只显示一条理由。用户只说"不想要的编号"；删除走四类处理（直接删除/功能替换/结构替换/方案受限）；输出预选列表后当前回合停止，收到回复再锁定；用户回复"都可以吃"整批接受 → 全部记 `accepted_batch`；点名想吃 → `explicitly_wanted`；不在候选 → `merely_allowed`；仅用户明确跳过/原请求要求直接生成/不支持多轮/fallback 默认篮子时转 provisional_locked_basket（user_reviewed=false, selection_mode=bypassed） | 预选结果（含三档语义） |
| 8 | 锁定食材篮子 | 生成 `locked_basket`（字段见 `references/output-schema.md`）：删除项不进入后续任何环节；后续菜谱原则上只用锁定核心食材，例外仅家庭基础调味、可省略装饰、用户同意的 1 种低频调料、已有库存 | 锁定食材篮子 |
| 9 | 菜谱库检索候选 | 在统一**生产**菜谱池过滤（仅 record_status=production：`data/recipe-index.json` 已审 HowToCook + `data/book-recipes.json` 已批准书籍菜谱 + `references/recipe-pool.md` 已批准母版；`data/library-manifest.json` 为准）：五层过滤：① locked_basket 符合性（核心食材必须来自锁定篮子）→ ② 安全与模式适配（过敏原/医嘱/周期模式/营养边界）→ ③ 烹饪条件（时间/厨具/技能）→ ④ 包装与余量（易腐复用/清库存）→ ⑤ 多样性；所在地常见可购性仅作排序加分；预选三档加分（explicitly_wanted > accepted_batch > merely_allowed）。书本菜谱不自动加权；来源配额仅柔性观察指标。**排序后跑覆盖门禁**：accepted_batch 未使用项逐项补偿搜索→替换模拟→营养/包装/预算/多样性复核→入选或写真实 reason_code 到 selection report | 候选菜谱集 + selection report |
| 10 | 约束装配 | 时间/厨具/包装/多样性约束逐条过：易腐食材≥2 顿；菜谱指纹多样性（见下）；烹饪时间在用户限额内 | 可行菜谱集 |
| 11 | 七天菜单 | 从可行集组合成 7 天菜单；一人食模式规则叠加生效；**做饭安排按用户明确信息执行**（未说明周末时标"待确认"，不假设三餐在家；直接生成时周末沿用已明确的每日自炊餐数，但不复制仅适用于工作日的地点；七天同模式不算错误，只与用户明确信息冲突才算）；**每日建议逐日独立撰写，禁止复制某一天的建议** | 菜单草稿 |
| 12 | 营养重算校验 | 用 `data/foods-table.json` 按本计划克数重算，**外食餐次纳入 `data/cafeteria-meal-templates.json` 的区间估算后算全天合计**；营养计算最多两轮（草案批量 + 最终复核）；跑 `scripts/macros_calculator.py --check`；超标→回第 11 步 | 达标菜单 |
| 13 | 反向汇总采购 | 菜单→汇总→扣库存→按包装规格取整；跑 `scripts/shopping_aggregator.py`。**未在菜单中使用的锁定食材不得进入采购清单**（含预选未入选项：只进 selection report 与执行提示一行说明） | 采购清单 |
| 13.5 | 价格锚定（硬门禁） | 每条采购项必须有价格：优先 `scripts/market_price_normalizer.py` + `references/cities/{city}-price-sources.yaml` 有效样本；无样本（confidence low/unavailable）按 `data/price-estimates.json` 六大类行情估算并标注估算口径。**禁止"暂无参考价/实价为准/待定"占位**；区间按上限累加，清单顶部显示"本周预算约 ¥XXX（估算口径，实际以购买时为准）" | 带价采购清单 |
| 14 | 输出采购信息 | 每项食材输出采购清单字段（`references/output-schema.md`：食材/常用购买名称/建议购买量/常见规格/参考价/平替/剩余去向）+ 储存方式 | 最终采购清单 |
| 15 | 定稿 plan.json 并渲染 | 业务结果一次写入并校验 plan.json（契约见 output-schema）；用 `scripts/render_plan.py` 固定组件渲染，禁止占位符全局 replace 与运行时修模板；按用户所选格式交付（单选只交单种）；**正式文件不含"03 本周食材选择"小节**；做法按问卷必选项（B 则 recipe_steps 读取数为 0） | 交付物 |

## 两次生成的核心原则

**先篮子，后菜单（两段之间加一次用户预选）。** 第一阶段的食材篮子决定"这周买什么"，用户只做减法与少量替换，锁定后第二阶段只在锁定篮子内选菜谱。禁止反过来——先想菜谱再凑采购，必然产生一次性配菜和浪费。

### 食材预选（步骤 7-8 的规则）

- 候选数量（一人食每日自炊 1 餐）：蛋白质候选 5 至 7 种、蔬菜候选 8 至 12 种、天然碳水候选 3 至 5 种、风味候选 4 至 6 种；每日 2 餐适度扩大（见 `scripts/ingredient_preselector.py` 内 QUOTA）
- 进入候选的最低要求：可匹配 ≥2 道菜、≥2 种烹法、≥2 种味型、≥1 个替代品、≥1 个明确余量去向
- 候选得分 = 用户偏好 25% + 可购性 20% + 菜谱支撑度 20% + 包装消耗度 15% + 加工便利性 10% + 时令 10%（无可靠价格时价格权重不参与，其余归一化）
- 偏好与安全分离：preference_status（favorite/acceptable/neutral/dislike_this_week/permanent_dislike）只管口味；restriction_status（allergy/medical/religious/ethical）是安全门禁，不进候选、不可恢复
- 一次删除默认 dislike_this_week；只有用户明确说"以后不要"才记 permanent_dislike
- 别名删除只删该食材（删"包菜"=删卷心菜，不株连十字花科）；食材与味型分离（删咖喱味型不删土豆）
- 用户删除全部鱼虾：不劝必须吃鱼，不自动推荐补充剂，从未排除蛋白质补足
- 用户删除全部主要蛋白质：暂停达标输出，只询问一个最关键问题，不生成虚假达标菜单
- 新增食材：检查安全/模式/所在地可获得性/设备/包装/≥2 道菜支撑/预算；暂不适合可标 optional_treat / next_week_candidate / special_purchase / single_meal_only
- 菜谱不足时的降级顺序：放宽菜谱来源 → 同食材不同味型 → 用户未排除的耐储替代 → 最后才追加询问一个最关键类别；**不得自动加回用户删除的新鲜食材**
 第一阶段的食材篮子决定"这周买什么"，第二阶段只在篮子内选菜谱。禁止反过来——先想菜谱再凑采购，必然产生一次性配菜和浪费。

**篮子四维平衡**：`proteins`（3 至 5 种）/ `vegetables`（4 至 8 种）/ `carbohydrates`（平衡激素日 2 至 3 种，酮生物日可为空）/ `flavor_bases`（从 `data/flavor-bases.json` 选 3 至 4 个味型）。一人食按 SKILL.md 分层表压缩总数。

## 菜谱指纹与多样性（步骤 9-10 的硬规则）

每道候选菜谱形成指纹：`recipe_fingerprint = {protein, vegetable, method, flavor, structure, texture}`。

- 相邻两顿指纹相似度 ≤ 70%（6 维中相同维 ≤4）
- 相似度 >85% 的组合一周内只出现一次
- 同一主蛋白出现 2 至 3 次时必须换烹法或味型（如鸡腿：焖→咖喱→烤）
- 同一蔬菜复用时不能总配同种蛋白
- 连续两顿不都是汤羹；连续两顿不都是清淡蒸煮
- 高油重口（麻辣/红烧/油炸）每周 ≤1 至 2 次
- 一周烹法覆盖 ≥3 种（快炒/蒸/焖/汤锅/凉拌中选）
- 校验工具：`scripts/diversity_checker.py`（指纹按六维比较，"菜名不同但结构相同"的菜会被识别为高度相似）
- 来源配额仅柔性观察指标，不得凌驾于 locked_basket、安全、包装消耗、时间、偏好与营养校验；无法满足时允许偏离并记录原因；书籍来源不自动加权（细则见 `references/book-recipe-extraction.md`）

## 质量指标（每次生成后自评，不达标先修）

| 指标 | 目标 | 计算 |
|---|---|---|
| 采购可执行率 | ≥95% | 有明确搜索词+购买规格的食材数 ÷ 总食材数 |
| 食材消耗率（易腐） | ≥85% | 计划内预计使用量 ÷ 建议购买量 |
| 菜谱多样性 | 综合达标 | 主蛋白/蔬菜类别/烹法/味型/结构五维覆盖 + 相邻相似度，不只看菜名重复 |

## 下周迭代（weekly_feedback）

用户执行一周后回访时，收集六类反馈并写入 `diet-plans/weekly_feedback.md`（格式见 `references/output-schema.md`）：

- `liked_recipes` → 保留其味型权重，下周可再出现 1 次
- `disliked_recipes` → 降低同味型/同结构权重
- `unavailable_ingredients` → 降低买不到食材的权重，优先用 `data/substitutions.json` 平替
- `actual_cooking_time` → 修正菜谱用时估计（偏差>10分钟下调难度档）
- `leftovers` → 下周篮子优先消耗剩余食材

菜单新旧比例：保留 1 至 2 道用户喜欢的熟悉菜，新增 3 至 4 道新菜。
