# 变更记录（唯一历史记录文件，最新在前）

## 用户指示 2026-08-24（round 37：定版 yueshi-1.0.0 Stable）
- **措辞修正**：plan_meta 契约中"八个明细版本字段"改为"各明细版本字段"（数量表述不准确：含构建与校验字段共 10 个，明细版本实为 7 个；SKILL.md 与 output-policy.md 同步）。
- **定版标记**：SKILL.md frontmatter 增加 `version: yueshi-1.0.0`，入口文件自本版起冻结。
- **维护口径固化**：developer/maintenance-map.md 新增「定版维护口径」——菜单问题改 runtime-rules/ranker、营养问题改 nutrition-routing/计算器、排版与漏字段改 output-policy/渲染器/CSS、数据问题改对应 JSON/manifest、所有修改写 CHANGELOG；不再往 SKILL.md 追加渲染/菜谱/测试细节。
- 新增 tests/test_round37_stable_release.py（4 项）。


## 用户指示 2026-08-24（round 36：定版候选修正）
- **plan_meta 契约补全**：SKILL.md 与 output-policy.md 的版本门禁字段列表正式声明 `build_id` 与 `rules_bundle_hash`（原先只在"构建标识"小节出现、契约列表遗漏）；明确渲染器优先校验 plan_schema_version + rules_bundle_hash，八个明细版本字段用于日志排错；哈希覆盖六文件（safety-rules / runtime-rules / nutrition-routing / output-policy / effective-parameters / library-manifest）写入契约。
- **fatal_after_retry 归入 fatal_reason**：门禁状态严格保持三类（auto_fix / user_input_required / fatal），不再出现第四个状态值；auto_fix 两轮后仍失败 → status 升级为 fatal、fatal_reason=auto_fix_retry_exhausted；fatal_reason 枚举固定为 core_rule_file_missing / safety_route_unresolvable / plan_schema_mismatch / rules_bundle_mismatch / corrupted_plan_json / auto_fix_retry_exhausted / renderer_retry_exhausted。
- 新增 tests/test_round36_release_candidate.py（4 项，含定版 18 项回归清单到测试文件的映射核验）；test_round35_gates.py 1 处断言同步更新。


## 用户指示 2026-08-24（round 35：门禁分类修正与可见范围限定）
- **gate_result 分类冲突修正**：`user_input_required` 明确定义为"可通过一次追问补齐"的缺失（餐次、做法选择、输出格式、预算、地区、必要健康信息）；`fatal` 收敛为核心规则文件缺失 / 安全路由无法执行 / plan_schema 不匹配 / rules_bundle_hash 不匹配 / plan.json 损坏 / 渲染器重试后仍失败；"安全筛查未完成"拆分：缺用户信息 → user_input_required，文件损坏或安全路由无法执行 → fatal。
- **入口门禁逐项标注失败等级**：11 项检查分别标注 [fatal] / [user_input_required] / [auto_fix]；auto_fix 两轮后仍失败升级为 `fatal_after_retry`，不再发现即停。
- **餐次完整性拆分两层错误码**：`MEAL_DATA_MISSING`（业务数据缺失 → 返回菜单装配层修复）与 `MEAL_RENDER_FIELD_DROPPED`（渲染漏字段 → 不重新计算菜单，只重跑固定渲染器）；render_plan.py 与 validate_html 分别实现。
- **术语门禁限定可见字段**：定义 `visible_text_fields`（cover/sections/days/meals/wisdom/disclaimer 的可见字段及最终文件可见文字），禁止对整个 plan.json 或构建目录全文搜索以免误报；黑名单补充 accepted_batch / locked_basket / provisional_locked_basket / plan.json / gate_result / low confidence / runtime-rules / nutrition-routing，并给出显示转换（已确认食材 / 本周食材 / 区间估算）。
- **餐次状态字段统一**：`meal_plan_mode` = planned / guidance_only / excluded，餐次类型另用 `meal_type`；不同时存在 breakfast_mode / meal_mode / recipe_mode 同义字段，历史 breakfast_mode 仅按 schema 映射（SKILL.md / runtime-rules.md / output-policy.md 同步）。
- **排版令牌扩展四格式**：`typography_tokens`（section_title/subsection_title/body/list/meal_title/meal_detail/nutrition_summary/disclaimer）；HTML/PDF → CSS class，DOCX → Yueshi Body / Yueshi List / Yueshi Disclaimer 命名样式（不照搬 CSS pt 值），Markdown → 标题层级与普通列表。
- **措辞与维护**：SKILL.md 摘要"周期协议参数"统一为"周期阶段参数"（nutrition-routing.md 保留 protocol_rule 正式定义）；rules_bundle_hash 覆盖补充 references/safety-rules.md（共 6 文件）；maintenance-map 标注 "render_plan.py is not an output router"。
- 新增 tests/test_round35_gates.py（10 项）；test_round32/34 各 1 处断言随措辞更新。


