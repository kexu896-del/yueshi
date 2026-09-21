# 变更记录（唯一历史记录文件，最新在前）

## 用户指示 2026-09-21（round 72：早餐"自己做"语义最终修正 + yueshi-1.4.3-ux-final 冻结）
依据《月食yueshi-1.4.3用户体验最终补丁方案》执行（1 项 P0 必改 + 2 项可选文案优化；本方案明确要求修改
SKILL.md 入口摘要，覆盖其冻结惯例，特此记录）：
- **Fixed**：
  - 修正"工作日早餐自己做"被自动推断为快手早餐的问题：SKILL.md 入口摘要「餐次状态契约」段仍残留
    "自己简单解决默认映射为 `planned` + `preparation_mode = quick_self_prepare`（给快手搭配）"旧规则，
    与 runtime-rules.md 正式 owner 规则（round65/round67 已修正）不一致——已按方案 §3.4 建议替换文本
    同步改写两处：早餐是否自做、可用时间、免开火和提前备餐拆分为独立事实（`preparation_mode` /
    `max_active_minutes` / `no_cook_allowed` / `advance_prep_allowed` 分别记录、不相互替代）；
    用户未提供早餐时间限制时，不得仅凭"自己做"或"简单解决"写入 `quick_self_prepare`。
  - 早餐保持 `planned`，继续纳入菜单、营养和采购（B01/B02 硬约束不变）；"自己简单解决""随便做点"
    仍不得降级为 `guidance_only`。
  - runtime-rules.md 补充两条防误读说明：选择早餐模板不回写 `quick_self_prepare` 等难度字段；
    无快手条件的 planned 早餐按一般家常规划，模板库仅作可选菜品来源、不作排除依据
    （早餐模板不会因餐次缺少 quick 标记而被错误排除）。
- **Changed（可选展示优化，不阻断冻结）**：
  - README「使用过程」五条改为冒号格式（仅排版，方案 §4.1）。
  - README 叮咚助手分发说明简化为一句话（"准备助手：解压并保留完整文件夹，不要只复制其中的 exe。"，
    方案 §5.1）；过渡交付方式、安装版规划与源码构建说明移至 MAINTENANCE.md
    新增「叮咚查价助手分发与构建」一节。
- **Unchanged**：
  - 方案 §6 冻结项一律不动（核心价值表达 / 自然语言描述与一轮补问 / 关键八项内容与列表样式 /
    价格方式两选项 / 用户动作流程 / 预选只做减法 / 查价后一次性出最终文件 / 四格式信息深度差异 /
    用户与维护者内容分离 / 模式系统推算 / 安全声明 / 不增加"30 秒开始使用"）。
  - 早餐模板库数据（data/breakfast-templates.json，22 模板十类）与构建脚本不变；
    历史 `breakfast_mode` 字段仍仅按 schema 映射为 `meal_plan_mode`。
- **同步检查（方案 §3.5）**：SKILL.md 入口摘要与 references/runtime-rules.md 已一致（五条规则句两边同有，
  由测试锁定）；问卷示例无需修改（round65 起即"工作日早餐自己做"，不附带快手推断）；早餐模板路由条件
  确认正确并加防误读说明；历史字段迁移逻辑确认无误（仅 schema 映射，无 quick 推断）；相关测试快照
  同步修正（test_round60 针脚随新措辞更新）。
- **测试与构建校验**：新增 `tests/test_round72_breakfast_semantics.py`（11 项，覆盖方案 §3.6 七个场景 +
  入口/owner 一致性 + 模板路由与构建幂等 + 历史字段映射）；全量回归 **70/73 通过**
  （3 项失败为提取副本缺少技能树外 yueshi-dingdong-helper 助手源码目录所致，与本轮无关）；
  pyflakes 清洁；`scripts/release_pack.py` 全链路通过——**package smoke PASS、reproducible_build true、
  hard_fails 为空**（同步技能目录后的副本复测不在本工作副本范围内）。
- **冻结**：yueshi-1.4.3 标记为稳定基线（yueshi-1.4.3-ux-final）。后续只响应真实用户操作障碍、
  菜单错误或可复现缺陷，不再因排版偏好或说明简化启动新轮次。

## 用户指示 2026-09-21（round 71：用户体验最终收口——README 拆分 / 价格方式二选一 / 问卷渐进披露 / 对话暂停点，yueshi-1.4.3-ux-final）
依据《月食yueshi-1.4.3用户体验最终收口方案》执行（仅文档与表达层收口，无功能变更）：
- **Changed**：
  - README.md 改为纯普通用户向：「使用前需要提供的信息」开头新增引导语"不需要逐项填写，按平常说话的方式
    描述即可；缺少的信息，月食会合并成一轮询问"；价格方式改为「A. 使用叮咚查价助手 / B. 使用公开参考价格」
    两个清晰选项（含"如果本周还没有选择，月食会在食材预选时一并询问，不会自行默认"），用户端不再出现
    use_helper / use_estimate / pending / request_id / awaiting_price_result 等内部词；「用户可见的状态流程」
    改写为「使用过程」五步用户动作（描述实际情况 → 删除不想要的食材 → 月食生成菜单并检查营养 →
    选择叮咚时完成一次查价 → 获取最终计划）；末尾只保留「维护与开发」四行指针块
    （SKILL.md / CHANGELOG.md / developer/maintenance-map.md / MAINTENANCE.md）。
  - 新增 MAINTENANCE.md：迁入原 README 的「基本流程（单人 15 步/家庭 13 步）」「给维护者 / 其他 AI」整节
    与「目录」整节，开头标明"面向开发、维护者和其他 AI；普通用户无需阅读或运行其中命令"。
  - references/questionnaire.md：追加「一轮补问模板（四区块）」——这周为谁安排 / 哪些餐需要安排 /
    做饭与采购 / 最终文件，用户可以整段回复、不要求逐格填写；追加「条件显示」六条规则（不适用周期不显示
    周期问题、未选叮咚不显示助手操作、单人不显示家庭成员配置、公开估价不解释 JSON 回传、无硬预算只问
    大致范围、已明确事实不重复询问）；追加「对话暂停点」固定话术（食材预选后 / 等待查价时 / 信息不足时
    三种暂停每次只给一个主要动作，不在同一暂停消息中解释完整内部流程、状态名称或下一阶段算法）；
    早餐快手判定补规则句"用户未说明早餐时间限制时，不得仅凭'自己做'或'简单解决'写入
    `quick_self_prepare`"（语义与 round65 餐次覆盖追问一致）。
- **Fixed**：
  - 修复"工作日早餐自己做"在文本层仍可能被过度推断为快手早餐的残留风险（round65 语义 + round71 规则句双锁定）。
  - 修复不适用字段仍在问卷中无条件展示的问题（条件显示规则）。
  - 修复普通用户与维护者内容混杂导致的理解负担（README / MAINTENANCE 拆分）。
- **Unchanged**：
  - 不增加"30 秒开始使用"模块；不要求关键八项改为有序子列表；不新增简洁版/详细版问卷项。
  - 方案 §9（PDF 紧凑 / HTML·Word·Markdown 保留详细附录）经核对已由 round56 定稿的格式差异化渲染覆盖
    （references/output-policy.md「对应菜单及用量的格式差异化策略」：HTML 默认完整保留可折叠、
    Word 默认附录、Markdown 分组列表、PDF 固定不展示），本轮仅核对已覆盖，不改动。
  - 方案 §10 保留项（核心价值表达"买得到、做得完、吃得完" / 食材预选只做减法 / 模式由系统推算 /
    查价前不冻结最终文件 / PDF 保持紧凑）全部确认不改动。
  - 叮咚助手首次运行自检、自然语言错误提示、分发说明简化（方案 §8）属助手侧改动，本轮不在技能仓文本层落实。
  - SKILL.md 入口冻结口径不变。
- **测试**：新增 `tests/test_ux_finalization.py`（16 项静态文本断言，覆盖方案 §13 可静态断言项）；
  历史测试 test_round57 / test_round58 / test_round59 / test_round61 / test_round63 / test_round64_1 /
  test_round67_final_acceptance 的 README 断言按新行为同步修正（维护者内容针脚改指 MAINTENANCE.md、
  价格方式与用户流程改指新文案）。全量回归 **69/72 通过**；3 项失败（test_round65_realrun /
  test_round67_runtime_reliability / test_round69_universal_gate）为提取副本缺少技能树外
  `yueshi-dingdong-helper` 助手源码目录所致，与本轮修改无关（修改前基线同样失败）。

## 用户指示 2026-09-21（round 70.1：五书 A 级 84 条规则落地 + 维护修复，yueshi-1.4.3 补丁）
承接 round70 五书精读，将 A 级候选从报告文本落为可执行、可校验的结构化规则库：
- **规则库入库**：新增 `data/functional-medicine-rules.json`——84 条（DN 14 / GE 17 / DD 23 / WW 14 / BA 16，
  与 round70 清单逐条对应），字段 rule_id / book / category / applies_to / auto_tip / tip_key / tip_text / note；
  **67 条 auto_tip**（行为与食物层面，可作执行提示候选）、**17 条非自动**（协议类：消除-回添、2 周排除-复引；
  安全转介：自免/桥本、备孕、哺乳；监测建议：腰围/腰高比、空腹胰岛素；认知纠偏与红线）。
- **数值边界（硬门禁）**：`numeric_policy=reference_only`——规则库不得含 parameter_id/effective_parameter_id 字段，
  自动提示文案禁止出现 g/kg、µU、HOMA、mg、mmol、%、阈值、剂量等数值型主张；模式配额、蛋白目标、断食时长
  仍以 `data/effective-parameters.json` 批准参数与断食窗口安排为唯一生产来源（round70 既定口径不变）。
- **选择器**：新增 `scripts/functional_medicine_rules.py`（加载/校验/选择；CLI `--mode/--context/--limit/--validate`）——
  auto_tip 候选按模式与情境（自免/肠道修复/备孕/哺乳/更年期/素食/减重）筛选，tip_key 去重（同一行为建议多书印证只取一条），
  确定性顺序；每份计划至多采纳 2 条，总数仍受 output-policy 执行提示上限约束。
- **文档接入**：`references/runtime-rules.md` 新增「功能医学行为规则」章节（自动与不自动边界、数值边界、红线）；
  `references/output-policy.md` 执行提示口径补一句来源说明；`developer/maintenance-map.md` 文件地图登记新文件。
- **测试**：新增 `tests/test_round70_1_functional_medicine_rules.py`——84 条计数与每书条数、id 唯一、数值门禁、
  选择器确定性/去重/协议与监测类排除/情境标签生效、禁用词与内部表达检查、反向探针（坏提示被拦）、
  提示并入 golden 计划后渲染校验通过；全量 **71/71** 通过后重新打包。
- **维护修复**：技能侧两个测试改为兼容助手源码包平铺/嵌套两种布局（`test_round67_runtime_reliability` /
  `test_round69_universal_gate`，助手目录去嵌套后 68/70 → 71/71）；`docs/history` 十个乱码文件名重命名为
  `change-comparison-roundNN.md`；旧提取产物按维护包恢复（09-18 维护包 36 文件 + 08-21 快照补齐
  鱼米之乡/一人锅/The-Complete-One-Pot/nutrition-audit 四目录），维护地图引用重新有效。

## 用户指示 2026-09-21（round 70：功能医学五书精读入库，yueshi-1.4.3 补丁）
依据《月食功能医学精读提示词（最终版）》对桌面"九本书"文件夹中的五本英文书完成全文精读与知识提炼：
- **五书**：The Disease Delusion（Bland）/ Good Energy（Means）/ Why We Get Sick（Bikman）/
  Beat Autoimmune（Kippola）/ Deep Nutrition（Shanahan）。全书逐章通读，案例/故事/营销内容剔除；
  每书产出《<书名> 对月食的知识提炼报告》（十部分结构 + 评分表），存于维护区
  `book-extraction/<book>/`（不进发布包；全文临时提取文件已按安全红线删除，不保存大段原文）。
- **共识矩阵扩容**：`references/book-consensus.md` 由十一本扩为十六本——新增两条跨书共识
  （进食顺序与时间架构 / 睡眠-活动-压力是饮食之外的一半）、五行"各书专属工具"背景资料、
  四条跨书分歧采纳口径（精炼种子油 / 乳制品与麸质 / 饱和脂肪 / 代谢优化阈值）。
- **采纳分层**：五书共产出 A 级（直接纳入规则库）候选 84 条——均为行为与食物层面规则
  （进食顺序、餐后步行、每餐五组件、低温烹饪、消除-回添协议、骨汤与发酵食品、每周 30 种植物等）；
  **数值型主张（代谢阈值、剂量、时长）一律未写入 `data/effective-parameters.json`**——
  生产参数仍须 source_verified + audit_status=approved 人工审核后方可进入计划计算；
  补充剂相关内容仅作知识库，月食不主动推荐补充剂的立场不变。
- **风险剔除**：各书 D 级剔除项（作者商业绑定的补充剂/医疗食品、裸盖菇素、能量医学、
  面相学、反他汀叙事、生奶与自制婴儿配方、无法验证的数字等）已在报告中标注，不进入任何规则层。
- **未改动**：cycle-protocol.md 仍称"十一本书协议库"——五本新书非周期/断食协议书，
  协议库范围不变；SKILL.md 入口冻结口径不变。

## 用户指示 2026-09-18（round 69：通用商品四维门禁 + 酮生物金丝雀，yueshi-1.4.3 补丁）
依据《月食yueshi-1.4.3通用商品门禁收口方案》：
- **通用四维门禁**：评估器统一输出 identity / composition / processing / attribute_evidence
  四维结构与 accepted / rejected / review_required 三态；判定器不含品类硬编码分支
  （品类差异全部来自结构化验收档案）；维度词表按框架归位（预制菜→composition；
  香煎/秘制/红烧/糖醋→processing.seasoned；即食/熟食/凉菜→processing.ready_to_eat；
  油炸/裹粉→processing.fried）；技能与助手两端同步。
- **概念关系类型**：助手词典建议新增 `relation_type` / `usage`——大品类召回词记为
  parent_category + search_recall_only（不再是 new_alias），其余候选记为
  synonym_candidate + requires_review；线上建议不自动写入生产词典。
