# ADR-0004：菜谱库构建链收敛为单一深模块（round76）

- 状态：已接受
- 日期：2026-09-21

## 背景

菜谱库构建链（分类 → 指纹 → 审计 → 发布门禁）此前只以 MAINTENANCE.md 的文字约定存在：

- 没有编排器（MAINTENANCE.md 自认"当前没有统一总控脚本"），前两环漏跑没有任何程序拦截；
- 门禁在 blocked 状态下仍以退出码 0 结束，状态只写在 JSON 里，依赖人眼读取；
- 两份快速模式索引（`recipe-production-index.json` / `ingredient-recipe-inverted.json`）入库却无生成脚本（孤儿产物），停留在 2026-08-21——快速模式读到的是过期数据，且书籍记录的 active 分钟数从未被映射（473 条为 null）。

## 决策

1. **编排器**：新增 `scripts/build_library.py`，接口三个开关：`--build-id`、`--approve --approved-by`、`--check`；内部固定顺序 classifier → fingerprint → audit → gate → quick_indices，任一步非零退出即停并透传退出码；`run_chain(runner=…)` 接受注入执行器（测试不依赖真实构建）。
2. **状态语义**：链结束读取 `library-manifest.release.release_status`——approved → 0；review_required 且未审批 → 2（提示审批参数）；blocked/未知 → 3。整链只有一个出口。
3. **孤儿产物收编**：新增 `scripts/build_quick_indices.py`（`--out`/`--check`）作为链末步骤，从 `recipe-index.json` + `book-recipes.json` + manifest 确定性派生两份快速索引；版本（production_pool_version / build_version）绑定 manifest 的 build_id。**不内嵌 manifest 字节哈希**：门禁的常规审批重放（以及运行门禁的回归测试）会改写 approved_at/approved_by 等元数据，字节级绑定会让索引"虚假过期"；manifest 与产物的一致性由 `--check` 的 artifact_hashes 校验负责。字段映射与旧产物逐字段核对；唯一有意差异：书籍记录的 `estimated_active_minutes` 由历史 null 修正为 `active_minutes`（473 条，快速模式时间筛选从"未知"变为可用）。
4. **只读校验**：`--check` 校验 release_status、artifact_hashes 逐项、快速索引新鲜度；失败即非零并列出差异。
5. **文档**：MAINTENANCE.md 的链条段改为编排器命令（保留内部顺序说明作为实现注记）。

## 后果

- 构建链的顺序与 build_id 一致性从"文档纪律"变为"代码强制"；单独重跑某一步再替换生产产物会在门禁的 artifact_hashes/一致性校验处暴露。
- blocked 不再静默成功：CI/维护者拿到非零退出码。
- 快速模式索引重新与生产池同步；书籍记录获得真实烹饪时长（行为改善，已在 CHANGELOG 记录）。
- 构建链仍直接写生产路径；把构建与测试写入隔离（--out 全链密封）留待测试密封化议题。
