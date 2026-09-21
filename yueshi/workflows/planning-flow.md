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
| 4.5 | 冻结模式计划（round60） | 把步骤 4 的模式决策一次性编译为 `mode_schedule.json`（`plan_id` + 逐日 `mode_schedule` + `mode_summary{keto_days,hormone_days}`），计算 `mode_schedule_hash`；**此后所有下游脚本只以 `--mode-schedule` 读取该文件，禁止手写独立模式参数**（M11：任一参数不一致即失败关闭） | 已冻结 mode_schedule |
| 5 | 预算与所在地价格口径 | 采购不再区分线上线下来源；只定所在城市公开价格来源；同时按日期规则定 start_date（默认 request_date+1，连续 7 天） | 价格口径与日期口径 |
| 6 | 初步食材篮子 | 先生成 `initial_basket` 草案（结构见 `references/output-schema.md`）：依据周期阶段、营养边界、所在地普遍可获得性、预算、当季（`data/seasonal-foods.json` + `data/seasonal-produce-cn.json` 时令证据链）、烹饪时间、包装规格（`data/package-rules.json`）、保存期；候选输出 `season_status` / `season_score`（S02），并应用跨周历史重复惩罚（`ingredient_history_4w` 上周出现降权、4 周 ≥2 次强降权）与用户偏好作用范围（本周删除本周禁止恢复；persistent_reduce 降权；permanent_dislike 硬排除）。**此时还没有菜谱** | 初步食材篮子（带时令与历史标注） |
| 7 | 用户食材预选 | 跑 `scripts/ingredient_preselector.py --build-candidates`：三层展示（本周核心食材 P/V/C 编号 + 本周风味 F + 可选点缀 O），每项只显示一条理由。用户只说"不想要的编号"；删除走四类处理（直接删除/功能替换/结构替换/方案受限）；**预选清单末尾同轮收集本周价格方式二选一（A 叮咚查价 / B 参考价估算；`dingdong_price_choice` 为 `pending` 时必须在本轮解决，不单独再追问一轮，不进入步骤 8 之后的正式生成链路；用户首轮已明确时仅回显"本周价格方式：叮咚查价助手（已选择）"）**；输出预选列表后当前回合停止，收到回复再锁定；用户回复"都可以吃"整批接受 → 全部记 `accepted_batch`；点名想吃 → `explicitly_wanted`；不在候选 → `merely_allowed`；仅用户明确跳过/原请求要求直接生成/不支持多轮/fallback 默认篮子时转 provisional_locked_basket（user_reviewed=false, selection_mode=bypassed） | 预选结果（含三档语义） |
| 8 | 锁定食材篮子 | 生成 `locked_basket`（字段见 `references/output-schema.md`）：删除项不进入后续任何环节；后续菜谱原则上只用锁定核心食材，例外仅家庭基础调味、可省略装饰、用户同意的 1 种低频调料、已有库存。**`dingdong_price_choice = use_helper` 时，本环节只登记派生只读字段 `dingdong_helper_opt_in: yes`（由 `dingdong_price_choice` 派生，不直接写入），不生成任何查价文件（无草稿）**；唯一正式查价清单在步骤 13 生成（契约见 `schemas/price-query.schema.json`）；`use_estimate` 不生成 | 锁定食材篮子 |
| 9 | 菜谱库检索候选 | 在统一**生产**菜谱池过滤（仅 record_status=production：`data/recipe-index.json` 已审 HowToCook + `data/book-recipes.json` 已批准书籍菜谱 + `references/recipe-pool.md` 已批准母版；`data/library-manifest.json` 为准）：五层过滤：① locked_basket 符合性（核心食材必须来自锁定篮子）→ ② 安全与模式适配（过敏原/医嘱/周期模式/营养边界）→ ③ 烹饪条件（时间/厨具/技能）→ ④ 包装与余量（易腐复用/清库存）→ ⑤ 多样性；所在地常见可购性仅作排序加分；预选三档加分（explicitly_wanted > accepted_batch > merely_allowed）。书本菜谱不自动加权；来源配额仅柔性观察指标。**round60：候选先生成 `recipe_fingerprint`（主蛋白族＋核心蔬菜族＋烹法＋主要风味＋菜品形态）并去重——相同或高度相似指纹只保留一个代表菜谱，候选数量不得虚高；模式、时令（season_score）、来源多样性、烹法多样性、历史重复惩罚（recipe_history_8w / protein_family_history_4w）进入评分**。**排序后跑覆盖门禁**：accepted_batch 未使用项逐项补偿搜索→替换模拟→营养/包装/预算/多样性复核→入选或写真实 reason_code 到 selection report；运行记录输出选择审计（`selection_audit`，契约见 `schemas/selection-audit.schema.json`：candidate_count_before_dedup / candidate_count_after_dedup / recipe_source_count / technique_count / cuisine_count / seasonal_candidate_count / selected_recipe_ids / selected_source_ids / selected_fingerprints / history_repeat_count / rejected_reason_counts / diversity_gate_result；未计算的字段记 null，**不得伪造具体数值**；连续多周出现来源集中 / 去重后候选骤减 / 书籍从未入选 / 烹法长期单一 → 先修索引、标签和排序，而不是补书） | 候选菜谱集 + selection report + 选择审计 |
| 10 | 约束装配 | 时间/厨具/包装/多样性约束逐条过：易腐食材≥2 顿；菜谱指纹多样性（见下）；烹饪时间在用户限额内。**round60 集合优化**：不逐餐独立选最高分，而从候选中选择整周整体差异更高的一组菜单（maximize 食材命中/时令得分/可执行性/包装消耗/来源、烹法、风味、蛋白族多样性；minimize 与最近 4 周重复/本周指纹重复/同一来源占比过高/同类快炒连续出现）；自炊正餐 ≥3 餐时执行 D01–D07 硬门禁（见下），少于 3 餐按实际餐数缩放，不强行制造多样性 | 可行菜谱集 |
| 11 | 七天菜单 | 从可行集组合成 7 天菜单；一人食模式规则叠加生效；**做饭安排按用户明确信息执行**（未说明周末时标"待确认"，不假设三餐在家；直接生成时周末沿用已明确的每日自炊餐数，但不复制仅适用于工作日的地点；七天同模式不算错误，只与用户明确信息冲突才算）；**每日建议逐日独立撰写，禁止复制某一天的建议** | 菜单草稿 |
| 11.5 | 每日目标预编译 + 热量粗筛（round58：菜单装配后、精确营养计算前） | 跑 `scripts/daily_target_compiler.py` 生成 `daily_targets.json`（7 天 × 模式/阶段/净碳水上下限/蛋白四字段/脂肪供能/热量安全线/取整容差），缺字段立即失败、不进入微调；随后做菜单热量粗筛：某日明显低于安全线时先补合格加餐、烹饪脂肪、主食或天然碳水、合适蛋白份量，**不把明显不合格的菜单送入精确求解** | 冻结的每日目标矩阵 + 通过粗筛的菜单 |
| 12 | 营养重算校验 | 用 `data/foods-table.json` 按本计划克数重算，**外食餐次纳入 `data/cafeteria-meal-templates.json` 的区间估算后算全天合计**；营养计算最多两轮（第 1 轮全周联合求解 + 第 2 轮只修复失败日期），**最终复核只读、不计轮次、不改克数**；求解只接收步骤 10.5 冻结的 `daily_targets.json`；跑 `scripts/macros_calculator.py --check`；超标→回第 11 步。**任何进入菜单的克数变化必须标记受影响日期 → 局部重算当天营养 → 更新 `nutrition_snapshot_hash`**；采购剩余安排不得写成菜单加量。**复核通过后只形成稳定快照（`menu_snapshot_hash` / `nutrition_snapshot_hash`），不在本步冻结最终 plan.json**：未启用叮咚查价时经步骤 13–14 后在步骤 15 直接冻结；启用叮咚查价时须等价格结果合并完成（步骤 15 恢复分支）才冻结 | 达标菜单（+ 稳定快照，未冻结） |
| 13 | 反向汇总采购 | 菜单→汇总→扣库存→按包装规格取整；跑 `scripts/shopping_aggregator.py`。**未在菜单中使用的锁定食材不得进入采购清单**（含预选未入选项：只进 selection report 与执行提示一行说明）。`dingdong_price_choice = use_helper` 时，**在本步骤生成并交付唯一正式的「月食-查价清单.json」**——必须使用最终 `new_purchase_amount > 0` 食材、最终克数、最终 ingredient_id 与 request_id（无采购需求项不列入）。**两阶段暂停（G12）**：正式清单交付后即进入 `awaiting_price_result` 状态——本阶段只交付查价清单与一段简短操作指引（拖入助手→查价→回传结果 JSON），**不执行步骤 14–15，不输出最终食谱、采购 PDF 或任何渲染产物（拒绝渲染属正常等待，不判 fatal）**；同时记录 `menu_snapshot_hash`（菜单草案+克数）、`nutrition_snapshot_hash`（营养计算结果）与 `shopping_demand_hash`（最终新购需求）供恢复时比对。用户回传有效「月食-叮咚价格结果.json」（G13 根级校验 + price_result_validator，必要时迁移器迁移并重新校验）或选择 `opt_out_after_query` 后才继续 | 采购清单（可选：唯一正式查价清单 → 流程暂停） |
| 13.5 | 价格锚定（硬门禁） | 每条采购项必须有价格：优先 `scripts/market_price_normalizer.py` + `references/cities/{city}-price-sources.yaml` 有效样本；无样本（confidence low/unavailable）按 `data/price-estimates.json` 六大类行情估算并标注估算口径。**禁止"暂无参考价/实价为准/待定"占位**；区间按上限累加，清单顶部显示"本周预算约 ¥XXX（估算口径，实际以购买时为准）" | 带价采购清单 |
| 14 | 输出采购信息 | 每项食材输出采购清单字段（`references/output-schema.md`：食材/常用购买名称/建议购买量/常见规格/参考价/平替/剩余去向）+ 储存方式 | 最终采购清单 |
| 15 | 定稿 plan.json 并渲染 | **格式差异化渲染（round56 定稿）**：「对应菜单及用量」HTML/Word/Markdown 默认完整保留（HTML 可折叠、Word 附录、Markdown 分组列表），**PDF 固定不展示**。业务结果一次写入并校验 plan.json（契约见 output-schema）；用 `scripts/render_plan.py` 固定组件渲染，禁止占位符全局 replace 与运行时修模板；按用户所选格式交付（单选只交单种）；**正式文件不含"03 本周食材选择"小节**；做法按问卷必选项（B 则 recipe_steps 读取数为 0）。**查价链路恢复（两阶段第二阶段）**：价格结果回传后先比对 `menu_snapshot_hash` / `nutrition_snapshot_hash` / `shopping_demand_hash`——三哈希均匹配时只做**价格层局部重算**（价格校验、候选筛选、包装组合、预算更新，即重跑步骤 13.5 后直接进入本步渲染，菜单、做法、营养不重算）；普通商品切换、促销价变化和包装取整不触发菜单重算；**只有 ingredient_id 发生替换时才局部重算对应餐次与当天营养**；任一快照哈希变化说明用户在查价期间改了菜单或参数，须回到对应步骤重算后再渲染。第二阶段一次性交付全部最终产物（最终文件只渲染一次；渲染失败只重跑渲染层），不再回到 awaiting_price_result。最终预算、采购表和价格说明引用同一 `price_result_hash` | 交付物 |