- **六类商品仅作回归样本**：酸奶（mixed_product）、面包（whole_grain 证据不足）、
  豆腐（单一原料）、猪里脊（物种+部位）、南瓜（零食形态）、带鱼（预制/加工形态）
  全部由同一判定器处理，不建立六套算法。
- **酮生物金丝雀**：新增 `data/golden/keto-canary-menu.json` 与端到端验证——实际菜单
  kcal 1664 / 净碳水 18.9g / 脂肪供能 76% / 蛋白 73.6g，全部满足安全线 1559.5、
  上限 50g、下限 60%、基础需要 70g；采购需求与菜单一致。
- **回归复评**：实时结果用四维门禁复评结果不变（15 accepted / 1 rejected / 2 review /
  6 最终采购 / 无效 0）。round69 真实链路复跑（助手源码 CLI + 登录态）：助手自判与技能复评
  **逐项最终采购完全一致**（6/6）；并据实测新增通用守卫——紧跟「味」的属性词是风味声明、
  不算原料证据（「全麦味」→ review_required，「全麦吐司」→ accepted）。
- **测试**：新增 `tests/test_round69_universal_gate.py`（四维门禁 + 无品类分支探针 +
  概念关系探针 + 金丝雀）；全量 70/70 通过后重新打包。

## 用户指示 2026-09-18（round 68：模式营养语义回归 + 查价证据层级收口，yueshi-1.4.3 补丁）
依据《月食yueshi-1.4.3营养语义与最终验收改进方案》：
- **模式营养语义落地验证**：新增 `scripts/run_mode_semantics_regression.py`——同一用户事实下
  两种模式受控对照，验证：结构化目标（热量/安全线/净碳水/蛋白四字段/脂肪下限）、
  目标来自 approved 参数（C05–C10、S-P01，source_rule_id 可追溯）、目标进入每日目标编译、
  篮子与 ranker 的模式约束差异真实存在、渲染器不定义目标、安全规则优先；
  产物 `mode-semantics-regression.json`（diet-plans/2026-09-18-mode-regression/）。
  实测差异：净碳水上限 50 vs 100g、脂肪下限 60% vs 0%、蛋白参考值 75 vs 50g；
  篮子：酮生物无碳水/平衡激素含天然碳水；ranker：41 vs 45 道候选。
- **查价证据层级收口**：plain 单品要求下调味/混合成分拒收（flavored_product /
  mixed_composition，如「0蔗糖酸奶（西柚脐橙燕麦爆珠）」）；无添加糖与全麦证据分层
  （标题声明记 title_claim，选择层透传 evidence_level 与「购买时请查看配料表确认」）；
  仅「黑麦/杂粮」不得自动满足全麦要求（review_required）；大品类召回词不再记为食材别名，
  改记 `parent_category_query`。
- **回归复评**：`run_price_regression.py` 新增 `--revalidate`（旧结果按当前门禁重评）；
  用户 GUI 实测结果复评：混合调味酸奶 rejected、黑麦欧包/杂粮吐司 review_required、
  最终采购改为全麦列巴；6/6 采购、无效采购 0、估价回退 0。
- **正式 PDF 重渲染（1.4.3 表达层）**：封面去试跑字样、模式显示「平衡激素模式」+ 通俗说明、
  可选加餐按饥饿程度、预算目标/范围/节省分列、估价说明一次、末页 ≤5 条；
  渲染门禁通过（无内部表达、无禁用语）。
- **测试**：新增 `tests/test_round68_mode_semantics.py`；round67 选择层新增实测校准断言；
  全量测试通过后重新打包。

## 用户指示 2026-09-18（round 67.1：真实平台回归修复——搜索响应等待 / 候选截断 / 语义词典实测校准，yueshi-1.4.3 补丁）
按《yueshi-1.4.3 最终验收改进方案》§6-§10 执行**真实平台回归**（六类食材，助手源码 + 本机登录态）：
- **助手搜索链路修复（真实平台实测）**：searchProduct 响应可能数秒才到、首击偶发不触发，
  原固定 1800ms 等待会抓到推荐流（有名无价）而误判"未查到"→ 改为等待 searchProduct 响应
  （未出现则重试 Enter，最多 2 次）；实测 6/6 查询命中真实搜索结果。
- **候选截断修复**：round67 保留 rejected/review_required 证据后，推荐流候选会挤占
  前 3 个名额把真实商品截断；截断前按 accepted > review_required > rejected 排序。
- **状态修正**：无 accepted 候选（仅剩证据）时不再标 success，返回 candidates_filtered +
  NO_ACCEPTED_CANDIDATE，供月食选择层回退参考估价。
- **语义词典实测校准**（两端同步）：`无蔗糖/0糖` 计入无添加糖证据；删除裸「卤」
  （卤水豆腐是凝固工艺，不是预制菜）；新增物种词误伤守卫（牛奶/奶油/牛油果/蜗牛
  不触发牛冲突）。
- **真实回归结果**：无糖酸奶/全麦面包/豆腐/猪里脊/南瓜/带鱼 6/6 最终采购，
  accepted 18、无效最终采购 0、估价回退 0；产物在
  `diet-plans/2026-09-18-regression-live/`（另保留 fixture 基线
  `diet-plans/2026-09-18-regression/`）。
- **测试**：round67 选择层新增三项实测校准断言；全量测试通过后重新打包。

## 用户指示 2026-09-18（round 67 最终验收 → yueshi-1.4.3-final：早餐语义 / README 结构 / 模式名称 / 固定查价回归）
依据《月食yueshi-1.4.3最终验收改进方案》执行：
- **早餐语义定稿（MEAL-STATE-001）**："工作日早餐自己做"映射 `planned`（计入菜单/营养/采购），
  不附带 `quick_self_prepare`；"自己简单解决/随便做点"只记 `preparation_preference=simple`，
  不得推断快手、免开火或固定时长；`quick_self_prepare` + `max_active_minutes` 仅在用户给出
  明确时间证据时写入；简单餐次不得降级 `guidance_only`；问卷示例与规则索引同步清理旧映射。
- **README 关键八项**：修正为 4 空格缩进的有序子列表（1–8），价格方式同级、不计入八项。
- **模式名称**：SKILL 营养路由措辞改为"平衡激素模式、酮生物模式及周期阶段适配规则"；
  全仓无旧模式名称残留。
- **固定查价回归（六类食材）**：无糖酸奶/全麦面包/豆腐/猪里脊/南瓜/带鱼；
  新增 `scripts/run_price_regression.py`，产物四件套（price-query-regression /
  price-result-regression / price-semantic-gate-report / price-regression-summary）输出到
  `diet-plans/2026-09-18-regression/`；本次 replay 结果：accepted 7 / rejected 7 /
  review_required 2 / 最终采购 6 / 估价回退 1 / **无效最终采购 0**；
  牛小里脊、南瓜脆片、预制带鱼、油豆腐均 rejected；无糖酸奶无候选按参考估价。
- **测试**：新增 `tests/test_round67_final_acceptance.py`（早餐 6 + README 3 + 模式 4 + 回归）；
  全量测试通过后经 `scripts/release_pack.py` 冻结。

## 用户指示 2026-09-18（round 67 → yueshi-1.4.3：用户表达层 + 模式显示统一 + 商品语义门禁与采购选择层）
依据《月食yueshi-1.4.2运行改进方案》执行（运行样本 2026-09-18~09-24 r2）：
- **模式显示统一**：正式名称「平衡激素模式 / 酮生物模式」，新增 `data/mode-display.json`
  映射与通俗执行说明；内部枚举保持兼容，正式文件不出现内部枚举与推算/校验字段；
  模式仍由系统推算，不作为问卷选项；全仓清理旧称。
- **用户表达层**：`output-policy.md` 新增「用户表达层」；新增
  `scripts/common/visible_messages.py`（可选加餐/蛋白/预算/估价/时令/查价失败话术）；
  可见消息类型与内部消息类型分离；PDF 每日营养默认只展示生活化摘要
  （`days[].nutrition_summary.user_line`），HTML/Markdown 保留参考估算行；
  PDF 执行提醒最多 5 条；预算摘要改为「目标预算 + 可接受范围」分开说明、
  节省建议最多两条；估价说明全文件一次；用户可见术语门禁扩充
  （新版试跑/覆盖层/角色对齐/热量补偿/主餐口径/不计上限/降权保留/校验通过/门禁结果）。
- **查价契约拆分**（`schemas/price-query.schema.json`）：新增 display_name /
  search_scope.category_query（大品类召回）/ acceptance_profile（品类、物种、部位、
  结构、加工、特定要求）/ uncertainty_policy；别名只用于召回，不再作为商品合格的充分条件。
- **商品语义门禁与三态**：新增 `data/product-acceptance-profiles.json`
  （无糖酸奶/全麦面包/豆腐/猪里脊/南瓜/芹菜/带鱼）与 `scripts/common/product_semantics.py`；
  助手侧新增 `src/semantics.py`，候选输出 candidate_decision / evidence /
  rejection_reasons；rejected 与 review_required 保留为候选证据但不进建议购买。
- **采购选择层**：新增 `scripts/purchase_selector.py`——最终采购建议只从 accepted
  候选中选（普通应付价 + 包装适配），记录 selection_change_reason_codes，
  禁止无日志静默替换；助手 eligible_for_purchase / suggested_purchase 不再视为最终结论。
- **助手侧**：大品类召回（search_scope 优先，父品类仅回退）、验收前剥离【】促销前缀、
  三态排序（accepted > review_required > rejected）、窗口模式精简诊断
  `logs/run-summary.json`（search_not_triggered / all_rejected / review_required_only /
  accepted_candidates_found 等阶段）。
- **修复**：猪里脊接受牛小里脊（species_conflict）；南瓜接受南瓜脆片/混合粗粮包
  （snack_product/composite_food）；芹菜接受芹菜香干（composite_food）；
  生带鱼接受预制香煎/秘制带鱼（prepared_dish）；无糖酸奶长尾词轮询与证据不足误判
  （大品类召回 + 证据分级，不足转 review_required）；全麦面包标题声明与验证混淆（title_claim）。
- **运行可靠性**：`render_pdf.py` 输出必须为文件路径（传目录显式失败）+ 产物存在性/页数校验；
  新增 `scripts/common/plan_patch.py`（合并补丁幂等，重复执行内容哈希一致）。
- **测试**：新增 test_round67_user_expression / test_round67_purchase_selector /
  test_round67_runtime_reliability；版本断言与 golden 样例同步升级 yueshi-1.4.3。

## 用户指示 2026-09-18（round 66.1：预选确认强制交互 SELECT-001 + 已删食材不再展示 + 包装单位口径告警，yueshi-1.4.2 补丁）
试跑复盘发现的流程缺口与单位口径问题：
- **SELECT-001（预选确认强制交互）**：候选清单必须展示并等待用户明确回复后才能锁定；
  执行方不得自行整批接受、不得跳过该步骤直接进入菜单生成或渲染；`locked_basket` 新增
  `selection_mode` 留痕（applied / bypassed / provisional，按"是否提供用户选择文件"判定；
  偏好文件中的 week_only_dislikes 自动剔除不算本轮选择），未确认锁定时输出 SELECT-001
  告警且禁止进入正式生成；用户明确"都可以，直接生成"记 bypassed。
  规则写入 `workflows/planning-flow.md` 与 `references/rule-index.md`。
- **本周已删除食材不再进入候选**：`ingredient_preselector.py` 把 `week_only_dislikes`
  从候选层剔除（此前仅标 dislike_this_week 仍展示，用户会在清单里再次看到刚删过的食材）；
  预筛选移除记录"本周已删除：不进候选（本周不恢复，下周自动恢复）"。
- **包装单位口径告警**：`shopping_aggregator.py` 对"包装单位=枚/根/个 + 需求量按克"的组合
  输出人工核对提示（试跑中单价表单位口径混填曾把预算放大到 ¥1486；正式口径为包装克重 +
  按包装计价）。
- **回归**：新增 `tests/test_round66_1_select_gate.py`；全量 64 个测试通过。

## 用户指示 2026-09-18（round 66：2026-09-18 运行评审修复——P02 契约 / 脚本缺陷 / 江淮时令覆盖层 / 加餐补偿，yueshi-1.4.2 补丁）
依据《月食2026-09-18运行评审与改进方案》直接执行（真实运行证据，版本维持 1.4.2）：
- **P0 P02/observed_at 双端修复**：月食侧 `price_result_validator.py` 判定改为「候选级 observed_at
  或批次级 observed_at 至少一个存在」，批次级取根级 `observed_at`、缺失回退 `completed_at`；
  `price_provider_router.build_price_snapshot_meta` 同口径并回退读取根级 `provider_version`；
  Schema 增补根级 `observed_at` / `provider_version` 说明；policy §7 P02 与 §4 增补同步。
  助手侧（源码）：结果根级新增 `observed_at`（=查询完成时间）与 `provider_version`（APP_VERSION 2.0），
  `run_warnings` 恒为数组；导出自检新增 E06（observed_at 非空），完成页门禁改 E01–E06。
  回测：2026-09-18 真实结果 P02 违例 46 → 0（原 P07 两条不变）。
- **P1 脚本缺陷修复**：① `ingredient_preselector.py --lock-basket` 合并 `user_selection.remove`
  与 `preferences.week_only_dislikes`，修复"用户删除项被加回"；② `basket_builder.py` /
  `ingredient_preselector.py` 入口 `sys.stdout.reconfigure(utf-8)`，不再依赖手工环境变量；
  ③ `shopping_aggregator.py` 分区表补齐菜单 CSV 展示分区名（蔬菜与菌菇/肉蛋水产与豆制品/
  谷物薯类与主食/乳品与油脂），"可选点缀"按 ingredient_family 细分（乳品→oil_nut），
  修复"乳品并入蔬菜区 → 核心食材 18>16 误报"；④ `render_pdf.py` 内置浏览器探测链
  （chromium → Chrome → Edge，含每用户目录与 PATH 兜底，支持 YUESHI_BROWSER 覆盖），
  废弃手工 .shim，不传 --no-sandbox，找不到浏览器退出码 2。
- **P1 江淮时令覆盖层**：`seasonal-foods.json` + `seasonal-produce-cn.json` 合并江淮覆盖层
  （来源：区域级公开资料 + 菜场/生鲜平台常见性），每月 21–32 项（9 月 7 → 32），
  条目新增 `evidence_type`（national_audited / jianghuai_overlay），version 维持 1.0.0；
  9 月篮子已实测命中当令蔬菜优先（S02 生效）。
