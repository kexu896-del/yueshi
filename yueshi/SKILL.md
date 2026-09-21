---
name: yueshi
version: yueshi-1.4.3
description: 为用户制定连续 7 天的个性化饮食计划、菜单和采购清单。当用户明确要求"周食谱""一周饮食计划""减重菜单""周期饮食""一人食采购规划"时触发；涉及断食、低碳水或周期阶段适配时执行安全筛查和营养校验。出现"双人餐""两人吃饭""全家食谱""同餐不同量""多人共餐""家庭版"时触发家庭模式（plan_mode 前置识别）。仅提问单个营养概念、疾病信息或菜谱知识时，不自动启动完整 15 步周计划。
---

# 月食 · 定制一周饮食计划

## 定位

根据**身体周期、所在地区、当地公开价格和做饭条件**，生成真正**买得到、做得完、吃得完**的一周饮食方案。输出：7 天菜单 + 采购清单（食材、购买量、常见规格、参考价、平替、剩余去向）+ 营养校验。

## 规则文件分工（本文件为入口：触发/路由/摘要/门禁）

| 文件 | 内容 |
|---|---|
| `references/runtime-rules.md` | 运行规则：信息采集、餐次三态、早餐轮换、预选闭环、一人食白名单、食堂外食、采购与价格三层、断食窗口、生成约束 |
| `references/nutrition-routing.md` | 营养路由：平衡激素模式、酮生物模式及周期阶段适配规则、蛋白质四字段、营养校验与渲染前自动修正 |
| `references/output-policy.md` | 输出策略：plan.json 契约、渲染架构、执行模式、章节白名单、视觉分页、最终门禁 |
| `references/household-runtime-rules.md` | 家庭模式增量规则（plan_mode ∈ household_plan_modes 时生效；单人规则为基底） |
| `references/price-provider-policy.md` | 外部价格 Provider 契约：职责边界、来源路由、抓价时机、状态映射、direct_public_price 收紧条件、P01–P09 采购门禁（含价格元数据一致性 P09）、价格快照元数据 |
| `workflows/household-planning-flow.md` | 家庭模式 13 步执行流程（单次检索、单次装配、批量营养、≤2 轮全局微调、缺席只合并 patch） |
| `references/rule-index.md` | 稳定规则 ID 索引（SAFETY-001 等，跨版本不变；ID 只增不改，废项标记 deprecated 不删除） |
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

**启用叮咚查价时的追加完整性检查（`dingdong_price_choice = use_helper` 才执行）**：`references/price-provider-policy.md`、`schemas/price-query.schema.json`、`schemas/price-result.schema.json`、`data/ingredient-catalog.json`、`data/product-form-dictionary.json` 与 `scripts/price_result_migrator.py`（声明支持旧版迁移时）必须全部可读取。任一缺失：阻止查价链路（不生成查价清单、不进入 awaiting_price_result），不得用模型记忆补写缺失契约或排除词；允许用户明确切换为估价路径（价格按三层口径并注明估算），但**不得伪装成叮咚直采价**。未启用叮咚时，价格契约文件缺失不影响普通估价流程。错误码统一映射为 `core_rule_file_missing`，详细错误中记录具体缺失文件（内部日志可用细粒度标识：price_provider_contract_missing / price_query_schema_missing / price_result_schema_missing / ingredient_catalog_missing / form_dictionary_missing / price_result_migrator_missing）。

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

> plan_mode ∈ household_plan_modes（含 split_safety_required）时改走 `workflows/household-planning-flow.md` 的 13 步（单次检索、单次装配、批量营养、≤2 轮全局微调、缺席只合并 patch），不得逐成员各跑一遍 15 步。

