# 采购流程（购买量 · 规格 · 平替 · 所在地公开市场价）

> 线上平台历史逻辑已全部删除：不再区分线上线下来源，无叮咚/盒马/开放平台配置，无线上库存与售价类字段，无策略三选一与订单拆分门槛。采购模块只负责：菜单实际需求量、建议购买规格、平替与剩余去向、所在地公开市场参考价预算。**正式采购表只含最终菜单实际使用的食材**；预选后未使用的食材（含 accepted_batch 未入选项）不作为数据行，只在"执行提示"一行说明真实原因与可替换方案。

## 1. 收集项（仅两项）

- 所在城市（问卷第 1 项"所在地区"）
- 每周预算（问卷第 6 项）

## 1.1 餐次采购范围门禁（B01–B02，round60；round61 改为可修复门禁）

- **B01 [auto_fix]**：`meal_plan_mode = planned` 且 `include_in_procurement = true` 的餐次，其食材**必须进入反向采购汇总**；不得因 `preparation_mode = quick_self_prepare`（"自己简单解决"）而降级为 guidance_only 或从采购中删除。**遗漏时重新执行该餐次的采购汇总和数量校验**（非终止），并同步更新 `shopping_demand_hash`。
- **B02 [auto_fix]**：任何餐次从 `planned` 改为 `guidance_only` / `excluded`，必须有用户原话或明确 reason_code；**"简单、快手、随便做"不是合法降级理由**。无合法依据时**恢复为 planned** 并重新执行该餐次的营养与采购校验；恢复后仍缺用户信息则转 `user_input_required`。
- **升级路径**：B01/B02 均不直接判 fatal；自动修复两轮仍失败时，统一升级为 `fatal_reason = auto_fix_retry_exhausted`。运行记录对每次降级判定写入早餐语义审计（`meal_semantic_audit`：`user_phrase` / `meal_type` / `meal_plan_mode` / `preparation_mode` / `include_in_nutrition` / `include_in_procurement`）。
- 语义映射表见 `references/runtime-rules.md`「餐次语义映射表」；`preparation_mode = external_purchase`（在外买）不计入家庭食材采购，可单列外购说明。

## 2. 采购清单（默认输出）

每种食材输出（契约见 `references/output-schema.md`）：

```
ingredient            食材标准名
purchase_name         常用购买名称（口语化+规格，如"冰鲜鸡腿 400g"）
required_quantity     菜单实际需求量
acceptable_package    常见购买规格（来自 data/package-rules.json）
reference_price       参考价（有可靠来源时）
substitutes           平替（来自 data/substitutions.json）
leftover_action       剩余去向
```

- `purchase_name` 规则：最短口语词，规格写进词里；买不到时逐级放宽（去规格→换品类词→用 substitutes）。
- **用户可见采购表只显示**：食材｜需要量｜建议购买规格｜参考价｜平替（剩余去向）。技术字段（price_confidence/price_type/budget_included/归一化过程/来源数）只保存在内部日志，不出现在 PDF 或 Word。
- 不承诺即时库存与即时价格。

## 3. 价格计算（所在地公开市场价，两层）

### 第一层：标准参考单价
统一归一为 `元/500g`（计件品类用 元/个、元/盒、元/袋）。公开市场价由 `scripts/market_price_normalizer.py` 归一化：单位换算、多来源加权、区间、异常值剔除、过期标记、批发价单独标注。

### 第二层：本周预计支出
> 预计支出 = 建议购买包装数 × 单包装价格（不按菜单净克数）

### 价格置信度门禁

- **high/medium**：当地公开近期市场零售价格等可靠来源，可进预算合计
- **low**：只显示参考区间（budget_included=false）
- **unavailable**：不输出金额、不计入总价、**不虚构数字**

每条价格带 `price_confidence`/`price_type`/`budget_included` 三字段；range 且 budget_included=true 时预算校验按区间上限。

**用户文件中的价格呈现**：采购清单逐项列出具体参考价（元/规格）与本周预计支出合计；**不出现"以实际成交价为准""实价为准"字样**。部分食材无可靠价格时另加一行："部分食材暂无可靠参考价，未计入预算总额"。政府部门名称、数据日期、单位、区间门禁、数据源数量与置信度只保存在内部日志，不进入用户版文件。

城市数据源配置在 `references/cities/<城市>-price-sources.yaml`（现有南京样板）；新增城市复制 yaml 换本地公开价格栏目。

## 4. 缺货替换闭环

发现主食材缺货时：

1. 从 `data/substitutions.json` 选同功能替代品
2. 检查替代品是否符合忌口、宗教和饮食模式
3. **按营养等价替换，不是同重量替换**
4. 重新计算该餐营养
5. 重新计算采购量与包装余量
6. 重新计算预计价格
7. 检查替换后是否破坏菜谱多样性（`scripts/diversity_checker.py`）
8. 全部门禁通过后才更新采购清单

两个平替都不可用 → 替换整道菜，不强行保留原菜名。
