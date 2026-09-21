# 外部价格 Provider 契约（price-provider-policy）

> 版本：price_provider_policy_version = 1.2（2026-08-26，round48：放弃地址读取、正式/诊断分离、精简候选、效率门禁）
> 价格数据契约版本 price_data_version = "1.2"（对应 price-query / price-result Schema 1.2）。
> 2026-08-27 增补（契约 1.2 向后兼容可选字段，helper v1.7）：候选可带
> `unit_price_yuan_per_100g`（元/100g）；单项结果可带 `suggested_purchase`
> （满足 required_grams 的最低总价组合：product_id/product_name/packages/
> total_grams/total_price_yuan/unit_price_yuan_per_100g）；批次可带
> `price_changes`（同一 request_id 重复查询时与上次结果的价格差异，
> change ∈ down/up/new/removed；条目以 ingredient_id 为稳定连接键，
> display_query 仅供显示——helper v1.8 起）。三者均可选，缺省时按原逻辑处理。
> 2026-08-28 增补（round52，helper v2.0，通用食材名称库与候选匹配方案）：
> 查询项可带 `exact_terms` / `broad_terms` / `category_substitution_allowed`
> （匹配质量分层：宽泛上位词只用于扩大召回，命中标 category_fallback，
> 不得冒充精确命中）；批次可带 `catalog_version` / `form_dictionary_version`
> （主库版本回显对账，主库为 data/ingredient-catalog.json 与
> data/product-form-dictionary.json）。候选可带 `match_quality`
> （exact/alias/category_fallback/low_confidence）、`product_form` 与
> `form_match`（形态正向匹配结论；设置 allowed_forms 时限制性形态不在
> 允许清单内即拒，鸡腿块不得冒充整腿）。单项结果可带 `substitution_notice`
> （建议为同类替代时必有）与 `dictionary_suggestions`（助手只建议，
> 不自动回写主库，需人工确认入库并提升 catalog_version）。
> `suggested_purchase` 可带 `total_count_text` / `package_text` /
> `match_quality`；建议门槛：exact/alias 优先，category_fallback 仅在
> 清单允许同类替代时进入，价格只在同等级内比较。`price_changes` 每条带
> `change_reason`（price_update/newly_observed/no_longer_in_top_candidates/
> filtered_by_rule/unavailable），removed 不再误表述为下架。结果瘦身：
> 候选省略 product_url/observed_at/空字段，抓取时间统一用批次时间。
> 2026-09-18 增补：结果根级新增 `observed_at`（= 本次查询完成时间，缺省时回退
> `completed_at`）与 `provider_version`；`run_warnings` 恒为数组（缺省 []）。
> P02 判定与 price_snapshot_meta.observed_at 均按「候选级或批次级至少一个存在」。
> 均向后兼容可选，契约版本维持 "1.2"。
> 2026-08-28 增补（helper v1.9）：查询项可带 `allowed_forms` / `excluded_forms`
> （形态约束：whole_leg/drumstick/wing/breast/diced/shredded/sliced/minced/
> marinated/cooked；排除形态命中即拒，优先形态影响排序与 suggested_purchase
> 挑选）；候选可带 `count_text`（枚数/件数原文，如「15枚」）与 `match_reason`
> （相关性命中依据，如 term:青菜）。均向后兼容可选。
> 2026-09-11 增补（round59）：`request_id` 生成规则定稿为 `{计划起始日期 YYYY-MM-DD}-{shopping_demand_hash 前 8 位}`
> （§3.1）；结果 Schema 对附加字段保持开放——根级与单项结果级 `additionalProperties` 放开，
> 助手新增字段不因 G13 误拒，契约版本维持 "1.2"（§4.2）；状态转移表定稿（§4.3）；
> 查询项生成规则与字典兜底定稿（§9.3），`data/ingredient-catalog.json` 与
> `data/product-form-dictionary.json` 纳入 G01 叮咚追加完整性检查清单。
> 适用范围：所有外部价格 Provider（当前唯一实例：叮咚网页只读助手 dingdong_web）。
> 本文件是外部抓价与月食主链路之间的唯一契约。SKILL.md 只保留摘要；运行时路由见 runtime-rules.md；采购门禁汇总见 output-policy.md。

