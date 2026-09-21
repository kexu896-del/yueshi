# round44 变更对照（发布链路定稿 + 版本切换 yueshi-1.1.0）

依据：《月食_round43发布链路与RC2改进意见.docx》。评审结论"round43 可继续作为 RC2 冻结基线"下的最终收口。

## P0

| 意见 | 落实 |
|---|---|
| 反向泄漏扫描 | release_pack 包后载荷扫描：包内出现 book-extraction 路径 / 电子书文件（.epub/.mobi/.azw/.azw3）/ .jsonl 提取缓存 → 构建失败（不告警）；T02 正负向用例锁定 |
| 运行依赖闭包显式验证 | dependency_closure()：SKILL 反引号路径引用 + PIPELINE_COMPONENTS + 哈希输入 + Schema/golden 清单；包内逐项存在性检查，缺件即失败（T04 含人为缺件负向用例） |

## P1

| 意见 | 落实 |
|---|---|
| manifest 记录排除策略 | excluded_paths / exclusion_reason / runtime_dependency=false / source_retention_policy + 全部审计字段（build_source、build_tool_version、created_at UTC、package_file_count、uncompressed_size_bytes、smoke_steps、runtime_dependency_check、copyright_payload_scan、reproducible_build、size_reduction_note） |
| 烟测缺家庭最终渲染 | 第 6 步 family_effective_render：新增 household_components.render_household_html（统一渲染器家庭入口最小实现，直接消费 validated effective_plan；成员营养块/份量块/三本账；断言无内部术语）；第 7 步 release hygiene |
| 正式包与维护包边界 | maintenance-map 新增「发布与维护区策略」：repo-only（book-extraction/、candidates/、__pycache__、scripts/extract_* 维护提取工具）/ release-only 分类、维护区路径集中登记、四条硬门禁、唯一发布入口；references 与 effective-parameters 中的维护性提法改指 maintenance-map；library-manifest 路径属来源隔离登记元数据（豁免并书面记录） |
| 可复现构建 | zip 固定排序/时间戳/权限位/压缩参数；每次发布自动重复构建两次校验 SHA-256 一致（T05） |
| 包体变化记录比例 | size_reduction_note："仅移除非运行期维护材料，无运行依赖变化" |

## 版本正式化

- SKILL frontmatter 与 golden 样例 plan_meta 统一 `yueshi-1.1.0`；数据契约 plan_schema_version 维持 const "v0.3-rc2"（契约版本与技能版本独立）。
- round43 T01 改为与 frontmatter 同源动态断言（以后切版不再改测试）。

## 冻结清单（意见§六）对照

统一渲染器消费 effective_plan ✅（最小家庭渲染 + 包内断言）｜迁移映射四部分 ✅（round43）｜性能基线分段 ✅（+family_effective_render 节点）｜release_pack 唯一发布入口 ✅（写入维护策略）｜闭包+载荷扫描 ✅｜重复构建一致 ✅｜版本统一切换 ✅｜rc2 manifest 追溯 ✅（CHANGELOG + 历史 manifest 口径）

## 联动更新（非回归）

round31（参数报告路径措辞）、round37（定版断言→1.1.0）、round41（版本断言动态化）、round43 T07（manifest 结构 5→7 步）。
