# 月食维护地图（developer/maintenance-map）

本文件是 SKILL.md 的拆分部分，面向维护者：书籍菜谱提取规则、数据状态机、测试清单与文件地图。日常生成计划不需要阅读本文件。

## 定版维护口径（yueshi-1.0.0 Stable 起生效）

入口文件 SKILL.md 已冻结：发现问题时按领域修对应文件，**不再把具体渲染、菜谱或测试细节追加到 SKILL.md**——
- 菜单选择问题 → 修改 `references/runtime-rules.md` 或 ranker；
- 营养问题 → 修改 `references/nutrition-routing.md` 或计算器；
- 字号、分页、漏字段问题 → 修改 `references/output-policy.md`、渲染器或 CSS；
- 数据问题 → 修改对应 JSON 和 manifest；
- 所有修改写入 `CHANGELOG.md`。


## 书籍菜谱提取与使用规则

书籍来源内容分为**三层、八类**：

1. 菜谱与组合层：
   - `explicit_recipe`：书中有明确菜名、食材和步骤——**只有它可进入明确菜谱改造流程**；
   - `meal_pattern`：书中只有食物组合或餐盘建议——只能据组合原则生成 `book_pattern_derived` 新菜谱，**永不以"原书菜谱"身份进入菜谱池**。
2. 技法与文化层（进入索引和母版，不单独成菜）：
   - `technique_note`：可迁移技法；
   - `flavor_template`：可迁移味型或酱汁结构；
   - `ingredient_culture_note`：物产、时令、地域、名称和食俗；
   - `service_or_eating_context`：上桌、搭配、场合、温度或进食方式；
   - `historical_recipe_lead`：历史/散文中的菜谱线索——必须由另一份可执行菜谱来源交叉验证后才能入池。
3. 协议层（进入营养规则审计）：
   - `protocol_rule`：书中只有饮食模式或阶段原则（属规则库，不进菜谱池）。

- 不得把 meal_pattern 或 protocol_rule 表述为书中原有菜谱；不得在提取阶段补写书中不存在的食材克数、步骤或营养数据。
- 书籍菜谱进入候选池前必须依次经过：来源定位 → 食材名称规范化 → 本地食材平替 → 一人食与厨具适配 → 烹饪时间适配 → 营养重算 → 菜谱指纹去重。改造后的标记 `book_adapted`；根据书中组合原则新生成的标记 `book_pattern_derived`；二者均不得表述为原书逐字菜谱。
- 书中原有热量、营养值和份数只作参考，最终计划必须按实际食材克数、实际用油和实际份数重新计算。
- **书籍来源不自动获得更高排序权重**：所有菜谱统一按可获得性、包装利用率、烹饪时间、用户口味、模式适配、多样性和营养校验排序。
- 来源配额仅为**柔性观察指标**（HowToCook 改造 30 至 50% / 书籍明确菜谱改造 20 至 30% / 组合原则生成 10 至 20% / 本地家常菜 20 至 30% / 用户喜欢菜 1 至 2 道），不得凌驾于 locked_basket、安全、包装消耗、烹饪时间、用户偏好和营养校验；无法在不增加食材、不降低执行性的情况下满足配额时，允许偏离并记录原因。
- 完整提取流程见 `references/book-recipe-extraction.md`。
- 安全红线：不上传书籍内容至网络或外部服务；不保存大段连续原文；遇 DRM/加密/无法合法解析即停止并在 audit-log.md 记录；不虚构原书没有的食材、用量、步骤、份数、时间、温度和营养值。

## 测试清单（合并前全量回归）

tests/ 下全部 test_*.py 为回归套件，合并候选前必须全量通过。规则类测试断言的规则文本以 SKILL.md + references/runtime-rules.md + references/nutrition-routing.md + references/output-policy.md 的合集为准（规则拆分后测试读取合并语料）。新增功能必须附带新测试文件。

## 文件地图