## 1. 职责边界

外部价格 Provider 是**可选外部适配器**，不是月食核心生成逻辑的一部分：

- Provider 只返回：商品候选、包装规格、页面价格、可售状态、查询时间。
- Provider **不读取、不保存、不验证具体收货地址**（round48 定稿）；用户在叮咚网页内自行确认地址，Provider 只记录 `delivery_context_confirmed_by_user`（用户已确认当前配送会话）。
- Provider **不具有**：修改菜单、恢复用户删除食材、越过安全排除项、加入购物车、提交订单、支付、领取优惠券、修改地址的任何权限。
- Skill **永远不启动浏览器**。浏览器、验证码、页面选择器、会话文件全部由本地助手管理；Skill 只知道输入查价清单 JSON、输出价格结果 JSON（文件名不限，按内容校验） 与状态枚举。叮咚改版时只更新 Provider，不重发整套月食 Skill。
- 浏览器会话（browser-profile）只存于用户本机；抓价日志不进入月食发布包。

## 2. 价格来源路由（price_provider_priority）

价格来源优先级（高 → 低）：

1. `dingdong_web_direct`：叮咚网页实时直接公开价（用户已确认登录与地址）；
2. `other_public_direct`：其他公开直接价（本地市场公开页面等）；
3. `category_estimate`：可解释的当地同类估算；
4. `historical_estimate`：有日期的历史公开价。

任一食材按优先级取可用最高层；高层失败即降级到下一层，不阻塞计划。四层均不可用时，沿用既有规则：在 plan.json 冻结前替换为可合理定价的同功能食材（替换必须回到菜单装配层重新做营养与安全校验，见 §8）。

### 2.1 provider 与 price_basis 是两个字段

- `provider` 表示**数据来源**，枚举：`dingdong_web` / `public_market_page` / `historical_cache` / `category_model`；
- `price_basis` 表示**证据等级**，枚举：`direct_public_price` / `direct_public_price_limited` / `category_estimate` / `historical_estimate`。

两者不得混写。例如 `{"provider": "dingdong_web", "price_basis": "direct_public_price"}` 表示数据来自叮咚且证据等级为直接公开价；同一 provider 在规格解析失败时只能产出 `direct_public_price_limited`（见 §5）。

## 3. 抓价时机：只在最终采购需求冻结之后

固定流程：

```
菜单草案
→ 营养联合求解
→ 最终菜单食材与需求克数冻结
→ 反向汇总 new_purchase 需求
→ 调用价格 Provider
→ 包装组合求解
→ 预算检查
→ 必要时最多一次预算回退
→ 冻结最终 plan
→ 渲染
```

### 3.1 request_id 生成规则（round59 定稿）

查价清单的 `request_id` 在生成清单时写入，格式固定为：

```
request_id = {计划起始日期 YYYY-MM-DD}-{shopping_demand_hash 前 8 位}
```

`shopping_demand_hash` 为最终新购需求（ingredient_id + new_purchase_amount 规范化序列）的哈希。**同一日期两版不同菜单必然产生不同 request_id**，G13 据此拒绝把上一版菜单的查价结果串用到本次计划（见 §4.2 分支④）；同一计划重新生成同一清单时 request_id 稳定不变，允许助手侧 `price_changes` 与上次同 request_id 结果比对。

禁止在菜单/营养仍在微调时抓价（会造成"抓价 → 换食材 → 再抓价 → 包装改变 → 再调菜单"的循环拖慢）。
**价格失败不得迫使整份菜谱重新生成**：抓价失败一律按 §2 回退链降级；包装与预算最多触发一次轻量回退，不得回到问卷或完整流程。

**只查询 `new_purchase_amount > 0` 的食材。** 以下项目一律不查：

- 完全使用库存的食材；
- excluded 日期对应的食材；
- 不进入采购的 guidance_only 餐次；
- 已被用户移除的食材；
- 菜单仍处于候选阶段的食材。

## 4. Provider 状态枚举与门禁映射

Provider 状态枚举（**不扩大现有 fatal_reason 枚举**）：

