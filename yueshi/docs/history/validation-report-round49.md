# 验证报告 round49（回传链路 + 助手发布修复）

日期：2026-08-26
基线：round48 已合并工作树（yueshi-1.2.1）

## 1. 测试

- 新增 test_round49_handoff_routing.py：7 断言全过
  （SKILL 回传链路 / 结果缺失路由 / 只回退价格层 / 不返回具体地址 /
   policy §4.1 / 路由器 unavailable·invalid_result 不判 fatal / 强制实时价 → user_input_required）。
- 全量回归：47/47 测试文件通过。

## 2. 助手冒烟（离线）

- 语法：gui/app/models/config/network_capture/page_fallback/build_exe 全部通过。
- INSPECT_ALLOWED 默认 False（未设 YUESHI_DEV）；RESULT_FILE 为 ASCII 名。
- looks_like_query：乱码文件名但内容合格的 JSON 判定为可载入；非清单 JSON 拒绝。

## 3. R01–R08 自评

| 门禁 | 状态 |
|---|---|
| R01 用户包只含 EXE+运行时+说明 | 构建脚本已保证（dist 只放 EXE/清单/使用说明）；待 Windows 构建验证 |
| R02 无 Python 干净环境可跑 | 待 Windows 构建后烟测（沙箱无法交叉编译） |
| R03 全程无终端窗口 | 代码层完成（CREATE_NO_WINDOW + pythonw + windowed 打包） |
| R04 不依赖固定中文名 | 完成，含乱码文件名自动识别 |
| R05 底层 ASCII | 完成 |
| R06 正式版无"侦察/inspect/GUI" | 完成（界面与日志零术语；inspect 需 YUESHI_DEV=1） |
| R07 生成有效 price-result.json 并提示拖回 | 完成（完成弹窗+摘要均提示） |
| R08 构建失败阻止发布 | 完成（build_exe.py 非零退出 + 产物存在性校验） |

## 结论

Skill 侧候选可合并；助手侧源码包修复完成，待 Windows 上构建并烟测 R01/R02。
