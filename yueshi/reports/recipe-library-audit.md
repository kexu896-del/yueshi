# 菜谱库覆盖审计报告

## 本次审计结论：passed_with_warnings

### 警告问题

- soft_cross_category_clusters_for_review

### 质量指标（生产准入口径）

- dish_category_coverage：1.0
- primary_ingredient_family_coverage：0.9981
- primary_protein_family_coverage：1.0
- classification_sample_accuracy：0.9829
- cross_category_cluster_count：0
- severe_protein_mislabel_count：0
- low_confidence_count：3
- low_confidence_reviewed_count：3
- unparseable_isolated_count：15
- exact_duplicate_recipes：0
- diversity_duplicate_recipes：497

### 是否满足生产准入门槛

是（见 recipe_release_gate.py 判定）

### 与上一版比较

- total_recipes：1576 → 1576
- parseable_recipes：1571 → 1571
- missing_primary_family：390 → 390
- high_duplicate_recipes：338 → 338
- dish_category_coverage：1.0 → 1.0
- primary_ingredient_family_coverage：0.9981 → 0.9981
- primary_protein_family_coverage：1.0 → 1.0
- classification_sample_accuracy：0.9829 → 0.9829
- cross_category_cluster_count：1 → 0

### 修复清单产物

- reports/recipe-unparseable.csv（不可解析隔离）
- reports/recipe-low-confidence.csv（低置信度人工复核队列）
- reports/recipe-classification-fixes.csv（自动修复记录）
- reports/recipe-duplicate-review.csv（精确重复簇复核）
- reports/recipe-missing-tags.csv（缺菜系/季节标签清单）

> 生成方式：scripts/recipe_library_auditor.py 离线统计（生产池：recipe-index.json + book-recipes.json；分类与指纹：recipe-classification.json / recipe-fingerprints.json）；启发式口径见脚本 docstring。

## 缺口判读（自动启发式）

- 菜系标签整体缺失：增加书籍不会改善菜系多样性，应先补结构化标签
- 季节标签整体缺失：时令评分无法落到菜谱层，应先补标签（与 S01–S04 联动）
- 主蛋白族 lamb 覆盖偏少（6 道）
- 主蛋白族 beef 覆盖偏少（5 道）
- 指纹重复度高：338 道可被簇去重压掉（占 21%），候选数量存在虚高
- 390 道缺主要食材族标注，指纹与多样性门禁对它们失效

## 总量与完整性

- 总菜谱数：1576
- 可解析菜谱数：1571（不可解析 5）
- 缺来源：0
- 缺烹法标签：0
- 缺菜系标签：1576
- 缺季节标签：1576
- 缺主要食材族：390
- 近似指纹簇数量：154
- 高度重复菜谱数量（指纹簇内可被去重压掉）：338

## 覆盖分布

### 主蛋白族

- egg：214
- poultry：77
- soy：69
- pork：53
- shellfish：50
- fish：36
- lamb：6
- beef：5

### 烹法

- 煮：797
- 炒：595
- 烤：485
- 凉拌：435
- 炖：357
- 蒸：243
- 卤：234
- 腌：224
- 煎：136
- 炸：136
- 调制：33
- 冷藏定型：18
- 烧：12
- 煲：11
- 焖：8
- 烩：2
- 白灼：2
- 烘焙：2

### 菜系

- （无菜系标签数据）

## 适用性覆盖（启发式）

- 快手菜（active ≤15min）：369
- 一人食适用：752
- 家庭模式适用：118

## 来源分布

- howtocook：365
- 川菜（扶霞·邓洛普）：156
- The Ultimate Cooking for One Cookbook：144
- 鱼米之乡（扶霞·邓洛普）：143
- One: Simple One-Pan Wonders (Jamie Oliver)：124
- The Complete One Pot (America's Test Kitchen)：108
- Dinner in One (Melissa Clark)：101
- 一人锅：一个人的小锅料理（小田真规子）：96
- One Pot, One Portion (Eleanor Wilkinson)：95
- Vietnamese Food Any Day (Andrea Nguyen)：83
- 够味儿：80道经典家常菜烹饪详解：80
- Vietnamese (Uyen Luu)：76

## 前 10 个近似指纹簇（去重收益最大的簇）

- `none|other|炒|咸鲜|快炒` × 20：辣椒炒肉、油泼辣子、蔗糖糖浆、耙耙柑茶、口水鸡
- `none|other|炖+煮||汤锅` × 20：柑橘醋风味生姜家常锅、腌鲑鱼乡土石狩锅、温暖浓稠涮涮锅、牛蒡牛肉柳川锅、芝麻豆浆猪肉涮涮锅
- `none|other|调制|咸鲜|饮品` × 11：印度奶茶、可乐桶、奶茶、杨枝甘露、长岛冰茶
- `egg|other|烤|奶香+清淡+酸甜口|烤/焗` × 11：Cardamom Sour Cream Pound Cake、Ricotta Olive Oil Pound Cake、Tender Chocolate Coconut Cake、Easy Chocolate Fudge Torte、CHOCOLATE PARTY CAKE
- `none|other|烤|奶香+清淡+酸甜口|烤/焗` × 11：LEMON BREAD + BUTTER PUDDING、BAKED PEACHES WITH CARAMEL SAUCE、CHOCOLATE CHIP COOKIE SKILLET、APPLE TARTE TATIN、APPLE CRUMBLE
- `soy|other|炖+煮||汤锅` × 10：山药泥豆浆锅、鸡肉末青菜蛋花汤锅、柚子胡椒风味鳕鱼锅、金枪鱼韭菜豆腐锅、豆腐小银鱼海苔锅
- `none|other|煮|奶香+酸甜口|汤/煮` × 9：GINGER + LIME POACHED PEAR、CARDAMOM + COCONUT RICE PUDDING WITH MANGO、BANOFFEE PIE MILKSHAKE、MAPLE NUT GRANOLA、Spinach and Cheese Quesadilla
- `none|oil|煮|奶香+蒜香+酸甜口|汤羹` × 8：Orzo Minestrone with Fresh Corn, Zucchini, and Pesto、Creamy Carrot Soup、French Onion Soup、Chicken with Creamy Paprika Sauce、Beef Stroganoff
- `none|other|炒|咸鲜|主食` × 7：手工水饺、炒河粉、凉粉、披萨饼皮、烙饼
- `none|other|烤|奶香+蒜香+酸甜口|烤/焗` × 7：Sheet Pan Thanksgiving: Roast Turkey Breast, Maple-Glazed Sweet Potatoes, and Brussels Sprouts、Roasted Tuna with Brown Butter Corn, Tomatoes, and Chile、Roasted Garlic Cauliflower、Roasted Broccoli、Baked Chicken Tenders