| provider_status | 含义 | 门禁映射 |
|---|---|---|
| `success` | 全部查询成功 | 正常进入价格层 |
| `partial` | 部分食材有结果 | 无结果食材按 §2 降级 |
| `user_action_required` | 验证码未完成 / 配送会话未确认 / 会话失效 | 用户明确要求叮咚实时价时 → `user_input_required`；未强制时 → 允许降级到后备价格层 |
| `unavailable` | 页面结构变化 / Provider 不可读 | **不判 fatal**；走 `category_estimate` / `historical_estimate` |
| `invalid_result` | 结果文件损坏 / Schema 不符 / 哈希不匹配 | 拒绝该抓价结果、不污染 plan.json、走后备价格；**不得记为 corrupted_plan_json** |

单项级降级：单商品无匹配 → 仅该食材降级；规格无法解析 → 该候选降级为 limited 或拒绝（§5）。

### 4.1 结果缺失路由（Skill 侧硬约束）

**前置门禁（round53；round55 统一生成时机；round59 字段收敛；round64.1 统一选择时点）**：查价清单只在本次计划的**食材预选环节**用户明确选择「叮咚查价助手」为 A（`dingdong_price_choice = use_helper`，**唯一写入字段**）时启用——该选择只对当前计划周期有效，不跨周沿用，尚未选择时不得静默按估价处理——`dingdong_helper_opt_in` 降级为**派生只读字段**（`use_helper` ⇔ `yes`），任何环节不得直接写入它，两处取值冲突时以 `dingdong_price_choice` 为准并记异常——预选阶段只登记意愿，**全流程只有一份正式查价清单**：七天菜单草案、做法、营养校验与最终新购需求汇总完成后，按最终 `new_purchase_amount`、最终 ingredient_id 与 request_id 生成并交付，交付即暂停（G12）；未选"是"（默认否、不追问）时全流程不生成查价清单、不出现助手引导、不走 `dingdong_web_direct`，价格按 §2 回退链处理。用户后续对话明确表示"用叮咚查价"视为补开。

月食与本地助手之间**没有自动上传通道**：月食生成「月食-查价清单.json」→ 用户本机查价 → 用户把「月食-叮咚价格结果.json」上传回对话。

- 用户未上传有效价格结果文件时，**不得声称已取得叮咚直采价**；
- 未强制实时价：按 §2 回退链降级，并如实标注 price_basis（category_estimate / historical_estimate）；
- 用户明确要求实时叮咚价：返回 `user_input_required`，请用户先完成本机查价并回传；
- 价格失败只回退价格层，不重新执行食材预选、菜单装配和营养全流程。

**两阶段流程（round54）**：`price_workflow_state` 枚举与产物矩阵见 runtime-rules.md「外部价格 Provider 路由」。要点：清单交付即停在 `awaiting_price_result`，此阶段禁止渲染任何最终产物（渲染门禁 M01–M10 在 output-policy.md）；有效结果回传或 `opt_out_after_query` 后才一次性渲染最终版。恢复时以 `menu_snapshot_hash` / `nutrition_snapshot_hash` 判定局部重算或全量重算（见 planning-flow.md 步骤 15）。

### 4.2 结果文件校验强化（round54；round55 定名 G13）

