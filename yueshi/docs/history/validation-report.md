# round 40 验证报告

- 日期：2026-08-25
- 基线：round39 合并版（yueshi.skill 828,129 bytes）
- 依据：《月食家庭版v0.3 RC2修改意见整合》+ 5 份 household schema

## 测试
- tests/test_household_rc2.py：12/12 通过（8 组 golden cases + 冻结清单负向用例）
- tests/test_household_skill_routing.py：6/6 通过
- 全量回归：39 个测试文件全部通过
- 冒烟：8 组案例逐一通过 bundle Schema 与引用校验器（CLI 退出码 0）

## 关键验证点
1. 修正 schema 的 not/required 多字段语义缺陷后：external_meal 单带 leftover_plan_id、after_shopping 带 shopping_delta、present_confirmed 带 action 均被拦截 ✅
2. 8 组 golden cases 全部通过 ✅
3. 三人比例 selected_pct 偏离 100 → SELECTED_PCT_SUM_EQUALS_100 fail ✅
4. base 混入 effective_meta → schema 失败 ✅
5. L3 无 gate 覆盖 / gate 不满足分锅 → schema + 脚本双层拦截 ✅
6. SKILL.md 四 plan_mode 路由 + locked_basket 分级 ✅

## 说明
- RC2-6（渲染器适配 household schema、迁移映射、性能基线）按文档顺序未在本轮范围；当前渲染器仍只渲染单人 plan.json，家庭版数据层（schema+校验器+案例）已就绪。
- 未合并；等待确认后执行合并打包。
