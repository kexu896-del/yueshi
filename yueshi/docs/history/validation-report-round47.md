# 验证报告 round47（价格数据契约 1.1）

日期：2026-08-26
基线：round46 已合并工作树（yueshi-1.2.0-rc）

## 1. Schema 校验

- `schemas/price-result.schema.json` / `schemas/price-query.schema.json`：jsonschema Draft7Validator.check_schema 通过。
- golden 结果样例（1.1 格式）对 result Schema 全量校验：0 错误。

## 2. 单元/契约测试

- 新增 `tests/test_round47_provider_contract.py`：5 组 20 断言，全部通过。
  - Schema 1.1：const "1.1"、delivery_area 五来源枚举、状态细分枚举、追溯字段、search_terms maxItems=3；
  - 校验器：golden 全过；user_manual+verified=false → P02_DELIVERY_AREA_UNVERIFIED；eligible_for_purchase=false → P06_NOT_ELIGIBLE_SKU；hard_excluded_terms（黑椒腌制里脊）→ P07_EXCLUDED_TERM；CLI 退出码 0；price_data_version="1.1"；报告含 delivery_area_source/verified；
  - 路由器：eligible=false → direct_public_price_limited；缺省 eligible 五要素推算（无 product_id → limited）；地址未验证 → limited；快照 meta 含地址证据分级字段；
  - 契约文档：1.1 版本头、§5.1 追溯、§6.1 分级、性能边界 ≤3 词、SKILL/output-policy 文本同步。
- `tests/test_round46_price_provider.py`（同步修订后）：全部通过。

## 3. 全量回归

- tests/ 目录 39 个测试文件逐一执行：**39/39 通过**。

## 4. 端到端校验器冒烟

```
python3 scripts/price_result_validator.py data/golden/price-result-sample.json \
  --request-id weekly-plan-2026-08-26-sample --query data/golden/price-query-sample.json
→ provider_status=success，无候选违例，exit=0，
  result_hash=sha256:6903c58c…，price_data_version=1.1，
  delivery_area_source=network_response，delivery_area_verified=true
```

## 5. 红线复核

- fatal_reason 七枚举未扩大；invalid_result 不记 corrupted_plan_json（测试断言）。
- Provider 只读边界、G06 范围、地址最小标签原则未松动。
- 哈希四分职责文本在 SKILL.md / output-policy.md / policy 三处一致（"1.1"）。

## 结论

round47 候选（Skill 侧契约 1.1 适配）验证通过，可合并打包；助手侧 v1.2（zip 已交付）与本契约一一对应。