- **G13 价格结果格式门禁（user_input_required）**：结果文件根级 `schema_version` / `provider` / `request_id` 必须齐备，且 **`request_id` 必须与本次查价清单一致**。处理分支：① 字段完整且 Schema 通过 → 进入候选筛选与价格锚定；② 明确识别为受支持旧版 → 运行迁移器补齐后**重新校验**；③ 字段缺失且版本无法识别 → 判 `price_result_invalid`，要求从本机助手重新导出（助手侧导出回归保证三字段恒在）；④ request_id 不匹配 → 拒绝使用并提示上传本次任务结果——**包括同一日期两版菜单的情形**：request_id 含 `shopping_demand_hash` 前 8 位（§3.1），旧版菜单的查价结果与本次清单哈希不同即拒绝，不串用旧价格；⑤ 内容看似完整但校验不通过 → **禁止人工静默绕过**。不记 corrupted_plan_json，按 invalid_result 路由走 §2 回退链或请用户重新查价。任何内容完整性判断都不能绕过 Schema。
- **对附加字段保持开放（round59）**：G13 以"必需字段齐全 + request_id 一致 + 已知字段类型合法"为准，**不因助手新增了 Schema 未登记的字段而拒绝**——price-result Schema 根级与单项结果级 `additionalProperties` 已放开（definitions 内部仍严格），未登记字段按透传处理、不进价格计算；若新增字段要进入正式契约，则按"登记字段 + 两边同步 bump `price_data_version` 与助手 `schema_version` + CHANGELOG 记录"的流程升级。
- **旧版结果迁移**：仅允许由迁移器脚本（`scripts/price_result_migrator.py`）做版本升级；`migration_log` 字段固定为 `source_schema_version` / `target_schema_version` / `fields_added` / `migrator_version` / `revalidation_passed`（另附 `migrated_at` 时间戳），迁移日志随构建记录保存但**不进入用户 PDF**。补齐约束：`provider` 只有在旧文件来源可唯一确认时才可补齐；`schema_version` 只能按已知旧结构映射，不能直接填最新版。迁移后必须重新执行同一 Schema 校验，`revalidation_passed=false` 按 invalid_result 处理。无 migration_log 的"已迁移"文件视为未迁移；不得人工编辑结果 JSON。
- **双重候选门禁（round54 助手侧）**：除 P06/P07 外，形态门禁（form gating，RESTRICTIVE_FORMS 未命中 allowed_forms 即拒，如"鸡蛋软饼"命中 pancake 形态被排除于"鸡蛋"查询）与条件接受（`conditional_accept`：含独立调味包/酱料包商品，本体合格但附调味时接受并写 `purchase_note` 提示，如"调味牛肉（附独立调味包，可不用）"）均在助手侧执行；月食侧 P07 复核时保留 form_match / conditional_accept 字段不回改。本机助手保存结果前必须回读并执行同一 Schema 校验（save_result 回读 model_validate），缺根级字段禁止导出。
- **哈希同源**：最终预算、采购表和价格说明引用同一 `price_result_hash`，防止价格层与说明层脱钩。

### 4.3 状态转移表（round59 定稿）

`price_workflow_state` 六态的合法转移全集（未列出的转移一律禁止；门禁列指该转移必须通过的门禁）：

| 当前状态 | 事件 | 新状态 | 允许动作 | 门禁 |
|---|---|---|---|---|
| `pending` | 用户选 A（用叮咚查价） | `use_helper` | 登记意愿、继续预选与正式生成链路 | 无（首轮明确即直记） |
| `pending` | 用户选 B（参考价估算） | `use_estimate` | 按 §2 回退链估价，一次性出最终版 | 不生成任何查价文件 |
| `pending` | 未作答 | `pending`（停留） | 只可展示食材预选，**不得进入预选后的正式生成链路** | 禁止静默按否处理 |
| `use_helper` | 正式查价清单生成并交付 | `awaiting_price_result` | 只交付清单与操作指引，流程暂停 | G12：禁止渲染任何最终产物 |
| `use_estimate` | （终态分支） | — | 估价完成即出最终版，注明估价口径 | 不得再走 `dingdong_web_direct` |
| `awaiting_price_result` | 有效价格结果回传 | `price_result_received` | 候选筛选、价格锚定、合并后一次性渲染 | G13 + P01–P08 + P09 |
| `awaiting_price_result` | **用户中途放弃查价**（"不查了/直接出计划"） | `opt_out_after_query` | 允许按回退链估价出最终版，**必须在结果说明注明估价口径**（"已按用户要求跳过叮咚查价，价格为估算"） | 不判失败；不回问卷 |
| `awaiting_price_result` | **助手无法运行**（如本机无可用浏览器） | `opt_out_after_query` | 同上，允许转估价路径 | 不判失败；须如实告知用户 |
| `price_result_received` | 价格合并完成 | `final_plan_ready`（终态） | 一次性渲染全部最终产物 | 此后不再回退到 `awaiting_price_result` |
| `opt_out_after_query` | 估价完成 | `final_plan_ready`（终态） | 一次性渲染全部最终产物 | 估价口径说明必带 |