> 意图识别 → 安全筛查 → 关键八项信息 → 周期阶段与进食窗口 → 预算与所在地价格口径 → **初步食材篮子** → **用户食材预选** → **锁定食材篮子** → 菜谱库检索 → 约束装配（时间/厨具/包装/多样性）→ 七天菜单 → 营养重算校验 → 反向汇总采购需求 → 生成采购数据 → **若未启用叮咚查价**：按价格三层完成采购清单并生成最终文件；**若启用叮咚查价**：按最终新购需求生成唯一正式查价清单并暂停在 awaiting_price_result → 收到并通过 G13 校验的价格结果后更新价格、包装和预算 → 再生成最终采购清单与最终文件。（价格结果回传前只能形成内部采购需求，不能称为"最终采购清单"。）

核心原则是**两次生成 + 中间一次预选**：先生成初步食材篮子（决定这周买什么），用户只做减法与少量替换（说"不想要的编号"即可）。正常多轮场景下，输出预选列表后结束当前回合，收到用户回复后再生成 locked_basket；只有用户明确跳过预选、原始请求要求直接生成、当前调用模式不支持多轮，或 fallback-flow 明确启用默认篮子时，才生成 provisional_locked_basket。锁定后只在锁定篮子内选菜谱；禁止先想菜谱再凑采购。用户删除的食材不进入锁定篮子、菜谱和采购清单；安全排除项（过敏原/医嘱/宗教饮食）在步骤 2 登记后不出现在预选候选中、也不可由预选恢复。缺信息/缺地区价格数据/缺外部数据按 `workflows/fallback-flow.md` 降级，不猜不伪造。

**关键八项**：基本情况、避开事项、周期情况、吃饭做饭、菜系口味、预算、做法选择、输出格式。另有一条**逐计划周期必显选答**（`dingdong_price_choice`，不跨周继承）：本周采购价格方式二选一——A. 使用「月食叮咚查价助手」按叮咚当前页面商品和价格规划预算（`use_helper`）/ B. 按所在地公开参考价格估算（`use_estimate`）。**不跨周自动沿用上周选择（"是"与"否"都不沿用）**：新计划初始为 `pending`，在食材预选清单一并与食材删减收集（不单独追问一轮），未选择时不进入预选后的正式生成链路、不生成正式查价清单，也**不静默判定为"否"**；用户首轮已明确（如"用叮咚查价生成下周食谱"）则直接记录并在预选时仅显示"本周价格方式：叮咚查价助手（已选择）"，不重复确认；该选择只对本次 request_id 有效。**只有选 A（等价于 `dingdong_helper_opt_in: yes`）才启用查价链路**（预选阶段只登记意愿；唯一正式查价清单在菜单、营养与最终新购需求确定后生成）。计划日期不进问卷，默认从发问次日起连续 7 天，用户另有指定时按用户要求。**所有缺失餐次与其他必填项必须合并在同一轮动态追问中，不得逐餐连续追问**；用户明确要求直接生成时，仅使用 runtime-rules.md 允许的降级状态，不得擅自补具体餐次。

## 主线路由（安全优先，详见 references/safety-rules.md）

