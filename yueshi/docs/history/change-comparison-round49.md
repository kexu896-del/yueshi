# 变更对照 round49（回传链路与结果缺失路由 + 助手发布修复适配）

依据：《月食叮咚查价助手_发布失败问题与修改意见.docx》§七（Skill/README 改动）。
基线：round48 已合并的 yueshi-1.2.1 工作树。

## Skill 侧文件级对照

| 文件 | 变更 | 说明 |
|---|---|---|
| `SKILL.md` | 修改 | Provider 摘要：返回字段改为"商品候选、规格、页面价格、可售状态、用户确认状态与查询时间"，明确不读取/不返回具体收货地址；新增回传链路（price-query.json → 本机查价 → price-result.json 上传回对话，无自动上传通道）；新增结果缺失路由（未上传有效结果不得声称已取得叮咚直采价；强制实时价 → user_input_required）；价格失败只回退价格层。 |
| `references/price-provider-policy.md` | 修改 | 新增 §4.1 结果缺失路由（Skill 侧硬约束），与 SKILL 摘要一致。 |
| `CHANGELOG.md` | 修改 | 新增 round49 条目。 |
| `tests/test_round49_handoff_routing.py` | 新增 | 2 组 7 断言（回传链路文本 / 缺失路由文本 / 无地址返回 / 路由器行为回归）。 |

## 助手侧（v1.3.1，不进本包，zip 另行交付）

按评审 §二–§六修复：

- **R05 底层 ASCII 化**：price-query.json / price-result.json / diagnostics.json；中文只留在界面文案与最终 EXE 显示名。
- **乱码根因修复**：build-exe.bat 改纯 ASCII 壳，中文打包逻辑（PyInstaller --name、add-data）移入 `build_exe.py`（Python 文件无 cmd 代码页问题）；install-deps.bat / start-gui.bat 保持纯 ASCII。
- **R04 输入不依赖固定中文名**：拖到 EXE（argv）/「选择查价清单」对话框 / 目录内自动识别任何含 request_id+items 的 JSON（兼容解压乱码文件名）；结果写到清单旁边。
- **开发模式代码层隔离**：`config.INSPECT_ALLOWED` 需环境变量 YUESHI_DEV=1；正式构建 build_exe.py 强制移除该变量；界面不出现"侦察/inspect/GUI"等术语，开发者菜单仅 YUESHI_DEV=1 时显示；正式入口 inspect_mode 恒为 False。
- **R03 无终端**：GUI 子进程统一 CREATE_NO_WINDOW；vbs/pythonw 静默启动不变。
- **日志规则**：用户日志只写业务文字；技术堆栈写入 logs/last-error.txt，界面给可行动提示。
- **README/DEVELOPMENT 拆分**：README 只保留普通用户六件事；源码运行/构建/inspect 全部移入 DEVELOPMENT.md。
- **R08**：build_exe.py 任一步失败非零退出，不留空 dist。

## 未做（环境限制，如实说明）

- **正式用户包（预构建 windowed EXE）必须在 Windows 上构建**，本沙箱无法交叉编译 Windows EXE。当前 zip 为**修复后的源码包**；在你电脑上跑一次 `install-deps.bat` + `build-exe.bat` 即可产出正式用户包 `dist\月食叮咚查价助手\`，此后分发的只是 dist 文件夹（符合"正式用户不运行构建脚本"的要求——构建者是你/维护者，不是最终用户）。
- R02 干净环境烟测需在无 Python 的 Windows 机器上执行。

## 回归

- tests/ 全量 47 个测试文件通过（含 round49 新增 7 断言）。