- **P1 低置信度日热量缺口补偿**：`nutrition-routing.md` 新增规则——全天估算热量低于安全线 −5% 时
  自动追加脂肪/蛋白型加餐（坚果 15g / 鸡蛋 1 个 / 无糖酸奶 100g），走统一调整器、
  来源限四类受控范围，执行提示注明"外食更足时可不吃"；补偿后仍低于 −5% 按不达标处理。
- **P1 蛋白角色全量对齐**：`protein-candidate-roles.json` 1.0.0 → 1.1.0，catalog 全部 32 种
  蛋白质逐一登记（staple 16 / rotation 12 / exploratory 4），移除 catalog 不存在的死条目
  （泛称与别名；未登记按 rotation 默认处理），鳕鱼按经济型预算口径由 staple 调整为 rotation；
  新增 `tests/test_round66_protein_roles.py` 回归。
- **测试环境与测试健壮性**：本机补装 jsonschema / python-docx / scipy；修正
  test_round65（UTF-8 fixture 写入与解码、助手目录兼容两种布局）、test_round46（临时文件 UTF-8）。
- **回归**：全量 63 个测试全部通过。
- **待办（需重跑发布链，未实施）**：catalog 增补江淮常见食材（鲫鱼/草鱼/黑鱼/黄颡鱼/鸡翅根/
  鹌鹑蛋/腐竹/素鸡/河虾）与 `provider_availability` 学习闭环——两者都会改变
  ingredient-catalog.json 哈希，须走 classifier → fingerprint → auditor → release gate 全链
  重新冻结；另发现 catalog 数据缺陷"牛里脊 ingredient_family=pork"（应为 beef），随下次
  catalog 变更一并修复。助手源码改动需重新打包（一键生成安装包.bat）后生效。

## 用户指示 2026-09-18（维护区批次：七书重新提取 + 5×5×5 防御食物清单 + 跨书产物重建，yueshi-1.4.2）
用户指示直接执行书籍补齐（不再另行打包方案）。2026-08-21 批次的维护区产物经全盘核查在本机缺失，
本次按 `references/book-recipe-extraction.md` 重新提取并重建全部维护区产物。**仅维护区（repo-only）变更：
未触碰生产池、未改 release artifact_hashes、无需重跑发布门禁。**
- **候选重建（全部保持 candidate，未入池）**：chinese_homestyle 82 条 + 酱汁模板 33 条；
  chinese_soul_food 98 条 + 快炒焖烧模板 9 条 + 平替表 72 条；woks_of_life 101 条 + 一锅面饭模板 7 条 +
  嫩化技法 7 条；coconut_sambal 91 条 + 参巴模板 10 条 + 调料复用图 14 条；各书均含 audit-report.md。
- **新增来源登记**：`how_to_eat_cookbook`（How to Eat to Beat Disease Cookbook，Hultin 2021）
  75 条候选，fingerprint = 源 EPUB sha256 前 16 位 `4db91cb377f7f119`。
- **5×5×5 防御食物清单落地**：从《Eat to Beat Disease》附录 A 解析出 5 系统 562 条映射、
  205 个唯一食物，中文化并标注大陆可得性与平替（`defense-foods.json`，原始英文清单留档
  `defense-foods-appendixA.json`）；配 `five-by-five-plan.md` 操作化摘要。菜谱书第 1-2 章
  表格为整页图片，以原版书附录 A 补齐。
- **文化/时令索引**：chihuo_cidian 144 词条；gusu_shihua 物产 53 条 + 节令 32 条 + 文化词条 307 条。
- **跨书产物重建**：gap-audit.json（核心食材缺口 24，high：芝麻酱/饺子皮/豆浆）；
  proposed-new-recipes.jsonl（15 条准入提案，待人工批准）；duplicate-merge-plan.json
  （20 个同名/同构家族）。原批次记录的 18 条提案 / 16 家族为旧提取结果，以本次重建为准。
- 候选状态机不变：未批准前不得合并进 `data/book-recipes.json`；生产池 1209 道与指纹不受影响。

## 用户指示 2026-09-17（round 65 → yueshi-1.4.2：真实运行问题修复——早餐语义 / 蛋白候选角色 / 商品形态门 / 预算三态）
依据用户《月食真实运行问题改进方案》与 2026-09-16 真实运行证据执行（满足 1.4.1 冻结重开条件：真实缺陷 + 高影响用户反馈）：
- **P0 早餐语义分离（MEAL-SELFCOOK-001）**：问卷示例与追问问法改为"工作日早餐自己做"；
  "自己做"只登记 planned + preparation_location=home + preparation_owner=self 三个事实字段，
  不再附带 quick_self_prepare / 15 分钟上限 / 免开火推断；快手参数需用户明确时间或做法证据，
  缺证据时合并追问"早餐大概几分钟"。
- **P0 蛋白候选角色（ROLE-001）**：新增 `data/protein-candidate-roles.json` 与
  `scripts/common/candidate_roles.py`——staple / rotation / exploratory 三角色，
  槽位 total 5 / minimum_staple 3 / maximum_exploratory 1，`mandatory_aquatic_slot: false`；
  exploratory（蛤蜊贝类/鱿鱼/内脏等）需准入条件方可进核心；核心删除冷却
  （首次 4 周可作替代、8 周内第二次 8 周且不可替代、permanent_dislike 硬排除、
  用户点名可覆盖）。真实运行中"蛤蜊进入 P1–P5 核心候选被用户删除"的缺陷由准入条件拦截。
- **P0 商品形态门（FORM-001）**：ingredient-catalog.json 1.5.0 → 1.6.0，补齐红薯 / 猪里脊
  query_profile（红薯排除叶/加工小吃/油炸/即食；猪里脊排除油炸/裹粉/熟食预制）；
  product-form-dictionary.json 1.3.0 → 1.4.0 新增 raw / root_tuber / frozen_raw / leaf /
  fried / breaded / ready_to_eat / cooked_snack 形态；新增共用形态门
  `scripts/common/product_forms.py`，price_result_validator 增加 P09 拒绝
  （鸡蛋软饼、香炸里脊小方、甘梅地瓜条、地瓜叶均不得为 exact/eligible）；
  叮咚助手 config 同步（FORM_DICTIONARY_VERSION 1.4.0 / CATALOG_RULES_VERSION 1.6.0，
  新增鸡蛋/红薯/猪里脊规则），并重新打包。
- **P1 预选可追溯**：预选候选新增 `score_breakdown`（availability / convenience / package /
  budget / recipe_support / diversity / familiarity / history / final）与
  `selection_decision.top_rejected_candidates`（含 reason_codes）。
- **P1 商品变更日志（CHANGE-001）**：新增 `scripts/common/selection_change_log.py`——
  provider_suggestion → final_selection 逐条记录 selection_change_reason_codes，
  纠错与包装优化分开统计。
- **P1 预算三态（BUDGET-001）**：budget_type = hard_cap / preferred_target / flexible_target
  + allowed_overrun_pct；问卷预算项改 A/B/C 问法；hard_cap 超支未经用户批准时
  shopping_aggregator 以退出码 2 阻止定稿。
- **P1 误报修复**：shopping_aggregator 菜单 CSV 缺 category 时改用 ingredient-catalog.json
  category 回填分区，修复"共 19 种必买"却报"核心食材 0 种"。
- **P2**：README 关键八项第 6 项改为"本周预算类型、预算金额和已有库存"；
  rule-index 新增 MEAL-SELFCOOK-001 / ROLE-001 / FORM-001 / BUDGET-001 / CHANGE-001。

## 用户指示 2026-09-15（yueshi-1.4.1 最终收口：README 列表修正 + 两项措辞优化 + 冻结）
依据用户《月食yueshi-1.4.1最终收口方案》执行（仅文档收口，无功能变更）：
- README「使用前需要提供的信息」按方案定稿：关键八项为有序子列表（1–8），
  本周采购价格方式与其同级、不计入八项；
- 可选优化一：README 维护命令中 `--mode` 说明改为"系统推算的本周安排，
  只能从已冻结 mode_schedule 读取，不接受人工选择"（命令与脚本接口不变）；
- 可选优化二：特殊人群路线"不启用禁食与模式"改为"不启用禁食或周期性内部饮食安排"
  （SKILL 与 safety-rules 同步，安全路由不变）；
- 冻结验证：全量 61 个测试通过、pyflakes 清洁、package_smoke PASS、
  reproducible_build true、同步副本完整性复验通过。
- **yueshi-1.4.1 标记为稳定基线并冻结**：后续修改只响应安全路由错误、流程无法完成、
  计算错误、发布链旁路、叮咚结果误用、正式文件缺陷、可复现测试失败或重复性高影响
  用户反馈；纯文档美化、字段名偏好、指标细分、架构偏好进入 backlog，不启动 Round 65。

## 用户指示 2026-09-15（round 64.1：一致性补丁——文档收口 / 字段边界 / 覆写闭环 / 漏斗闭合 / 发布不变量，仍为 1.4.1 补丁）
依据用户《月食Round64.1完善方案》执行（小补丁定位，不新增业务模式、不改叮咚助手、不扩库）：
- **文档收口**：男性路线删除"两种模式任选"（safety-rules / SKILL 统一为"系统自动路由，
  不要求用户选择内部饮食模式"）；叮咚价格方式启用时点全仓统一为"本次计划的食材预选环节
  明确选择 `use_helper`"（SKILL / README / price-provider-policy）；README 维护命令改名
  "正式生产链组件"并补齐菜谱库构建链 classifier → fingerprint → auditor → release gate；
  SKILL 文件头统一称"加载器元数据头"（保持 yueshi-X.Y.Z 加载器契约）。
- **模式字段边界加固**：`reject_user_mode_fields()` 改为明确拒绝集合
  FORBIDDEN_USER_MODE_FIELDS（精确匹配，禁止模糊匹配 mode 子串），plan_mode /
  meal_plan_mode / preparation_mode / source_mode 等合法字段不受影响。
- **人工覆写闭环**：`pending_reclassify` 迁移为明确状态机（applied_pending_rule_fix /
  resolved_in_classifier / rejected / review_required）；每条覆写绑定 source_recipe_hash /
  taxonomy_bundle_hash / ingredient_catalog_hash；review-overrides.json 纳入 manifest
  artifact_hashes 与 ranker 启动校验；gate 对 review_required 与 stale 一律 blocked，
  分类器输出已与批准值一致时自动转 resolved_in_classifier，净变化为零时自动解除 stale。
- **候选漏斗闭合**：时间分桶改为互斥且穷尽（quick_le_15 / regular_gt_15_le_30 / slow_gt_30 /
  time_unknown，总和闭合 = 1426）；精确重复拆分 input/groups/records/retained +
  canonical_selection_policy；新增 protein_family_coverage 真实约束切片（一人食快手/常规、
  家庭、常见厨具、价格可解析）——lamb 21 道（独立指纹 19、solo 常规 11、价格可解析 0）、
  fish 113 道（指纹 78、solo 常规 53）；扩库决策只依据该切片，不以原始数量判断。
- **发布不变量**：release_pack 打包前生成 `data/release-invariants.json`（技能版本 /
  build_id / 测试汇总 / 11 项不变量，全部来自机器结果）与 `reports/release-summary.md`
  （展示用，不作门禁输入）；任一硬不变量不符即硬失败不标记发布；不变量文件随包发布。
- **回归**：新增 `tests/test_round64_1_consistency_patch.py`；全量 61 个测试通过，
  pyflakes 清洁，package_smoke PASS，reproducible_build true。

## 用户指示 2026-09-15（round 64：模式推算职责纠偏 + 发布链防旁路 + 质量可复现，版本 1.4.1）
依据用户《月食Round64改进完善方案》（基线 yueshi-1.4.0）执行，技能版本升至 **yueshi-1.4.1**：
- **模式纠偏（P0）**：内部饮食模式（酮生物 / 平衡激素）从用户问卷语义中移除——README
  关键八项第 7 项「做法选择」恢复为一锅餐/提前备餐/剩余复用/免开火等烹饪偏好，第 3 项
  「周期情况」明确"用户提供事实、系统推算本周安排"；新增规则 MODE-INPUT-001（用户不得
  直接选择内部模式，`scripts/common/mode_schedule.py` 的 reject_user_mode_fields 拒绝或
  清除用户 payload 中的 mode/mode_schedule 等字段）、MODE-DERIVE-001（系统按周期事实→
  安全筛查→阶段计算→更保守参数推算，nutrition-routing.md）、MODE-FREEZE-001（推算后冻结、
  下游只读、周期事实变化触发重新推算，runtime-rules.md）；三者登记入 references/rule-index.md，
  MODE-001 保留为总规则。
- **文档真实性（P0）**：删除 SKILL.md 末尾重复残句「代替正规治疗的建议。」；front matter
  版本 yueshi-1.4.1（保持加载器契约 yueshi-X.Y.Z）；README 关键八项改为有序子列表；
  叮咚查价时点统一为"本次计划的食材预选环节明确选择"。
- **发布链防旁路（P1）**：`recipe_release_gate.py` 在 release 块写入 artifact_hashes
  （recipe_index / book_recipes / classification / fingerprints / audit_data /
  ingredient_catalog / taxonomy_bundle 的 sha256）；分类器在 recipe-classification.json
  记录 source_hashes（taxonomy bundle + 食材目录），gate 检测 taxonomy_drift /
  ingredient_catalog_drift 即阻断；`recipe_ranker.py` 启动前 verify_release_integrity——
  approved 状态 + build_id + 全部产物内容哈希同时一致才读取生产库，批准后篡改、
  新旧混用、同 build_id 不同内容一律拒绝（release_integrity_failed）。
- **质量可复现（P1）**：`data/audit/human-review.json` 增加 sampling（population_build_id /
  sample_size / strategy=stratified_plus_risk_based / random_seed=63）、分字段准确率
  （dish_category 0.9915 / family 1.0 / protein 0.9915 / overall 0.9825，分母
  correct+incorrect）、随机分层样本（121）与风险样本（3，全部低置信度项）分离、
  review 复核结果六字段；新增 `data/audit/review-overrides.json` 单独记录人工覆写
  （2 条 pending_reclassify：tcop-029 主蛋白、uyenluu-067 一级类型），不覆盖原始自动判断。