1. **慢性病/用药** → 停止自动定制，仅在医嘱范围内做菜单与采购适配；书中疾病方案只作"原书观点"介绍。
2. **健康成年女性（无慢病）** → 周期阶段适配主线（规则见 references/nutrition-routing.md「女性周期断食整合」；是否安排进食窗口由该文件决定）。
3. **健康成年男性** → 不进行女性周期阶段推算；系统根据健康目标、断食经验、作息和安全限制自动路由适用安排，不要求用户选择内部饮食模式。如安排时间限制进食，起步与上限时长为 `skill_safety_policy` 参数，由 `references/safety-rules.md` 管理。
4. **孕产哺乳、未成年人、进食障碍史** → 不启用禁食或周期性内部饮食安排，建议先咨询医生。
5. **一人食识别**（家庭人数=1 且每日自炊 ≤2 餐，或用户明确要求）→ 任何主线下叠加"一人食模式"（结构白名单见 references/runtime-rules.md）。
6. **用餐人数前置识别（`plan_mode`）**：开始生成前先确认 plan_mode，四种取值与边界：
   - `solo`（单人）：默认主线，完整支持；
   - `shared_uniform`（多人同餐同量）：按家庭模式管线（schemas/household/，见 runtime-rules「家庭模式」）；
   - `shared_meal_personalized`（多人同餐不同量）：同上，份量按 portion_method 拆分；
   - `split_safety_required`（安全冲突须分锅/分餐）：成员间存在过敏、医嘱等安全冲突时**直接进入本模式**，不经追问降级为共锅。
   以上三种多人取值统称**家庭模式**（`household_plan_modes` = {shared_uniform, shared_meal_personalized, split_safety_required}）；本文所有家庭模式条件一律按**集合成员**判定，禁止用 "shared_*" 字符串前缀匹配（split_safety_required 不匹配该前缀，漏判会绕回单人 15 步并跳过家庭校验）。
   多人场景当前不静默降级为 solo：先按 user_input_required 合并追问一轮（成员清单/各成员限制/共同餐次/默认共锅策略/份量精度），未确认前不生成共享菜单；家庭摘要页最多并排展示 3 名成员；成员总数可大于 3，超出部分进入成员附页，不为卡页数把字号降到正文字号下限以下；家庭人数上限唯一参数来源为 `data/household-limits.json`（summary_inline_members / max_members），脚本与问卷不得各自写死；若超过 max_members，在生成前返回 user_input_required 或改用适合的输出格式，不在渲染阶段静默截断。

## 关键规则摘要（细则以拆分文件为准；冲突时按上文优先级）