```
SKILL.md                        入口（触发/定位/优先级/路由/15步/关键规则摘要与指针）
CHANGELOG.md                    参数与规则变更的唯一历史记录位置
references/runtime-rules.md     运行规则（信息采集/餐次/早餐/预选/一人食/外食/采购/断食窗口/生成约束）
references/nutrition-routing.md 营养路由（模式/周期协议/蛋白质四字段/营养门禁/渲染前自动修正）
references/output-policy.md     输出策略（渲染架构/执行模式/章节白名单/视觉分页/做法规则/最终门禁）
developer/maintenance-map.md    本文件（书籍提取/测试/文件地图）
workflows/planning-flow.md      15步固定执行顺序 · 两次生成+食材预选 · 菜谱指纹 · 质量指标 · weekly_feedback
workflows/procurement-flow.md   采购汇总 · 采购清单字段 · 所在地公开价格适配
workflows/fallback-flow.md      缺信息 / 无地区价格 / 临时变更 / 输出失败的降级路径
references/safety-rules.md      安全路由 · L0/L1/L2 · 特殊人群 · 安全门禁
references/questionnaire.md     关键八项一行式问卷模板（行内示例，做法必选无默认）+ 动态追问
references/output-schema.md     initial_basket / provisional_locked_basket / locked_basket / 搜索清单 / 指纹 / recipe_instruction / weekly_feedback 字段契约
references/visual-spec.md       全部视觉与输出规范（硬约束）
references/cycle-protocol.md    十一本书协议库（精读校准数字，仅人工说明）
references/book-consensus.md    书籍共识矩阵（背景资料）
references/book-recipe-extraction.md  EPUB 书籍菜谱七步提取流程与记录格式
references/tcm-food-style.md    中医食养修饰器速查
references/foods-table.md       常用食材每100g营养表
references/recipe-pool.md       书籍菜谱池 + 一锅出专区
references/tcm-exercise.md      中医功法（可选模块）
references/cities/nanjing-price-sources.yaml   南京菜价数据源样板
data/recipe-index.json          HowToCook 结构化索引（指纹字段；计数见 manifest）
data/book-recipes.json          已批准入库的书籍菜谱生产池（指纹+来源+改造标记；计数见 manifest）
data/package-rules.json         常见包装规格
data/ingredient-catalog.json    食材目录（别名/当令/包装/易腐/平替/最低菜数）
data/ingredient-preference-schema.json  偏好与安全分离的状态枚举与规则
data/functional-substitution-groups.json  功能替换组（删食材后同类推荐 1 至 3 个）
data/substitutions.json         平替表
data/flavor-bases.json          常备调味包与味型公式
data/seasonal-foods.json        月度当令食材
data/library-manifest.json      生产版本清单（各来源 record_status 与计数，脚本维护）
data/effective-parameters.json  经来源审计批准的生产参数（唯一生产计算来源；parameter_id 全局唯一、source_rule_id 可追溯）
data/price-estimates.json       所在地同类行情估算价（契约字段 city/as_of/unit_standard/method/version；items 含 spec/price/upper/price_basis）
data/cafeteria-meal-templates.json  食堂/外食点餐模板与区间营养估算（template_id/version/estimate_basis/confidence；菜单/校验/渲染共用唯一来源）
data/foods-table.json           营养计算使用的机器可读食材表（由 references/foods-table.md 校验生成）
data/recipe-production-index.json  快速模式使用的轻量生产菜谱索引（只含 production 记录和检索必要字段）
data/ingredient-recipe-inverted.json  ingredient→recipe 倒排索引（快速模式候选检索，不扫描菜谱正文）
scripts/macros_calculator.py    营养目标/周期阶段/达标校验
scripts/basket_builder.py       食材篮子草案
scripts/common/recipe_normalization.py  菜谱指纹/列表字段与比较口径唯一公共模块（空指纹合法，禁无保护 [0]）
scripts/recipe_ranker.py        菜谱候选五层过滤 + 一锅出结构白名单（只读 production 来源）
scripts/diversity_checker.py    菜谱指纹多样性校验
scripts/ingredient_preselector.py  食材预选（候选三层展示/删除四类处理/锁定篮子/最低校验）
scripts/shopping_aggregator.py  采购反向汇总 + 明细 + 采购清单导出（支持 --selection-report 排除未入选食材）
scripts/market_price_normalizer.py  菜场参考价归一化
scripts/render_plan.py          HTML 固定组件渲染器本体（plan.json → HTML，含渲染完整性与 plan_meta 版本门禁）。**注意：render_plan.py is not an output router**——名称易误认为总控，实际总控是 render_output.py；本文件相当于 html_components.py（未来重命名候选）
scripts/render_html.py          render_plan.py 的命令行包装（HTML 入口）
scripts/render_pdf.py           PDF 渲染器（render_html → Chromium 打印一次 → 删临时文件）
scripts/render_output.py        输出总控路由：按用户所选格式分发到对应渲染器
scripts/render_markdown.py      plan.json → Markdown 渲染器
scripts/render_docx.py          plan.json → Word 渲染器
scripts/build_recipe_index.py   菜谱索引离线构建（HowToCook 更新时重跑）
scripts/extract_book_recipes.py EPUB 书籍菜谱提取（换书/加书时重跑）
scripts/extract_yumizhixiang.py 《鱼米之乡》精读提取
scripts/extract_yirenguo.py     《一人锅》精读提取
scripts/extract_tcop_stage1.py  The Complete One Pot 阶段一候选清点
scripts/extract_tcop_stage2.py  The Complete One Pot 阶段二精读入库
scripts/wuyun_liuqi.py          五运六气
templates/plan-template.html    HTML 结构参考骨架（正式渲染走 scripts/render_plan.py 固定组件）
styles/screen.css               网页屏幕样式
styles/print.css                PDF 和打印专用样式（首页 cover、日期、月相、采购表格、分页和午餐布局的权威样式）
book-extraction/鱼米之乡/       鱼米之乡精读产物（菜谱JSONL/味型模板/时令地图/平替/审计）
book-extraction/一人锅/         一人锅精读产物（汤底模板/投料顺序/主食收尾/组装模式/审计）
book-extraction/The-Complete-One-Pot/  TCOP 两阶段精读产物（候选清单/工作日评级/缩份风险）
book-extraction/nutrition-audit/    营养学十一书二次审计；parameter-build-report.md 唯一路径
book-extraction/chinese_homestyle/  Chinese Homestyle 的候选、酱汁模板和审计结果
book-extraction/woks_of_life/       The Woks of Life 的候选、一锅面饭模板和嫩化技法
book-extraction/chinese_soul_food/  Chinese Soul Food 的候选、快炒焖烧模板和平替表
book-extraction/chihuo_cidian/      吃货辞典文化索引（不入菜谱池）
book-extraction/gusu_shihua/        姑苏食话时令物产索引（不入菜谱池）
book-extraction/coconut_sambal/     Coconut & Sambal 新版（印尼独立来源，参巴模板）
book-extraction/duplicate-merge-plan.json  中餐去重计划（待批准）
book-extraction/gap-audit.json      核心食材缺口审计
book-extraction/proposed-new-recipes.jsonl  新菜准入提案（待人工批准）
```