- **有效候选覆盖（P2）**：审计报告新增 effective_candidate_coverage 漏斗——总 1576 →
  生产池 1561 → 正餐池 1426 → 精确去重 1426 → ≤15 分钟快手 294 / ≤30 分钟常规 721，
  及各主蛋白族/烹法独立多样性指纹数（lamb 15、fish 83）；完成该评估前不决定扩库方向。
- **回归**：新增 `tests/test_round64_mode_semantics_release.py`（问卷不暴露内部模式 /
  用户模式输入拒绝 / 哈希失配失败关闭 / 手工改状态·篡改菜谱·taxonomy 漂移·同 build_id
  不同哈希全部拒绝 / 抽样可复现 / 文档 lint / 单人·篡改金丝雀）；全量 60 个测试通过，
  pyflakes 清洁。叮咚查价助手本轮无改动。

## 用户指示 2026-09-15（round 63：菜谱库数据治理 + 规则文档重构 + 生产门禁完善，版本 1.4.0）
依据用户《月食Skill改进实施方案》（适用 yueshi 1.3.0）执行，技能版本升至 **yueshi-1.4.0**：
- **A 一级菜谱类型**：新增 `data/taxonomy/dish-categories.json` 等 5 个分类法文件与
  `scripts/recipe_classifier.py`——全部菜谱强制 `dish_category` 十值枚举；仅
  main_dish/staple/soup/side/composite_meal 进正餐候选池，dessert/beverage/
  sauce_or_condiment/snack 不参与正餐多样性。生产覆盖率 100%，无空值/other 兜底。
- **B 蛋白族拆分**：`primary_ingredient_family` 与 `primary_protein_family` /
  `secondary_protein_families` 拆分，附 classification_method/confidence/evidence；
  禁止仅凭名单一关键词定蛋白、禁止以 none/other 掩盖待复核。族覆盖 99.8%、蛋白族覆盖
  100%、严重误标 0、人工抽样 124 条准确率 98.3%（歧义项计入复核不计入分母）。
  同步修正 ingredient-catalog 六处族归属错误（鸡蛋/鸭蛋→egg、全脂牛奶→dairy、
  土豆→root、牛油果→fruit、海带→other_vegetable、鱼露→flavor），目录版本 1.4.0→1.5.0。
- **C 指纹三层拆分**：`scripts/recipe_fingerprint_builder.py` 产出 exact_fingerprint
  （仅数据去重）/ diversity_fingerprint（仅菜单多样性，diversity_checker 经 --fingerprints
  接入）/ semantic_cluster_key（仅审计）；主次烹法拆分；精确重复 0。不可解析记录
  （书籍索引页等 15 条）隔离出生产池并列修复清单。
- **E 验收报告**：`recipe_library_auditor.py` 升级——audit_status（passed /
  passed_with_warnings / failed）+ blocking_issues + warnings + quality_metrics +
  与上一版比较 + 修复清单 CSV + 人工抽样结果（data/audit/human-review.json）。
- **F 发布门禁**：新增 `scripts/recipe_release_gate.py` 为 `library-manifest.json`
  release 块的唯一写入方；阻断→blocked、警告→review_required（可留痕批准）、清洁→approved；
  build_id 三方（classification/fingerprints/manifest）不一致即阻断。`recipe_ranker.py`
  仅读取 release_status=approved 的菜谱库，并按一级类型过滤正餐池。
- **G 规则文档重构**：SKILL.md 保持入口/路由/摘要/门禁定位（146 行 <150），新增
  `references/rule-index.md` 稳定规则 ID 索引（SAFETY-001…OUTPUT-001，ID 只增不改）；
  round60/61 历史轮次标记迁出至本文件；front matter 统一 `version: yueshi-1.4.0`。
- **I README 口径**：价格方式说明统一为"随食材预选一并选择、逐周期重选"；新增用户可见
  状态流程（收集信息→食材预选→生成菜单→等待价格结果（仅叮咚模式）→生成最终文件）；
  关键八项逐项一句话解释；维护命令分四层（正式生产入口/调试工具/只读审计工具/禁止单独
  运行的内部组件）。
- **回归**：新增 `tests/test_round63_taxonomy_gate.py`；全量 59 个测试全部通过。
  门禁指标：dish_category 覆盖 1.0、族覆盖 0.998、蛋白族覆盖 1.0、抽样准确率 0.983、
  跨类簇 0、严重误标 0；release 状态 approved（build_id 2026-09-15-r63）。

## 用户指示 2026-09-14（round 62：菜谱库覆盖审计 + 选择审计契约 + 快手早餐模板库）
依据用户三优先指示（覆盖审计 / 验证书籍是否影响菜单 / 完善早餐结构）：
- **优先一 覆盖审计**：新增 `scripts/recipe_library_auditor.py`——离线审计生产菜谱池
  （recipe-index 367 + book-recipes 1209）：总数 / 可解析数 / 缺来源·烹法·菜系·季节·主要食材族 /
  指纹簇数与高度重复数 / 主蛋白族·烹法·菜系覆盖 / 快手菜·一人食·家庭适用覆盖 / 来源分布 /
  前 10 指纹簇 + 自动缺口判读。启发式口径在脚本 docstring 与报告中明示。首轮结论：菜系与季节
  标签整体缺失（应先补标签而非补书）、羊肉族仅 4 道、330 道（21%）可被指纹簇去重、390 道缺
  食材族标注——缺口明确前不新增综合菜谱书。
- **优先二 选择审计契约**：`selection_audit` 字段统一为规范命名（candidate_count_before_dedup /
  candidate_count_after_dedup / recipe_source_count / selected_recipe_ids / selected_source_ids /
  selected_fingerprints / technique_count / history_repeat_count / diversity_gate_result），新增
  `schemas/selection-audit.schema.json`（十字段必需，未计算必须为 null，不得伪造）；审计只进运行
  记录不进用户文件；来源集中/去重骤减/书籍从未入选/烹法长期单一 → 先修索引标签排序，不补书。
- **优先三 快手早餐模板库**：新增 `data/breakfast-templates.json`（22 个模板、十类全覆盖：无需烹饪 /
  5分钟组装 / 10分钟平底锅 / 可前夜准备 / 可带走 / 乳制品替代 / 鸡蛋替代 / 不同碳水组 / 咸味 /
  温热），每个模板带活跃时间/总时间/工作日适用/可前夜准备/食材克数/营养/替换规则；
  营养值由 `scripts/build_breakfast_templates.py` 从 foods-table 实时计算（未知食材直接失败，
  禁止手填）；全部模板固定 planned + quick_self_prepare、计入营养与采购（B01/B02）；
  runtime-rules.md 早餐轮换节与 SKILL.md 摘要接入模板库。
- 测试：新增 tests/test_round62_recipe_audit_breakfast.py（审计字段完整性、指纹簇生效、
  审计规范字段与 null 约定、模板十类覆盖、营养与 foods-table 重算一致、构建器幂等）；
  test_round60 审计字段探针同步规范命名；清理 recipe_ranker 未用导入。

## 用户指示 2026-09-14（round 61：封版一致性——README 口径 / fatal_reason 枚举 / B 门禁降级 / D01 统一 / 时令条件完整性）
依据用户《v1.3.0 早餐语义、模式一致性、多样性与时令最终改进方案》"继续改进"：
- **P0-1 README 口径**：删除 `--mode keto` / `--keto-days` / `--hormone-days` 旧示例，basket_builder /
  recipe_ranker 示例改为 `--mode-schedule mode_schedule.json`（macros_calculator 模式参数加注
  "取自 mode_schedule"）；菜谱数量不再手写（以 data/library-manifest.json 为准）。
- **P0-2 fatal_reason 枚举**：新增 `mode_schedule_mismatch`（SKILL.md 门禁分类，最终八值枚举）。
- **P0-3 B01/B02 降级为 auto_fix**：B01 遗漏时重跑该餐次采购汇总并同步 shopping_demand_hash；
  B02 无合法依据降级时恢复 planned 并重跑营养与采购校验，仍缺用户信息转 user_input_required；
  两轮自动修复失败统一升级 auto_fix_retry_exhausted；运行记录写 meal_semantic_audit。
- **P1-1 D01 统一**：定稿"正餐主蛋白优先不重复，重复最多 2 次且烹法或主风味必须不同"，废止笼统的
  "同一主食材一周 ≤3 次"（runtime-rules / SKILL / sample-days 同步）；分类豁免（早餐基础食材 /
  调味与基础油不适用；蔬菜相邻正餐避免完全相同组合；批量备餐按用户策略）；diversity_checker
  规则 3 改 D01（>2 次违规，重复须换烹法/味型）；新增 D01–D07 适用范围（≥3 硬门禁 / =2 软约束 /
  =1 不执行）与"多样性不得凌驾"七条件。
- **P1-2 时令条件完整性**：G01 追加时令检查——启用时令优先或输出"当季/时令/正当季"文字时校验
  data/seasonal-produce-cn.json；缺失且用户未强制时令 → 停用"当季"表述并记 seasonal_data_unavailable
  （非 fatal）；用户强制时令 → user_input_required 或 core_rule_file_missing；不得凭月份常识补写；
  S01 升级为 region + month + season_status + source_rule_id 四要素，并明确"--month 传参不等于
  时令规则影响了选择"。
- **P1-3 助手交付口径**：README 标注"当前过渡交付方式：完整文件夹分发"，安装版目标写入助手
  dev/DEVELOPMENT.md，不并列声称两种正式路径。
- **P2**：SKILL 门禁分类补非 fatal 状态码（seasonal_data_unavailable /
  breakfast_procurement_omitted / meal_mode_invalid_downgrade / diversity_gate_failed）及升级路径；
  planning-flow 新增执行审计要求（meal_semantic_audit / mode_consistency_audit 三组件哈希一致 /
  selection_audit / 时令证据，未计算字段记 null 不伪造）。
- 测试：新增 tests/test_round61_freeze_consistency.py（README 废弃参数静态检查、枚举、B 降级、
  D01 行为与旧规则残留否定语境判断、时令条件完整性、助手交付口径、审计字段）；
  test_round60 探针随 B01/B02 级别调整同步。

## 用户指示 2026-09-14（round 60：早餐语义修正 + 模式一致性 M11 + 菜谱多样性与时令证据链）
依据用户《早餐语义、菜谱多样性与时令选材改进方案》与《执行过程记录》"结合执行过程和改进方案，进行改进"：
- **P0-1 早餐语义修正（简单解决 ≠ 不计划、不采购）**：runtime-rules.md 新增「餐次语义映射表」——
  "自己简单解决"默认 planned + preparation_mode=quick_self_prepare（计入营养与采购），仅"只给原则/
  不用安排"类明确表达才允许 guidance_only；新增 preparation_mode / include_in_nutrition /
  include_in_procurement / max_active_minutes / recipe_detail_level 字段语义；questionnaire.md 早餐
  问法改 A–E 五选（直接说"自己简单解决"默认映射 A）；procurement-flow.md 新增采购门禁 B01/B02
  （planned 且 include_in_procurement=true 必须进采购汇总；"简单快手"不是合法降级理由）；
  nutrition-routing.md 明确 planned 快手早餐必须计入营养。
- **P0-2 模式路由修复 + M11 门禁**：新增 scripts/common/mode_schedule.py（fail-closed 加载器，
  mode_summary 与逐日重算不一致即 mode_schedule_mismatch；basket_builder.py / recipe_ranker.py
  新增 --mode-schedule 为唯一模式来源，手写 --keto-days/--hormone-days/--mode 仅作交叉核对，
  冲突即失败关闭）；planning-flow.md 新增步骤 4.5「冻结模式计划」；output-policy.md 新增执行门禁
  M11（fatal: mode_schedule_mismatch）。
- **P0-3 删除反馈四档**：ingredient-preference-schema.json 新增 persistent_reduce（以后少推荐，
  降权不硬排除）与 temporarily_unavailable（这次买不到，只影响本周）；runtime-rules.md 定稿四选项
  与跨周重复惩罚（ingredient_history_4w / recipe_history_8w / protein_family_history_4w：上周出现
  降权、4 周 ≥2 次强降权、本周删除本周禁止恢复、长期避开硬排除）；跨计划频次统计仅供维护端，
  不得混用其他用户偏好；ingredient_preselector.py 实现历史惩罚与 candidate_reason_codes。
- **P1-1 菜谱指纹与集合多样性**：recipe_ranker.py 候选先做 recipe_fingerprint（主蛋白族＋核心蔬菜族
  ＋烹法＋风味＋形态）去重再入选；planning-flow.md 步骤 10 改整周集合优化；新增 D01–D07 硬门禁；
  diversity_checker.py 新增 D04（相邻不得同"快炒+咸鲜"）并与 D01–D07 规则编号对齐。
- **P1-2 时令证据链**：新增 data/seasonal-produce-cn.json（派生自已审核 seasonal-foods.json，
  逐项 source_rule_id 可追溯；region=全国通用，城市级细化须另有审核来源，不得虚构"当季"）；
  basket_builder.py 输出 season_status（peak/in_season/shoulder/unknown）与 season_source_rule_id；
  planning-flow.md 新增 S01–S04 时令门禁与时令优先级顺序。
- **P1-3 选择审计**：recipe_ranker.py 新增 --audit-report 输出 selection_audit
  （candidate_count_total / after_fingerprint_dedup / source_count / technique_count /
  selected_recipe_ids / selected_recipe_source_ids / selected_recipe_fingerprints 等；
  未计算字段记 null，不伪造数值）。
- **数据**：ingredient-catalog.json 全量条目新增 ingredient_family（蛋白类另有 protein_family），
  catalog_version 提升 1.4.0（测试断言同步）。
- 测试：新增 tests/test_round60_breakfast_mode_diversity.py（探针 + 脚本行为：M11 失败关闭、
  指纹去重计数、历史惩罚降权、D04 识别、时令来源可追溯）；test_round52/54/58 目录版本断言
  同步 1.4.0。