## 两次生成的核心原则

**先篮子，后菜单（两段之间加一次用户预选）。** 第一阶段的食材篮子决定"这周买什么"，用户只做减法与少量替换，锁定后第二阶段只在锁定篮子内选菜谱。禁止反过来——先想菜谱再凑采购，必然产生一次性配菜和浪费。

### 食材预选（步骤 7-8 的规则）

- **SELECT-001（2026-09-18，强制交互点）**：步骤 7 必须把候选清单**原文展示给用户并停止等待回复**；只有用户明确回复（删除/替换/点名，或"都可以，直接生成"）后才能进入步骤 8 锁定。**执行方不得自行整批接受、不得用默认值代替用户回复、不得跳过该步骤直接进入菜单生成或渲染**；用户明确"都可以/直接生成"时以 `selection_mode=bypassed` 记录（`provisional_locked`）；未收到回复时 `selection_mode=provisional`，**禁止进入正式生成与渲染**。锁定结果必须留痕 `user_reviewed` / `selection_mode` / 用户回复原文。**本周已删除（week_only_dislikes）的食材不得再次出现在候选清单**（本周不恢复，下周自动恢复 neutral）。
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

### D01–D07 多样性硬门禁（round60；round61 统一主蛋白规则与适用范围）

**适用范围（按 planned 自炊正餐数量缩放）**：≥3 餐时 D01–D05 作为硬门禁执行；=2 餐时按可行性尽量满足（软约束），不因多样性强制增加食材或设备负担；=1 餐时不执行 D01–D05。D06/D07 跨周规则不受餐数缩放影响。

