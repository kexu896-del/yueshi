# 月食输出策略（output-policy）

本文件是 SKILL.md 的拆分部分，承载渲染架构、执行模式、输出格式、章节白名单、视觉与分页、做法规则、执行规范与输出前最终门禁。所有格式（HTML/PDF/Markdown/Word）共用同一份 plan.json；渲染器只读 plan.json，不得重新编排菜单或营养。

## 渲染架构（三层，禁止运行时修模板）

- **三层固定**：①`plan.json`——菜单、营养、采购、显示开关一次定稿并通过校验；②固定组件渲染器；③`styles/screen.css` 与 `styles/print.css` 只负责屏幕与打印样式。
- **渲染器分工（五个脚本，语义唯一）**：`scripts/render_plan.py`——HTML 固定组件实现本体（不当总控）；`scripts/render_html.py`——HTML 入口（render_plan 的命令行包装）；`scripts/render_pdf.py`——PDF 渲染器：调 render_html 链路生成临时自包含 HTML → Chromium 打印一次 → 删除临时文件；`scripts/render_markdown.py`——Markdown；`scripts/render_docx.py`——Word；`scripts/render_output.py`——总控路由，按用户所选格式分发，本身不含渲染逻辑。所有渲染器只读 plan.json 与统一配置文件（食堂模板/价格估算），不得各自实现营养计算或菜单逻辑。
- **plan.json 版本门禁（plan_meta 契约）**：plan.json 必须携带 `plan_meta` 版本块，字段固定为 `build_id` / `plan_schema_version` / `rules_bundle_hash` / `skill_version` / `runtime_rules_version` / `nutrition_rules_version` / `output_policy_version` / `recipe_manifest_version` / `effective_parameters_version` / `price_data_version`。渲染前校验：① plan_schema_version 与渲染器支持版本一致；② rules_bundle_hash 与当前规则文件组合哈希一致（存在时强制比对）；③ effective_parameters_version 与计算日志一致；④ recipe_manifest_version 与 ranker 日志一致。任一不满足即停止渲染，防止新版生成器配旧版渲染器、新版营养参数配旧版 plan.json 混跑。
- **固定渲染规则**：plan.json 校验通过后渲染阶段不得重新编菜单或营养；禁止几十个占位符全局 replace；禁止运行时调整替换顺序、猜测锚点、重写 `<main>`、提取 CSS 自建替代 body；发现未填充变量、组件缺失或结构错误立即停止并报告缺失字段；HTML 只渲染一次，PDF 只转换一次；调用方式固定为 `python scripts/render_plan.py --input plan.json --format pdf --output plan.pdf`，不在 shell 命令里拼长 HTML。
- **plan.json 是唯一中间件（强制）**：模型只负责产出并校验 plan.json；HTML 由固定组件生成，**禁止模型手写、拼接或改写 HTML**（包括封面、目录、表格、样式块）；发现需要调整页面结构时，改渲染器或 CSS，不改单个交付文件的 HTML。
- **视觉语言（固定组件不等于简陋页面）**：保留高对比 hero、大号日期、状态四宫格与章节自动编号；保留柔和分区底色、圆角日卡、每日营养合计底条和备餐/建议卡；不使用 checkbox、localStorage、线上平台下单逻辑和多余营养图。
- **组件黑名单（永久禁用）**：目录页/TOC 组件（一周文档不需要目录）、环形图/饼图/甜甜圈图等一切营养图形组件（营养信息以每日一行合计呈现）。**食材↔菜谱对照（menu-map）保留**：网页版为可折叠下拉，打印/PDF 自动展开为表格。
- **一人食一锅出硬过滤**：正餐只保留一锅出结构（白名单见 references/runtime-rules.md「一人食模式」；recipe_ranker.apply_one_pot_rule；元数据缺失时记录日志并放行，不得伪造字段）；一锅出菜谱排序加权。
- **单文件自包含**：交付 HTML 必须把 CSS 与 SVG 全部内联（渲染时读取 `styles/screen.css` / `styles/print.css` 内嵌为 `<style>`），不得出现相对路径样式引用，离开项目目录仍能完整显示。
- **PDF 首页核验**：首页日期和月相必须经过打印预览、实际 PDF 和 PDF 转 PNG 三道检查；最后一页不得出现免责声明独占页。
- **页数硬约束与压缩顺序**：一周计划 **PDF ≤9 页（含封面）**。字号下限：正文 ≥9pt、采购表格 ≥8.5pt、行高 ≥1.25——不得为压页数跌破下限。新增内容导致超页时按固定顺序压缩：①删重复说明 → ②合并备注列 → ③简化平替与余量表述 → ④调边距 → ⑤在下限内轻微缩字号 → ⑥仍不行才允许第 10 页并在内部日志记录原因。免责声明与末节同页。
- **色块统一**：所有章节卡片使用同一中性底色（#fcfaf5 系），只允许细边条和标题点缀用紫/绿；采购清单、食养之理等任何章节不得使用大面积黄色或紫色底块。
- **迭代期性能规则（fast 模式补充）**：迭代调试时只跑受影响测试与首页/末页 PNG 抽查；chromium 每次只启动一次完成打印；全量回归与逐页检查只在合并前跑一次。各步骤耗时记入内部性能日志。
- **渲染后自动门禁**：HTML 不得出现 `{{` `}}` PLACEHOLDER undefined None [object Object]；只有一个 main 和一个 cover；每天一个 day-card；每餐 time/status 字段各最多一次；无空 section、无相对路径样式引用、无结尾 page-break。PDF 侧：首页标题/日期/月相清晰、标题区非纯白或深色标题带、食材名不逐字竖排、午餐时间与状态不重叠、免责声明不独占一页、最后一页无异常少量正文、无文字截断/表格横溢/空白尾页。