## 用户指示 2026-09-11（round 59：v1.3.0 增量——查询库接线 / request_id 规则 / Schema 开放 / 状态转移表 / 字段收敛）
依据用户《月食SKILL-v1.3.0改进方案》"继续改进"：
- **P0-1 查询库接线**：price-provider-policy.md 新增 §9.3「查询项生成规则与字典兜底」——库内食材按
  query_profile 展开；库外食材走全局形态词典（制品/加工形态排除、"免/无/不含/原切"前缀豁免）+
  类别白名单（肉禽蛋/水产/蔬菜放行，熟食/速食/烘焙拒绝）兜底并标注低置信度；
  `data/ingredient-catalog.json` 与 `data/product-form-dictionary.json` 纳入 G01 叮咚追加完整性
  检查（细粒度标识 ingredient_catalog_missing / form_dictionary_missing）；
  dictionary_suggestions 学习闭环定稿（助手只建议，用户确认后回写主库并提升版本）。
- **P0-2 request_id 定稿**：`request_id = {计划起始日期}-{shopping_demand_hash 前 8 位}`（policy §3.1）；
  G13 追加"同日两版菜单哈希不同即拒绝，不串用旧价格结果"。
- **P0-3 Schema 开放**：price-result Schema 根级与 query_result 级 `additionalProperties` 放开
  （definitions 内部仍严格），G13 以"必需字段齐全 + request_id 一致 + 已知字段类型合法"为准，
  不因助手新增未登记字段误拒；契约版本维持 "1.2"。
- **P1-1 状态转移表**：policy 新增 §4.3——六态（pending / use_helper / use_estimate /
  awaiting_price_result / price_result_received / opt_out_after_query）× 事件 → 新状态 × 允许动作 ×
  门禁；两易漏转移（清单交付后中途放弃、助手无法运行 → opt_out_after_query）单列，均不判失败。
- **P1-2 字段收敛**：`dingdong_price_choice` 为唯一写入字段；`dingdong_helper_opt_in` 降级为派生
  只读（policy §4.1 / runtime-rules Provider 路由 / SKILL G01·G12 / output-policy G12 / planning-flow
  步骤 8 同步措辞）。
- **P1-3 README**：新增「叮咚查价助手使用说明」（整个文件夹拷贝 / 浏览器前提 / 四步操作 / 只读承诺 /
  价格以结算页为准）；顶部加"适用 SKILL 版本：1.3.0"。
- **P1-4**：SKILL Provider 摘要加价格失败回退链一行
  （direct_public_price → category_estimate → historical_estimate → 替换同功能食材须回菜单营养层）。
- **P2**：H04 增补"未来待确认事项"例子；README 家庭版摘要页最多并排 3 名成员；维护者节加
  "先读 CHANGELOG；未选 A 时价格契约文件缺失不影响估价流程"；output-policy 显示转换新增价格失败
  用户话术「叮咚没查到价，已按当地参考价估算」。
- 测试：新增 tests/test_round59_v130_incremental.py（探针 40+）；test_round53 / test_round57
  探针随措辞同步。

## 用户指示 2026-09-11（round 58：逐周必显选答 + 封面四卡恢复 + 营养目标预编译 + 助手窗口改造）
依据用户《新周查价选答、助手窗口、PDF封面与生成性能改进方案》"继续改进"：
- **P0-1 逐周选答语义修正（核心：逐周选答 ≠ 每周默认否）**：`dingdong_price_choice`
  状态机 pending/use_helper/use_estimate 落地——新计划初始 pending、不跨周继承
  （"是"与"否"都不沿用）、选择只对本次 request_id 有效；pending 时可展示食材预选
  但不进入正式生成链路；价格方式二选一固定在食材预选清单末尾同轮收集，不单独追问；
  用户首轮已明确则直接记录、预选时仅回显"已选择"；删除"默认否、不追问"与
  "本周默认不生成……需要的话回复"旧话术（runtime-rules 仅以禁止形式保留该句作防复现
  说明）。SKILL/questionnaire/runtime-rules/planning-flow/README 五处口径统一；
  use_helper 等价 dingdong_helper_opt_in=yes（G12/G13 等既有门禁不变）。
- **P0-3 营养目标预编译**：新增 `scripts/daily_target_compiler.py`——第一次营养计算前
  生成 `daily_targets.json`（7 天 × 模式/阶段/净碳水上下限/蛋白四字段/脂肪供能/热量
  安全线/取整容差），approved 参数全部在第 0 步解析（含 hormone_net_carb_weightloss_g=100），
  缺字段即失败（--check 退出码 3）不进入微调；执行语义定稿：第 1 轮全周联合求解、
  第 2 轮只修复失败日期、最终复核只读不计轮次不改克数；菜单装配后先做热量粗筛；
  任何菜单克数变化强制标记受影响日期并局部重算、更新 nutrition_snapshot_hash，
  采购剩余安排不得写成菜单加量。nutrition-routing 与 planning-flow（新增步骤 11.5）同步。
- **P0-4 CSS 正式合入**：print.css/screen.css 的 .ingredient-name 改为
  `white-space: normal; overflow-wrap: anywhere; word-break: break-word`
  （不再每次临时打补丁，不用 break-all）；采购表整行 `break-inside: avoid`、
  分类标题与首行绑定、表头跨页重复；output-policy 新增"分页修复不得改业务文本"硬规则。
- **P0-5 封面恢复四张等宽摘要卡**：plan.stats 契约固定为 天数/模式/进食窗口/预算
  （render_cover 硬校验，非四卡即 SystemExit）；阶段变化写入副标题摘要行；模式卡主值
  最多一行，比例放辅助行；家庭模式同样四卡。output-schema/visual-spec/output-policy
  三处契约同步；六个旧测试夹具更新为四卡。
- **P1-7 食材规则回写通用库**：ingredient-catalog.json → 1.3.0（鸡腿拒绝腊制/腌制
  〔cured〕、三文鱼拒绝刺身〔sashimi，调味附包走 conditional_accept〕、玉米拒绝
  玉米须茶/茶饮品、芹菜拒绝芹菜牛肉丝等组合菜，query_profile 新增可选
  hard_excluded_terms）；product-form-dictionary.json → 1.3.0（新增 cured/sashimi
  限制性形态）。
- **P1-8/P2**：查价清单精简结构（ingredient_id + 需求 + required_form +
  catalog_version，规则由助手本地词典展开，override 优先；price-query Schema 增补
  required_form 并写入精简说明，契约版本保持 1.2 向后兼容）；price-provider-policy
  新增 §9.1 精简清单与词典展开、§9.2 助手端导出门禁 E01–E06 与用户提示分层、
  月食侧分阶段耗时记录字段（profile_load_ms … pdf_layout_retry_count 与
  nutrition_adjustment_rounds ≤2 / menu_days_recomputed / candidate_manual_review_count
  异常指标 / pdf_render_count=1）；render_pdf 注释定稿"禁止改业务文本修分页"。
- 测试：新增 `tests/test_round58_weekly_choice_and_perf.py`（6 项）；round53/54、
  pdf_layout、round25、round26、round31、render_gates、visual 快照等既有测试按
  新口径更新针脚/夹具。全量测试通过；改动脚本 pyflakes 零告警。
- **助手侧同步变更**（yueshi-dingdong-helper，需重新生成安装包）：
  完成页改为"摘要 + 查看全部结果▾ 可滚动明细 + 底部固定操作栏"（保存按钮始终可见，
  失败项可点击查看原因，支持滚轮与 PageUp/PageDown/Home/End）；窗口可调大小并记忆
  上次尺寸（不小于 600×440）；新增 export_selfcheck（E01–E05 自检，E06 完成页展示
  "结果已通过格式校验"，技术字段只在诊断导出中出现）；config.py 同步形态词典 1.3.0
  与目录规则快照 CATALOG_RULES 1.3.0（腊制/刺身/玉米茶/组合菜剔除）；load_query 支持
  精简清单按 ingredient_id 展开、override 优先；新增 dev/test_round58_gui_and_rules.py。

## 用户指示 2026-09-11（round 57：v1.3.0 封版前一致性收口——两项 P0 + 四项 P1 + 维护项）
依据用户《月食_v1.3.0当前文件复核与改进建议》"继续改进"：
- **P0-1 营养管线冻结时机**：SKILL.md 营养管线摘要改为分支口径——最终营养复核后只形成
  稳定快照（menu/nutrition/shopping_demand 三哈希），**未启用查价时**随后冻结最终
  plan.json 并渲染；**启用叮咚查价时**先生成唯一正式查价清单并暂停，收到通过 G13 的
  价格结果、完成价格/包装/预算更新后**才冻结最终 plan.json**，查价前任何阶段不得冻结。
  planning-flow 步骤 12 同步注明"只形成稳定快照，不在本步冻结"。
- **P0-2 完整性门禁扩展**：规则文件完整性门禁新增"启用叮咚查价时的追加完整性检查"
  （dingdong_helper_opt_in=yes 才执行）：price-provider-policy.md、price-query /
  price-result Schema、price_result_migrator.py 缺一不可，缺失即阻止查价链路；错误码
  统一映射 core_rule_file_missing（细粒度标识 price_provider_contract_missing 等仅进
  内部日志），不扩大 fatal 枚举；允许用户明确切换估价路径但不得伪装成叮咚直采价；
  未启用叮咚时价格契约缺失不影响普通估价流程。
- **P1-3 Provider 摘要缩短**：SKILL.md Provider 摘要缩短为指针版（保留启用条件、快照、
  唯一正式清单、G12/G13 指针、冻结时机、商品名边界、PDF 不展示、默认否口径）；
  权限边界/地址边界/回传方式/失败回退等完整表述落在 price-provider-policy.md。
  round46/49 测试针脚同步改指 policy 文件。
- **P1-4 README 重排**：章节改为 这是什么 → 使用前需要提供的信息（关键八项+叮咚选答）→
  基本流程（单人15步/家庭13步）→ 使用叮咚查价时 → 各格式差异 → 给维护者/其他 AI →
  目录 → 安全声明；叮咚与格式说明从安全声明下迁出并升为二级标题。
- **P1-5 PDF=hidden 固定**：output-policy 组件黑名单条目残留的旧口径"PDF 按版面评估选
  full/summary/hidden"改为"固定不展示（固定规则而非用户选项）"；全库复查无
  auto/full/summary 试排功能残留（仅存禁止性说明）。
- **P1-6 P09 价格元数据一致性门禁**：price-provider-policy §7 扩为 P01–P09——结果根级
  provider / schema_version / request_id 必须与 price_snapshot_meta 完全一致，不一致即
  拒绝渲染、不自动择值、要求重新迁移或导出；result_hash 必须等于规范化结果文件 SHA-256
  且预算卡/采购表/价格说明引用同一 price_result_hash。SKILL 文件地图、output-policy
  汇总条、runtime-rules 路由段、maintenance-map 同步 P01–P09（validator 执行组件保持
  P01–P08 文件级校验，P09 在合并/渲染侧执行）。
- **P2-7 术语门禁扩充**：禁用词追加 Round55/56 内部字段（awaiting_price_result /
  price_result_received / opt_out_after_query / dingdong_helper_opt_in /
  menu_snapshot_hash / nutrition_snapshot_hash / shopping_demand_hash /
  price_result_hash / migration_log / provider_product_name /
  shopping_meal_usage_map），并新增显示转换（等待叮咚价格结果 / 已读取价格结果 /
  已改用参考价格估算 / 文件兼容处理记录）；render_plan.py BANNED_TITLE_TERMS 同步。
- **P2-8 README 依赖表述核对**：全脚本 import 复核均为标准库（jsonschema 为可选回退、
  PDF 渲染调用本机 Chromium 二进制而非 Python 包），表述保留"纯 Python 标准库"并补充
  Chromium 说明，避免绝对化冲突。
- 测试：新增 `tests/test_round57_consistency.py`（7 项：冻结时机/完整性门禁/摘要缩短与
  指针完整性/README 结构/PDF 固定无残留/P09/术语扩充）；round53 前置门禁针脚回补。
  全量测试通过；改动脚本 pyflakes 零告警。
- 助手侧无变更，zip 不更新，无需重新生成安装包。

## 用户指示 2026-09-01（round 56 定稿：PDF 固定移除「对应菜单及用量」映射模块，SKILL/README 口径收口）
依据用户《Round56最终改进方案_基于当前SKILL与README》"继续改进"——在 round56 试验基础上
**PDF 由"auto/full/summary 试排"定稿为固定 hidden**，其余格式维持完整展示：
- **渲染器**：`render_plan.py` 删除 PDF 的 auto/full/summary 分支与版面评估日志
  （"[meal_usage_map] pdf=auto → …"等）；`_meal_map_mode` 对 pdf 只接受 hidden（缺省即
  hidden），配置为 full/summary/auto/非法值即渲染失败
  （SystemExit("meal_usage_map 配置错误：PDF 固定 hidden…")），无降级路径。
  HTML=可折叠完整版、Word=完整附录、Markdown=分组列表不变；plan.json 数据层始终完整保留
  meal_allocation / shopping_meal_usage_map。
- **样式清理**：print.css 移除全部映射表打印规则与 menu-map 相关引用，仅留定稿注释；
  screen.css 保留折叠交互样式（供 HTML 使用）。
- **SKILL.md 收口**：固定执行顺序 15 步的结尾改为分支表述（未启用叮咚→按价格三层直接完成
  并生成最终文件；启用叮咚→唯一正式查价清单→暂停 awaiting_price_result→G13 校验通过后
  更新价格/包装/预算→再生成最终采购清单与最终文件），并明确"价格结果回传前只能形成内部
  采购需求，不能称为最终采购清单"；Provider 摘要区分"查价前只形成稳定快照、不冻结最终
  plan.json"与"收到合规结果后才冻结最终 plan.json"；G11 追加 meal_usage_map 分格式检查项
  （HTML 可折叠无截断 / Word 附录可跨页 / Markdown 分组无超宽表格 / PDF 不出现章节、表头、
  残留行与空白占位页 / 全格式不读 provider_product_name）；G12/G13 完整定义保持在
  「入口级最终门禁」清单。
- **文档同步**：output-policy.md 差异化策略节定稿——"PDF 固定 hidden，不再支持
  auto/full/summary 试排、版面评估、模式降级与映射表评估日志"，配置固定，禁止
  "见网页版展开"字样；M06 保持差异化口径；visual-spec.md / planning-flow.md 同步
  "PDF 固定不展示"；README.md 同步（关键八项+选答叮咚、单人 15 步/家庭 13 步入口、
  两阶段查价与格式差异化说明）。
