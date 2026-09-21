# 变更对照 round48（价格数据契约 1.2 · 放弃地址读取 + 正式/诊断分离 + 效率门禁）

依据：《月食叮咚查价助手_普通用户简易化与菜谱效率改进方案.docx》；配套助手 v1.3（zip 已交付）。
基线：round47 已合并的 yueshi-1.2.0 工作树。

## 核心定稿（文档 table 15）

- **放弃地址读取**：助手不读取、不保存、不验证具体收货地址；用户在叮咚网页内自行确认，结果只记录 `delivery_context_confirmed_by_user`。
- **正式/诊断分离**：正式结果只留月食采购字段；原始字段名、过滤计数、被剔除候选进 logs/price-diagnostics.json。
- **效率门禁**：主词 ≥3 个合格候选即停止别名搜索；候选按 product_id 去重；价格失败按回退链降级、不重跑菜单。

## 文件级对照

| 文件 | 变更 | 说明 |
|---|---|---|
| `schemas/price-result.schema.json` | 修改 | schema_version const "1.2"；删除 delivery_area / delivery_area_label / address_confirmed_by_user / 顶层 diagnostics；新增 delivery_context_confirmed_by_user；status 枚举删 address_unconfirmed；候选删 raw_field_names / image_url / delivery_area_label；query_result 删 diagnostics。Draft7 check_schema 通过。 |
| `schemas/price-query.schema.json` | 修改 | 删除 delivery_area_expected（不再做区域预期核对）；description 升 1.2。 |
| `references/price-provider-policy.md` | 修改 | 版本头 1.1→1.2；§1 增"不读取/保存/验证具体收货地址"；§3 增"价格失败不得迫使整份菜谱重新生成、最多一次轻量回退"；§5 条件 6 改配送会话确认；§5.1 增效率门禁与正式/诊断分离；§6 快照示例改 delivery_context_confirmed_by_user；§6.1 地址证据分级整节删除；P02 改 P02_DELIVERY_CONTEXT_UNCONFIRMED；§9 补"≥3 合格即停"。 |
| `scripts/price_result_validator.py` | 修改 | PRICE_DATA_VERSION="1.2"；P02 改读批次级 delivery_context_confirmed_by_user（违例码 P02_DELIVERY_CONTEXT_UNCONFIRMED）；报告附该字段；删除地址证据逻辑。 |
| `scripts/price_provider_router.py` | 修改 | DIRECT_PRICE_REQUIRED_FIELDS 删 delivery_area_label；assign_price_basis 文档对齐"配送会话确认"；build_price_snapshot_meta 输出 delivery_context_confirmed_by_user（删三个地址字段），result_schema_version 默认 "1.2"。 |
| `data/golden/price-result-sample.json` | 修改 | 迁移 1.2：删地址字段、删 raw_field_names/diagnostics，加 delivery_context_confirmed_by_user；保留促销价样例。 |
| `data/golden/price-query-sample.json` | 修改 | 删 delivery_area_expected。 |
| `SKILL.md` / `references/output-policy.md` | 修改 | price_data_version 文本 "1.1"→"1.2"；快照字段清单同步。 |
| `CHANGELOG.md` | 修改 | 新增 round48 条目。 |
| `tests/test_round48_provider_contract.py` | 新增 | 5 组 18 断言（地址字段移除 / 候选精简 / P02 新违例 / 快照字段 / 文档文本）。 |
| `tests/test_round47_provider_contract.py` | 修改 | 地址证据分级断言移除（被 round48 取代）；版本断言改为与 Schema const 同源动态断言；其余（状态细分/追溯/eligible/排除词）保留。 |
| `tests/test_round46_price_provider.py` | 修改 | snapshot meta 断言同步契约 1.2 字段清单。 |

## 助手侧（yueshi-dingdong-helper v1.3，zip 已交付）

- models.py 契约 1.2（删 DeliveryArea；候选精简；新增 DiagnosticsLog / QueryDiagnostics）；
- app.py 删除全部地址读取（read_address_label / wait_for_address / last-address.txt / 区域不符退出码 3）；
  确认流程改为"登录 + 你已在叮咚网页确认收货地址"；主词 ≥3 合格即停；product_id 去重；
  正式结果 `output/月食-叮咚价格结果.json` 与诊断 `logs/price-diagnostics.json` 分离；
- gui.py 文案（登录或更换叮咚账号 / 地址已确认，开始查价）、完成弹窗明确提示"拖入月食对话"、
  支持把清单拖到 exe 图标或在"更多"菜单选择清单文件；
- 清单改名 `月食-本周查价清单.json`（兼容旧名 price-query.json）；
- README 普通用户化（4 步流程；Python/pip 内容移入开发文档）；build-exe.bat 产物名 月食叮咚查价助手.exe；
- 冒烟：黑椒腌制里脊硬排除、售罄剔除、聚合节点剔除、促销价分类、1.2 序列化/回读全过。

## 不变项（红线复核）

- fatal_reason 七枚举未扩大；invalid_result 不记 corrupted_plan_json；unavailable 不判 fatal。
- Provider 只读边界不变；G06 范围未扩大；哈希四分职责不变。
- 地址隐私反而收紧：连"最小标签"也不再读取。

## 回归

- tests/ 全量 46 个测试文件通过（round48 新增 18 断言；round46/47 同步修订后全绿）。
- 校验器端到端：golden 1.2 样例 success、零违例、exit 0。

## 未做/后续

- 正式用户包（预构建 EXE 便携包）需在你的 Windows 上跑 build-exe.bat 产出；沙箱无法打 Windows EXE。
- 窗口内"拖到窗口"受 tkinter 原生限制，落地为"拖到 exe 图标 + 更多菜单选择文件"两种等效入口。