- **模式与周期（规则 ID：MODE-INPUT-001 / MODE-DERIVE-001 / MODE-FREEZE-001）**：内部饮食模式（酮生物 / 平衡激素）**不是问卷项**——用户只提供周期日期、规律性、断食经验、作息等事实；逐日模式由系统按「周期事实→完整性检查→安全筛查→阶段计算→适用性检查→更保守参数→生成并冻结 mode_schedule」推算，用户输入不得直接写入 mode_schedule，推算失败不转嫁为用户选模式；用户纠正周期事实后重新推算而非手工改结果。两种模式参数只从 `data/effective-parameters.json` 的 approved 参数读取。周期阶段参数满足 source_verified=true、audit_status=approved 且 source_rule_id 可追溯后，**方可进入计划计算**；实际执行仍须通过适用人群、周期信息完整性、断食经验、作息和 Skill 安全上限检查，发生冲突时采用更保守的安全参数。任何输出不得把书籍观点表述为医学证明（细则见 nutrition-routing.md）。
- **餐次三态**：餐次计划状态统一字段 `meal_plan_mode` = planned / guidance_only / excluded（餐次类型另用 `meal_type` = breakfast / lunch / dinner / snack；不同时存在 breakfast_mode / meal_mode / recipe_mode 等同义字段，历史数据中的 breakfast_mode 仅按 schema 映射为 meal_plan_mode）；用户没提到的餐次必须合并进同一轮追问，不得默认安排或省略；早餐碳水四组轮换、相邻两天不同组（见 runtime-rules.md）。
- **一人食**：正餐结构白名单 true_one_pot / synchronized_one_cooker / one_hot_dish_plus_ready_staple / one_hot_dish_plus_no_cook_side；拒绝两菜一汤与多锅组合（见 runtime-rules.md 与 recipe_ranker.apply_one_pot_rule）。
- **预选闭环**："都可以吃/全部保留" = `accepted_batch`（user_reviewed: true），**不得**当作跳过预选；accepted_batch 与点名食材未入选必须有真实 reason_code，点名食材未入选要在执行提示中给出用户可见原因（见 runtime-rules.md）。
- **价格三层与完整性**：`price_basis` = direct_public_price / category_estimate / historical_estimate；直采价显示 ¥X–Y，估算价显示 约¥X–Y；每行必须有价格，空价 = 渲染门禁失败。**价格完整性不等于允许编造价格**：每项价格必须来自直接公开价、可解释的当地同类估算或有日期的历史公开价；三者均不可用时，在 plan.json 冻结前将该食材替换为可合理定价的同功能食材。预算按区间上限合计（见 runtime-rules.md「采购输出」）。
- **外部价格 Provider**：仅在本次计划食材预选环节明确选择 `use_helper` 时启用（逐周期重选、不跨周沿用，未选不静默按否）。预选阶段只登记查价意愿；菜单结构、营养结果和最终新购需求形成稳定快照（`menu_snapshot_hash` / `nutrition_snapshot_hash` / `shopping_demand_hash`）后，按最终 `new_purchase_amount > 0` 食材生成并交付唯一正式的「月食-查价清单.json」，随后暂停在 awaiting_price_result（受 G12、G13 约束）。收到合规结果后只更新价格、包装和预算，**再冻结最终 plan.json 并完成一次最终渲染**。叮咚商品名仅进入采购清单；PDF 不展示「对应菜单及用量」，其他格式按 `references/output-policy.md` 展示。未选 A（`use_estimate` 或尚未选择）时全流程不生成查价清单，价格按既有三层口径处理。价格失败回退链：`direct_public_price → category_estimate → historical_estimate → 替换同功能食材（须回菜单营养层）`。查价清单 `request_id = {计划起始日期}-{shopping_demand_hash 前 8 位}`，防同日两版菜单串用旧价格结果。Provider 权限边界、地址边界、回传方式、候选筛选、六态状态转移表（§4.3）与 P09 元数据一致性的详细契约见 `references/price-provider-policy.md`。
- **营养管线**：菜单草案 → 批量营养计算 → 自动微调克数（≤2 轮）→ 最终营养复核 → 形成稳定快照（`menu_snapshot_hash` / `nutrition_snapshot_hash` / `shopping_demand_hash`）。**未启用外部查价时**，随后冻结最终 plan.json 并渲染；**启用叮咚查价时**，先生成唯一正式查价清单并暂停在 awaiting_price_result，收到通过 G13 校验的价格结果、完成价格/包装/预算更新后，**才冻结最终 plan.json** 并一次渲染——查价前任何阶段不得冻结最终 plan.json。禁止渲染完成后再人工改数；蛋白质按 safety_floor_g / individual_target_g / book_reference_g / medical_limit_g 四字段判定（见 nutrition-routing.md）。
- **渲染架构**：plan.json 是唯一中间件，禁止手写 HTML。渲染器分工：`scripts/render_plan.py`（HTML 组件实现本体）、`scripts/render_html.py`（HTML 入口）、`scripts/render_pdf.py`（PDF：调 render_html 生成临时自包含 HTML → Chromium 打印一次 → 删临时文件）、`scripts/render_markdown.py`、`scripts/render_docx.py`；`scripts/render_output.py` 为总控路由（按用户所选格式分发）。家庭模式追加：`scripts/household_override_merger.py`（patch 合并器：base + overrides → effective_plan，缺席重归一 selected_pct）、`scripts/household_components.py`（成员营养块、份量块、采购三本账行组件；其余组件继承 solo 渲染器）。渲染输入口径：solo 渲染**校验通过的 plan.json**；家庭模式渲染前置链路为 base_plan (+ overrides) → household_override_merger → effective_plan → effective Schema 校验 → 统一渲染；**无 override 时也走 identity merge**（effective_meta.applied_override_ids 为空数组），家庭渲染器永远只面对 effective_plan 一种输入，渲染器只读**校验通过的 effective_plan**，base 与 overrides 不直接进入表现层；若统一中间件文件名 plan.json，须由总控把通过校验的输入复制到临时构建目录并记录 source_artifact（solo=base plan，家庭=effective_plan）。校验器必须显式指定 artifact schema（base_plan / overrides / effective_plan），禁止按文件名猜测，artifact 与实际 Schema 不一致即失败。PDF 页数预算：solo ≤9 页且字号有下限；家庭版为基础 9 页 + 成员附页预算，禁止为卡页数降低字号；章节白名单固定顺序；禁止 TOC 与营养图形组件（见 output-policy.md）。
- **plan.json 版本门禁**：plan.json 必须带 `plan_meta` 版本块，字段固定为 `build_id` / `plan_schema_version` / `rules_bundle_hash` / `skill_version` / `runtime_rules_version` / `nutrition_rules_version` / `output_policy_version` / `recipe_manifest_version` / `effective_parameters_version` / `price_data_version`。渲染前**优先校验 plan_schema_version 与 rules_bundle_hash**（与当前规则文件组合哈希比对，哈希至少覆盖 references/safety-rules.md、runtime-rules.md、nutrition-routing.md、output-policy.md、data/effective-parameters.json、data/library-manifest.json）；plan_mode ∈ household_plan_modes 时，rules_bundle_hash 输入追加 references/household-runtime-rules.md、workflows/household-planning-flow.md 与 schemas/household/ 契约清单（任一变更即触发 rules_bundle_mismatch）。再校验 effective_parameters_version 与计算日志一致、recipe_manifest_version 与 ranker 日志一致。任一不满足即停止，防止新版生成器与旧版渲染器混跑；各明细版本字段用于日志与排错（契约见 output-policy.md）。四个版本/哈希职责唯一：`rules_bundle_hash` = 规则是否匹配；`pipeline_bundle_hash` = 执行组件是否匹配；`price_result_hash` = 本次抓价结果是否被修改；`price_data_version` = 价格数据契约版本（price-query / price-result Schema 契约版本，当前 "1.2"；不是缓存批次、来源版本或某次快照版本）。使用外部价格 Provider 时，plan.json 追加可选顶层块 `price_snapshot_meta`（provider / provider_version / result_schema_version / delivery_context_confirmed_by_user / observed_at / source_mode / request_id / result_hash，契约见 price-provider-policy.md §6）；契约 1.2 起 Provider 不读取具体收货地址，只记录用户已确认当前配送会话，价格失败按回退链降级、不重跑菜单；Provider 商品数据不加入 rules_bundle_hash。
- **生成约束**：净碳水/蛋白/脂肪逐日达标按 `references/foods-table.md` 每 100g 数值计算；烹饪时间分层（快手 ≤15min / 常规 15–30min / 慢炖 >30min）；正餐主蛋白重复按 D01（优先不重复，确需重复最多 2 次且烹法或主风味不同；早餐基础食材、调味与基础油不适用）；慢病用户仅在医嘱范围内适配（完整清单见 runtime-rules.md）。
- **用户可见术语门禁**：内部规则术语可用于 plan.json 内部字段、日志、审计报告和开发文件，但**不得进入用户可见文字**。门禁只扫描可见字段范围（`visible_text_fields`：cover.title / cover.subtitle / cover.status_cards[].label / sections[].title / days[].display_title / meals[].title / meals[].display_content / meals[].status_label / wisdom.paragraphs[] / wisdom.action_items[] / disclaimer.display_text，以及最终用户文件中的可见文字）；**禁止对整个 plan.json 或构建目录做全文搜索以免误报**。禁用词：周期协议、audit_status、source_verified、source_rule_id、protocol_version、effective_parameters、safety_policy、reason_code、accepted_batch、locked_basket、provisional_locked_basket、plan.json、gate_result、low confidence、runtime-rules、nutrition-routing、portion_method、attendance_override、leftover_plan、selected_pct、participant_member_ids、external_meal、uncertain、shared_base、member_portions、pending_attendance_resolution、shopping_delta、awaiting_price_result、price_result_received、opt_out_after_query、dingdong_helper_opt_in、dingdong_price_choice、menu_snapshot_hash、nutrition_snapshot_hash、shopping_demand_hash、price_result_hash、migration_log、provider_product_name、shopping_meal_usage_map。显示转换：周期协议 → 阶段适配；协议执行 → 按当前阶段安排；协议参数 → 本周安排参数；reason_code → 未入选原因；accepted_batch → 已确认食材；locked_basket → 本周食材；low confidence → 区间估算；portion_method → 盛取方式；external_meal → 外食；uncertain → 待定；member_portions → 各人份量；shared_base → 共享基础味；leftover_plan → 剩余安排；attendance_override → 就餐变化；selected_pct → 实际分配比例；awaiting_price_result → 等待叮咚价格结果；price_result_received → 已读取价格结果；opt_out_after_query → 已改用参考价格估算；migration_log → 文件兼容处理记录。
- **章节排版一致性**：同一章节内的自然段、普通说明和项目符号必须使用同一正文字号与行距；项目符号只改变缩进，不改变字号。"食养之理与执行说明"正文和列表统一正文样式；免责声明可比正文小 1 至 1.5pt，但必须是独立区块。排版令牌固定于 output-policy.md，渲染器不得各自解释字号。
- **餐次状态契约**：`planned`——该餐有明确安排，进入菜单、营养和采购，不得显示"自行处理"；`guidance_only`——只提供原则或组合建议、不生成固定逐日克数、不进入采购清单、营养仅作 low 置信度区间估算；`excluded`——不生成菜单、不进入采购、不进入营养合计。**语义修正（规则 ID：MEAL-STATE-001，round72 定稿）**："工作日早餐自己做"映射为 `planned`，计入菜单、营养和采购；"自己简单解决""随便做点"同样不等于"不做这餐"，不得降级为 `guidance_only`；是否属于快手、免开火或提前备餐，应根据用户明确提供的时间和做法条件分别判断——用户未提供早餐时间限制时，不得仅凭"自己做"或"简单解决"写入 `quick_self_prepare`；`preparation_mode`（quick_self_prepare / assembly_only / external_purchase / none）、`max_active_minutes`、`no_cook_allowed` 和 `advance_prep_allowed` 分别记录，不相互替代；只有"只给原则/不用安排/不纳入这份计划"类明确表达才允许 `guidance_only`；完整映射表见 runtime-rules.md，采购范围硬约束见门禁 B01/B02；用户明确给出快手条件的早餐优先从 `data/breakfast-templates.json` 结构化模板库（十类，营养由 foods-table 计算）选择，模板是菜品来源，选择模板不回写难度字段。
- **模式参数一致性（规则 ID：MODE-001）**：周期模式决策后在食材篮子之前冻结 `mode_schedule.json`（逐日模式 + mode_summary），所有下游脚本（basket_builder / recipe_ranker / 营养求解）只以 `--mode-schedule` 读取该文件，禁止手写独立模式参数；不一致即 M11 失败关闭。
- **时令与多样性证据链（规则 ID：SEASON-001 / DIVERSITY-001）**：候选菜谱先做 `recipe_fingerprint` 去重再参与整周集合多样性优化（D01–D07 硬门禁）；时令声称必须有 region + month + source_rule_id（S01–S04，`data/seasonal-produce-cn.json`，无审核来源不得虚构"当季"）；跨周重复惩罚（ingredient_history_4w / recipe_history_8w / protein_family_history_4w）进入候选评分；用户删除反馈区分"本周不吃 / 以后少推荐 / 完全不要 / 这次买不到"四档。细则见 workflows/planning-flow.md 步骤 4.5/6/9/10 与 references/runtime-rules.md。