- 测试：`tests/test_round56_format_differential.py` 的 PDF 用例翻转为定稿口径
  （缺省/显式 hidden 通过且无映射标记；full/summary/auto/非法值均 rc≠0 且报"PDF 固定
  hidden"；print.css 不含 menu-map）；round55 测试的 print.css 断言同步翻转。全量测试
  通过；改动文件 pyflakes 零告警。
- 助手侧无变更，zip 不更新，无需重新生成安装包。

## 用户指示 2026-09-01（round 56：「对应菜单及用量」改为格式差异化展示，PDF 完整展开试验）
依据用户《Round55后续修改意见_格式差异化版》"继续修改，pdf版先把对应菜单及用量展开试试看，
其余格式保留此项"——**撤销 round55 修正五的"全格式删除"，其余四项收口（唯一正式清单/G12/G13/
商品名边界/性能规则）全部保留不回退**：
- **渲染器恢复映射组件**（render_plan.py `render_meal_usage_map`）：HTML=可折叠完整版
  （details，无截断、无"见网页版展开"）；PDF=完整展开的可见表格（`.menu-map-full`，
  跨页重复表头，8.5pt 不下压）；Markdown=按食材分组列表（`### 猪里脊，共 240g` + 逐餐
  bullet）；Word 经 Markdown 链路继承分组展示。三格式均不读取 provider_product_name。
- **PDF 三模式与 auto 评估**：新增 `output_options.meal_usage_map.{html,docx,markdown,pdf}`
  ∈ full/summary/hidden/auto；缺省 html/docx/markdown=full、pdf=auto。试验期 auto 按 full
  渲染并输出评估日志（"[meal_usage_map] pdf=auto → 本轮按 full 渲染"）；summary 只列
  食材/总需求/用于 N 餐；hidden 整模块移除；非法取值即渲染失败。模式降级只重跑渲染层。
  已对 golden 样例实测：full 模式 PDF 共 3 页、映射表完整展开、版面正常。
- **文档同步**：output-policy.md 新增「对应菜单及用量的格式差异化策略」专节（含数据层始终
  保留、四格式口径、auto 评估顺序与降级约束、禁止"见网页版展开"）；M06 改为差异化口径；
  visual-spec.md 恢复折叠交互说明；planning-flow 步骤 15 加差异化渲染说明；runtime-rules
  补固定执行顺序分支（防执行器跳过暂停直落最终渲染）。
- **入口摘要分工（方案 §七）**：SKILL.md Provider 摘要缩短为指针版；**G12/G13 完整定义唯一
  保留在「入口级最终门禁」清单**（G12/G13 正式列入 G01–G11 之后），摘要与门禁不再双版本。
- **版本升级**：skill_version → `yueshi-1.3.0`；golden 家庭样例 plan_meta 版本同步 1.3.0；
  price_data_version 保持 "1.2"（价格 Schema 未变，不随 skill 升级强制升级）。
- 测试：新增 `tests/test_round56_format_differential.py`（6 项：策略文档/版本/HTML 折叠完整版
  与商品名唯一出现/PDF 四模式与 auto 日志/Markdown 分组/门禁不回退）；round33/54/55 相关断言
  按差异化口径更新。全量 53 项测试通过；改动文件 pyflakes 零告警。
- 助手侧无变更，zip 不更新。

## 用户指示 2026-09-01（round 55：叮咚查价两阶段流程最终修订——五项收口）
依据用户《月食_叮咚查价两阶段流程_最终修订方案》"继续改进"：
- **修正一（统一生成时机）**：全流程只有一份正式查价清单——预选阶段只登记
  `dingdong_helper_opt_in: yes`，**不再生成查价清单草稿**；正式清单在七天菜单草案、做法、
  营养校验与最终新购需求汇总完成后生成（最终 new_purchase 克数、最终 ingredient_id、
  request_id），交付即暂停。questionnaire / runtime-rules / SKILL / planning-flow /
  price-provider-policy 五处口径全部统一，删除"预选锁定后出草稿"旧表述。
- **修正二（G12 等待价格结果门禁）**：定名入口级最终门禁（user_input_required，非 fatal）——
  awaiting_price_result 状态禁止生成 PDF/Word/最终食谱/最终采购清单，只交付清单与操作提示；
  `render_output.py` 报错口径更新为 G12/M10；opt_out_after_query 允许估价生成但必须注明估价口径。
- **修正三（G13 价格结果格式门禁）**：根级 schema_version/provider/request_id 齐备 +
  request_id 与本次清单一致；五分支处理（通过→候选筛选；可识别旧版→迁移器补齐并重新校验；
  无法识别→重新导出；request_id 不匹配→拒绝；看似完整但校验不通过→禁止人工静默绕过）。
  `price_result_migrator.py` 重写：migration_log 定稿字段（source_schema_version /
  target_schema_version / fields_added / migrator_version / revalidation_passed / migrated_at）；
  provider 仅在来源可唯一确认时补齐（delivery_context_confirmed_by_user → dingdong_web）；
  schema_version 只按已知旧结构映射；迁移后经 price-result.schema.json 重新校验
  （schema 根级新增 migration_log 可选字段）；日志不进入用户 PDF。
  新增哈希同源约束：最终预算、采购表、价格说明引用同一 price_result_hash。
- **修正四（商品名边界）**：output-policy 明确 provider_product_name 仅允许 shopping_items 与
  price_snapshot；七天菜单/菜名/逐餐用量/做法/复热说明均不得含商品名；
  购买备注与剩余去向分开（"附调味包可不用"不得写入剩余去向）；
  `check_provider_name_leak` 值级门禁同步挂到 render_markdown.py / render_docx.py（全格式生效）；
  采购表列顺序按方案定稿为 食材/需要量/建议购买规格/参考价/购买备注/替代/剩余去向；
  嵌套括号转逗号（"（叮咚：新鲜猪大里脊，去筋膜）"）；Markdown 采购表补齐购买备注列与叮咚注记。
- **修正五（映射表全格式移除）**：menu-map「对应菜单及用量」从 HTML/PDF/Word/Markdown
  **全部渲染格式**移除（round54 仅 PDF 隐藏、网页版保留——本轮收口为全移除）；
  render_plan.py / render_markdown.py 删除生成代码，print.css / screen.css 清理全部相关规则；
  meal_allocation 仅保留在 plan.json 内部供校验。
- **性能规则（§七）**：planning-flow 步骤 15 增加 shopping_demand_hash（与 menu/nutrition 哈希
  三件套）；三哈希匹配只跑价格校验/候选筛选/包装/预算/渲染；普通商品切换、促销价变化、
  包装取整不触发菜单重算；仅 ingredient_id 替换才局部重算对应餐次与当天营养；
  最终文件只渲染一次，渲染失败只重跑渲染层。
- 测试：新增 `tests/test_round55_final_revision.py`（7 项验收：唯一清单生成点/G12 拦截/
  G13 字段与迁移日志/映射表全格式移除/列顺序与括号规范化/快照哈希/商品名复热说明门禁）；
  round33 menu-map 断言改为全格式缺席断言；round54 迁移器断言更新为 G13 字段；
  round53 问卷/规则断言同步新口径；修复 print.css 注释中 "plan.json" 字样被内联进 HTML
  触发 golden 禁语的问题。全量 52 项测试通过；改动文件 pyflakes 零告警。
- 助手侧无代码变更（round54 已满足"保存前回读校验、缺根级字段禁止导出"），zip 不更新。

## 用户指示 2026-09-01（round 54：两阶段查价流程 + 校验强化 + 采购表排版 + 候选双重门禁）
依据用户两份改进方案（《问卷流程与PDF采购清单改进方案》《两阶段流程_校验与候选筛选整合方案》）"继续改进，优化流程"：
- **两阶段流程**：`price_workflow_state` 状态枚举（disabled/awaiting_basket_confirmation/query_ready/
  awaiting_price_result/price_result_received/final_plan_ready）写入 runtime-rules.md（含产物矩阵）；
  查价清单交付即停在 awaiting_price_result，只交付清单与操作指引，**禁止同时输出最终食谱/PDF**；
  新增 `opt_out_after_query` 分支（用户查价前放弃 → 回退链降级直接出最终版并标注）。
  SKILL.md / planning-flow.md（步骤 13 暂停点、步骤 15 恢复）/ price-provider-policy.md §4.1 同步。
- **快照哈希**：清单交付时记录 `menu_snapshot_hash` / `nutrition_snapshot_hash`；结果回传后比对——
  未变只做价格层局部重算（13.5→15），已变回对应步骤重算（planning-flow.md 步骤 15）。
- **渲染门禁 M01–M10**（output-policy.md）：M10 为 awaiting_price_result 渲染禁令，执行于
  `scripts/render_output.py` 入口（命中即停止并报 price_result_pending）；
  M04 provider_product_name 防泄漏、M05 采购表 7 列、M06 menu-map 不入 PDF。
- **PDF 采购清单改版**（render_plan.py + print.css）：7 列结构（食材/需要量/建议购买规格/参考价/替代/
  购买备注/剩余去向）；食材列双行显示——主行标准名 + 次行小字灰"（叮咚：实际商品名）"
  （`_normalize_provider_name` 防嵌套括号）；**删除 PDF「对应菜单及用量」映射表**（menu-map 改网页版
  专属、完整列出无截断、无"见网页版展开"提示），同步清理 print.css/screen.css 陈旧规则与
  visual-spec.md/output-policy.md 表述。
- **provider_product_name 防泄漏硬门禁**：`check_provider_name_leak` 字段级 + 值级双检查，
  商品名出现在 days/recipes/meals/menu 任一层即渲染失败（M04）。
- **结果校验强化**（price-provider-policy.md §4.2）：缺 schema_version/provider/request_id 即
  `price_result_invalid`，禁止人工放行；旧版结果只允许 `scripts/price_result_migrator.py`（新增）
  迁移且必须写 `migration_log`（from/to/migrated_at/changes）。
- **助手侧双重候选门禁**（v1.2.0 词典）：新增 shell_egg/pancake/pastry/cooked_egg/salted_egg 形态
  （鸡蛋软饼/卤蛋/皮蛋等不再能替代带壳鲜蛋）；新增 conditional_accept 检测（附/赠/含/送/配 +
  调味包/酱料包/料包/酱汁包/蘸料），本体合格附独立调味包的商品接受并写 `purchase_note`
  （如"附独立调味包，可不用"），渲染进采购表购买备注列。
- **导出契约修复**：exclude_defaults 瘦身会误裁取默认值的 schema_version/provider——save_result
  回读前显式补回三个根级必填字段，保证月食侧"缺即 invalid"规则下助手导出恒有效；
  GUI 完成页新增"结果文件已通过格式校验"提示。
- 问卷 Q9 改 A/B 格式（A. 是，生成叮咚查价清单…/B. 否，按所在地参考价格估算，不填默认 B）。
- Schema 同步：price-result.schema.json 候选与建议购买新增 conditional_accept/purchase_note；
  ingredient-catalog 1.2.0（鸡蛋 query_profile：allowed_forms=shell_egg/fresh/frozen，
  excluded_states 追加蛋类加工形态）；product-form-dictionary 主库 1.2.0（含 conditional_accept 规则块）。
- 测试：新增 `tests/test_round54_two_stage.py`（10 项：文档口径/M10 拦截/迁移器/Schema 目录同步/
  7 列双行渲染/泄漏门禁）；round33 menu-map 断言按新规范重写；round52 版本断言升 1.2.0；
  round28 周期断言改为动态日期（修复真实日期推进导致的漂移）；round53 问卷断言同步 A/B 口径。
  全量 51 项测试通过；改动文件 pyflakes 零告警（顺带清理 render_cover 遗留未用变量）。

## 用户指示 2026-08-28（round 53：问卷新增叮咚查价选答项，选"是"才生成查价清单）
依据用户指示「问卷中增加是否主要通过叮咚买菜采购本周食材，并希望使用月食叮咚查价助手
查询商品规格和当前页面价格，以规划本周采购预算；选是之后才会在食材预选环节生成查价清单」：
- `references/questionnaire.md` 问卷模板新增选答第 9 行「叮咚查价」（是/否，不填默认否）；
  明确只有选"是"才在食材预选环节生成「月食-查价清单.json」，未选全流程不生成、不出现助手引导；
  用户后续说"用叮咚查价"可补开。
- `references/runtime-rules.md` 增加选答字段 `dingdong_helper_opt_in`（默认否、不追问）
  与生成时机口径（预选锁定出草稿、步骤 13 按最终 new_purchase 定稿）；外部价格 Provider
  路由增加前置门禁（未选择时跳过 dingdong_web_direct）。
- `SKILL.md` 关键八项说明与 Provider 摘要同步前置门禁。
- `workflows/planning-flow.md` 步骤 8（预选锁定生成查价清单草稿）与步骤 13（定稿交付）同步。
- `references/price-provider-policy.md` §4.1 增加前置门禁段。
- 新增 tests/test_round53_dingdong_optin.py；既有门禁回归（填写区仍无"主要购买方式"）。

## 用户指示 2026-08-28（round 52：通用食材库与匹配质量分层，配套 helper v2.0）
依据《月食叮咚查价助手_通用食材名称库与候选匹配改进方案.docx》与《月食叮咚查价助手_命名统一与查价质量改进方案.docx》：
- 新增 `data/product-form-dictionary.json`（全局形态与加工状态词典主库，form_dictionary_version=1.1.0；
  含否定前缀、restrictive 标记与判定规则）；`data/ingredient-catalog.json` 增加 `catalog_version=1.1.0`
  并为上海青/鸡腿/鸡蛋增加 `query_profile`（exact_terms/aliases/broad_terms/allowed_forms/替代权限集中维护）。
- `schemas/price-query.schema.json` 增补可选 `exact_terms` / `broad_terms` /
  `category_substitution_allowed` 与批次级 `catalog_version` / `form_dictionary_version`。
- `schemas/price-result.schema.json` 增补候选 `match_quality` / `product_form` / `form_match`，
  单项 `substitution_notice` / `dictionary_suggestions`，建议购买 `total_count_text` / `package_text` /
  `match_quality`，批次 `catalog_version` / `form_dictionary_version`；结果瘦身——候选 `observed_at`
  与 `data_source` 改为可省略（统一用批次 completed_at，缺省即接口来源）。