两个易漏转移已单列：`awaiting_price_result → opt_out_after_query`（用户中途放弃 / 助手无法运行）均为合法转移，不判失败、不记 fatal，只要求估价口径明示。

## 5. direct_public_price 收紧条件

只有**同时满足**以下全部条件，候选才可标 `price_basis = direct_public_price`：

1. 商品名称；
2. 包装规格原文；
3. 可换算重量或容量；
4. 页面展示价（且单位已显式确认，见 P04）；
5. 查询时间（带时区）；
6. 用户已确认当前配送会话（`delivery_context_confirmed_by_user = true`）；
7. 商品可售状态为可售，且 `eligible_for_purchase = true`（eligible SKU 门槛：product_id + 名称 + 价格 + 可换算规格 + availability == "available" 五要素齐备，见 §7 P06）；
8. Provider 名称；
9. 数据来源类型（network_response / page_dom）；
10. 无严重解析警告（PRICE_UNIT_UNCONFIRMED / PRICE_UNRESOLVED / PACKAGE_WEIGHT_UNRESOLVED 均属严重警告）。

不足时的处理：

- **有价格但规格解析失败** → 标 `direct_public_price_limited`，`confidence = low`，`package_resolution = unresolved`；**不得进入包装组合求解**，仅作展示参考。
- **配送会话未经用户确认**（`delivery_context_confirmed_by_user = false`）→ 不得写"XX 叮咚当前价"，只能写"页面参考价，配送会话未完成确认"；建议直接降级，不纳入正式预算锁定。
- **仅有活动价/会员价** → `regular_price` / `promotion_price` / `member_price` 单独记录，不得混写；活动价（vip 无、price < origin_price）记入 `promotion_price_yuan` 且 `price_type = promotion`，不得只塞进 `listed_price_yuan` 而丢失活动标签；预算按 `ordinary_payable_price`（普通应付价）或规则指定的保守价格计算，不得把会员价默认当作所有用户可得的预算价。

### 5.1 查询词分层召回与追溯

- 每个食材最多 3 个查询词（`search_terms` ≤ 3，主词在前），逐层尝试；任一层产生合格候选即提前停止，不耗尽全部词。
- 每项查询结果必须记录 `attempted_queries`（实际执行过的查询词序列）、`matched_query`、`match_strategy`（`primary` / `alias_tier` / `none`），使"哪个词命中"可追溯。
- **效率门禁**：主词取得 ≥3 个合格候选即停止，不再搜索别名；候选按 product_id 去重。
- 无结果状态必须细分：`search_empty`（搜索无返回）/ `candidates_filtered`（候选全部被相关性或排除词过滤）/ `candidates_unpriced`（候选全部无可用价格）/ `candidates_unavailable`（候选全部不可售或不合格）/ `no_match`（兜底），分阶段诊断计数（raw / relevant / excluded / unpriced / unavailable）、接口原始字段名、被剔除候选清单**不进正式结果**，由 Provider 写入本机诊断日志（logs/price-diagnostics.json），供排查"是搜不到还是过滤掉"；正式结果只保留月食采购需要的字段。

## 6. 价格快照元数据与哈希职责

plan.json 增加**可选**顶层块 `price_snapshot_meta`（使用了外部 Provider 时必填）：

```json
{
  "price_snapshot_meta": {
    "provider": "dingdong_web",
    "provider_version": "1.2.0",
    "result_schema_version": "1.2",
    "delivery_context_confirmed_by_user": true,
    "observed_at": "2026-08-26T08:30:00+08:00",
    "source_mode": "live",
    "request_id": "weekly-plan-...",
    "result_hash": "sha256..."
  }
}
```

四个版本/哈希字段职责唯一、不得混用：

- `rules_bundle_hash`：规则文件组合是否匹配；
- `pipeline_bundle_hash`：执行组件是否匹配；
- `price_result_hash`：本次抓价结果文件是否被修改（对价格结果文件规范化字节的 sha256，见 scripts/price_result_validator.py）；
- `price_data_version`：**价格数据契约版本**（price-query / price-result Schema 契约版本，当前 "1.2"）。它不是缓存批次、不是来源版本、不是某次快照版本——那些含义由 price_snapshot_meta 各字段承担。

