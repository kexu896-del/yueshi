# round44 验证报告

## 新增测试

tests/test_round44_release_hardening.py：8 组 41 断言，全部通过。

- T01 版本 1.1.0：SKILL/golden 同步、数据契约 const 维持 v0.3-rc2
- T02 载荷扫描：干净包通过；book-extraction 路径 / .epub / .jsonl 注入均命中
- T03 运行文件引用扫描 0 命中；发布策略与四条硬门禁在 maintenance-map；维护区路径集中登记
- T04 依赖闭包完整（当前包 0 缺失）；人为移除 SKILL.md 即失败
- T05 可复现构建：两次构建 SHA-256 一致、固定时间戳
- T06 家庭渲染：成员标签/份量块/三本账渲染、4 个内部术语零出现、缺席成员不进份量行
- T07 发布链路全通：exit 0、manifest 13 个审计字段齐、可复现=真、扫描 0 命中、闭包通过、烟测 7 步全过且含 family_effective_render 与 release_hygiene
- T08 性能基线含 family_effective_render 节点

## 全量回归

42 个测试文件全部通过（pass=42 fail=0）。

四处预期联动（非回归）：round31 参数报告措辞、round37 定版断言切 1.1.0、round41 版本断言动态化、round43 T07 manifest 结构——均为本轮意见直接要求的变更。

## 发布验证（候选内实测）

- release_pack 全链路 exit 0；硬门禁 0 触发；7 步烟测全过
- reproducible_build=true；双产物 sha256 一致
- 载荷扫描 / 引用扫描 / 依赖闭包全过

## 冻结状态

意见§六冻结清单 8 项全部满足，版本已切 yueshi-1.1.0。本轮合并打包后即为正式版构建。