- `references/price-provider-policy.md` 头部同步增补说明。契约版本维持 "1.2"（向后兼容可选字段）。
- 新增 tests/test_round52_rule_matrix.py。
- 助手侧（不进本包）：用户可见名称统一为「月食叮咚查价助手」（删除"便携版"）；匹配质量分层
  exact/alias/category_fallback（宽泛同类不得冒充精确命中，建议为同类时必有 substitution_notice）；
  形态词典扩充（cut_pieces/filled/ball/patty/pie/roll/whole_leaf/fresh/frozen），allowed_forms
  正向硬门禁（鸡腿块 form_not_allowed 被拒）；suggested_purchase 增加 total_count_text/package_text；
  诊断计数修正（search_response_count 改为实时接口响应计数、cache_hit_count/recovered_record_count
  分列、sku_record_count 更名 json_node_examined_count）；price_changes 增加 change_reason
  （removed 区分规则过滤/未选入/不可售，不再误称下架）；dictionary_suggestions 只建议不回写；
  结果瘦身（省略 product_url/observed_at/空字段与重复元数据）。

## 用户指示 2026-08-28（round 51：形态约束与结果增强，配套 helper v1.9）
依据《月食与叮咚查价助手_构建入口回退及后续改进方案.docx》§三：
- `schemas/price-query.schema.json` 增补可选 `allowed_forms` / `excluded_forms`
  （菜谱做法形态约束：整腿需求不被肉丁替代；排除形态命中即拒）。
- `schemas/price-result.schema.json` 候选增补可选 `count_text`（枚数/件数原文）
  与 `match_reason`（相关性命中依据，供类别审计）。
- `references/price-provider-policy.md` 同步。契约版本维持 "1.2"（向后兼容可选字段）。
- 助手侧（不进本包）：TargetClosedError 收尾修复（goto 前 is_closed 检查、监听器先移除、
  结果保存后的关闭错误不再写 last-error）；VBS 入口废弃回退维护者 BAT；诊断计数改名
  search_response_count / sku_record_count；解析前按 product_id 即时去重。

## 用户指示 2026-08-27（round 50：价格结果契约 1.2 可选字段增补，配套 helper v1.7）
依据《月食叮咚查价助手优化与瘦身方案（最终版）》§七：
- `schemas/price-result.schema.json` 增补三个可选字段（向后兼容，price_data_version 维持 "1.2"）：
  候选 `unit_price_yuan_per_100g`（元/100g）；单项 `suggested_purchase`
  （满足 required_grams 的最低总价组合）；批次 `price_changes`（同 request_id 重查的价格差异 down/up/new/removed）。
- `references/price-provider-policy.md` 头部增补字段说明。
- 助手侧（不进本包）：浏览器检测补 Edge 每用户路径与 PATH 兜底；排除词否定前缀（免/无/不含/未/去）不误伤；
  诊断 dropped 去重 + recovered 标记；TargetClosedError 人话提示；venv 与运行数据迁至 %LOCALAPPDATA%；
  成品便携版输出到项目根第一层；界面拖放区卡片化。

## 用户指示 2026-08-26（round 49：回传链路与结果缺失路由 + 助手发布修复适配）
依据《月食叮咚查价助手_发布失败问题与修改意见.docx》（§七 Skill 改动；配套助手 v1.3.1 发布修复）：
- **输入回传说明（SKILL.md Provider 摘要）**：月食生成 price-query.json → 用户本机查价 → 用户把 price-result.json 上传回对话；两侧没有自动上传通道。
- **Provider 结果缺失路由（policy 新增 §4.1）**：用户未上传有效 price-result.json 时不得声称已取得叮咚直采价；未强制实时价按回退链降级并如实标注 price_basis；强制实时价返回 user_input_required；价格失败只回退价格层，不重跑食材预选/菜单装配/营养全流程。
- **SKILL.md 摘要同步契约 1.2**：Provider 返回字段改为"商品候选、规格、页面价格、可售状态、用户确认状态与查询时间"，明确不读取、不返回具体收货地址。
- 新增 tests/test_round49_handoff_routing.py。
- 助手侧（不进本包）：ASCII 文件名与批处理、inspect 代码层隔离（YUESHI_DEV）、任意 JSON 拖入/选择载入、结果写到清单旁、README/DEVELOPMENT 拆分。

## 用户指示 2026-08-26（round 48：价格数据契约 1.2 · 放弃地址读取 + 正式/诊断分离 + 效率门禁）
依据《月食叮咚查价助手_普通用户简易化与菜谱效率改进方案.docx》（普通用户简易化定稿；配套助手 v1.3）；**版本 yueshi-1.2.1**（契约 1.2 补丁发布，frontmatter 与 golden 样例同步）：
- **正式放弃地址读取（P0）**：price-result Schema 删除 delivery_area / delivery_area_label / address_confirmed_by_user 与状态枚举 address_unconfirmed；新增批次级 `delivery_context_confirmed_by_user`（用户已在叮咚网页确认当前配送会话）；price-query 删除 delivery_area_expected；policy §5 条件 6 改为配送会话确认，§6.1 地址证据分级整节删除；P02 违例改为 P02_DELIVERY_CONTEXT_UNCONFIRMED。
- **正式结果与诊断分离（P0）**：候选删除 raw_field_names / image_url；分阶段计数、接口原始字段名、被剔除候选由 Provider 写入本机 logs/price-diagnostics.json，不进正式结果；正式结果只保留月食采购字段（体积明显缩小）。
- **效率门禁（P0）**：主词取得 ≥3 个合格候选即停止别名搜索；候选按 product_id 去重（policy §5.1 / §9）。
- **抓价失败不拖累主链路（P1）**：policy §3 明确价格失败一律按回退链降级，包装与预算最多一次轻量回退，不得回到问卷或完整流程。
- **执行组件对齐**：validator PRICE_DATA_VERSION="1.2"、P02 改读 delivery_context_confirmed_by_user、报告附该字段；router 的 DIRECT_PRICE_REQUIRED_FIELDS 去掉 delivery_area_label，snapshot meta 改为 delivery_context_confirmed_by_user。
- golden 样例迁移契约 1.2（精简候选 + 配送会话确认字段）；新增 tests/test_round48_provider_contract.py；round47 测试中地址证据分级断言按 1.2 契约改写。

## 用户指示 2026-08-26（round 47：价格数据契约 1.1 · 地址证据分级 + 查询追溯 + eligible SKU 门槛）
依据《月食叮咚查价助手_v1.2改进方案.docx》（RC-5 Skill 契约修改；配套助手 v1.2）；**版本正式化 yueshi-1.2.0**（round46 rc 转正，frontmatter 与 golden 样例 plan_meta 同步切换）：
- **契约版本 price_data_version "1.0" → "1.1"**：`schemas/price-result.schema.json` 的 schema_version 切 const "1.1"；新增顶层可选块 `delivery_area`（label / source / verified / station_id / observed_at）；query_result 新增 `attempted_queries` / `matched_query` / `match_strategy` / `diagnostics`，status 枚举扩展 search_empty / candidates_filtered / candidates_unpriced / candidates_unavailable；product_candidate 新增 `matched_query` / `eligible_for_purchase`。`schemas/price-query.schema.json` 新增 `search_terms`（≤3）/ `positive_terms` / `hard_excluded_terms`。
- **地址证据分级（policy §6.1）**：delivery_area.source 五枚举（network_response / page_dom / browser_storage / user_manual / unresolved）；verified=true 仅限受信三来源 + 用户显式确认，user_manual / unresolved 永远 false；`price_snapshot_meta` 新增 delivery_area_source / delivery_area_verified 字段；direct_public_price 条件 6 收紧为「已确认且已验证的配送区域」。
- **查询词分层召回与追溯（policy §5.1）**：每食材 search_terms ≤3 逐层尝试、命中即停；结果必须记录 attempted_queries / matched_query / match_strategy 与分阶段诊断计数（raw/relevant/excluded/unpriced/unavailable）；无结果状态细分四类；性能硬边界由"1 主词 + 1 别名"调整为"≤3 查询词 + 提前停止"。
- **eligible SKU 门槛（policy §5/§7 P06）**：正式采购候选须 eligible_for_purchase=true（product_id + 名称 + 价格 + 可换算规格 + availability=="available" 五要素齐备）；活动价必须记入 promotion_price_yuan 且 price_type=promotion，不得只写 listed_price_yuan 丢失活动标签。
- **执行组件对齐**：`price_result_validator.py` PRICE_DATA_VERSION="1.1"；P02 改读批次级 delivery_area（label 非空 + verified=true，违例 P02_DELIVERY_AREA_UNVERIFIED）；P06 新增 P06_NOT_ELIGIBLE_SKU；P07 优先对照 positive_terms / hard_excluded_terms（兼容旧 aliases / excluded_terms）；校验报告附 delivery_area_source / delivery_area_verified。`price_provider_router.py` assign_price_basis 纳入 eligible 门槛（缺省按五要素推算）；build_price_snapshot_meta 输出地址证据分级字段。
- golden 样例迁移契约 1.1（data/golden/price-result-sample.json 含 delivery_area 验证块与追溯字段，price-query-sample.json 改用 search_terms/positive_terms/hard_excluded_terms）；新增 tests/test_round47_provider_contract.py。

## 用户指示 2026-08-26（round 46：外部价格 Provider 契约 · 叮咚接入适配，版本 yueshi-1.2.0-rc）
依据《月食改动0826 1.docx》（Skill 侧 Provider 契约评审；配套本机只读助手 yueshi-dingdong-helper）：
- **新增 `references/price-provider-policy.md`**：Provider 职责边界（只读、不启动浏览器、无替代决策权）、price_provider_priority 回退链（dingdong_web_direct > other_public_direct > category_estimate > historical_estimate）、抓价时机（最终采购需求冻结后、仅 new_purchase_amount > 0）、direct_public_price 十项收紧条件与 direct_public_price_limited 降级、活动价/会员价分离与 ordinary_payable_price 预算口径、价格快照元数据、性能硬边界（1 主关键词 + 1 别名 / 5 候选 / 单会话批量 / 缓存优先）。
- **Provider 状态枚举**（success / partial / user_action_required / unavailable / invalid_result）映射进既有三类门禁，**不扩大 fatal_reason 七枚举**：用户强制实时价 + 需操作 → user_input_required；unavailable / invalid_result → 降级不判 fatal；invalid_result 拒绝结果文件且不记 corrupted_plan_json。
- **新增两份 Schema**：`schemas/price-query.schema.json` 与 `schemas/price-result.schema.json`（契约版本 price_data_version = "1.0"，与助手模型一一对应）。
- **新增 P01–P08 采购门禁**（合法 price_basis / 必需字段 / 规格可解析 / 单位显式确认 / 价格类型不混写 / 售罄剔除 / 相关性排除词 / 批次匹配），各门禁出错处理以 policy §7 为唯一定义；执行组件 `scripts/price_result_validator.py`（校验 + sha256 结果哈希）与 `scripts/price_provider_router.py`（纯函数路由，不启动浏览器），二者已加入 PIPELINE_COMPONENTS。
- **哈希职责四分**：rules_bundle_hash=规则 / pipeline_bundle_hash=组件 / price_result_hash=抓价结果完整性 / price_data_version=价格数据契约版本（唯一含义澄清，其他含义拆入 price_snapshot_meta）；plan.json 新增可选顶层块 `price_snapshot_meta`（provider/版本/区域/时间/source_mode/request_id/result_hash）。
- **G06 自动修复范围限定**（policy §10）：只允许换同食材合格候选/重算包装/合法回退层/修展示格式/补剩余去向；不得编价、错误规格、会员价当普通价、替换用户没选的食材；食材替换必须回菜单营养层。
- **性能基线**：perf_baseline 新增 price_gate_validate 节点；login_wait_ms（用户操作等待）口径与自动执行耗时分开，不计入 Skill 侧基线。
- 新增 tests/test_round46_price_provider.py（6 组 20+ 断言）；golden 样例 data/golden/price-query-sample.json 与 price-result-sample.json。

## 用户指示 2026-08-25（round 45：实跑反馈 · 口径修正 + 生成提速）
依据《月食改动0825.docx》（成品 8.5/10，慢点在试错式营养微调）：
- **取整口径（方案 A）**：nutrition-routing 新增「营养显示取整口径」——未舍入值超上限 ≤0.9g 记 rounding tolerance 视为达标；可见目标写"约"区间并允许"个别日期因食材取整允许约 1g 浮动"；禁止内部放行而页面看似超标。
- **米类生熟硬校验（渲染门禁）**：采购米类必须以生米（raw）汇总并标注"生米约 Xg（对应熟米饭约 Yg）"，熟饭重充当生米重量即渲染失败；runtime-rules 同步规则。
- **非做饭日标准文案（渲染门禁）**：excluded 日统一"今天不在家用餐，本计划不安排菜单，也不计入本周采购与营养合计"；"三餐自行解决/无人在家吃饭"进 BANNED 清单。
- **包装消耗优先级**：①本周可消耗小包装 → ②散装称重 → ③大包装本周两餐 → ④续存下周（写明去向）；剩余超半包须复核小包装/散装。
- **局部重装配模式**：change_scope=schedule_and_ingredient_patch（仅 cooking_days/excluded_days/excluded_ingredients 变化）走 7 步局部管线，跳过安全重采/目标重算/预算库存重问/完整预选。
- **份量一次联合求解**：新增 `scripts/household_portion_solver.py`（scipy linprog/HiGHS，L1 最小改动；约束=热量上下限/净碳水上限/蛋白下限/脂肪范围/克数上下限；locked 食材作常量；infeasible 退出码 3）——替代模型逐项试克数。
- **求解与渲染纪律**：先求解再统一渲染（只渲染一次，渲染后不再调营养采购）；不变数据（成员目标/库存/预算/价格/菜谱索引/营养表/换算表）按哈希缓存复用。
- 新增 tests/test_round45_speed_and_caliber.py（6 组 25 断言）。

