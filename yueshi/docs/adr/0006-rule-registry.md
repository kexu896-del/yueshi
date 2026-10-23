# ADR-0006：规则注册表与合并语料助手（round78）

- 状态：已接受
- 日期：2026-09-21

## 背景

规则文本分散在 SKILL.md 与 references 的三份规则文件中（runtime-rules / nutrition-routing /
output-policy），测试侧的消费方式长期靠手抄：

- 约 10 个测试各自写"SKILL.md + 三元组"的字符串拼接，其中 4 处把三元组**连拼两遍**
  （复制粘贴产物，断言在重复语料上失真）；
- `references/rule-index.md` 只是人工表格，测试用正则从 Markdown 散捡规则 ID；
- SKILL.md 摘要与 owner 规则的"双写契约"靠单个测试的逐字断言（MEAL-STATE-001），没有全局守护；
- 新增规则时"登记 ID + 写 owner"没有强制路径。

## 决策

1. **注册表唯一人工源**：`references/rule-index.md` 保持表格不变（ID 只增不改）；新增
   `scripts/common/rule_index.py` 解析为结构化注册表（rule_id / topic / rule / owners / deprecated），
   不新增第二份 JSON——避免 MD/JSON 双源漂移。解析失败抛错，不静默跳过。
2. **语料助手唯一实现**：新增 `tests/rule_corpus.py`（`load_corpus()` = SKILL.md → runtime-rules →
   nutrition-routing → output-policy 的顺序拼接，进程内缓存；`read(rel)`）；10 个历史语料测试
   全部改用，删除手写拼接与重复段。
3. **中心化校验**：新增 `tests/test_round78_rule_registry.py`——
   - 注册表完整性（条目 ≥18、ID 唯一且格式合法、字段非空）；
   - 每条规则的细则路径存在，且规则 ID 至少出现在一个 owner 文件中；
   - 弃用（deprecated）规则不得被 SKILL.md 引用；
   - **镜像一致性**：SKILL.md 提及的每个规则 ID 必须已登记（镜像集合自动发现，不手写清单）；
   - 语料助手与顺序拼接等价，且每份规则文件在语料中只出现一次（防重复拼接回潮）；
   - 10 个历史语料测试必须引用统一助手（防回退）。
4. **登记流程**：新增规则 → 在 `rule-index.md` 追加一行（ID / 主题 / 一句话 / 细则位置）→
   测试按 ID 断言；SKILL.md 摘要如引用 ID，必须先在索引登记。

## 后果

- 规则 ID 成为跨版本契约：测试引用 ID、owner 可迁移、废止保留标注。
- 合并语料的拼接逻辑只有一份；历史"连拼两遍"的失真被清除并由测试守护。
- 新增规则时忘记登记会在 test_round78 处失败（SKILL 引用未登记 ID / owner 缺 ID）。
- SKILL.md 与 owner 的**逐字**一致性仍由具体规则测试（如 MEAL-STATE-001）负责；
  本轮不重构摘要的刻意重复（AI 入口需要摘要）。
