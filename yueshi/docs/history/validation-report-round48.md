# 验证报告 round48（价格数据契约 1.2）

日期：2026-08-26
基线：round47 已合并工作树（yueshi-1.2.0）

## 1. Schema 校验

- 两份 Schema Draft7Validator.check_schema 通过；const "1.2"；地址字段与 raw_field_names 移除有测试断言。
- golden 结果样例（1.2）全量校验 0 错误。

## 2. 契约测试

- 新增 test_round48_provider_contract.py：5 组 18 断言全过
  （地址字段移除 / 候选精简 / delivery_context_confirmed_by_user 门禁 /
   快照 meta 新字段 / 效率门禁与"价格失败不重跑菜单"文档断言）。
- test_round47 按契约演进修订（地址证据分级断言移除、版本断言动态化）后全过；
  test_round46 快照断言同步后全过。

## 3. 全量回归

- tests/ 46 个测试文件逐一执行：46/46 通过。

## 4. 端到端冒烟

```
python3 scripts/price_result_validator.py data/golden/price-result-sample.json \
  --request-id weekly-plan-2026-08-26-sample --query data/golden/price-query-sample.json
→ provider_status=success，无候选违例，exit=0，
  result_hash=sha256:ede98e7b…，price_data_version=1.2，
  delivery_context_confirmed_by_user=true
```

助手侧离线冒烟：黑椒腌制里脊硬排除、售罄剔除、聚合节点剔除、促销价分类
（promotion_price_yuan=10.0 / regular=15.0）、契约 1.2 序列化与回读校验全过。

## 5. 红线复核

- fatal_reason 七枚举未扩大；invalid_result 不记 corrupted_plan_json（测试断言）。
- 只读门禁（URL 审计 / 按钮文本审计 / 退出码 4）保持。
- 隐私收紧：连最小地址标签也不再读取、不保存。
- 哈希四分职责不变，price_data_version 三处文本一致（"1.2"）。

## 结论

round48 候选验证通过，可合并打包。助手 v1.3 zip 已同步交付；
正式免安装 EXE 便携包需在你的 Windows 上双击 build-exe.bat 产出（README 有说明）。