Provider 的实际商品数据**不加入** rules_bundle_hash。


## 7. 采购门禁 P01–P09

- **P01**：每个 new_purchase 食材均有合法 price_basis；
- **P02**：direct_public_price 必须有 provider、observed_at，且批次级 `delivery_context_confirmed_by_user = true`；observed_at 判定口径（2026-09-18 修复）：**候选级 observed_at 或批次级 observed_at 至少一个存在**即通过——v2.0 结果瘦身允许候选省略抓取时间，批次级取根级 `observed_at`，缺失时回退 `completed_at`；`price_snapshot_meta.observed_at` 同口径（批次 observed_at 优先，其次 completed_at）；
- **P03**：用于包装计算的候选必须有可解析规格；
- **P04**：页面价格必须明确价格单位，禁止按数值大小猜"元/分"；
- **P05**：普通价、活动价、会员价不得混写；
- **P06**：售罄商品不得作为正式采购候选；正式采购候选必须满足 eligible SKU 门槛（`eligible_for_purchase = true`：product_id + 名称 + 价格 + 可换算规格 + availability == "available" 五要素齐备）；
- **P07**：商品候选必须通过食材相关性（positive_terms 正向词命中）和排除词（hard_excluded_terms 命中即拒）检查；
- **P08**：price-result 的 request_id、Schema（契约 1.2）和哈希必须匹配本次采购需求；
- **P09（round57 新增：价格元数据一致性门禁）**：价格结果文件根级 `provider` / `schema_version` / `request_id` 必须与最终 plan.json 的 `price_snapshot_meta.provider` / `result_schema_version` / `request_id` **完全一致**——这是审计冗余而非可选项，两边都必须填写且不得漂移。不一致时：不允许渲染最终文件；**不自动选择其中一个值**；返回价格结果校验失败，要求重新迁移或重新导出。
  哈希门禁：`price_snapshot_meta.result_hash` 必须等于规范化后的价格结果文件 SHA-256（即 `price_result_hash`，见 §6 与 scripts/price_result_validator.py）；预算卡、采购表和价格说明必须引用同一 `price_result_hash`，禁止各自计算或引用不同批次。

出错处理：

- P01、P02 → 尝试价格降级（§2 回退链）；
- P03 → 换其他候选；
- P04、P05 → 拒绝该候选；
- P06 → 查下一个候选；
- P07 → 拒绝错误商品；
- P08 → 拒绝整个结果文件，但**不判菜单损坏**；
- P09 → 拒绝渲染最终文件并返回价格结果校验失败（不自动择值，须重新迁移或重新导出）。

## 7.5 商品语义门禁与采购选择层（round67，2026-09-18）

链路定稿为：**查价助手负责找 → 商品语义门禁负责判 → 月食负责选**。

- **大品类召回**：查价请求拆分为「显示名称 / 搜索范围 / 验收条件 / 需求量 / 未知处理」。
  `search_scope.category_query` 是稳定大品类词（酸奶/面包/豆腐/猪里脊），
  逐级同义词轮询与长尾标题模拟一律停止；`fallback_category_query` 只放宽召回，
  不放宽验收。别名只用于召回，**不再作为商品合格的充分条件**。
- **验收条件**（`acceptance_profile`，数据档案见 `data/product-acceptance-profiles.json`）：
  品类 → 物种 → 部位/可食部分 → 单一原料/复合食品 → 加工状态 → 特定要求（无添加糖/全谷物）。
- **三态决策**：`accepted`（必要条件有充分证据，可进入包装与价格比较）/
  `rejected`（明确冲突：species_conflict、snack_product、wrong_processing_state、
  composite_food、prepared_dish、requirement_not_verified 等）/
  `review_required`（证据不足，保留为候选证据但**不得自动采用**）。
  证据强度：配料或营养标签 > 平台结构化标签 > 标题声明 > 类目名；
  标题无"糖"字不得推断为无糖；"全麦"标题仅为 title_claim，不得描述为已验证比例。
