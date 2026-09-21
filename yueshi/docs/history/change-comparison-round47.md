# 变更对照 round47（价格数据契约 1.1 · 地址证据分级 + 查询追溯 + eligible SKU 门槛）

依据：《月食叮咚查价助手_v1.2改进方案.docx》RC-5（Skill 契约修改）；配套本机助手 yueshi-dingdong-helper v1.2（已另行交付 zip）。
基线：round46 已合并的 yueshi-1.2.0-rc 工作树。

## 文件级对照

| 文件 | 变更 | 说明 |
|---|---|---|
| `references/price-provider-policy.md` | 修改 | 版本头 1.0→1.1；§5 条件 6 收紧为「已确认且已验证的配送区域」、条件 7 纳入 eligible_for_purchase；新增 §5.1 查询词分层召回与追溯（attempted_queries / matched_query / match_strategy / 状态细分 / 诊断计数）；§6 快照示例新增 delivery_area_source / delivery_area_verified；新增 §6.1 配送区域证据分级表（五来源，user_manual/unresolved 永远 verified=false）；§7 P02/P06/P07/P08 文案对齐 1.1；§9 性能边界「1 主词 + 1 别名」→「≤3 查询词 + 提前停止」；活动价必须落 promotion_price_yuan。 |
| `schemas/price-result.schema.json` | 修改 | schema_version const "1.1"；新增顶层 `delivery_area` 块（label/source/verified/station_id/observed_at）；query_result 新增 attempted_queries/matched_query/match_strategy/diagnostics，status 枚举 +search_empty/candidates_filtered/candidates_unpriced/candidates_unavailable；product_candidate 新增 matched_query/eligible_for_purchase。Draft7 check_schema 通过。 |
| `schemas/price-query.schema.json` | 修改 | query_item 新增 search_terms（maxItems 3）/ positive_terms / hard_excluded_terms；description 注明契约 1.1。 |
| `scripts/price_result_validator.py` | 修改 | PRICE_DATA_VERSION="1.1"；P02 改读批次级 delivery_area（label 非空 + verified=true，新增违例 P02_DELIVERY_AREA_UNVERIFIED）；P06 新增 P06_NOT_ELIGIBLE_SKU（available 但 eligible_for_purchase=false）；P07 优先对照 positive_terms / hard_excluded_terms（兼容旧 aliases / excluded_terms）；报告新增 delivery_area_source / delivery_area_verified 字段。 |
| `scripts/price_provider_router.py` | 修改 | assign_price_basis 纳入 eligible SKU 门槛（显式字段优先，缺省按五要素推算；无 product_id 的 DOM 候选至多 limited）；build_price_snapshot_meta 输出 delivery_area_source / delivery_area_verified，result_schema_version 默认 "1.1"。 |
| `data/golden/price-result-sample.json` | 修改 | 迁移契约 1.1：schema_version "1.1"、delivery_area 验证块（network_response + verified=true）、逐项 attempted_queries/matched_query/match_strategy/diagnostics、候选 eligible_for_purchase=true；豆腐候选改为活动价样例（promotion_price_yuan + price_type=promotion，覆盖 RC-3 活动价口径）。 |
| `data/golden/price-query-sample.json` | 修改 | 改用 1.1 字段：search_terms / positive_terms / hard_excluded_terms。 |
| `SKILL.md` | 修改 | price_data_version 文本 "1.0"→"1.1"；price_snapshot_meta 字段清单补 delivery_area_source / delivery_area_verified。 |
| `references/output-policy.md` | 修改 | price_data_version 文本 "1.0"→"1.1"；注明 1.1 起快照含地址证据分级字段。 |
| `CHANGELOG.md` | 修改 | 新增 round47 条目（最新在前）。 |
| `tests/test_round47_provider_contract.py` | 新增 | 5 组 20 断言（Schema 1.1 / 校验器门禁 / 路由器 eligible 与快照 / 契约文档文本）。 |
| `tests/test_round46_price_provider.py` | 修改 | 性能边界断言同步「≤3 查询词」；price_basis 测试字典补 product_id + eligible_for_purchase（对齐 eligible 门槛）。 |

## 不变项（契约红线复核）

- fatal_reason 仍为 7 枚举，未新增 Provider 类 fatal；invalid_result 仍不记 corrupted_plan_json。
- Provider 仍只读、不启动浏览器（Skill 侧）、无食材替代决策权；G06 修复范围未扩大。
- 地址只保存最小标签；user_manual / unresolved 来源不得支撑 direct_public_price。
- 哈希四分职责不变（rules/pipeline/price_result/price_data_version），price_data_version 唯一含义=价格数据契约版本。

## 回归

- tests/ 全量 39 个测试文件通过（含新增 round47 20 断言；round46 同步修订后仍全绿）。