## 入口级最终门禁（详细门禁见 output-policy.md；结果分三类）

**门禁结果分类（`gate_result`）**：
- `auto_fix`：可由数据层或渲染层自动修正（营养微调 / 采购量不匹配 / 价格估算或替换 / 食材未使用 / 可见术语转换 / 渲染字段修复 / 排版修复），最多两轮；两轮后仍失败则 status 升级为 `fatal`，`fatal_reason` 记为 `auto_fix_retry_exhausted`（门禁状态始终只有三类，不设第四个状态值）；非 fatal 状态码（`seasonal_data_unavailable` / `breakfast_procurement_omitted` / `meal_mode_invalid_downgrade` / `diversity_gate_failed` 等）不新建 fatal_reason，优先走 auto_fix 或 user_input_required；
- `user_input_required`：缺少用户餐次、做法选择、输出格式、预算、地区或必要健康信息等**可通过一次追问补齐**的内容；合并成一轮追问，只问一轮；
- `fatal`：核心规则文件缺失、安全路由无法执行、plan_schema 版本不匹配、rules_bundle_hash 不匹配、plan.json 损坏、模式计划不一致、渲染器重试后仍失败；停止，不生成正式文件。`fatal` 须带 `fatal_reason`，枚举固定为：core_rule_file_missing / safety_route_unresolvable / plan_schema_mismatch / rules_bundle_mismatch / corrupted_plan_json / mode_schedule_mismatch / auto_fix_retry_exhausted / renderer_retry_exhausted。