- **D01（round61 定稿，替代旧"同一主食材一周 ≤3 次"）**：planned 自炊正餐 ≥3 餐时优先使主蛋白不重复；因库存消耗、包装完整利用、预算、用户点名或批量备餐需要重复时，**同一主蛋白最多出现 2 次，并且烹法或主风味必须不同**。分类处理：正餐主蛋白按本条；早餐基础食材（鸡蛋/牛奶/燕麦等）允许规律重复；蔬菜允许跨餐消耗但相邻自炊正餐避免完全相同组合；调味和基础油不适用重复限制；批量备餐按用户明确策略处理；
- **D02**：至少使用 2 种不同烹法（本技能既有标准为 ≥3 种，从严执行）；
- **D03**：同一 `recipe_fingerprint` 不得重复；
- **D04**：相邻自炊餐不得同时为"快炒＋咸鲜"组合；
- **D05**：同一菜谱来源（source_id）不得包揽全部自炊正餐；
- **D06**：最近 4 周已出现的完全相同菜谱默认降权（不绝对拒绝；用户点名、库存消耗或只存在一个安全可行候选时允许保留，但必须记录原因）；
- **D07**：用户点名保留的菜不受一般重复惩罚，但仍受安全、医嘱、过敏原、时间、设备和营养门禁。

