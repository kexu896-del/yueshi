---
name: yueshi
version: yueshi-1.0.0
description: 为用户制定连续 7 天的个性化饮食计划、菜单和采购清单。当用户明确要求"周食谱""一周饮食计划""减重菜单""周期饮食""一人食采购规划"时触发；涉及断食、低碳水或周期阶段适配时执行安全筛查和营养校验。仅提问单个营养概念、疾病信息或菜谱知识时，不自动启动完整 15 步周计划。
---

# 月食 · 定制一周饮食计划

## 定位

根据**身体周期、所在地区、当地公开价格和做饭条件**，生成真正**买得到、做得完、吃得完**的一周饮食方案。输出：7 天菜单 + 采购清单（食材、购买量、常见规格、参考价、平替、剩余去向）+ 营养校验。

## 规则文件分工（本文件为入口：触发/路由/摘要/门禁）

| 文件 | 内容 |
|---|---|
| `references/runtime-rules.md` | 运行规则：信息采集、餐次三态、早餐轮换、预选闭环、一人食白名单、食堂外食、采购与价格三层、断食窗口、生成约束 |
| `references/nutrition-routing.md` | 营养路由：两种模式、周期阶段规则、蛋白质四字段、营养校验与渲染前自动修正 |
| `references/output-policy.md` | 输出策略：plan.json 契约、渲染架构、执行模式、章节白名单、视觉分页、最终门禁 |
| `developer/maintenance-map.md` | 维护：书籍提取规则、测试清单、文件地图（**不参与用户计划决策**） |
| `CHANGELOG.md` | 参数与规则变更的唯一历史记录位置（**只记录历史，不是运行规则**） |

### 规则冲突裁决（按领域，不做简单高低覆盖）

- 安全问题 → `references/safety-rules.md`（安全永远最高）
- 参数数值 → `data/effective-parameters.json` 中 approved 生产参数
- 营养与阶段计算 → `references/nutrition-routing.md`
- 菜单、预选、餐次、采购 → `references/runtime-rules.md`
- 章节、样式、分页、格式 → `references/output-policy.md`

**output-policy 不得删除 runtime-rules 要求用户必须看到的字段；runtime-rules 不得规定具体字体、分页和视觉样式。** SKILL.md 只负责路由和摘要，摘要与详细规则冲突时以对应详细规则文件为准。`developer/maintenance-map.md` 不参与用户计划决策；`CHANGELOG.md` 只记录历史，不是运行规则。

### 规则文件完整性门禁（失败关闭）

开始生成前确认 `references/runtime-rules.md`、`references/nutrition-routing.md`、`references/output-policy.md`、`references/safety-rules.md` 均可读取。任一核心文件缺失或解析失败：不继续完整计划生成；**不使用模型记忆补写缺失规则**；返回缺失文件名称；允许降级为一般饮食建议，但**降级结果不得伪装成完整周计划**：只输出一般性饮食原则和不超过 3 个示例餐；不输出七天菜单、不输出预算合计、不输出周期阶段或禁食安排、不生成 PDF/Word 等正式计划文件；标题必须标记"规则文件不完整，本次仅提供一般建议"。

## 决策优先级

### 不可违反的硬门槛
安全、过敏原、热量安全线、蛋白质基础需要、医嘱要求——必须全部满足，不为任何便利让步（细则见 references/safety-rules.md）。

### 合规方案之间的排序（硬门槛全部满足后，冲突时从高到低）
1. 用户实际生活条件（烹饪时间、厨具、一人食）
2. 食材可获得性（所在地普遍买得到）
3. 烹饪便利性（做得完）
4. 包装消耗与减少浪费（吃得完）
5. 预算
6. 菜谱多样性
7. 营养估算可信度（数据来源完整、克数和份数一致、计算可复核；不以显示到个位数作为准确性的证明）

理论展示不是菜单决策因素：**理论展示不得反向影响菜单、预算、食材和营养决策，只在最终输出中解释已完成的选择**。

## 固定执行顺序（15 步）

