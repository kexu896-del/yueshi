# round42 验证报告

## 新增测试

tests/test_round42_rc2_freeze.py：10 组 54 断言，全部通过。

- T01 split_safety_required 进入家庭集合：SKILL 集合定义、正文无 shared_* 条件残留、代码常量、split 与 shared_uniform 哈希一致且异于 solo
- T02 契约外字段注入（顶层 _note/debug、嵌套 _debug）均被 effective Schema 拒绝
- T03 双人 base 通过 → 缺席后 effective 通过、成员主数据仍 2 人、单餐参与者降至 1 人、base_build_id 保留
- T04 错误 Schema 模式（effective 按 base、overrides 按 effective）明确失败；overrides 模式正向通过
- T05 pending override 不被应用、份量不动、源文件保留
- T06 external_meal 不物化 leftover、采购契约字段在、override_id 可溯
- T07 人数/分页口径文案（摘要页 3 人并排、总数可超、不静默截断、家庭页数预算、旧"上限 3 人"表述清除）
- T08 家庭哈希随规则/Schema 变化、solo 哈希不受家庭文件影响、探测后文件还原
- T09 G01–G11 / H01–H06 编号齐、pending 口径收窄文案
- T10 合并器落盘前校验失败即中断、不写半成品（含 .tmp）

## 全量回归

40 个测试文件全部通过（pass=40 fail=0）。

两处预期联动（非回归）：round41 测试的检查项编号断言（12–17 → H01–H06）与合成夹具 validate=False——均为本轮意见直接要求的变更。

## 意见§七冻结判断对应

- 合并器契约外字段、effective 人数冲突：round41 已修，本轮 T02/T03/T04 固化为回归
- 3 个 P0：全部落地并有 T01/T08 锁定
- 意见结论"完成后进入 rc2 冻结与扩大回归，不需要重做 Schema 总体架构"：Schema 未改动（仅校验器使用侧修正）

## 已知边界

- RC2-6（统一渲染器消费 effective_plan、迁移映射、性能基线）仍未连线；T07 为文案级口径测试，渲染连线后需补产物级断言。
- leftover 物化属渲染连线时按契约 leftover_plans 实现，本轮维持追溯不物化。
