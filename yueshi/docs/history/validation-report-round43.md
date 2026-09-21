# round43 验证报告

## 新增测试

tests/test_round43_release_readiness.py：8 组 39 断言，全部通过。

- T01 版本一致性：SKILL frontmatter=yueshi-1.1.0-rc2、无无序号 rc 残留、golden 样例 plan_meta 同步、CHANGELOG 最新条目为 round43
- T02 G03a/G03b 新表述在、旧混合 G03 已清除
- T03 identity merge：无 override 产出 effective、applied_override_ids=[]、merged_at 非空、过 effective Schema；SKILL 声明单一输入
- T04 household-limits：字段齐、SKILL 引用唯一来源、文件变更触发家庭哈希变化
- T05 pipeline 哈希：16 位、与规则哈希不同、执行组件变更即变、探测后还原
- T06 迁移映射四部分 + 拒绝策略原则
- T07 发布链路：release_pack 全链路 exit 0、manifest 版本/sha256/两包一致/5 步烟测日志/双哈希/test_summary
- T08 性能基线：脚本可运行、6 个关键节点齐全且为正值

## 全量回归

41 个测试文件全部通过（pass=41 fail=0）。

三处预期联动（非回归）：round32 门禁关键词、round40 locked_basket 分级断言、round42 T09 编号循环——均随 G03 拆分（意见 P0-2 直接要求）更新。

## 意见"RC2-6 完成标准"8 条对照

| 标准 | 状态 |
|---|---|
| 有无 override 均消费 validated effective_plan | ✅ 本轮（identity merge + T03） |
| renderer 不直读 base/override | ✅ 口径三连（SKILL/planning-flow/runtime-rules）；产物级连线属剩余 RC2-6 |
| household_plan_modes 集合判定 | ✅ round42 已锁定 |
| max_members 唯一参数来源 | ✅ 本轮 |
| 迁移映射四部分 | ✅ 本轮 |
| solo/2人/3人/override 性能基线 | ✅ 本轮（分段节点） |
| 压缩包解压重跑最小烟测 | ✅ 本轮（release_pack 包内 5 步） |
| 版本号/Schema const/CHANGELOG/manifest/包内元数据一致 | ◐ rc2 层级已一致并由 T01 锁定；切 1.1.0 属 RC2-6 完成时一次性动作 |

## 已知边界

- 统一渲染器真正消费 effective_plan 的 HTML/PDF 产物级连线仍是 RC2-6 剩余项。
- household-limits 数值（3/6）为初始值，可按渲染与性能测试调整，结构调整需改哈希。