本文件是参数与规则变更的唯一历史记录位置。SKILL.md、脚本注释中不再内嵌"某年某月某日用户指示"类变更说明；规则正文只描述当前有效行为，历史沿革一律写在这里。CHANGELOG.md 只记录历史，不是运行规则，不参与规则冲突优先级。

## 2026-08-24 · round 34（入口门禁收口与排版令牌）

- 用户可见术语门禁升入 SKILL.md 入口摘要与入口级最终门禁（禁用词含 reason_code；执行提示也在范围内）；description 与内部措辞改用"周期阶段适配/周期阶段规则"。
- 规则冲突从线性优先级改为按领域裁决；output-policy 不得删除 runtime-rules 必需用户字段，runtime-rules 不得规定视觉样式。
- 入口级最终门禁扩为 10 条，增加：术语检查、餐次内容完整性（cafeteria 必须显示点餐结构）、meal_mode 与字段一致性、免责声明独立组件。
- 门禁结果三分类 gate_result：auto_fix（≤2 轮自动修正）/ user_input_required（合并缺失项只问一轮）/ fatal（停止不出文件）。
- 降级输出边界：核心文件缺失时只输出一般原则 + ≤3 个示例餐，不生成七天菜单/预算/阶段安排/正式文件，标题标记"规则文件不完整"。
- 排版令牌固定于 output-policy.md（section_title 18pt / body 10.5pt / list 10.5pt / disclaimer 9pt），渲染器不得各自解释字号。
- 食养节拆两个同字号子区块（本周怎么安排 / 本周执行要点），.wisdom-subheading 样式；执行提示不重复正文内容。
- plan_meta 增加 build_id 与 rules_bundle_hash（五文件组合哈希），渲染器校验，错配即停止。

## 2026-08-24 · round 33（用户可见层语义与组件完整性修复）

- 用户可见术语门禁：封面/章节/日卡标题禁止出现"周期协议"及内部字段名（BANNED_TITLE_TERMS + validate 强制）。
- 食养之理与执行说明字体一致：打印端自然段与项目符号统一 10.5pt/行距 1.6，免责声明 9pt；#why 整节防断页。
- 食堂餐次内容完整性：模板 display 为空即渲染失败（修复 render_pdf 路径未加载模板导致"食堂点餐："空白的问题）。
- 餐次状态一致性：有克数餐次不得标"自行处理"（planned ≠ guidance_only），validate 报错。
- 当日建议贴卡（.day-advice break-before/break-inside: avoid），不漂入下一章节。
- menu-map 打印压缩为前 8 项重点 + "其余见网页版展开"提示；网页版完整折叠。
- 库存食材价格列显示"库存"（purchase_status: from_inventory 或 0 元库存），不再显示"约0元"。
- meal_structure.structure_note 渲染（如"同一蒸锅上下层完成"）。
- 本周阶段表只保留本周+下周两行；"代谢最佳状态"等绝对表述改平实；末页删互动推动句。

## 2026-08-24 · round 32（入口加固与渲染器命名统一）

- 渲染器命名统一：render_plan.py = HTML 实现本体；render_html.py = HTML 入口；新增 render_pdf.py（render_html → Chromium 打印一次 → 删临时文件）；新增 render_output.py 总控路由。
- plan.json 增加 plan_meta 版本块契约（schema/规则文件/参数/菜谱库/价格源版本），渲染前由 check_plan_meta 校验，不一致即停止。
- 周期协议口径改写：approved 参数"方可进入计划计算"，实际执行仍受适用人群、作息、断食经验与安全上限约束，冲突取更保守值。
- 价格桥接条款：价格完整性不等于允许编造价格；三层来源均不可用时冻结前替换食材。
- SKILL.md 新增：规则冲突优先级（safety-rules 最高，摘要最低）、规则文件完整性门禁（失败关闭，禁止凭记忆补规则）、入口级最终门禁 6 条、八项问卷摘要与单轮合并追问规则。
- 决策优先级移除"理论展示"项，改为约束句：理论展示不得反向影响菜单/预算/食材/营养决策。
- description 收窄为"制定 7 天计划"场景；仅问概念/疾病/菜谱知识不自动启动 15 步。
- 免责声明改写：不主动推荐补充剂，用户询问时只提示咨询医生或药师。
- 餐次追问规则：所有缺失餐次合并进同一轮动态追问，不逐餐连续追问。