## 执行模式（默认快速路径）

`execution_mode`：默认 `fast`；重型维护用 `maintenance_audit`（需明确要求才运行）。

**快速模式（fast）规则**：
1. 启动时一次加载生产 manifest、机器食材表 `data/foods-table.json` 和轻量菜谱索引 `data/recipe-production-index.json`；
2. 候选检索用 ingredient→recipe 倒排索引（`data/ingredient-recipe-inverted.json`），先按 locked_basket 过滤，再打开少量完整菜谱；用户不需要做法时 recipe_steps 读取数为 0，需要时只打开最终入选的 moderate/complex 中饭晚饭；
3. 只对最终候选重新计算营养；营养计算最多两轮（草案批量计算 + 最终复核）；
4. 菜单与包装锁定后才运行价格计算；只运行一次采购汇总；
5. 只生成用户选择的一个最终格式；
6. **不运行**全库书籍提取、全库去重、来源审计、多格式渲染或调试输出；
7. 各步骤耗时记录到内部性能日志，不写入用户文件。性能日志固定字段：`performance_log: manifest_load_ms / food_table_load_ms / basket_build_ms / recipe_filter_ms / recipe_open_count / nutrition_passes / nutrition_ms / price_ms / render_ms / output_count`。
8. 行为验收（不规定固定秒数）：`nutrition_passes <= 2`；用户选一种格式时 `output_count == 1`（用户要求多格式时等于所选数量）；完整菜谱文件只对最终候选打开；未调用书籍提取、全库去重扫描或 maintenance_audit。
- 多样性只在本周候选集合中计算，不做全库两两相似度。

## 输出格式（按用户选择交付）

可选格式：`pdf` / `html`（网页）/ `md` / `docx`。