每次生成周计划按 `workflows/planning-flow.md` 的 15 步执行，不得跳步换序：

> 意图识别 → 安全筛查 → 关键八项信息 → 周期阶段与进食窗口 → 预算与所在地价格口径 → **初步食材篮子** → **用户食材预选** → **锁定食材篮子** → 菜谱库检索 → 约束装配（时间/厨具/包装/多样性）→ 七天菜单 → 营养重算校验 → 反向汇总采购 → 输出采购清单（食材/购买量/规格/参考价/平替/剩余去向）→ 最后按用户所选格式生成最终文件。

核心原则是**两次生成 + 中间一次预选**：先生成初步食材篮子（决定这周买什么），用户只做减法与少量替换（说"不想要的编号"即可）。正常多轮场景下，输出预选列表后结束当前回合，收到用户回复后再生成 locked_basket；只有用户明确跳过预选、原始请求要求直接生成、当前调用模式不支持多轮，或 fallback-flow 明确启用默认篮子时，才生成 provisional_locked_basket。锁定后只在锁定篮子内选菜谱；禁止先想菜谱再凑采购。用户删除的食材不进入锁定篮子、菜谱和采购清单；安全排除项（过敏原/医嘱/宗教饮食）在步骤 2 登记后不出现在预选候选中、也不可由预选恢复。缺信息/缺地区价格数据/缺外部数据按 `workflows/fallback-flow.md` 降级，不猜不伪造。

**关键八项**：基本情况、避开事项、周期情况、吃饭做饭、菜系口味、预算、做法选择、输出格式。计划日期不进问卷，默认从发问次日起连续 7 天，用户另有指定时按用户要求。**所有缺失餐次与其他必填项必须合并在同一轮动态追问中，不得逐餐连续追问**；用户明确要求直接生成时，仅使用 runtime-rules.md 允许的降级状态，不得擅自补具体餐次。

## 主线路由（安全优先，详见 references/safety-rules.md）

1. **慢性病/用药** → 停止自动定制，仅在医嘱范围内做菜单与采购适配；书中疾病方案只作"原书观点"介绍。
2. **健康成年女性（无慢病）** → 周期阶段适配主线（规则见 references/nutrition-routing.md「女性周期断食整合」；是否安排进食窗口由该文件决定）。
3. **健康成年男性** → 两种模式任选 + 温和时间限制进食（起步与上限时长为 `skill_safety_policy` 参数，由 `references/safety-rules.md` 管理）。
4. **孕产哺乳、未成年人、进食障碍史** → 不启用禁食与模式，建议就医。
5. **一人食识别**（家庭人数=1 且每日自炊 ≤2 餐，或用户明确要求）→ 任何主线下叠加"一人食模式"（结构白名单见 references/runtime-rules.md）。

## 关键规则摘要（细则以拆分文件为准；冲突时按上文优先级）

