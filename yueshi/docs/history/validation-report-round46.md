# Validation Report · round46

日期：2026-08-26
候选：`candidates/round46/`（基线 = 已合并 round45，yueshi-1.1.0）

## 全量回归

- 测试文件：44 个（含新增 test_round46_price_provider.py，6 组 20 断言）
- 结果：**44/44 全部通过，0 失败**

## round46 新测试要点

- 新文件齐备（policy / 2 Schema / 2 脚本 / 2 golden 样例）；两份 Schema 通过 Draft7Validator.check_schema
- SKILL.md：版本 yueshi-1.2.0-rc、Provider 摘要段、哈希职责四分、G06 范围限定；fatal_reason 七枚举未扩大（provider_unavailable / login_failed / price_fetch_failed 均不存在）
- validator：golden 样例 exit 0 且 provider_status=success、result_hash 为 sha256；损坏 JSON → invalid_result + exit 3；request_id 不匹配 → P08 + exit 3；售罄 + 排除词候选 → P06/P07 检出 + exit 2
- router：5 种状态 × 强制/非强制映射均不产出 fatal；user_action_required+强制 → user_input_required；invalid_result 不记 corrupted_plan_json；未知状态 ValueError；price_basis 收紧（地址未确认/规格失败 → limited；无价 → 拒绝）；会员价不作 ordinary_payable_price
- perf_baseline 含 price_gate_validate 节点与 login_wait_ms 分离口径；PIPELINE_COMPONENTS 含两个新脚本

## 版本联动更新（沿用既有惯例）

round37 / round41 t02a / round43 T01b / round44 T01a+T01b+T07b 的版本断言改为与 SKILL frontmatter 动态同源或语义化格式断言；golden 家庭样例 plan_meta 同步 1.2.0-rc，price_data_version 澄清为 "1.0"。

## 配套助手验证（yueshi-dingdong-helper）

- 全部 6 个 Python 文件 ast 语法通过；price-query.json JSON 合法
- 离线门禁断言全过：未登记单位数值价格 → 拒价 + PRICE_UNIT_UNCONFIRMED；显式 cent → /100；排除词（黑椒/熟食/水饺）过滤；无关商品（苹果）过滤；规格 400g 解析正确

## 待合并后执行

`rsync -a --exclude 'candidates' candidates/round46/ ./` → 全量回归 → `scripts/release_pack.py`（唯一发布入口，含载荷扫描/闭包/可复现构建/7 步烟测）→ 同步 /app/.agents/skills/yueshi/ → 烟测。