- **用户明确选择一种格式时，只交付该一种**：选 PDF 只交付 plan.pdf，选 Word 只交付 plan.docx，不再额外交付其他格式。
- 用户未指定 → 默认 Markdown；用户明确要求多种格式 → 可同时交付多种，不限制。
- 转换所需中间文件写入 tmp 目录，不作为附件。
- **写作约定、品牌视觉、月相算法、采购清单页面、信息架构、打印与 PDF 门禁全部见 `references/visual-spec.md`（硬性约束）**；打印样式与网页样式分开维护（`styles/print.css` / `styles/screen.css`）。
- **章节白名单（最终用户可见，固定顺序）**：① 本周阶段（周期适配启用时）→ ② 采购清单（品类分组，含预算合计）→ ③ 备餐任务（含食材流转核验）→ ④ 七天菜单 → ⑤ 食养之理与执行提示（理论+操作合并为一节）→ ⑥ 安全提示/免责声明。**禁止独立的"本周档案/基本情况/个人数据"章节**——用户基本信息只用于内部计算，不呈现在交付文件中；initial_basket、removed_items、replacements、locked_basket 只保留在内部。
- **每日卡片标题行不得出现"禁食""空腹"字样**：标题行只写 周X · 日期 · 阶段 · 模式 · 进食 HH:MM–HH:MM；"夜间空腹 12h"一类表述只允许在末节"食养之理与执行提示"中出现一次。
- **食养之理与执行说明（合并节，必保留）**：理论部分为 3 段自然叙述、不列点，每段 2 至 3 句、每句一个信息点——第一段：周期阶段 + 禁食安排 + 碳水选择逻辑；第二段：时令食材 + 蛋白质搭配 + 体质适配（如缺铁/胀气）；第三段：简要操作提示。执行提示 4 至 6 条、每条 15 至 25 字（用药间隔/外食策略/备餐顺序/不适调整），不重复正文已解释的内容，不出现推动互动的句子；对应 plan.json 的 `wisdom.paragraphs` 与 `execution_tips` 字段。节内只允许"本周怎么安排 / 本周执行要点"两个固定子标题（同字号加粗，见"食养节子区块"）；全部达标时不重复罗列营养数字。
- **自行解决早餐只显示菜品与克数**：日卡中写"全麦面包2片60g · 水煮蛋1个 · 牛奶250ml"，禁止附加"自行简单解决（……约xxx kcal）"一类描述；状态列已标注"自行处理"。
- **备餐任务节（必保留）**：主采购日任务 + 备餐日任务 + **食材流转核验**（逐项列出"购买量 vs 计划用量 → 0 剩余 / 剩余去向"，至少 3 项 0 剩余验证）。
- **采购清单按品类分组展示**（肉蛋水产与豆制品 / 蔬菜与菌菇 / 谷物薯类与主食 / 乳品与油脂 / 水果 / 调味与干货 / 其他），每项字段：食材、需要量、建议购买规格、参考价、替代、剩余去向；**"替代"与"剩余去向"是两个独立列**；参考价列按"每行必须有价格"硬门禁执行。
- 采购清单使用**静态表格**，不设计可点击交互；网页不含 checkbox、localStorage 或勾选状态说明。
- 理论依据必附、直接展示不折叠、只说人话；不默认展示完整书目，但涉及书中特有模式、周期数字或存在争议的观点时，应标注来源层级，详细来源放在附注"依据说明"中。
- 中饭/晚饭稍复杂菜式按问卷必选项附做法（见"菜谱做法规则"）。

**营养信息展示**：
- 默认**不设独立的"营养概览"章节**，不生成环形图、柱状图、进度条或目标带。
- 每日菜单末尾显示当日营养估算一行：净碳水、蛋白质、脂肪和总能量；外食日标区间估算并注明"不标记为精确达标"。
- 营养校验属于内部必做步骤（macros_calculator.py --check），不因取消视觉概览而省略。
- 全部达标时不重复展示周汇总；只有出现超标、低于安全线、偏离原书参考值或外食低置信度时，才在"执行提示"中展示对应提醒。
- 用户主动要求详细数据时，可另附七天营养汇总表或 CSV。