## 用户指示 2026-08-25（round 44：发布链路定稿 + 版本切换 yueshi-1.1.0）
依据《月食_round43发布链路与RC2改进意见.docx》（最终轮）：
- **版本正式化**：SKILL frontmatter 与 golden 样例 plan_meta 统一切换 `yueshi-1.1.0`（家庭数据契约 plan_schema_version 维持 const "v0.3-rc2"，与技能版本独立）；round43 T01 改为与 frontmatter 同源动态断言。
- **泄漏防线（P0）**：release_pack 包后载荷扫描——包内出现 book-extraction 路径、电子书文件（.epub/.mobi/.azw/.azw3）或 .jsonl 提取缓存即构建失败；运行文件（SKILL/references/workflows/schemas/scripts）引用 book-extraction 即失败（references 与 effective-parameters 的维护性提法已改指 maintenance-map；library-manifest 中的路径属来源隔离登记元数据，豁免并记录）。
- **运行依赖闭包（P0）**：从 SKILL 引用、PIPELINE_COMPONENTS、哈希输入与 Schema/golden 清单生成闭包，包内逐项存在性检查，缺失即失败。
- **发布策略定稿**：maintenance-map 新增「发布与维护区策略」（repo-only/release-only 分类、维护区路径集中登记、四条硬门禁、唯一发布入口）。
- **manifest 审计字段**：build_source / build_tool_version / created_at(UTC) / excluded_paths / exclusion_reason / source_retention_policy / package_file_count / uncompressed_size_bytes / smoke_steps / runtime_dependency_check / copyright_payload_scan / reproducible_build / size_reduction_note。
- **可复现构建**：zip 固定排序、时间戳、权限位与压缩参数；每次发布自动重复构建两次校验 SHA-256 一致（reproducible_build 字段）。
- **烟测 5→7 步**：新增第 6 步家庭 effective 渲染（household_components.render_household_html：统一渲染器家庭入口的最小实现，直接消费 validated effective_plan，含成员营养块/份量块/三本账，禁内部术语）与第 7 步 release hygiene（引用扫描复验）。
- **性能基线**：新增 family_effective_render 节点。
- 新增 tests/test_round44_release_hardening.py。

## 用户指示 2026-08-25（round 43：正式发布前收口 · 版本语义/identity merge/发布验证）
依据《月食改进.docx》（RC2-6 前收口意见）：
- **版本语义**：`yueshi-1.1.0-rc` → `yueshi-1.1.0-rc2`（SKILL frontmatter + golden 样例 plan_meta 同步；一致性由测试锁定，RC2-6 完成后统一切 1.1.0）。
- **G03 机器可读分级**：拆为 G03a [user_input_required]（预选未确认）/ G03b [fatal]（已确认但生成失败/损坏/版本不匹配），消除"标 fatal 却含 user_input_required 分支"的自相矛盾。
- **identity merge**：家庭模式无论有无 override 都经 merger 产出 effective_plan（无 override 时 applied_override_ids=[]、merged_at=构建时间），渲染器永远只面对一种输入；merger CLI overrides 参数转为可选；planning-flow 第 13 步与 household-runtime-rules §12 同步。
- **max_members 唯一来源**：新增 `data/household-limits.json`（summary_inline_members=3 / max_members=6），SKILL 引用；纳入家庭 rules_bundle_hash。
- **双哈希分工**：render_plan 新增 compute_pipeline_bundle_hash（12 个执行组件：生成器/合并器/校验器/渲染器），与 rules_bundle_hash（规则/参数/Schema）区分"规则错配"与"执行组件错配"。
- **发布验证**：新增 `scripts/release_pack.py`——打包 → 解压到全新临时目录 → 包内最小烟测（renderer import / identity merge / override merge / effective 校验 / solo golden 渲染）→ 生成 `data/release-manifest.json`（版本、产物 sha256、三类哈希、烟测日志）。
- **迁移映射**：新增 `developer/migration-map.md`（字段/文件/行为/拒绝策略四部分；迁移器负责转换，Schema 不为旧字段放宽）。
- **性能基线**：新增 `scripts/perf_baseline.py` + `data/perf-baseline.json`，按节点分段（哈希/identity merge/override merge 2人3人/effective 校验/solo 渲染）。
- 新增 tests/test_round43_release_readiness.py；round42 T09 编号断言随 G03 拆分联动更新。
- P2 文档减重列入 1.1.1 维护任务，本轮不拆文件。

## 用户指示 2026-08-25（round 42：v1.1.0-rc 烟测后修改意见 · rc2 冻结前收口）
依据《月食家庭版_v1.1.0-rc烟测后修改意见》：3 P0 + 5 P1 + 契约补强 + T01–T08。
- **P0-1 家庭模式集合判定**：SKILL 定义 `household_plan_modes` = {shared_uniform, shared_meal_personalized, split_safety_required}，全文家庭条件改为集合成员判定，禁止 "shared_*" 前缀匹配（split_safety_required 不匹配该前缀）；render_plan 新增 HOUSEHOLD_PLAN_MODES 常量；household-runtime-rules 同步。
- **P0-2 渲染输入口径**：solo 渲染校验通过的 plan.json；家庭渲染链路 base_plan + overrides → merger → effective_plan → effective Schema 校验 → 统一渲染，渲染器只读校验通过的 effective_plan，base/overrides 不进表现层；统一文件名时由总控复制到临时构建目录并记录 source_artifact；校验器必须显式指定 artifact schema（新增 --schema overrides）。
- **P0-3 家庭规则纳入哈希**：plan_mode ∈ household_plan_modes 时 rules_bundle_hash 输入追加 household-runtime-rules、household-planning-flow 与 schemas/household 五件契约；T08 验证规则/Schema 变更即触发 mismatch 且 solo 哈希不受影响。
- **P1 收口**：人数表述改为"摘要页最多并排 3 人、成员总数可大于 3、超限生成前 user_input_required 不静默截断"（SKILL/runtime-rules/household-runtime-rules 同步）；家庭页数预算 = 基础 9 页 + 成员附页，禁止为卡页数降字号；H04 pending 口径收窄为"本次 effective 截止前且影响当前输出"，未来事项保留在 override 源文件；检查项统一编号 G01–G11 / H01–H06；家庭文件完整性条件保留 G01 单点定义、生成前即执行。
- **契约补强（§四）**：合并器落盘前先做 effective Schema 校验、失败不落盘、os.replace 原子写出；merge_status != applied 的 pending override 跳过并记 stderr（保留在源文件）；成员主数据不裁剪（effective.members 仍全员，仅餐次参与集合收缩）。
- 新增 tests/test_round42_rc2_freeze.py（T01–T08 + 编号/pending + 原子写出，54 断言）；round41 测试两处联动更新（编号 H01–H06、合成夹具 validate=False）。

## 用户指示 2026-08-25（round 41：SKILL 联动修订 · 家庭模式接入入口，1.1.0-rc）
- 依据《SKILL联动修订草案》+ 配套 household-planning-flow / household-runtime-rules / household_override_merger.py / golden 样例：
- **版本**：`yueshi-1.0.0` → `yueshi-1.1.0-rc`（路由与门禁语义已变）。
- **description 触发词**：追加"双人餐""两人吃饭""全家食谱""同餐不同量""多人共餐""家庭版"。
- **新文件**：`workflows/household-planning-flow.md`（家庭 13 步固定流程 + 缺席 patch 子流程 + uncertain 子流程）、`references/household-runtime-rules.md`（家庭增量规则：共锅两级判定 / 调味四级 / 六类 portion_method / 执行节奏 / 采购三本账 / 三层文件 patch 管线）、`scripts/household_override_merger.py`（patch 合并器：absent 移除份量、ratio_split 重归一 selected_pct、present_confirmed 关闭 uncertain、shopping_delta 减采购、写 effective_meta；base 冻结不改）、`scripts/household_components.py`（成员营养块 / 份量块 / 采购三本账行 HTML 组件）、`data/golden/household/samples/`（双人不同量 base + 缺席 patch 样例）。
- **SKILL.md**：完整性门禁按 plan_mode 扩展（shared_* 追加校验家庭规则/流程/契约文件，缺失 → fatal 不降级 solo）；固定执行顺序补家庭 13 步分支；渲染器分工补 merger + household_components 与渲染前置顺序；术语门禁追加 11 个家庭禁用词与 8 条显示转换；入口检查项追加第 12–17 项家庭检查（仅 shared_* 执行）。
- **校验器取舍**：草案版 household_reference_validator.py（13 大写 + 行内置信度检查）未替换 round40 正式版——正式版已覆盖其全部检查且按餐次粒度输出、与 schema check 枚举一一对应；置信度联动维持生成器自检 `ratio_split_confidence_ok`。
- **schema 防回归**：用户重传的 (1) 版 schema 回退了 round40 的逐字段 not 修复（多字段 not/required 缺陷），正式版保持修复态，tests/test_round41 锁定。
- 新增 tests/test_round41_household_flow.py（10 组 54 断言）。
- 合并后烟测修复：合并器输出不再夹带 schema 外内部字段（_note/_pending_leftover_refs 移除，leftover 去向由 override 记录与 effective_meta 追溯）；校验器新增 `--schema effective_plan`（有效计划契约：effective_meta 并入校验、缺席后 participant_member_ids 合法降至 1 人——golden-cases 期望语义，base 冻结态仍 minItems=2）；bundle 内 effective_plan 的 `#/base_plan` 根级引用按语义等价方式展开。
- 待后续（RC2-6）：统一渲染器消费 effective_plan 全链路、迁移映射、性能基线后冻结。

## 用户指示 2026-08-25（round 40：家庭版 v0.3 RC2 落地 RC2-3/4/5）
- **schemas 入库**：`schemas/household/` 收入 shared-definitions / household-base-plan / household-overrides / household-effective-plan + household-schemas.bundle.json（全解析版）。
- **schema 缺陷修正**：`not: {required: [多字段]}` 在 Draft-07 下仅当多字段同时出现才拦截，与"external_meal 禁止 action 与 leftover_plan_id"等意图不符——已在 shared-definitions 与 bundle 中拆为逐字段 not（present_confirmed / external_meal 两处）。
- **RC2-3 校验器**：`scripts/household_reference_validator.py`——集合（成员唯一/primary 唯一/参与者引用）、比例（ratio 集合=参与者、Σmin≤100≤Σmax、selected_pct Σ=100）、not_participating 排除、leftover/condiment/override 引用、L3 gate 一致性、reuse_chain 餐次绑定、check_id 完整性（生成器 13 项 + 脚本 13 项各恰好一次）；支持 --write 回写 household_validation。
- **RC2-4 Skill 路由**：SKILL.md 主线路由第 6 条扩为四 plan_mode（solo / shared_uniform / shared_meal_personalized / split_safety_required；安全冲突直接进 split）；locked_basket 门禁分级（用户未确认→user_input_required，生成器失败→fatal）；runtime-rules 新增「家庭模式」（一轮合并问卷 / 检索一次 / 营养批处理 / 份量一次求解 / 缺席局部重算不判 fatal / 渲染上限 3 人、超出摘要页+成员附页）。
- **RC2-5 golden cases**：`data/golden/household/` 8 组（双人同量/双人不同量/三人不同量/安全分锅/采购前缺席/采购后外食/uncertain 关闭/三人缺席重分配），生成器 `scripts/build_household_golden_cases.py`。
- 新增 tests/test_household_rc2.py（12 项，含冻结前 11 项清单负向用例）与 test_household_skill_routing.py（6 项）。
- 待后续（RC2-6）：渲染器适配 household schema、迁移映射与性能基线后冻结。


## 用户指示 2026-08-25（round 39：文案与数据同源 + 双人评审适用项）
- 依据《月食双人版评审与改进建议》合并优先级中适用于单人版的部分（双人 household_plan schema 属双人版变体，不在本仓实现）：
- **plan_mode 前置路由**：SKILL.md 主线路由新增第 6 条——solo（完整支持）/ shared_meal_personalized（多人同餐不同量）；多人场景不静默降级，按 user_input_required 追问成员结构与分量方式。
- **月相连贯性**：满月/新月窗口收窄至各约 ±0.8 天，一周轨道同名"满月"≤2 天（修复"7 天 4 个满月"类错误）；旧测试断言 2026-08-26 满月更正为 2026-08-28。
- **日期派生校验**：备餐日/采购日标签"周X M/D"由渲染器对照真实星期校验，不符即渲染失败；一切日期/克数/价格文案必须从 plan.json 派生。
- **采购一行一食材硬门禁**：食材名含 、，+/和 等合并符即渲染失败。
- **预算双口径**：from_inventory 食材价格列显示"库存（参考 X元/规格）"；预算区并列"本周实际支出（不含库存）/ 含库存全口径约"。
- **功效断言门禁**：可见文字禁止未标注来源的功效表述（对骨骼/血脂/代谢更友好、延缓衰老、治疗等），validate 正则扫描。
- **safety-rules 新增绝经/更年期参数**：减重蛋白质下限 ≥1.1g/kg/日、每日 ≥1 份钙来源、默认 L0 禁食。
- **golden sample**：data/golden/golden-sample-plan.json + tests/test_golden_sample.py 基准比对。
- 新增 tests/test_round39_consistency.py（6 项）与 test_golden_sample.py；test_visual_palette_moon.py 月相断言随窗口收窄更新。


## 用户指示 2026-08-24（round 38：统一营养调整候选表，替代运行时临时搜索）
- 依据《月食_统一营养调整候选表模板》：新增 `data/nutrition-adjustment-options.json`（23 条内置候选，覆盖 protein_low_fat / protein_energy / energy_carb / energy_fat / carb_reduce / fat_reduce / energy_reduce / package_use 八类）、`schemas/nutrition-adjustment-options.schema.json`、`scripts/build_adjustment_options.py`（nutrition_delta 一律由 foods-table per_100g 推算，禁止手填）、`scripts/nutrition_adjuster.py`（完整 nutrition_gap 差额向量；一次评估四项差额选最小调整集；来源限当前菜谱食材/locked_basket/库存/approved 平替；直接更新 meal.ingredients，禁止旁路字段；最多两轮，第二轮小幅收口；两轮后返回局部换菜或失败原因；冻结后禁止调整；nutrition_adjustment_log 可追溯）。
- `references/nutrition-routing.md`「渲染前自动修正」补充统一候选表管线口径（营养域修改，SKILL.md 保持冻结）。性能改进点：营养修正不再运行时搜索"怎么补"，直接从本地候选表一次选择，nutrition_passes 上限仍为 2。
- 新增 4 个测试文件（共 16 项）：test_nutrition_adjustment_options / test_adjustment_source_scope / test_adjustment_updates_meal_ingredients / test_two_pass_limit。


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
