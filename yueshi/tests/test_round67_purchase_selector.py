# -*- coding: utf-8 -*-
"""round67（2026-09-18）：商品语义门禁与采购选择层回归。

断言（对应方案 §10/§16.3）：
- 猪里脊：牛小里脊 species_conflict rejected；物种不明的小里脊 review_required；
- 南瓜：脆片 snack_product rejected；混合粗粮包 composite_food rejected；
- 芹菜：芹菜香干 composite_food rejected；
- 带鱼：香煎/秘制预制带鱼 prepared_dish rejected；
- 豆腐：油豆腐 wrong_processing_state rejected；
- 全麦面包：白吐司 rejected；全麦吐司 title_claim 接受；
- 无糖酸奶：无候选 → fallback_to_estimate；
- 最终商品只从 accepted 中选，且记录与助手建议的差异原因。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import purchase_selector as ps  # noqa: E402
from product_semantics import evaluate_candidate, load_profiles  # noqa: E402

fails = []
profiles = load_profiles()
result = json.loads(open(os.path.join(ROOT, "data/golden/price-result-round67-sample.json"),
                         encoding="utf-8").read())
query = {"request_id": result["request_id"], "items": [
    {"ingredient_id": "猪里脊", "query": "猪里脊", "required_grams": 300},
    {"ingredient_id": "南瓜", "query": "南瓜", "required_grams": 330},
    {"ingredient_id": "芹菜", "query": "芹菜", "required_grams": 60},
    {"ingredient_id": "带鱼", "query": "带鱼", "required_grams": 200},
    {"ingredient_id": "无糖酸奶", "query": "酸奶", "required_grams": 550},
    {"ingredient_id": "全麦面包", "query": "面包", "required_grams": 40},
    {"ingredient_id": "豆腐", "query": "豆腐", "required_grams": 150},
]}
sel = ps.select_batch(result, query, profiles)


def item(name):
    return sel["items"][name]


def rejected_names(entry):
    return [r["product_name"] for r in entry["rejected"]]


def rejected_has(entry, part):
    return any(part in n for n in rejected_names(entry))


def rejected_reasons(entry, name_part):
    for r in entry["rejected"]:
        if name_part in r["product_name"]:
            return r["reasons"]
    return []


# 猪里脊
e = item("猪里脊")
if not e["final_selection"] or "猪小里脊" not in e["final_selection"]["product_name"]:
    fails.append("猪里脊最终选择应为猪小里脊：%s" % (e["final_selection"] or {}))
if not rejected_has(e, "牛小里脊"):
    fails.append("牛小里脊未被 rejected")
if "species_conflict" not in rejected_reasons(e, "牛小里脊"):
    fails.append("牛小里脊缺 species_conflict 原因")
if "精选小里脊 300g" not in (e.get("review_required") or []):
    fails.append("物种不明的精选小里脊应为 review_required")
if "species_conflict_rejected" not in e["change_reasons"]:
    fails.append("猪里脊未记录 species_conflict_rejected 差异原因")

# 南瓜
e = item("南瓜")
if "贝贝南瓜" not in e["final_selection"]["product_name"]:
    fails.append("南瓜最终选择应为鲜南瓜")
if "snack_product" not in rejected_reasons(e, "脆片"):
    fails.append("南瓜脆片缺 snack_product 原因")
if "composite_food" not in rejected_reasons(e, "粗粮包"):
    fails.append("粗粮包缺 composite_food 原因")

# 芹菜
e = item("芹菜")
if "香芹" not in e["final_selection"]["product_name"]:
    fails.append("芹菜最终选择应为香芹")
if "composite_food" not in rejected_reasons(e, "香干"):
    fails.append("芹菜香干缺 composite_food 原因")

# 带鱼
e = item("带鱼")
if "冷冻带鱼段" not in e["final_selection"]["product_name"]:
    fails.append("带鱼最终选择应为冷冻生带鱼段")
if "prepared_dish" not in rejected_reasons(e, "香煎"):
    fails.append("预制香煎带鱼缺 prepared_dish 原因")
if "prepared_dish" not in rejected_reasons(e, "秘制"):
    fails.append("预制秘制带鱼缺 prepared_dish 原因")

# 无糖酸奶
e = item("无糖酸奶")
if e["status"] != "fallback_to_estimate" or "fallback_to_estimate" not in e["change_reasons"]:
    fails.append("无糖酸奶无候选应 fallback_to_estimate")

# 全麦面包
e = item("全麦面包")
if "全麦吐司" not in e["final_selection"]["product_name"]:
    fails.append("全麦面包最终选择应为全麦吐司（title_claim）")
if not rejected_has(e, "白吐司"):
    fails.append("白吐司未被 rejected")
if "原味欧包 300g" not in (e.get("review_required") or []):
    fails.append("无全麦证据的原味欧包应为 review_required")
if "ordinary_price_preferred" not in e["change_reasons"] and \
        "product_form_correction" not in e["change_reasons"]:
    fails.append("全麦面包未记录与助手建议的差异原因")

# 豆腐
e = item("豆腐")
if not rejected_has(e, "油豆腐"):
    fails.append("油豆腐未被 rejected")
if "wrong_processing_state" not in rejected_reasons(e, "油豆腐"):
    fails.append("油豆腐缺 wrong_processing_state 原因")

# 门禁单元断言：别名命中不能单独接受
d, ev, rs = evaluate_candidate("小里脊 300g", profiles["猪里脊"])
if d != "review_required":
    fails.append("仅命中部位、物种不明的候选应为 review_required，实为 %s" % d)
d, ev, rs = evaluate_candidate("0蔗糖酸奶 135g", profiles["无糖酸奶"])
if d != "accepted" or (ev.get("attribute_evidence") or {}).get("no_added_sugar") != "title_claim":
    fails.append("0蔗糖酸奶应为 accepted(title_claim)：%s %s" % (d, ev))
d, ev, rs = evaluate_candidate("原味酸奶 100g", profiles["无糖酸奶"])
if d != "review_required":
    fails.append("原味酸奶（无糖证据不足）应为 review_required，实为 %s" % d)
# round67.1 实测修正：无蔗糖 = 无添加糖；卤水豆腐是凝固工艺不是预制菜；牛奶不触发物种冲突
d, ev, rs = evaluate_candidate("吾岛无蔗糖0乳糖酸奶 420g/桶", profiles["无糖酸奶"])
if d != "accepted":
    fails.append("无蔗糖酸奶应为 accepted，实为 %s（%s）" % (d, rs))
d, ev, rs = evaluate_candidate("有豆志卤水老豆腐 400g/份", profiles["豆腐"])
if d != "accepted":
    fails.append("卤水老豆腐应为 accepted，实为 %s（%s）" % (d, rs))
d, ev, rs = evaluate_candidate("黄油奶香麦皮香蕉牛奶味（6袋）60g", profiles["猪里脊"])
if d == "rejected" and "species_conflict" in rs:
    fails.append("牛奶不应触发物种冲突：%s" % rs)
# round68：混合调味酸奶不得当 plain 单品；0蔗糖为 title_claim；黑麦≠全麦
d, ev, rs = evaluate_candidate("君乐宝简醇0蔗糖酸奶(西柚脐橙燕麦爆珠）200g/瓶",
                               profiles["无糖酸奶"])
if d != "rejected" or not {"flavored_product", "mixed_composition"} <= set(rs):
    fails.append("混合调味酸奶应为 rejected(flavored/mixed)：%s %s" % (d, rs))
d, ev, rs = evaluate_candidate("0蔗糖酸奶 135g", profiles["无糖酸奶"])
if d != "accepted" or ev.get("evidence_level") != "title_claim":
    fails.append("0蔗糖酸奶应为 accepted + title_claim：%s %s" % (d, ev.get("evidence_level")))
d, ev, rs = evaluate_candidate("黑麦坚果切片欧包（5片装）180g", profiles["全麦面包"])
if d != "review_required":
    fails.append("仅黑麦不得自动满足全麦要求（应 review_required）：%s" % d)
d, ev, rs = evaluate_candidate("全麦吐司 400g", profiles["全麦面包"])
if d != "accepted" or ev.get("evidence_level") != "title_claim":
    fails.append("全麦吐司应为 accepted + title_claim：%s" % d)
# 选择层证据层级透传
sel_wm = ps.select_batch(result, {"items": [{"ingredient_id": "全麦面包", "required_grams": 40}]},
                         profiles, revalidate=True)
fs = sel_wm["items"]["全麦面包"]["final_selection"] or {}
if fs.get("evidence_level") != "title_claim" or "配料表" not in (fs.get("user_visible_note") or ""):
    fails.append("final_selection 未透传 evidence_level/提示：%s" % fs)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round67 商品语义门禁与采购选择层全部通过")
print("summary:", sel["summary"])