## 菜谱做法规则（recipe_steps，仅中饭和晚饭）

- "稍复杂的菜式"只针对中饭和晚饭；早餐、简单冷食、直接加热食品或明显无需解释的搭配，不强制附做法。
- **优先使用菜谱元数据复杂度字段** `complexity: simple | moderate | complex`：只有 moderate/complex 的中饭和晚饭才展开步骤；无该字段时再按下列条件判定。
- 判定为稍复杂（满足任一）：操作步骤 ≥4 步；需提前腌制；需焯水或煎制后再焖烧；需预先调碗汁/酱汁；需两种以上火力阶段；需特别判断熟度、收汁或口感；使用电饭煲/蒸锅/空气炸锅的非直观程序。
- **做法由问卷必选项决定（无默认值）**：选"需要"时，最终入选且 complexity=moderate/complex 的中饭和晚饭必须在最终文件出现"做法"小节（早餐、简单冷食、直接加热食品不受影响）；选"不需要"时**不读取、不生成、不渲染 recipe_steps**（读取数=0）；漏选只补问这一项。模板含 `recipe_steps` 插槽；选了"需要"但内部有步骤未渲染 = 验收失败。
- 做法字段（output-schema：`recipe_instruction`）：steps、preparation_notes、heat_or_temperature、doneness_signal、advance_prep。

## 执行规范

- 每餐食材给克数和每餐营养素小计；用油控制总量、避免氢化油与反复煎炸油、不为凑脂肪比例大量添加黄油椰子油；碳水 A 模式优先绿叶菜、B 模式主食轮换（同一种 ≤3 次/周），南瓜/胡萝卜/白萝卜算蔬菜；蛋白优先蛋鸡鸭鱼虾瘦牛豆腐，加工肉 ≤2 次/周；调味以淡为主、禁用人工甜味剂；进餐先蛋白蔬菜后主食（建议非强制）；酒精默认不推荐；每日饮水 1.5 至 2.5L。
- 营养置信度每餐标注：high（称重/标签）/ medium（食谱估算）/ low（外食目测）；当天有 low 餐次时不得标"精确达标"，改"预计接近目标"。
- 执行偏差不惩罚：不补偿性节食、不额外延长禁食；连续 3 天执行差先怀疑计划。

## 输出前最终门禁（全部通过才可输出）

- **safety**：无慢病自动方案；未生成 >16h 禁食；无医学断言；无体质诊断标签；无补充剂剂量；无补偿性节食表述；无排泄类描述。
- **nutrition**：净碳水超限或蛋白不合规已在 plan.json 冻结前自动微调克数并复核通过（渲染后手改即失败）；蛋白判定按四字段执行，book_reference 不作硬上限；热量不低于安全线；蛋白不低于下限；过敏原已剔除；宏量合计与食材行一致；low 置信度餐次未标"精确达标"。
- **execution**：采购数量与菜单匹配；采购清单字段齐全（可执行率≥95%）；易腐消耗率≥85%；备餐解冻自洽；烹饪时间在限额内；进食窗口与作息匹配；多样性规则通过；预算按购买包装计算而非菜单净需求量；无可靠价格时未输出虚构总价；仅 budget_included=true 的区间价格按上限校验预算，low 置信度区间未计入合计；缺货替换后已重算营养/包装/价格/多样性；参考价的来源/发布日期/单位/置信度只保存在内部日志，用户文件只出现具体参考价。
- **rendering**：PDF 标题、日期和副标题为黑色且对比度合格；月相装饰未覆盖文字；meal_time 与 meal_status 分字段渲染；午餐 12:00 与"外食 · 区间估算"无重叠；全文不含 BOM、软连字符和零宽字符；页面无文字截断、表格溢出和异常分页；打印样式来自 styles/print.css，不内联在模板中。
- **consistency**：无"长禁食可执行"残留；书中观点未写成医学事实；模板无硬编码热量数字；月相未参与健康判断。
- **preselection**："都可以吃/全部保留"已生成 `accepted_batch`（user_reviewed=true）而非 bypassed；`accepted_batch_items` 均已使用，或每项有 `ingredient_selection_result` 且原因码来自 ranker 日志（不由渲染器猜测）；explicitly_wanted 未入选时有用户可见原因；未入选食材未进入采购表和预算（用户可见文件最多在执行提示中说明一行并给出可替换菜式）；可替换方案已完成营养、包装与预算模拟；菜谱核心食材均来自 locked_basket 或允许例外白名单；removed_items、week_only_dislikes 和 permanent_dislikes 未出现在菜谱、平替或采购清单；用户新增食材已通过安全与模式检查；locked_basket 中未实际使用的核心食材未进入采购清单；锁定食材利用率达标或已记录偏离原因。
- **data-status**：recipe_ranker 只读取 library-manifest 中 record_status=production 的来源；effective-parameters.json 由 approved 审计记录生成且无人工无记录修改（parameter_id 唯一、数值与单位一致、source_rule_id 可追溯、protocol_version 与 manifest 一致、SKILL/脚本无参数硬编码残留）；candidate、proposed、culture_only、historical_lead、rejected 和 stale 记录未进入正式计划；数据源版本和计划生成日期已写入内部日志。

