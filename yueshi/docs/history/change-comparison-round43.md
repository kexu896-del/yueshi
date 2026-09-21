# round43 变更对照（正式发布前收口）

依据：《月食改进.docx》。结论"可进入 RC2-6、不再扩功能/改 Schema 主结构"下的收口实施。

## P0

| 意见 | 落实 |
|---|---|
| 正式版代码与 RC 元数据并存 | 版本统一切到 `yueshi-1.1.0-rc2`（带序号可区分冻结轮次）：SKILL frontmatter + golden 样例 plan_meta（skill_version + 6 个明细版本）同步；T01 自动化一致性测试，不依赖人工全文搜索；RC2-6 完成后一次性切 1.1.0 |
| G03 等级自相矛盾 | 拆为 G03a [user_input_required]（预选未确认）/ G03b [fatal]（已确认但生成失败/损坏/版本不匹配）；机器与文档语义一致；round32/round40/round42 相关断言联动更新 |
| 无 override 家庭计划的渲染输入 | identity merge：merger overrides 参数转可选，无 patch 也产出 effective_plan（applied_override_ids=[]、merged_at=构建时间）；SKILL/planning-flow 第 13 步/household-runtime-rules §12 三处口径统一为"渲染器永远只面对 effective_plan 一种输入" |

## P1

| 意见 | 落实 |
|---|---|
| max_members 未落地 | `data/household-limits.json`（summary_inline_members=3 / max_members=6，数值可按渲染与性能测试再调）为唯一来源，SKILL 声明"脚本与问卷不得各自写死"；纳入家庭 rules_bundle_hash（T04c） |
| 双哈希分工 | compute_pipeline_bundle_hash（12 个执行组件脚本）与 rules_bundle_hash 并存；排错可区分"规则错配"与"执行组件错配"（T05） |
| 包内测试 | `scripts/release_pack.py`：打包 → 解压全新临时目录 → 包内 5 步烟测（renderer import / identity merge / override merge / effective 校验 / solo golden 渲染）→ 全过才放行（T07a/e） |
| 打包清单与校验摘要 | `data/release-manifest.json`：release_version、两产物 size+sha256（一致性比较，T07d）、三类哈希、schemas 清单、test_summary、烟测日志 |
| 迁移映射四部分 | `developer/migration-map.md`：字段/文件/行为/拒绝策略；原则"迁移器负责转换，Schema 不为旧字段放宽 additionalProperties" |
| 性能基线分节点 | `scripts/perf_baseline.py` → `data/perf-baseline.json`：哈希/identity merge/override merge（2 人、3 人缺席）/effective 校验/solo 渲染分段计时（本机参考：家庭管线节点均 <25ms，solo 渲染 ~135ms） |

## P2

文档减重（SKILL 瘦身、gate registry、机器可读哈希清单）列入 1.1.1 维护任务，本轮不拆文件（CHANGELOG 已记）。

## 联动更新（非回归）

- round32 入口门禁关键词、round40 locked_basket 分级断言、round42 T09 编号循环：随 G03 拆分更新。