- **模式与周期**：两种模式（酮生物 / 平衡激素）参数只从 `data/effective-parameters.json` 的 approved 参数读取。周期阶段参数满足 source_verified=true、audit_status=approved 且 source_rule_id 可追溯后，**方可进入计划计算**；实际执行仍须通过适用人群、周期信息完整性、断食经验、作息和 Skill 安全上限检查，发生冲突时采用更保守的安全参数。任何输出不得把书籍观点表述为医学证明（细则见 nutrition-routing.md）。
- **餐次三态**：餐次计划状态统一字段 `meal_plan_mode` = planned / guidance_only / excluded（餐次类型另用 `meal_type` = breakfast / lunch / dinner / snack；不同时存在 breakfast_mode / meal_mode / recipe_mode 等同义字段，历史数据中的 breakfast_mode 仅按 schema 映射为 meal_plan_mode）；用户没提到的餐次必须合并进同一轮追问，不得默认安排或省略；早餐碳水四组轮换、相邻两天不同组（见 runtime-rules.md）。
- **一人食**：正餐结构白名单 true_one_pot / synchronized_one_cooker / one_hot_dish_plus_ready_staple / one_hot_dish_plus_no_cook_side；拒绝两菜一汤与多锅组合（见 runtime-rules.md 与 recipe_ranker.apply_one_pot_rule）。
- **预选闭环**："都可以吃/全部保留" = `accepted_batch`（user_reviewed: true），**不得**当作跳过预选；accepted_batch 与点名食材未入选必须有真实 reason_code，点名食材未入选要在执行提示中给出用户可见原因（见 runtime-rules.md）。
- **价格三层与完整性**：`price_basis` = direct_public_price / category_estimate / historical_estimate；直采价显示 ¥X–Y，估算价显示 约¥X–Y；每行必须有价格，空价 = 渲染门禁失败。**价格完整性不等于允许编造价格**：每项价格必须来自直接公开价、可解释的当地同类估算或有日期的历史公开价；三者均不可用时，在 plan.json 冻结前将该食材替换为可合理定价的同功能食材。预算按区间上限合计（见 runtime-rules.md「采购输出」）。
- **营养管线**：菜单草案 → 批量营养计算 → 自动微调克数（≤2 轮）→ 最终复核 → **冻结 plan.json** → 渲染；禁止渲染完成后再人工改数；蛋白质按 safety_floor_g / individual_target_g / book_reference_g / medical_limit_g 四字段判定（见 nutrition-routing.md）。
- **渲染架构**：plan.json 是唯一中间件，禁止手写 HTML。渲染器分工：`scripts/render_plan.py`（HTML 组件实现本体）、`scripts/render_html.py`（HTML 入口）、`scripts/render_pdf.py`（PDF：调 render_html 生成临时自包含 HTML → Chromium 打印一次 → 删临时文件）、`scripts/render_markdown.py`、`scripts/render_docx.py`；`scripts/render_output.py` 为总控路由（按用户所选格式分发）。所有渲染器只读 plan.json。PDF ≤9 页且字号有下限；章节白名单固定顺序；禁止 TOC 与营养图形组件（见 output-policy.md）。
- **plan.json 版本门禁**：plan.json 必须带 `plan_meta` 版本块，字段固定为 `build_id` / `plan_schema_version` / `rules_bundle_hash` / `skill_version` / `runtime_rules_version` / `nutrition_rules_version` / `output_policy_version` / `recipe_manifest_version` / `effective_parameters_version` / `price_data_version`。渲染前**优先校验 plan_schema_version 与 rules_bundle_hash**（与当前规则文件组合哈希比对，哈希至少覆盖 references/safety-rules.md、runtime-rules.md、nutrition-routing.md、output-policy.md、data/effective-parameters.json、data/library-manifest.json）；再校验 effective_parameters_version 与计算日志一致、recipe_manifest_version 与 ranker 日志一致。任一不满足即停止，防止新版生成器与旧版渲染器混跑；各明细版本字段用于日志与排错（契约见 output-policy.md）。
- **生成约束**：净碳水/蛋白/脂肪逐日达标按 `references/foods-table.md` 每 100g 数值计算；烹饪时间分层（快手 ≤15min / 常规 15–30min / 慢炖 >30min）；同一主食材一周 ≤3 次；慢病用户仅在医嘱范围内适配（完整清单见 runtime-rules.md）。
- **用户可见术语门禁**：内部规则术语可用于 plan.json 内部字段、日志、审计报告和开发文件，但**不得进入用户可见文字**。门禁只扫描可见字段范围（`visible_text_fields`：cover.title / cover.subtitle / cover.status_cards[].label / sections[].title / days[].display_title / meals[].title / meals[].display_content / meals[].status_label / wisdom.paragraphs[] / wisdom.action_items[] / disclaimer.display_text，以及最终用户文件中的可见文字）；**禁止对整个 plan.json 或构建目录做全文搜索以免误报**。禁用词：周期协议、audit_status、source_verified、source_rule_id、protocol_version、effective_parameters、safety_policy、reason_code、accepted_batch、locked_basket、provisional_locked_basket、plan.json、gate_result、low confidence、runtime-rules、nutrition-routing。显示转换：周期协议 → 阶段适配；协议执行 → 按当前阶段安排；协议参数 → 本周安排参数；reason_code → 未入选原因；accepted_batch → 已确认食材；locked_basket → 本周食材；low confidence → 区间估算。
- **章节排版一致性**：同一章节内的自然段、普通说明和项目符号必须使用同一正文字号与行距；项目符号只改变缩进，不改变字号。"食养之理与执行说明"正文和列表统一正文样式；免责声明可比正文小 1 至 1.5pt，但必须是独立区块。排版令牌固定于 output-policy.md，渲染器不得各自解释字号。
- **餐次状态契约**：`planned`——有固定日期、时间、食材和克数，进入采购和营养计算，不得显示"自行处理"；`guidance_only`——只给组合建议、不生成固定逐日克数、不进入采购清单、营养仅作 low 置信度区间估算；`excluded`——不生成菜单、不进入采购、不进入营养合计。