## 用户可见术语门禁（round33 新增，round35 限定扫描范围并扩充黑名单）

内部术语允许存在于 plan.json 内部字段、日志、审计报告和开发文件；门禁**只扫描可见字段范围**，禁止对整个 plan.json 或构建目录做全文搜索（避免误报）：

```
visible_text_fields:
  - cover.title
  - cover.subtitle
  - cover.status_cards[].label
  - sections[].title
  - days[].display_title
  - meals[].title
  - meals[].display_content
  - meals[].status_label
  - wisdom.paragraphs[]
  - wisdom.action_items[]
  - disclaimer.display_text
```

及以上字段在最终用户文件（HTML/PDF/MD/DOCX）中对应的可见文字。禁用词：**周期协议**、source_verified、audit_status、source_rule_id、protocol_version、effective_parameters、safety_policy、reason_code、accepted_batch、locked_basket、provisional_locked_basket、plan.json、gate_result、low confidence、runtime-rules、nutrition-routing。内部字段无需改名；显示转换：周期协议 → 阶段适配；协议参数 → 本周饮食安排；协议执行 → 按当前阶段安排；reason_code → 未入选原因；accepted_batch → 已确认食材；locked_basket → 本周食材；low confidence → 区间估算。渲染器 validate 强制检查。

## 章节字体一致性（round33 新增）

同一章节内自然段、项目符号和普通说明使用相同正文字号。"食养之理与执行说明"：标题走章节标题统一字号；自然段与项目符号打印端均 10.5pt、行距 1.55–1.65；项目符号只改变缩进，不改变字号；**禁止列表继承浏览器默认字号**；免责声明可比正文小 1 至 1.5pt（9pt、行距 1.55）。

## 餐次内容完整性（round33 新增，round35 拆分两层错误码）

餐次完整性分两层门禁，错误码分开处理，不得用同一个错误兜底：

```
meal_content_gate:
  business_data:
    required: [source, time, title, display_content, status_label]
  rendered_output:
    verify_visible: [title, display_content, status_label]
```

- **MEAL_DATA_MISSING**（业务数据缺失）：plan.json 或食堂模板缺少上述必填字段 → 返回菜单装配层修复，不进入渲染；
- **MEAL_RENDER_FIELD_DROPPED**（渲染字段遗漏）：plan.json 数据齐全但最终文件漏出（如只显示"食堂点餐："而无具体内容）→ **不重新计算菜单**，只重跑固定渲染器。

cafeteria 餐次必须同时显示：点餐结构（模板 display）、外食状态、营养估算与置信度；meal_title 与 order_template.display 均不得为空。