## 2026-08-24 · round 31（定版拆分与补全）

- SKILL.md 减负拆分：详细运行规则移至 `references/runtime-rules.md`（餐次/早餐/一人食/外食/预选/采购）、`references/nutrition-routing.md`（模式/周期/蛋白质四字段/营养门禁）、`references/output-policy.md`（章节白名单/格式/视觉/分页/渲染架构）；维护信息移至 `developer/maintenance-map.md`（书籍提取/索引/测试/文件地图）。SKILL.md 保留触发、路由、15 步与关键规则。
- 新增早餐三态 `breakfast_mode`：planned / guidance_only / excluded。
- 一人食正餐结构白名单：true_one_pot / synchronized_one_cooker / one_hot_dish_plus_ready_staple / one_hot_dish_plus_no_cook_side；拒绝 two_independent_hot_dishes / two_dishes_one_soup / multi_pan。
- 价格口径升级为三层 `price_basis`：direct_public_price / category_estimate / historical_estimate；直采价显示 ¥X–Y，估算价显示 约¥X–Y；预算按区间上限合计；无法定价食材在菜单冻结前替换。
- 食堂模板补齐 template_id / version / estimate_basis / confidence 字段。
- 渲染器扩展为四个，均只读 plan.json：render_html.py（原 render_plan.py 包装）、render_markdown.py、render_docx.py（新增）。
- "用户指示 2026-08-21"等内嵌变更说明从 SKILL.md 与 macros_calculator.py 注释移入本文件；parameter-build-report.md 路径统一为 `book-extraction/nutrition-audit/parameter-build-report.md`。

## 2026-08-23 · round 30（分页孤行治理）

- 分页守卫：h2/h3/h4 break-after:avoid；thead header-group；tr break-inside:avoid；日卡标题与首餐绑定（`.window + .meal` break-before:avoid）。
- 食材↔菜谱对照（menu-map）改为简短文字描述（如"周六午140g · 周三晚160g"），列宽 16/18/66。

## 2026-08-23 · round 29（视觉统一与页数硬约束）

- 所有章节统一中性底色 #fcfaf5 系；禁止大面积黄/紫色块。
- PDF ≤9 页硬约束写入 SKILL.md；打印压缩（字号/间距/内边距）。
- 迭代期性能规则（fast 模式）：只跑受影响测试、chromium 单次启动、合并前才全量回归。

## 2026-08-22 · round 28（本周阶段与周期协议启用）

- 新增"01 本周阶段"章节（三周展望表）；周期安全筛查清单固定七项；缺铁性贫血服用铁剂不属于禁食禁忌。

## 2026-08-21 · 周期协议证据门禁调整（用户指示）

- `external_evidence_reviewed` 否决门禁取消：周期协议参数满足 `source_verified + audit_status: approved + source_rule_id` 即按书直接执行；macros_calculator.py 对 cycle_phases / manifestation_fasting_cap_h / nurture_fasting 显式调用 approved()。安全筛查前置条件（慢病/用药/妊娠等）保留不变。参数构建记录见 `book-extraction/nutrition-audit/parameter-build-report.md`。
- 同时取消：每日打卡 CSV 与相关章节（更早轮次）。

## 2026-08-20 及更早 · round 24–27 摘要

- round 24：视觉语言恢复（柔和分区底色、圆角日卡、状态四宫格）。
- round 25：月相 SVG 单路径修复；价格硬门禁（空价=渲染失败）；采购清单品类分组；plan.json 中间件强制；组件黑名单（TOC/环形图）。
- round 26：早餐碳水四组轮换硬规则；价格估算层（price-estimates.json）；删除"本周档案"章节；备餐节含食材流转核验（≥3 项）；食养之理与执行说明合并节。
- round 27：menu-map 下拉恢复（网页折叠/PDF 自动展开）；早餐行只显示菜品+克数；一锅出硬过滤（apply_one_pot_rule）。