"安全筛查未完成"须进一步区分：因缺用户信息未完成 → `user_input_required`；文件损坏或安全路由无法执行 → `fatal`。

检查项（逐项标注失败等级）：
G01. [fatal] 核心规则文件及规则包版本有效（含安全筛查路由可执行）；plan_mode ∈ household_plan_modes 时在生成前即追加校验 references/household-runtime-rules.md、workflows/household-planning-flow.md、schemas/household/ 全套契约文件，任一缺失 → fatal（core_rule_file_missing），不降级为 solo；**时令条件检查（规则 ID：SEASON-001）**：计划启用时令优先、或最终输出准备使用"当季/时令/正当季"等文字时，追加校验 `data/seasonal-produce-cn.json` 可读取且条目带 source_rule_id——缺失且用户未强制时令时停止使用"当季"表述继续生成（记录 seasonal_data_unavailable，非 fatal）；用户明确要求必须按时令时转 user_input_required 或 fatal（core_rule_file_missing）；不得凭月份常识补写当季结论；
G02. [user_input_required] 用户必填信息、餐次、做法和格式明确；
G03a. [user_input_required] 预选尚未由用户确认（locked_basket 等待用户回复，不生成共享菜单）；
G03b. [fatal] 用户已完成预选或进入允许自动锁定的路径，但 locked_basket 生成失败、损坏或版本不匹配；
G04. [fatal] plan.json 版本校验通过（plan_schema_version 与 rules_bundle_hash）；
G05. [auto_fix] 营养校验通过；
G06. [auto_fix] 采购数量、价格和食材去向完整；自动修复范围限定为：换用同一食材的另一合格候选、重算包装数量、使用合法价格回退层、修正展示格式、补齐可推导剩余去向；不得编价、不得用错误规格、不得把会员价当普通价、不得替换用户没选的食材（食材替换必须回菜单营养层；详见 price-provider-policy.md §10）；
G07. [auto_fix] 所有餐次业务字段完整（缺 → MEAL_DATA_MISSING，返回菜单装配层修复）；
G08. [auto_fix] 所有必显餐次字段已实际渲染（漏 → MEAL_RENDER_FIELD_DROPPED，不重新计算菜单，只重跑固定渲染器）；
G09. [auto_fix] `meal_plan_mode` 与餐次数据一致（无 planned 数据使用 guidance_only 标签）；
G10. [auto_fix] 用户可见文字不含内部术语（仅扫描 visible_text_fields 范围）；
G11. [auto_fix] 字体、分页和免责声明独立组件检查通过；**meal_usage_map 输出检查**：HTML 完整可折叠展示、无截断、不出现"见网页版展开"；Word 完整展示（建议附录、可跨页）、不出现"见网页版展开"；Markdown 按食材分组完整展示、不使用超宽表格；PDF 不出现"对应菜单及用量"章节、不出现映射表表头/残留行/空白占位页；全部格式的 meal_usage_map 不得读取 provider_product_name；
G12. [user_input_required] 等待价格结果门禁：`dingdong_price_choice = use_helper`（派生字段 `dingdong_helper_opt_in = yes`，只读）且 `price_workflow_state = awaiting_price_result` 时，禁止生成 PDF、Word、HTML、Markdown、最终食谱和最终采购清单，只允许交付「月食-查价清单.json」及简短操作提示；`render_output.py` 在此状态拒绝全部正式格式（拒绝渲染属正常等待，非 fatal）。收到通过 G13 校验的价格结果后状态转 `price_result_received`；用户明确放弃查价时转 `opt_out_after_query`，允许估价生成最终版，但必须注明估价口径；
G13. [user_input_required] 价格结果格式门禁：叮咚价格结果根级字段必须包括 `schema_version` / `provider` / `request_id`，且 `request_id` 必须与本次正式查价清单一致。处理分支：字段完整且 Schema 通过 → 继续；明确识别为受支持旧版 → 运行兼容迁移器（`scripts/price_result_migrator.py`）、写入 `migration_log`、重新校验；版本无法识别或字段无法可靠补齐 → 要求从本机助手重新导出；`request_id` 不匹配 → 拒绝使用；禁止因"内容看起来完整"而人工静默绕过（分支细节以 references/price-provider-policy.md §4.2 为准，此处为唯一入口级定义）。

