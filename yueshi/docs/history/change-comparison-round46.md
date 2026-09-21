# 变更对照 · round46（外部价格 Provider 契约 · 叮咚接入适配）

依据：《月食改动0826 1.docx》（Skill 侧评审）+《月食改动0826.docx》（助手框架）。
候选目录：`candidates/round46/`（基于已合并的 round45 基线复制，未直接改动正式文件）。

## 一、新增文件

| 文件 | 内容 | 对应文档要求 |
|---|---|---|
| `references/price-provider-policy.md` | Provider 契约唯一文件：职责边界 / price_provider_priority 回退链 / 抓价时机 / 状态枚举映射 / direct_public_price 收紧 / P01–P08 / price_snapshot_meta / 性能硬边界 / G06 范围限定 / Provider 登记 | 最终结论 6 项之 1、3、5；§一～§九 |
| `schemas/price-query.schema.json` | 抓价输入契约（draft-07），price_data_version = "1.0"；aliases maxItems=1 落实性能边界 | 最终结论第 4 项 |
| `schemas/price-result.schema.json` | 抓价结果契约，与 yueshi-dingdong-helper 的 pydantic 模型一一对应 | 同上 |
| `scripts/price_result_validator.py` | P01–P08 校验 + price_result_hash（sha256 规范化字节）；退出码 0/2/3 | 最终结论第 5、6 项 |
| `scripts/price_provider_router.py` | 纯函数路由：状态→门禁映射、price_basis 收紧赋值、ordinary_payable_price、price_snapshot_meta 构建；**不启动浏览器** | §三、§四、§五 |
| `data/golden/price-query-sample.json` / `price-result-sample.json` | golden 样例（猪瘦肉/北豆腐两条，含排除词演示） | 测试与 perf 基线输入 |
| `tests/test_round46_price_provider.py` | 6 组 20 断言 | 回归 |

## 二、修改文件

| 文件 | 修改 |
|---|---|
| `SKILL.md` | ① version → yueshi-1.2.0-rc；② 文件分工表新增 price-provider-policy.md 行；③「价格三层与完整性」后追加「外部价格 Provider」摘要段（文档表 31 口径）；④ plan.json 版本门禁段追加四哈希职责唯一 + price_snapshot_meta 可选块说明；⑤ G06 追加自动修复范围限定 |
| `references/runtime-rules.md` | 「采购输出」新增「外部价格 Provider 路由」条：优先级、provider/price_basis 分离、抓价时机与查询范围（仅 new_purchase_amount > 0）、状态枚举→三类门禁映射（不扩大 fatal_reason）、执行组件指针 |
| `references/output-policy.md` | plan_meta 契约段追加四哈希职责 + price_snapshot_meta；新增 P01–P08 采购门禁条（唯一定义指向 policy §7） |
| `developer/maintenance-map.md` | 维护口径加「外部抓价问题 → price-provider-policy.md / validator / router」；文件地图登记 5 个新文件 |
| `scripts/render_plan.py` | PIPELINE_COMPONENTS 追加 price_result_validator.py 与 price_provider_router.py |
| `scripts/release_pack.py` | 依赖闭包追加 5 个 round46 新文件 |
| `scripts/perf_baseline.py` | 新增 price_gate_validate 节点；注释明确 login_wait_ms（用户等待）与自动执行分离、不计入 Skill 侧基线（文档 §九） |
| `data/golden/household/samples/golden-base-plan-sample.json` | skill_version/明细版本 → 1.2.0-rc；price_data_version → "1.0"（round46 澄清其唯一含义为价格数据契约版本，文档 §十一.1） |
| `CHANGELOG.md` | 最新在前追加 round46 条目 |
| `tests/test_round37_stable_release.py` | 版本断言改为语义化格式（允许新周期 -rc，沿用 round42/43/44 联动更新惯例） |
| `tests/test_round41_household_flow.py` | t02a 改为「非 1.0.x」断言 |
| `tests/test_round43_release_readiness.py` | T01b 改为语义化格式断言（round44 正式版要求已记录于断言说明） |
| `tests/test_round44_release_hardening.py` | T01a/T01b/T07b 版本断言改为与 SKILL frontmatter 动态同源 |

## 三、文档要求 → 落实对照

| 文档 B 要求 | 落实位置 |
|---|---|
| ①新增 price-provider-policy.md | 新文件，SKILL.md 只留摘要 |
| ②只在最终采购需求冻结后抓价 | policy §3 固定流程 + runtime-rules 路由条 |
| ③登录/地址/页面失败 = 可降级 Provider 状态而非 fatal | policy §4 状态枚举 + router.map_provider_status（测试断言任何状态都不映射 fatal） |
| ④price-query / price-result 两份 Schema | schemas/ 两份 draft-07 |
| ⑤P01–P08 价格门禁 | policy §7 + validator 执行 + output-policy 汇总条 |
| ⑥plan.json 增加 price_snapshot_meta | policy §6 + router.build_price_snapshot_meta + SKILL/output-policy 说明 |
| provider 与 price_basis 分离 | policy §2.1 + router 枚举分离 |
| direct_public_price 收紧 + limited 降级 + 地址未确认降级文案 | policy §5 + router.assign_price_basis |
| 活动价/会员价分离，预算按 ordinary_payable_price | policy §5 + router.ordinary_payable_price（会员价不入围） |
| 四哈希职责 + price_data_version 唯一含义 | SKILL/output-policy 版本门禁段 + golden 样例 price_data_version="1.0" |
| Provider 无替代决策权（黑椒腌制里脊等不得自动进计划） | policy §8 + validator P07 + helper 端 excluded_terms |
| 性能硬边界 + login_wait_ms 分离 | policy §9 + perf_baseline 节点与注释 |
| G06 auto_fix 范围限定 | policy §10 + SKILL G06 条 |

## 四、配套交付（非 Skill 包内容）

`yueshi-dingdong-helper/`（本机助手，独立 zip）：文档 A 框架代码 + §十二 五项门禁全部落地
（价格单位门禁 PRICE_FIELD_UNITS / 地址门禁 / 相关性门禁 / 只读门禁 FORBIDDEN_ACTIONS+URL 与按钮审计，退出码 4 / 原子输出 tmp→回读校验→替换）。
门禁行为已经离线断言验证（未登记单位拒价、cent 显式换算、排除词过滤、地址缺失告警）。