## 入口级最终门禁（详细门禁见 output-policy.md；结果分三类）

**门禁结果分类（`gate_result`）**：
- `auto_fix`：可由数据层或渲染层自动修正（营养微调 / 采购量不匹配 / 价格估算或替换 / 食材未使用 / 可见术语转换 / 渲染字段修复 / 排版修复），最多两轮；两轮后仍失败则 status 升级为 `fatal`，`fatal_reason` 记为 `auto_fix_retry_exhausted`（门禁状态始终只有三类，不设第四个状态值）；
- `user_input_required`：缺少用户餐次、做法选择、输出格式、预算、地区或必要健康信息等**可通过一次追问补齐**的内容；合并成一轮追问，只问一轮；
- `fatal`：核心规则文件缺失、安全路由无法执行、plan_schema 版本不匹配、rules_bundle_hash 不匹配、plan.json 损坏、渲染器重试后仍失败；停止，不生成正式文件。`fatal` 须带 `fatal_reason`，枚举固定为：core_rule_file_missing / safety_route_unresolvable / plan_schema_mismatch / rules_bundle_mismatch / corrupted_plan_json / auto_fix_retry_exhausted / renderer_retry_exhausted。

"安全筛查未完成"须进一步区分：因缺用户信息未完成 → `user_input_required`；文件损坏或安全路由无法执行 → `fatal`。

检查项（逐项标注失败等级）：
1. [fatal] 核心规则文件及规则包版本有效（含安全筛查路由可执行）；
2. [user_input_required] 用户必填信息、餐次、做法和格式明确；
3. [fatal] locked_basket 已生成；
4. [fatal] plan.json 版本校验通过（plan_schema_version 与 rules_bundle_hash）；
5. [auto_fix] 营养校验通过；
6. [auto_fix] 采购数量、价格和食材去向完整；
7. [auto_fix] 所有餐次业务字段完整（缺 → MEAL_DATA_MISSING，返回菜单装配层修复）；
8. [auto_fix] 所有必显餐次字段已实际渲染（漏 → MEAL_RENDER_FIELD_DROPPED，不重新计算菜单，只重跑固定渲染器）；
9. [auto_fix] `meal_plan_mode` 与餐次数据一致（无 planned 数据使用 guidance_only 标签）；
10. [auto_fix] 用户可见文字不含内部术语（仅扫描 visible_text_fields 范围）；
11. [auto_fix] 字体、分页和免责声明独立组件检查通过。

auto_fix 类两轮后仍失败即升级为 `fatal`（fatal_reason=auto_fix_retry_exhausted），停止输出并返回失败项；fatal 类任一不满足即停止输出。

## 免责声明

本技能输出为一般性健康饮食建议，不构成医疗诊断或处方。以下情况必须输出免责声明并建议先咨询医生：妊娠/哺乳、未成年人、糖尿病用药者、心血管/肝肾疾病、进食障碍史、正在服用影响血糖/凝血/电解质药物者。**本技能不主动推荐补充剂**；用户主动询问时，只提示应与医生或药师确认，不提供品牌、具体剂量或代替正规治疗的建议。
