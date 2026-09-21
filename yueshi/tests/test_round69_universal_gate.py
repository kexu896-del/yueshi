# -*- coding: utf-8 -*-
"""round69（2026-09-18）：通用商品四维门禁 + 酮生物模式金丝雀。

对应《月食yueshi-1.4.3通用商品门禁收口方案》§4/§5/§9/§12/§15：
- 统一四维结果：identity / composition / processing / attribute_evidence；
- 判定器不按品类硬编码分支（六类只作回归样本）；
- 父品类/别名使用关系类型（helper 源码探针）；
- 酮生物金丝雀：实际菜单满足净碳水、脂肪、热量、蛋白目标，采购需求与菜单一致。
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
from product_semantics import evaluate_candidate, load_profiles  # noqa: E402

fails = []
profiles = load_profiles()


def helper_src(*parts):
    """助手源码探针读取（兼容平铺 src/ 与嵌套 yueshi-dingdong-helper/src/ 两种布局）。"""
    base = os.path.join(ROOT, "..", "yueshi-dingdong-helper")
    cands = [os.path.join(base, *parts),
             os.path.join(base, "yueshi-dingdong-helper", *parts)]
    return open(next((p for p in cands if os.path.exists(p)), cands[0]),
                encoding="utf-8").read()


def ev_of(name, key):
    d, ev, rs = evaluate_candidate(name, profiles[key])
    return d, ev, rs


def dim(ev, key, field="status"):
    return (ev.get(key) or {}).get(field)


# ---------- 1) 四维统一结构（六类回归样本） ----------
# 身份冲突：牛小里脊
d, ev, rs = ev_of("国产谷饲冷鲜精修牛小里脊 300g", "猪里脊")
if d != "rejected" or dim(ev, "identity") != "conflict" or "species_conflict" not in rs:
    fails.append("identity 冲突未正确 rejected：%s %s" % (d, ev))

# 身份匹配 + 部位匹配：猪小里脊
d, ev, rs = ev_of("严选鲜切猪小里脊 约170g", "猪里脊")
if d != "accepted" or dim(ev, "identity") != "matched" \
        or dim(ev, "composition") != "single_ingredient" or dim(ev, "processing") != "ok":
    fails.append("猪小里脊四维结果异常：%s %s" % (d, ev))

# 结构冲突：混合调味酸奶
d, ev, rs = ev_of("君乐宝简醇0蔗糖酸奶(西柚脐橙燕麦爆珠）200g/瓶", "无糖酸奶")
if d != "rejected" or dim(ev, "composition") != "mixed_product":
    fails.append("composition 冲突（mixed_product）未正确：%s %s" % (d, ev))

# 结构冲突：南瓜脆片（零食）
d, ev, rs = ev_of("叮咚V5益生元南瓜脆片 50g/袋", "南瓜")
if d != "rejected" or dim(ev, "composition") != "snack":
    fails.append("composition 冲突（snack）未正确：%s %s" % (d, ev))

# 加工冲突：秘制即食带鱼（processing: seasoned/ready_to_eat）
d, ev, rs = ev_of("秘制即食带鱼 200g", "带鱼")
if d != "rejected" or dim(ev, "processing") != "excluded":
    fails.append("processing 冲突未正确：%s %s" % (d, ev))
# 结构冲突：预制菜（composition: prepared_dish）
d, ev, rs = ev_of("叮咚王牌菜香煎舟山带鱼 240g", "带鱼")
if d != "rejected" or dim(ev, "composition") != "prepared_dish":
    fails.append("composition 冲突（prepared_dish）未正确：%s %s" % (d, ev))

# 属性证据不足：仅黑麦 → review_required + other_grain
d, ev, rs = ev_of("黑麦坚果切片欧包（5片装）180g", "全麦面包")
if d != "review_required" or (ev.get("attribute_evidence") or {}).get("whole_grain") != "other_grain":
    fails.append("全麦证据不足未正确 review_required：%s %s" % (d, ev))

# 全维度通过：全麦吐司 → accepted + title_claim
d, ev, rs = ev_of("全麦吐司 400g", "全麦面包")
if d != "accepted" or (ev.get("attribute_evidence") or {}).get("whole_grain") != "title_claim" \
        or ev.get("evidence_level") != "title_claim":
    fails.append("全麦吐司四维结果异常：%s %s" % (d, ev))

# round69 实测修正：紧跟「味」的属性词是风味声明，不算原料证据
d, ev, rs = ev_of("全麦味大列巴 300g", "全麦面包")
if d != "review_required" or (ev.get("attribute_evidence") or {}).get("whole_grain") != "unknown":
    fails.append("「全麦味」不得当作全麦证据：%s %s" % (d, ev))
d, ev, rs = ev_of("杂粮坚果味全麦吐司 300g", "全麦面包")
if d != "accepted":
    fails.append("含真实「全麦吐司」字样应 accepted：%s" % d)

# 豆腐单一原料：卤水老豆腐 accepted
d, ev, rs = ev_of("有豆志卤水老豆腐 400g/份", "豆腐")
if d != "accepted" or dim(ev, "composition") != "single_ingredient":
    fails.append("豆腐原料四维结果异常：%s %s" % (d, ev))

# ---------- 2) 判定器无品类硬编码分支 ----------
sem_src = open(os.path.join(ROOT, "scripts", "common", "product_semantics.py"),
               encoding="utf-8").read()
branch_hits = []
for i, line in enumerate(sem_src.splitlines(), 1):
    code = line.split("#", 1)[0]
    if not re.match(r"\s*(if|elif|else|for|while)\b", code):
        continue
    if any(k in code for k in ("酸奶", "面包", "豆腐", "猪里脊", "南瓜", "带鱼", "ingredient")):
        branch_hits.append("L%d: %s" % (i, line.strip()[:100]))
if branch_hits:
    fails.append("判定器出现品类/ingredient 硬编码分支：%s" % branch_hits[:3])

# helper 端同样探针（判定器不得按品类分支）
helper_semantics = helper_src("src", "semantics.py")
for i, line in enumerate(helper_semantics.splitlines(), 1):
    code = line.split("#", 1)[0]
    if re.match(r"\s*(if|elif)\b", code) and any(
            k in code for k in ("酸奶", "面包", "豆腐", "猪里脊", "南瓜", "带鱼")):
        fails.append("助手判定器出现品类硬编码：L%d %s" % (i, line.strip()[:80]))

# ---------- 3) 概念关系类型（helper 源码探针） ----------
helper_app = helper_src("src", "app.py")
for needle in ("parent_category_query", "search_recall_only", "relation_type"):
    if needle not in helper_app:
        fails.append("助手概念关系缺：%s" % needle)
if '"type": "new_alias"' in helper_app:
    fails.append("助手仍把父品类写入 new_alias")

# ---------- 4) 酮生物模式金丝雀 ----------
canary = json.load(open(os.path.join(ROOT, "data", "golden", "keto-canary-menu.json"),
                        encoding="utf-8"))
FT = json.load(open(os.path.join(ROOT, "data", "foods-table.json"),
                    encoding="utf-8"))["foods"]
tot = {"nc": 0.0, "p": 0.0, "f": 0.0, "kcal": 0.0}
demand = {}
for meal in canary["meals"]:
    for ing in meal["ingredients"]:
        food, g = ing["food"], ing["grams"]
        if food not in FT:
            fails.append("金丝雀食材不在 foods-table：%s" % food)
            continue
        n = FT[food]
        tot["nc"] += n["net_carbs"] * g / 100
        tot["p"] += n["protein"] * g / 100
        tot["f"] += n["fat"] * g / 100
        tot["kcal"] += n["kcal"] * g / 100
        demand[food] = demand.get(food, 0) + g
tg = canary["targets"]
fat_pct = tot["f"] * 9 / tot["kcal"] * 100 if tot["kcal"] else 0
if tot["kcal"] < tg["calories_safety_floor_kcal"]:
    fails.append("金丝雀热量低于安全线：%.0f" % tot["kcal"])
if tot["nc"] > tg["net_carb_max_g"]:
    fails.append("金丝雀净碳水超上限：%.1f" % tot["nc"])
if fat_pct < tg["fat_min_energy_pct"]:
    fails.append("金丝雀脂肪供能不足：%.1f%%" % fat_pct)
if tot["p"] < tg["protein_safety_floor_g"]:
    fails.append("金丝雀蛋白低于基础需要：%.1f" % tot["p"])
# 采购需求与菜单一致：每个菜单食材进入需求且总克数>0
menu_foods = {i["food"] for m in canary["meals"] for i in m["ingredients"]}
if set(demand) != menu_foods or any(v <= 0 for v in demand.values()):
    fails.append("采购需求与菜单不一致：%s vs %s" % (sorted(demand), sorted(menu_foods)))

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round69 通用四维门禁 + 酮生物金丝雀全部通过")
print("canary: kcal=%.0f nc=%.1f fat%%=%.1f protein=%.1f" % (
    tot["kcal"], tot["nc"], fat_pct, tot["p"]))
