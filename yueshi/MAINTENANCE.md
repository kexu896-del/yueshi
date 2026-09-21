# 月食（yueshi）维护文档

> 面向开发、维护者和其他 AI；普通用户无需阅读或运行其中命令。

## 基本流程
- **单人 15 步**：意图识别 → 安全筛查 → 信息采集 → 周期阶段 → 价格口径 → 初步食材篮子 → 用户预选 → 锁定篮子 → 菜谱检索 → 约束装配 → 七天菜单 → 营养校验 → 采购汇总 → 采购输出 → 定稿渲染。
- **家庭 13 步**：多人同餐（同量/不同量/安全分餐）走家庭管线：单次检索、单次装配、批量营养、≤2 轮全局微调、缺席只合并 patch。家庭版摘要页最多并排展示 3 名成员，超出 3 人时其余成员信息进附页。

## 给维护者 / 其他 AI
0. **先读 `CHANGELOG.md`** 了解最近变更再动手；未启用叮咚查价（未选 A）时，价格契约文件（price-provider-policy / price-query / price-result Schema 等）缺失不影响普通估价流程。
1. 先把 `SKILL.md` 交给 AI 作为系统提示/知识库。
2. 让 AI 按其中"文件地图"读取 workflows/ 与 references/ 下的支撑文件。
3. 告诉 AI 用户问卷中的关键八项（以及叮咚查价选答）。
4. `scripts/` 维护命令按用途分层（全部为纯 Python 标准库；PDF 渲染额外调用本机 Chromium 浏览器，非 Python 包）。当前没有统一总控脚本，以下均为**生产链组件**，不是可独立运行的完整入口：
   - **正式生产链组件**（生成计划的正规链路，由规划流程按序调用）：
     - `macros_calculator.py --cycle --last-period YYYY-MM-DD` → 周期阶段
     - `macros_calculator.py --sex f --age 28 --height 163 --weight 70 --goal lose --mode <系统推算的本周安排>` → 营养素目标；该参数只能从已冻结的 mode_schedule 读取，不接受人工选择
     - `basket_builder.py --meals-per-day 1 --mode-schedule mode_schedule.json --month 8` → 食材篮子草案（模式只读自已冻结的 mode_schedule，M11）
     - `recipe_ranker.py --basket 鸡腿,鸡蛋,菠菜 --mode-schedule mode_schedule.json --max-minutes 25` → 候选菜谱（仅读取 release_status=approved 的菜谱库）
     - `shopping_aggregator.py --menu meals.csv --search-list out.csv` → 采购汇总+搜索清单
     - `render_output.py` → 按用户所选格式分发渲染（总控入口）
   - **调试工具**（开发排查用，不进用户计划链路）：
     - `diversity_checker.py menu.csv [--fingerprints data/recipe-fingerprints.json]` → 菜谱指纹多样性校验
     - `market_price_normalizer.py prices.csv --city references/cities/nanjing-price-sources.yaml` → 菜场参考价
     - `wuyun_liuqi.py 2026-08-27` → 五运六气与时令
   - **菜谱库构建链**（内部固定链路，必须按固定顺序、同一 build_id、同一 taxonomy bundle 与食材目录版本执行，不得单独重跑后直接替换生产产物）：
     - `recipe_classifier.py` → `recipe_fingerprint_builder.py` → `recipe_library_auditor.py` → `recipe_release_gate.py`
   - **只读审计工具**（只产出报告，不改写生产数据）：
     - `recipe_library_auditor.py` → 菜谱库审计/验收报告（reports/ 与 data/audit/；同时是构建链第三环）
   - **禁止单独运行的内部组件**：
     - `scripts/common/mode_schedule.py`：内部饮食安排组件，不得作为用户入口单独运行；
     - `recipe_release_gate.py`：`data/library-manifest.json` 中 release 块的唯一合法写入方，只允许由构建链末端调用。

## 叮咚查价助手分发与构建
- **当前过渡交付方式为完整文件夹分发**：以便携版文件夹（或 zip 压缩包）**整个文件夹拷贝**到本机，不能只拿其中的 exe（配置与词典文件在同目录下，只复制 exe 会因缺少配套文件无法运行）；正式 Windows 安装版为既定目标，转换完成后用户侧说明将只保留安装版口径。
- 源码构建说明见助手包内 `dev/DEVELOPMENT.md`；助手源码与打包脚本不进本技能包。

## 目录
- SKILL.md                  主流程（触发/路由/规则摘要/单人15步与家庭13步入口/最终门禁）
- workflows/                规划流程 · 采购流程 · 降级流程
- references/               安全规则 · 问卷 · 输出契约 · 视觉规范 · 协议库 · 食材表 · 菜谱池 · 城市价格源
- data/                     结构化菜谱索引（当前已验证菜谱数量以 data/library-manifest.json 为准，不手工维护）· 包装规格 · 平替表 · 味型公式 · 时令食材
- scripts/                  营养计算 · 篮子生成 · 菜谱检索 · 多样性校验 · 采购汇总 · 价格归一化
- templates/                网页模板（月相图/环形图/时间轴）
