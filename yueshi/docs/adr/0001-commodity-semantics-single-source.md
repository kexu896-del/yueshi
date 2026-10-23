# ADR-0001：商品语义判定单一来源化（round73）

- 状态：已接受
- 日期：2026-09-21

## 背景

商品语义判定（四维门禁 + 形态识别 + 目录规则）长期双仓维护：

- 判定器两份实现：技能仓 `scripts/common/product_semantics.py` 与助手仓 `src/semantics.py`；
- 词表 ≥6 处副本：两侧代码硬编码词表 + 形态词典主库 vs 助手 FORM_KEYWORDS 手抄快照 + 目录规则字段名/值集分歧（excluded_states vs excluded_forms、marinated vs marinated_ready、raw/frozen_raw 词条差异）；
- 同步只靠"两端手改 + 测试读源码文本断言"，round 67–69 四轮校准后仍出现真实行为漂移：round69 的「味」风味守卫只在技能侧生效，助手把「全麦味大列巴」误判 accepted；
- 版本号（form_dictionary_version / catalog_version）在 4–5 个文件硬编码，升级词典要手改多处。

## 决策

1. **单一数据来源**：新建 `data/commodity-vocabulary.json`（词汇契约，含版本号），判定词表全部入数据；两侧判定器只保留判定逻辑、从数据加载。形态词典与食材目录保持原文件、作为既有数据来源。
2. **助手快照**：`scripts/export_helper_semantics.py` 把词汇契约 + 形态词典 + 目录规则导出为助手内嵌 `src/semantics-snapshot.json`（带三份源文件哈希）；助手 `config.py`/`semantics.py` 从快照派生全部词表与规则，`_MEIPASS`/`__file__` 双模式加载；`build_exe.py` 在打包前强制重跑导出并 `--add-data` 内嵌。
3. **字段名统一**：助手目录规则改用主库字段名 `excluded_states`（QueryItem 模型字段同名，旧清单的 `excluded_forms` 经 AliasChoices 兼容读取）。
4. **漂移修复方向 = 主库数据**：助手词表对齐主库（raw 补「生」、frozen_raw 补全、marinated_ready→marinated）；助手独有的正确知识回填主库（hard_excluded_terms）；`processed/prepared` 死状态本轮保持不动（两侧一致地不命中），登记入 GLOSSARY、留待独立清理。
5. **同步验证行为化**：跨仓探针由"读源码文本"改为行为对拍——同一组边界商品名两侧判定一致；快照新鲜度由导出脚本 `--check`（重导出逐字节比对）兜底；助手源码缺失时 SKIP 而非崩溃。
6. **判定副本收敛**：`judge_candidate` 成为候选判定唯一入口，purchase_selector 与 run_price_regression 不再各自维护复评副本。

## 后果

- 改一个词条 = 改一处数据 + 提升版本 + 重跑导出；漂移在行为对拍层立即显形，不再依赖人工"两端同步"。
- 助手构建依赖技能仓同级存在（快照导出是运行依赖，缺失即构建失败）——两个仓库的摆放关系成为构建前提。
- QueryItem 字段名变化：旧查价清单文件的 `excluded_forms` 仍可读（别名兼容），新清单统一 `excluded_states`。
- 目录版本升级（1.6.0→1.7.0）触发菜谱库发布门禁，必须重跑完整构建链并重新审核人工覆写——这是既有门禁的预期行为，不是新增成本。
