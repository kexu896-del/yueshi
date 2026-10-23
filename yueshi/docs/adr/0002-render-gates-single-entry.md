# ADR-0002：渲染门禁单一入口与出口语义归一（round74）

- 状态：已接受
- 日期：2026-09-21

## 背景

渲染链有四个格式入口（render_plan/render_html、render_pdf、render_markdown、render_docx），门禁长期分散：

- 顶层必填键三份（render_plan、render_markdown、render_docx 各写一遍；render_pdf 缺失，缺键时以 KeyError 崩溃）；
- 价格硬门禁与流转核验各三处（渲染组件内联、validate_html、render_markdown）；
- `validate_html` 三档分化：HTML 入口是硬门禁（exit 3）、PDF 调用后丢弃返回值（禁用词/结构检查在 PDF 上形同虚设）、Markdown/Word 完全不调用；
- `render_plan --format pdf` 只产 HTML，与 output-policy 的固定调用说明矛盾（会把 HTML 写进 .pdf 文件）；
- render_pdf 文档声称"调 render_html 链路"，实际进程内 import render_plan；
- render_markdown/render_docx 借用 render_plan 的下划线私有函数，跨模块私有耦合。

## 决策

1. **门禁唯一实现**：`scripts/render_gates.py`——
   - `enforce(plan, fmt)`：计划级门禁（必填键 / plan_meta 版本与哈希 / 商品名泄漏 / 价格完整性 / 流转核验 / PDF 执行提醒 ≤5），四个入口与 `render_document` 统一调用；
   - `validate_user_text(text)`：Markdown/Word 产物文字门禁（内部表达、标题内部术语、非做饭日违禁文案、占位符异常值）——此前 md/docx 完全不查；
   - `validate_html(html, plan)`：HTML 结构门禁（从 render_plan 迁入）；render_pdf 的校验错误不再丢弃（未过门禁不打印）。
2. **render_plan 只产 HTML**：`--format` 仅接受 html；传 pdf 显式拒绝（rc=2）并指向 render_pdf/render_output。文档同步。
3. **共享辅助公开化**：`scripts/common/render_shared.py`（clean / display_price / window_no_fasting / normalize_provider_name / load_cafeteria_templates / CATEGORY_ORDER）；render_plan 保留旧下划线别名 re-export，render_markdown 不再借用私有函数。
4. **G12 仍由 render_output 总控执行**；planning-flow 步骤 15 的指引改为总控调用，消除"直连 render_plan 绕过 G12"的文档旁路。
5. **文档实况修正**：render_pdf 链路描述、MAINTENANCE 目录行（模板描述去掉已禁用的环形图/时间轴）、visual-spec 模板定位（参考骨架，运行时以固定组件与样式为准）。

## 后果

- 门禁改一处，四种格式同时生效；PDF 恢复完整校验；Markdown/Word 首获文字门禁。
- render_plan 的 `--format pdf` 调用方（若有）会得到显式错误而不是错误产物——属有意的破坏性收紧。
- render_gates 与 render_shared 进入 pipeline_bundle_hash 组件清单（执行组件变更可追溯）。
- 渲染入口的"必须记得调门禁"隐式契约消失：所有入口都只调一个 `enforce`。
