# 月食营养路由（nutrition-routing）

本文件是 SKILL.md 的拆分部分，承载饮食模式、周期协议、蛋白质四字段与营养门禁的完整规则。任何模式数字、阶段参数只以 `data/effective-parameters.json` 为唯一生产来源；本文件不重复保存参数数值。

## 两种饮食模式（参数以已批准来源为准，失败关闭）

> **来源状态说明（主从关系固定）**：`references/cycle-protocol.md` 负责人工审核、来源定位和解释性说明，**不供程序直接取数**；`data/effective-parameters.json` 由 approved 审计记录构建，是正式计算**唯一取值来源**；`book-extraction/nutrition-audit/parameter-build-report.md`（唯一路径）记录来源 rule_id、版本、哈希和一致性检查，供维护核对。维护者不得手工同时改两份数字：改数字必须走审计→构建→报告流程。只有同时满足 `source_verified: true` 且 `audit_status: approved` 的参数才参与正式计划计算。audit_status 为 needs_review、uncertain、source_not_found 或缺少状态字段时，不进入生产计算，按以下方式降级：
> 1. 不自动启用书籍特有饮食模式；
> 2. 不自动使用周期阶段对应的宏量参数；
> 3. 仅生成一般均衡饮食方案；
> 4. 禁食窗口采用经安全规则允许的最温和范围；
> 5. 对用户说明"书籍协议参数尚未完成来源核证，本次未自动使用"。
>
> **单一事实来源**：cycle-protocol.md = 参数权威来源；macros_calculator.py = 从 effective-parameters.json 读取并计算；本文件只描述模式含义，不重复保存参数数值。
>
> **周期协议执行口径**：周期协议参数满足 source_verified=true、audit_status=approved 且 source_rule_id 可追溯后，**方可进入计划计算**；实际执行仍须通过适用人群、周期信息完整性、断食经验、作息和 Skill 安全上限检查，协议参数与安全参数冲突时采用更保守值（见 safety-rules.md）。安全筛查前置条件（慢病/用药/妊娠等）保留，见"女性周期断食整合"。变更历史见 CHANGELOG.md。**任何输出不得把书籍观点表述为已获医学证明的结论**。

### 参数来源四分类（parameter_origin）

每个生产参数必须归入且仅归入一类，写入 effective-parameters.json 的 `parameter_origin` 字段：

1. `audited_book_protocol`：书籍协议参数，来源于已批准审计记录（如模式碳水/蛋白/脂肪参数、周期阶段参数），进入 effective-parameters.json 参与生产计算。
2. `skill_safety_policy`：月食自身安全策略参数，由 `references/safety-rules.md` 管理（断食起步时长、L1 分级上限、L2 医疗监督红线等），不依赖书籍审计。
3. `calculation_constant`：纯计算常数（每克碳水/蛋白质/脂肪热量、进食窗口 = 24 − 禁食时长等）。
4. `user_input`：用户提供的个体数据（身高体重、周期日期、预算等）。

**冲突裁决**：书籍协议参数与月食安全参数冲突时，**更保守的安全参数优先**，并在输出中说明原因（例：原书某阶段允许更长禁食，但安全分级上限更短时按安全上限执行）。

### 参数主源链（master-source chain）

审计批准记录（audit approved records）→ `references/cycle-protocol.md`（仅人工说明）→ 构建 `data/effective-parameters.json`（唯一机器可读生产源）→ `scripts/macros_calculator.py` 读取计算。每次构建由 `book-extraction/nutrition-audit/parameter-build-report.md` 记录 source_rule_id、协议版本、构建时间、文件哈希与一致性校验结果。

### 模式 A：酮生物饮食（keto-biologic）
- 净碳水：低碳水模式，以绿叶蔬菜等天然复杂碳水为主；上限数值从 effective-parameters.json 的 `keto_net_carb_cap_g` 读取
- 脂肪：优质脂肪为主要供能；下限从 `keto_fat_energy_min_pct` 读取
- 蛋白质参考上限：`keto_protein_reference_cap_g`（原书参考值，非硬执行，见下方蛋白质规则）

### 模式 B：平衡激素饮食（hormone-balance）
- 净碳水：中碳水模式，以根茎类与水果等天然复杂碳水为主（薯类、南瓜、山药、莲藕、玉米、糙米、豆类、低糖水果）；上限从 `hormone_net_carb_cap_g` 读取
- 优质脂肪按需摄入
- 蛋白质参考上限：`hormone_protein_reference_cap_g`（原书参考值，非硬执行）

**蛋白质规则**：书籍模式中的蛋白质参考上限从 `data/effective-parameters.json` 读取，仅用于提示，不作为无条件执行上限。**个体蛋白质基础需要优先于书籍参考值**——若个体目标高于书籍参考参数，按个体目标执行并说明原因；肾病或医嘱限蛋白者仅按医嘱执行。

**模式选择建议**：
- 健康成年人仅以一般减重、饱腹感或饮食偏好为目标时，可在安全门槛内选择模式 A 或 B（想减重快、偏低碳者倾向 A；以天然碳水为主者倾向 B）。
- 用户自述或已诊断存在胰岛素抵抗、糖尿病、低血糖、代谢疾病，或正在使用影响血糖的药物时，**不根据书籍规则自动分配模式**，转入慢病/用药路由（见 SKILL.md 安全筛查），仅按医嘱做菜单和采购适配。
- "女性养激素""长期低能量"等表述仅作为用户偏好或原书观点，不作为疾病判断。
- 孕产哺乳/青少年/体重过低 → 不启用模式。