## 餐次状态一致性（round33 新增，round35 统一字段名）

餐次计划状态统一字段 `meal_plan_mode` = planned / guidance_only / excluded（餐次类型另用 `meal_type`；不同时存在 breakfast_mode / meal_mode / recipe_mode 等同义字段，历史 breakfast_mode 仅按 schema 映射）。有固定日期、食材、克数并进入采购和营养的餐次（planned），不得标记"自行处理"；guidance_only 餐次不得有固定逐日克数、不得进入采购清单。validate 对"有克数却标自行处理"直接报错。

## 其他渲染细节（round33 新增）

- **当日建议贴卡**：`.day-advice` 必须与所属日卡同页（break-before/break-inside: avoid），不得作为独立色条漂到下一章节上方。
- **menu-map 打印压缩**：打印/PDF 只展示前 8 项重点（易腐/0剩余优先），其余折叠行打印隐藏并附"其余见网页版展开"提示；网页版完整可折叠。
- **库存食材价格显示**：`purchase_status: from_inventory` 或参考价为 0 元库存项，采购清单价格列显示"库存"，预算按 0 元计，不显示"约0元"。
- **一锅出结构说明**：plan.json 餐次可带 `meal_structure`（type / equipment_count / simultaneous / structure_note），渲染时在克数下方显示 structure_note（如"同一蒸锅上下层完成"），不得只贴"蒸锅组合"标签。
- **阶段表行数**：本周阶段表只保留"本周 + 下周"两行，不做下下周远期推算。
- **文案平实化**：不写"代谢最佳状态"一类绝对表述，改用"部分人在这个阶段会感觉精力逐步回升，以实际状态为准"；末页不出现"提前告诉我"一类推动互动句。

## 排版令牌（round34 新增，round35 扩展到四种输出格式；渲染器不得各自解释字号）

```
typography_tokens:
  section_title:    { pt: 18 }
  subsection_title: { pt: 12, bold: true }
  body:             { pt: 10.5, line_height: 1.6 }
  list:             { pt: 10.5, line_height: 1.6 }
  meal_title:       { pt: 11, bold: true }
  meal_detail:      { pt: 10.5, line_height: 1.5 }
  nutrition_summary:{ pt: 10, line_height: 1.5 }
  disclaimer:       { pt: 9, line_height: 1.5 }
```

**四格式映射（语义一致，不照搬 CSS 数值）**：
- HTML/PDF → CSS class（pt 值直接生效）；
- DOCX → Word 命名样式实现，不得直接搬"10.5pt CSS"：`Yueshi Body`（正文）、`Yueshi List`（列表）、`Yueshi Disclaimer`（免责声明），其余令牌同理对应命名样式；
- Markdown → 标题层级（# / ## / ###）与普通列表表达同一语义层级。

同一章节内自然段、普通说明和项目符号必须使用同一正文字号与行距；项目符号只改变缩进不改变字号；免责声明是独立区块，不得作为执行提示列表的尾项（plan.json 中 wisdom.paragraphs / execution_tips 与 disclaimer 分字段存放，渲染器分开渲染）。

## 食养节子区块（round34 新增）

"食养之理与执行说明"在同一章节卡片内分两个子区块：**本周怎么安排**（3 段正文，解释阶段、食材和做饭逻辑）与**本周执行要点**（4 至 5 条具体动作，不重复正文已解释的内容）。子标题用 `.wisdom-subheading`（与正文同字号、加粗），不另起章节。

## plan_meta 构建标识（round34 新增）

plan_meta 在明细版本字段之外增加：`build_id`（如 yueshi-2026.09-v1）与 `rules_bundle_hash`（runtime-rules + nutrition-routing + output-policy + safety-rules + effective-parameters + recipe-manifest 的组合哈希）。渲染器优先校验 plan_schema_version 与 rules_bundle_hash；各明细版本字段用于日志和排错。