**多样性不得凌驾的条件**（优先级高于全部 D 门禁）：① 安全与医嘱；② 用户明确排除；③ 餐次时间和厨具；④ 库存优先消耗；⑤ 一人食包装利用；⑥ 预算上限；⑦ 用户明确要求批量备餐。豁免必须记录 reason_code。

### S01–S04 时令门禁（round60）

- **S01**：声称"当季"必须具备 `region` + `month` + `season_status` + `source_rule_id` 四要素（数据见 `data/seasonal-produce-cn.json`，来源必须可追溯，**找不到审核过的时令数据时不得虚构"当季"结论**）；脚本传了 `--month` 只能证明月份进入流程，不能单独证明时令规则实际影响了候选选择；
- **S02**：食材篮子输出必须记录每个候选的 `season_status`（peak / in_season / shoulder / off_season / unknown）与 `season_score`；
- **S03**：至少一个时令候选应进入预选集合；如无，记录原因；
- **S04**：时令不得覆盖用户排除、安全规则和库存优先消耗；优先级顺序为：安全与医嘱 → 用户明确偏好/排除 → 菜单营养与形态适配 → 当地可获得性 → 时令状态 → 包装与预算 → 多样性。时令评分口径：`peak` 明显加分、`in_season` 加分、`shoulder` 中性、`off_season` 降权但不硬拒绝；用户点名、库存消耗和特殊营养需要可覆盖时令降权；叮咚实际可售与价格可作为当地可获得性的补充证据。预选阶段可向用户简短说明时令取舍（如"本周优先：当季叶菜 3 种"），但不得使用无可追溯资料支撑的"当季"标签。

**时令数据缺失降级（round61，G01 条件完整性）**：启用时令优先或准备输出"当季"文字时先查 `data/seasonal-produce-cn.json`；用户未强制时令 → 停止使用"当季"表述继续生成并记录 `seasonal_data_unavailable`（非 fatal）；用户明确要求必须按时令 → `user_input_required` 或 `core_rule_file_missing`；不得凭月份常识补写当季结论。

**执行审计（round61，运行记录必须包含，未实际计算的字段记 null，不得填猜测值）**：`meal_semantic_audit`（user_phrase / meal_type / meal_plan_mode / preparation_mode / include_in_nutrition / include_in_procurement）、`mode_consistency_audit`（mode_schedule_hash 与 basket_builder / recipe_ranker / 营养求解三组件 match 布尔，最终审计要求三组件哈希完全一致）、`selection_audit`（指纹去重前后候选数、来源数、烹法数、时令候选数、近 4 周重复数、selected ids/source_ids/fingerprints、diversity_gate_result）、时令证据（地区 / 月份 / 时令规则版本 / 进入预选的时令候选 / 最终入选食材 season_status）。

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