- **采购选择层**：`scripts/purchase_selector.py` 只从 accepted 候选中选，按普通应付价与
  包装适配排序；助手 `eligible_for_purchase` / `suggested_purchase` 不再视为最终结论；
  最终商品与助手建议不一致时记录 `selection_change_reason_codes`
  （smaller_package / ordinary_price_preferred / product_form_correction /
  species_conflict_rejected / prepared_food_rejected / better_required_amount_fit /
  fallback_to_estimate），禁止无日志静默替换。
- **无 accepted 候选**：按 `uncertainty_policy.no_accepted_candidate_action`
  回退参考价估算或替换同功能食材；`review_required` 商品不得进入正式采购建议。
- **维护方式**：只维护错误类别与稳定品类/属性，不维护商品全称映射；
  平台促销前缀（如【红烧很香】）在评估前剥离，不因标题变化追加黑名单。

## 8. Provider 不具有替代决策权

Provider 搜索别名仅用于寻找目标商品，不具有食材替代决策权。价格 Provider 不得恢复用户删除项、不得越过安全排除项、不得自行把相近商品视为正式替代。

例：目标「猪瘦肉」可用别名「猪里脊」搜索；但「黑椒腌制里脊」「猪肉水饺」「熟食肉片」不能因名称含"里脊/肉"而自动进入计划。真正的替代必须返回菜单装配层，并重新做营养和安全校验。

## 9. 性能硬边界

- 每个食材最多查询 3 个查询词（主词 + 最多 2 个别名层；主词取得 ≥3 个合格候选即停止，见 §5.1）；
- 每个关键词最多保留 5 个候选；
- 一次浏览器会话批量完成全部查询；
- 优先读取有效缓存；只对缺失、过期、无货项重新访问页面；
- 不打开无必要的商品详情页；不抓取全站分类；
- 不因单个食材失败重复整个批次。

性能基线必须拆分记录（`login_wait_ms` 是用户操作等待，与自动执行耗时分开，不得误判为系统算法慢）：

`browser_start_ms` / `login_wait_ms` / `query_total_ms` / `query_per_item_ms` / `normalization_ms` / `package_solver_ms` / `price_gate_ms`。

月食侧运行记录按阶段拆分（round58）：`profile_load_ms` / `questionnaire_merge_ms` / `basket_build_ms` / `recipe_search_ms` / `menu_assembly_ms` / `daily_target_compile_ms` / `nutrition_round_1_ms` / `nutrition_round_2_ms` / `nutrition_final_check_ms` / `shopping_aggregate_ms` / `price_query_build_ms` / `price_result_validate_ms` / `candidate_filter_ms` / `package_solver_ms` / `html_render_ms` / `pdf_print_ms` / `layout_retry_count`；并同时记录 `nutrition_adjustment_rounds`（≤2）/ `menu_days_recomputed`（无食材替换时价格回传后应为 0）/ `candidate_manual_review_count`（异常指标）/ `pdf_render_count`（正式渲染应为 1）/ `pdf_layout_retry_count`。目标不是预设虚假秒数，而是让"慢"可定位。

## 9.1 精简查价清单与助手端词典展开（round58）

查价清单默认采用**精简项目结构**：每项只携带 `ingredient_id` + `query` + `required_grams`（+ 可选 `required_form` 用途形态约束），批次级携带 `catalog_version` / `form_dictionary_version` 回显对账；**不再逐项重复** `search_terms` / `positive_terms` / `hard_excluded_terms`——匹配规则由助手从本地词典/目录快照（FORM_KEYWORDS / CATALOG_RULES，版本与主库一致）按 `ingredient_id` 展开。只有本周有特殊用途时才在对应字段提供 override，**override 优先于词典展开**。月食侧与助手侧不得各自维护两套排除词：规则单一来源为 `data/ingredient-catalog.json` 的 query_profile 与 `data/product-form-dictionary.json`，助手构建时快照同步并提升版本。

## 9.2 助手端导出门禁 E01–E06（round58）

