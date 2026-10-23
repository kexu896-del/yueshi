# ADR-0005：测试密封性——跑测试不得改变工作树（round77）

- 状态：已接受
- 日期：2026-09-21

## 背景

回归套件里有一批"写库测试"，历史上直接改动工作树：

- 子进程运行 `release_pack.py` / `perf_baseline.py` / `build_breakfast_templates.py` / `recipe_release_gate.py`，
  把 `data/release-manifest.json`、`release-invariants.json`、`perf-baseline.json`、
  `breakfast-templates.json`、`library-manifest.json`、`audit/latest-audit.json`、
  `reports/release-summary.md` 写回仓库；
- 少数测试用 `open(w/ab)` 临时篡改文件（household-limits / render_html / recipe-index / taxonomy /
  review-overrides）再在 finally 还原；
- 存在跨测试顺序依赖（round44 读 round43 刚生成的 perf 基线）；
- 后果：任何人跑一次全量回归都会弄脏仓库（时间戳/基线/哈希被改写），发布前必须重新构建或手工还原；
  round76 的构建链 `--check` 也因此在同一棵树内"跑一遍测试就报错"。

## 决策

1. **沙箱化写库测试**：新增 `tests/sandbox.py` 的 `make_sandbox()`——把技能树复制到临时目录
   （排除 book-extraction 与缓存），进程退出自动删除。六个写库测试在启动时把 `ROOT/BASE`
   指向沙箱，所有读写与子进程都在副本内发生；生产脚本的默认写出路径不变（构建链写生产目录是生产行为）。
2. **消除跨测试依赖**：沙箱是完整数据副本（含 perf 基线等），每个测试独立、可单跑、可乱序。
3. **篡改式测试**：保留原有 finally 恢复逻辑，但发生在沙箱内——即使恢复失败也不污染仓库。
4. **不变量测试**：`tests/test_round77_test_hermeticity.py` 在真实树上对 `data/`、`reports/`、
   `scripts/` 做哈希快照，依次运行六个写库测试，断言仓库逐字节不变；并检查关键生成物哈希不变、
   六个测试均引用沙箱模块。
5. **范围边界**：本轮不改生产脚本的写出路径（不给 release_pack/perf_baseline/gate 增加
   `--out/--data-dir`）；脚本级可重定向留作可选后续。

## 后果

- **不变量**：任何测试运行后，工作树保持逐字节不变（test_round77 持续守护）。
- 写库测试可在本地随意重跑，不再需要"跑完重新构建"；round76 的 `build_library.py --check` 在测试后仍然成立。
- 新增会写文件的测试：必须 `from sandbox import make_sandbox` 并在沙箱内操作（维护地图测试节记录）。
- 沙箱每次复制整棵技能树（约 5MB，<1s）；测试总时长略增，换取可重复与可并行。
