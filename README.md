# 月食（yueshi）——采购驱动的周期断食周饮食计划技能

## 这是什么
根据身体周期、采购渠道、当地价格和做饭条件，生成真正**买得到、做得完、吃得完**的一周饮食方案：
先定食材篮子（买什么），再从结构化菜谱库选菜（怎么做），最后反向汇总采购清单（怎么买）。
输出：7 天菜单 + 采购清单（食材、购买量、常见规格、参考价、平替、剩余去向）+ 营养校验；最终格式按用户单选（PDF/网页/Markdown/Word）。

## 怎么用（其他 AI）
1. 先把 `SKILL.md` 交给 AI 作为系统提示/知识库。
2. 让 AI 按其中"文件地图"读取 workflows/ 与 references/ 下的支撑文件。
3. 告诉 AI 核心五项信息：基本情况（性别年龄身高体重目标）/ 要避开的情况（慢病用药过敏忌口）/ 周期情况（仅女性）/ 吃饭做饭方式 / 买菜方式和预算。
4. `scripts/` 全部为纯 Python 标准库（无第三方依赖）：
   - `macros_calculator.py --sex f --age 28 --height 163 --weight 70 --goal lose --mode keto` → 营养素目标
   - `macros_calculator.py --cycle --last-period YYYY-MM-DD` → 周期阶段
   - `basket_builder.py --meals-per-day 1 --keto-days 2 --hormone-days 5 --month 8` → 食材篮子草案
   - `recipe_ranker.py --basket 鸡腿,鸡蛋,菠菜 --mode keto --max-minutes 25` → 候选菜谱
   - `diversity_checker.py menu.csv` → 菜谱指纹多样性校验
   - `shopping_aggregator.py --menu meals.csv --search-list out.csv` → 采购汇总+搜索清单
   - `market_price_normalizer.py prices.csv --city references/cities/nanjing-price-sources.yaml` → 菜场参考价
   - `wuyun_liuqi.py 2026-08-27` → 五运六气与时令

## 目录
- SKILL.md                  主流程（定位/优先级/安全路由/13步概览/模式硬规则/一人食/门禁）
- workflows/                规划流程 · 采购流程 · 降级流程
- references/               安全规则 · 问卷 · 输出契约 · 视觉规范 · 协议库 · 食材表 · 菜谱池 · 城市价格源
- data/                     菜谱索引(367道) · 包装规格 · 平替表 · 味型公式 · 当令食材
- scripts/                  营养计算 · 篮子生成 · 菜谱检索 · 多样性校验 · 采购汇总 · 价格归一化
- templates/                网页模板（月相图/环形图/时间轴）

## 安全声明
输出为一般性饮食建议，不构成医疗建议；孕产哺乳、未成年、慢病用药者请先咨询医生。