价格结果文件的技术字段由助手自动生成并自检，**不把 schema_version / provider / request_id 的理解负担转给普通用户**：

- **E01**：`schema_version` 存在且为受支持版本；
- **E02**：`provider = dingdong_web`；
- **E03**：`request_id` 与导入的查价清单一致；
- **E04**：`results` 非空或带明确部分失败状态；
- **E05**：保存后回读并通过同一份 Schema 校验（先写临时文件 → 回读校验 → 原子替换正式文件）；
- **E06**：完成页向用户展示"结果已通过格式校验"。

用户提示分层：普通用户只看到"结果文件格式不完整，请回到查价助手重新保存"；"查看诊断"中才显示具体缺字段明细。迁移规则不变：可识别旧版迁移并重新校验后使用；无法识别拒绝；`request_id` 不匹配**永不自动迁移为本周**；禁止因"内容看起来完整"人工静默放行。人工候选复核（`candidate_manual_review_count`）计入运行记录并作为异常指标跟踪，目标是逐步降到异常分支。

## 9.3 查询项生成规则与字典兜底（round59 定稿）

生成查价清单时，每个查询项的匹配规则按以下来源展开，**新食材首次查价不需要手工编写排除词**：

1. **库内食材**（`data/ingredient-catalog.json` 存在该 ingredient_id）：按其 `query_profile` 展开——`search_terms` / `positive_terms` / `hard_excluded_terms` / `allowed_forms` / `excluded_forms` 全部来自主库快照，清单默认不逐项重复（§9.1 精简结构），本周特殊用途才写 override 且 override 优先。
2. **库外食材**（目录中不存在）：走**全局形态词典兜底**——
   - 形态排除：默认排除制品形态（丁/丝/片/馅/丸/饼/卷等加工形态词）与加工方式形态（烤/炸/腌/卤/制/即食/预制等），命中即拒；
   - 前缀豁免：名称含"免/无/不含/原切"等豁免前缀时不按加工形态排除（如"原切牛排"不因"切"被拒）；
   - 类别白名单兜底：按食材所属类别判定放行方向——category_path 属肉禽蛋/水产/蔬菜的原料型商品放行，熟食/速食/烘焙类目商品拒绝；
   - 兜底展开的查询项必须标注**低置信度**（`match_quality` 上限为 `low_confidence`，不得冒充 exact/alias 命中），并在运行记录中计入待复核。
3. **完整性门禁**：G01 叮咚追加完整性检查的文件清单包含 `data/ingredient-catalog.json` 与 `data/product-form-dictionary.json`（与 price-query / price-result Schema 同级别；细粒度标识 `ingredient_catalog_missing` / `form_dictionary_missing`），缺失即阻止查价链路，不得凭模型记忆补写排除词。
4. **学习闭环（dictionary_suggestions）**：助手结果中单项可带 `dictionary_suggestions`（新别名建议 / 误伤词报告 / 待入库条目）。助手**只建议，不自动回写主库**；月食侧汇总建议清单交用户确认，确认后才回写 `data/ingredient-catalog.json` 或 `data/product-form-dictionary.json` 并提升 `catalog_version` / `form_dictionary_version`，助手构建时快照同步新版本。

## 10. G06 自动修复范围限定

接入 Provider 后，G06（auto_fix）"自动修复价格"**只允许**：

- 换用同一食材的另一个合格商品候选；
- 重新计算包装数量；
- 使用合法的价格回退层；
- 修正展示格式；
- 补齐已有数据可推导的剩余去向。

**不允许**：模型编一个价格数字；自动使用错误规格；自动把会员价改成普通价；自动替换成用户没选的食材。涉及食材替换，必须回到菜单和营养层。

## 11. Provider 实例登记

当前登记的 Provider：

| provider | 适配器 | 输入 | 输出 | 状态枚举 |
|---|---|---|---|---|
| `dingdong_web` | 本机 yueshi-dingdong-helper（Playwright，只读） | 月食-查价清单.json | 月食-叮咚价格结果.json | success / partial / user_action_required / unavailable / invalid_result |

新增 Provider 时：在本表登记、提供对应 Schema 与校验器映射，不改动 §1–§10 的契约层。