家庭模式追加检查项 H01–H06（仅 plan_mode ∈ household_plan_modes 时执行；家庭文件完整性条件以 G01 为唯一定义，此处不重复）：
H01. [auto_fix] 每餐 household 总量 = Σ member_portions + 损耗/剩余；
H02. [auto_fix] participant_member_ids = member_portions 成员集合（not_participating 不进入）；
H03. [auto_fix] ratio_split 的 portion_ratios 覆盖整锅且 selected_pct Σ=100；
H04. [auto_fix] 缺席已局部重算（仅禁止本次 effective 截止时间前且影响当前输出的 pending 遗留；未来待确认事项保留在 override 源文件，不写入 effective，不判失败——例：用户说"下周四可能不在家吃晚饭"而本次计划只到本周日，则该事项只留在 override 源文件待届时确认，不写进本周 effective，H04 不因此判失败）；
H05. [auto_fix] leftover 去向已解析、nutrition_transfer 一致；
H06. [auto_fix] 跨引用校验器全部检查项通过（scripts/household_reference_validator.py）。

采购范围门禁（B，详见 workflows/procurement-flow.md §1.1）：B01. [auto_fix] planned 且 include_in_procurement=true 的餐次食材必须进入反向采购汇总，不得因 quick_self_prepare 降级为 guidance_only 或从采购删除；遗漏时重跑该餐次采购汇总与数量校验，并同步更新 shopping_demand_hash；B02. [auto_fix] 餐次从 planned 降级必须有用户原话或明确 reason_code，"简单、快手、随便做"不是合法降级理由；无合法依据时恢复 planned 并重跑该餐次营养与采购校验，恢复后仍缺用户信息转 user_input_required；两轮自动修复仍失败统一升级为 fatal_reason=auto_fix_retry_exhausted。