**周期切换规则**：首次使用且为断食新手 → 整周采用单一温和模式，不跨日切换（但经前阶段"不安排延长禁食"的安全规则仍优先生效）；已执行至少一周且适应良好 → 按周期阶段逐日切换，跨阶段周分两段标注并预告下周。

## 女性周期断食整合（健康成年女性适用）

**启用条件（全部满足才启用精细周期切换）**：健康成年女性（无慢病诊断）；月经规律，周期 21–35 天；已提供周期天数与末次月经日期；周期阶段参数与禁食参数均为 audit_status: approved。周期阶段、模式及禁食窗口参数一律从 `data/effective-parameters.json` 的 approved 参数读取；原书协议的完整阶段表与精确数字见 `references/cycle-protocol.md`（仅作人工说明，程序不得直接读取）。

**安全筛查（命中任一即不启用周期协议）**：糖尿病（使用胰岛素或促泌剂）；正在服用抗凝药物；1 型糖尿病；既往进食障碍史；妊娠或哺乳期；BMI < 18.5 或近 3 个月体重下降超过 5%；医生明确告知不宜禁食的其他情况。命中时输出"你目前的情况不适宜执行周期禁食协议，建议在医生指导下确定合适的饮食模式"，转常规均衡饮食建议。**缺铁性贫血服用铁剂不属于禁食禁忌**，但铁剂应与餐同服或遵医嘱调整服药时间。

**周期降级（以下任一触发即整体降级，六触发五结果）**：
触发条件——①必需参数未批准；②周期长度超出协议已核证范围；③排卵时间不明确；④周期近期明显变化；⑤日期信息不足；⑥用户不希望做周期适配。
降级结果——①不自行按比例推算排卵期、不自动应用固定阶段天数；②整周使用单一温和饮食模式；③不安排延长禁食；④标记 `cycle_confidence: low`；⑤告知用户本周未启用精细周期协议。

- 禁食权限 L0/L1/L2（各档时长为 `skill_safety_policy` 参数，由 `references/safety-rules.md` 统一管理与取值；与书籍协议参数冲突时取更保守者）。
- 当前阶段计算：`python scripts/macros_calculator.py --cycle --last-period 上次月经开始日 --cycle-len 周期天数`；周计划按天切换，跨阶段周分两段标注并预告下周。
- 协议细节与十一本书精确数字见 `references/cycle-protocol.md`；书籍观点矩阵见 `references/book-consensus.md`（只作背景，不驱动方案）。

## 营养素目标计算（调脚本）

```
python scripts/macros_calculator.py --sex f --age 32 --height 165 --weight 55 --activity 1.4 --goal maintain --mode keto
```

- BMR 用 Mifflin-St Jeor；TDEE = BMR × 活动系数（久坐 1.2 / 轻 1.375 / 中 1.55 / 高 1.725）；减重 TDEE −15 至 20% 且不低于 BMR×1.1。
- **蛋白质四字段（固定判定口径）**：`safety_floor_g`（安全下限 = 体重 × 系数 0.8/1.0–1.2/增肌 1.2，低于即不合规）；`individual_target_g`（计划目标 = max(floor, preferred)）；`book_reference_g`（原书参考，从 effective-parameters.json 读取，**只提示偏离，不参与硬上限失败判断**）；`medical_limit_g`（医嘱上限，默认 null）。状态五档：`below_floor`（不合规）/ `below_target`（提示）/ `within_band`（达标）/ `above_band`（容差内，不失败）/ `above_medical_limit`（有医嘱上限时违规）。容差带由 `effective-parameters.json` 的 `protein_tolerance_pct` 统一管理。
- 脂肪供能 = 剩余热量；模式脂肪供能下限从 effective-parameters.json 读取。脂肪不足时：先查蛋白/碳水是否超标 → 总能量安全线内调整 → 适量食物来源脂肪；**不通过降总热量突破安全底线，不为凑比例大量添加黄油/防弹咖啡**。
- 女性经前一周/经期饥饿时：优先在模式上限内靠近上限安排碳水。"上浮 20%"为本技能派生的缓冲建议（audit_status=needs_review，无书籍出处），不作为自动计算规则；仅在用户自述经前饥饿时作为提示性建议并标注派生属性。

## 校验与下周迭代（无每日打卡）

1. 生成后跑 `scripts/macros_calculator.py --check 周计划食材明细.csv`，超标调整克数重算直到合规。蛋白质判定按四字段执行（见上）。
2. 不提供每日打卡 CSV 与打卡章节；用户**主动提供**的周后反馈照收（liked/disliked/unavailable/actual_cooking_time/leftovers 等，写入 `diet-plans/weekly_feedback.md`）。
3. **下周迭代**：下周菜单保留 1 至 2 道喜欢的熟悉菜 + 新增 3 至 4 道新菜；买不到的食材降权并走平替；剩余食材优先消耗。

## 营养超限的渲染前自动修正（禁止渲染后手改）

固定管线：**菜单草案 → 批量营养计算 → 自动微调克数 → 最终复核 → 冻结 plan.json → 渲染 HTML/PDF 等输出格式**。净碳水或蛋白不合规时，必须先自动微调食材克数并重算（最多两轮，见执行模式），复核通过后才允许冻结 plan.json；**禁止渲染完成后再人工减克数并重新修改输出文件**。所有自动调整必须记录：食材、前后克数、前后营养值、调整原因，写入内部日志。