执行与多样性门禁（M11 / D / S，详见 output-policy.md 与 workflows/planning-flow.md）：M11. [fatal] 下游脚本模式摘要必须与冻结 mode_schedule_hash 一致（mode_schedule_mismatch），禁止手写独立模式参数；D01–D07. [auto_fix] 菜谱多样性硬门禁（主蛋白不重复 / ≥2 烹法 / 指纹不重复 / 相邻不重复"快炒+咸鲜" / 来源不包揽 / 近 4 周重复降权 / 点名保留不受重复惩罚但受安全门禁）；S01–S04. [auto_fix] 时令门禁（当季声称须 region+month+source_rule_id 可追溯 / 篮子输出 season_status 与 season_score / 至少一个时令候选进预选否则记录原因 / 时令不得覆盖用户排除、安全与库存优先）。

auto_fix 类两轮后仍失败即升级为 `fatal`（fatal_reason=auto_fix_retry_exhausted），停止输出并返回失败项；fatal 类任一不满足即停止输出。

## 免责声明

本技能输出为一般性健康饮食建议，不构成医疗诊断或处方。以下情况必须输出免责声明并建议先咨询医生：妊娠/哺乳、未成年人、糖尿病用药者、心血管/肝肾疾病、进食障碍史、正在服用影响血糖/凝血/电解质药物者。**本技能不主动推荐补充剂**；用户主动询问时，只提示应与医生或药师确认，不提供品牌、具体剂量或代替正规治疗的建议。
