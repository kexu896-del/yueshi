# -*- coding: utf-8 -*-
"""round73（2026-09-21）：商品语义判定单一来源化。

断言：
- 词表唯一来源 data/commodity-vocabulary.json（product_semantics 只持有逻辑）；
- judge_candidate 合并了 purchase_selector._decision_for 与 run_price_regression._decision_of；
- 助手快照由导出脚本生成、与主库逐值一致、且已提交的快照新鲜；
- 行为对拍：同一商品名在技能侧与助手侧判定结果一致（含「全麦味」守卫回归）；
- 形态识别对拍：detect_forms 两侧一致（否定前缀/整块守卫）；
- 助手源码不在位时相关探针 SKIP（exit 0），在位时硬校验。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from product_semantics import (load_vocabulary, load_profiles, evaluate_candidate,  # noqa: E402
                               judge_candidate, SPECIES_TERMS, NO_SUGAR_TERMS,
                               WHOLE_WHEAT_TERMS)
from product_forms import detect_forms, load_catalog, load_dictionary  # noqa: E402
from export_helper_semantics import build_snapshot, render  # noqa: E402
import probe_common as pc  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# ---------- 1) 词表唯一来源 ----------
vocab = load_vocabulary()
check(vocab.get("vocabulary_version") == "1.0.0", "词汇契约版本应为 1.0.0")
for key in ("no_sugar_terms", "whole_wheat_terms", "species_terms", "category_terms",
            "composite_terms", "fried_terms", "seasoned_terms", "ready_to_eat_terms",
            "flavor_mix_terms", "processing_state_forms"):
    check(vocab.get(key), "词汇契约缺 %s" % key)
check(SPECIES_TERMS == vocab["species_terms"], "product_semantics 物种词表须来自词汇契约")
check(NO_SUGAR_TERMS == vocab["no_sugar_terms"], "product_semantics 无糖词表须来自词汇契约")
check(WHOLE_WHEAT_TERMS == vocab["whole_wheat_terms"], "product_semantics 全麦词表须来自词汇契约")

# ---------- 2) judge_candidate 合并 ----------
ps_src = open(os.path.join(ROOT, "scripts", "purchase_selector.py"), encoding="utf-8").read()
rr_src = open(os.path.join(ROOT, "scripts", "run_price_regression.py"), encoding="utf-8").read()
check("def _decision_for" not in ps_src, "purchase_selector 不得再定义 _decision_for")
check("def _decision_of" not in rr_src, "run_price_regression 不得再定义 _decision_of")
cand = {"product_name": "猪小里脊 300g", "candidate_decision": "accepted", "evidence": {"x": 1},
        "rejection_reasons": []}
d, ev, rs = judge_candidate(cand, None)
check(d == "accepted" and ev == {"x": 1}, "judge_candidate 透传助手判定")
profiles = load_profiles()
d2, _, rs2 = judge_candidate({"product_name": "香煎猪小里脊"}, profiles["猪里脊"]["acceptance_profile"],
                             revalidate=True)
check(d2 == "rejected" and "wrong_processing_state" in rs2, "judge_candidate 重评路径")
d3, _, _ = judge_candidate({"form_match": "rejected"}, None)
check(d3 == "rejected", "judge_candidate 旧字段保守回退")

# ---------- 3) 快照内容与新鲜度 ----------
snap = build_snapshot()
check(snap["catalog"]["version"] == load_catalog()["catalog_version"], "快照目录版本=主库")
check(snap["form_dictionary"]["version"] == load_dictionary()["form_dictionary_version"],
      "快照形态版本=主库")
zlj = snap["catalog"]["rules"]["猪里脊"]
check("marinated" in zlj["excluded_states"] and "marinated_ready" not in zlj["excluded_states"],
      "猪里脊 marinated_ready 已改名 marinated")
check("炸" in zlj.get("hard_excluded_terms", []), "猪里脊 hard 词已回填")
check("腊鸡腿" in snap["catalog"]["rules"]["鸡腿"].get("hard_excluded_terms", []), "鸡腿 hard 词已回填")
check("卤蛋" in snap["catalog"]["rules"]["鸡蛋"].get("hard_excluded_terms", []), "鸡蛋 hard 词已回填")
check("地瓜叶" in snap["catalog"]["rules"]["红薯"].get("hard_excluded_terms", []), "红薯 hard 词已回填")
raw_kw = snap["form_dictionary"]["forms"]["raw"]["keywords"]
check("生" in raw_kw, "raw 形态须含「生」")
frozen_kw = snap["form_dictionary"]["forms"]["frozen_raw"]["keywords"]
check(set(frozen_kw) == {"冷冻", "速冻", "冻品"}, "frozen_raw 词表须与主库一致")

committed = pc.read_helper("semantics-snapshot.json")
if committed is None:
    pc.skip("助手快照不在位（%s）" % os.path.join(ROOT, "..", "yueshi-dingdong-helper"))
else:
    check(render(snap) == committed, "助手快照陈旧：主库已变，请重跑 export_helper_semantics.py")

# ---------- 4) 行为对拍（助手源码在位时；round75 经 probe_common） ----------
hsem = pc.load_helper_module("helper_semantics_r73", "semantics.py")
hcfg = pc.load_helper_module("helper_config_r73", "config.py")
if hsem is None or hcfg is None:
    pc.skip("助手源码不在位，跳过行为对拍（%s）" % os.path.join(ROOT, "..", "yueshi-dingdong-helper"))
else:
    GOLDEN = [
        ("0蔗糖低GI草原酸奶300g", "无糖酸奶"),
        ("0蔗糖酸奶（西柚脐橙燕麦爆珠）", "无糖酸奶"),
        ("无糖酸奶（果粒）", "无糖酸奶"),
        ("全麦坚果大列巴面包 300g/份", "全麦面包"),
        ("全麦味大列巴 300g", "全麦面包"),
        ("黑麦欧包 300g", "全麦面包"),
        ("白吐司 400g", "全麦面包"),
        ("【非转基因大豆】卤水老豆腐 400g/份", "豆腐"),
        ("香干 200g", "豆腐"),
        ("严选鲜切猪小里脊 约170g", "猪里脊"),
        ("国产谷饲冷鲜精修牛小里脊 300g", "猪里脊"),
        ("香煎猪小里脊 200g", "猪里脊"),
        ("秘制即食带鱼段 500g", "带鱼"),
        ("王牌菜香煎带鱼 400g", "带鱼"),
        ("冷鲜带鱼1条约200g", "带鱼"),
        ("惠和贝贝南瓜 约500g", "南瓜"),
        ("南瓜脆片 100g", "南瓜"),
    ]
    for name, key in GOLDEN:
        ap = profiles[key]["acceptance_profile"]
        skill_r = evaluate_candidate(name, ap)
        helper_r = hsem.evaluate_candidate(name, ap)
        check(skill_r == helper_r,
              "对拍不一致 %s「%s」\n  技能=%s\n  助手=%s" % (key, name, skill_r, helper_r))

    # 「全麦味」守卫回归：两侧必须同判 review_required
    d_skill, ev_skill, _ = evaluate_candidate("全麦味大列巴 300g",
                                              profiles["全麦面包"]["acceptance_profile"])
    d_helper, ev_helper, _ = hsem.evaluate_candidate("全麦味大列巴 300g",
                                                     profiles["全麦面包"]["acceptance_profile"])
    check(d_skill == d_helper == "review_required",
          "全麦味守卫未在两侧同时生效：%s vs %s" % (d_skill, d_helper))
    check((ev_skill.get("attribute_evidence") or {}).get("whole_grain") == "unknown",
          "技能侧全麦味应记 unknown：%s" % ev_skill)

    FORMS_GOLDEN = [
        "鲜鸡蛋30枚装", "鸡蛋软饼", "卤蛋茶叶蛋即食", "松花皮蛋", "带壳鲜鸡蛋10枚",
        "不含调味鸡胸", "调味鸡胸", "免腌制鸡胸", "整块鸡胸", "切块鸡胸",
        "冷鲜猪里脊", "冻品猪里脊", "香炸里脊", "六鳌蜜薯", "地瓜叶 300g",
    ]
    for name in FORMS_GOLDEN:
        s_f = sorted(detect_forms(name))
        h_f = sorted(hcfg.detect_forms(name))
        check(s_f == h_f, "形态对拍不一致「%s」：技能=%s 助手=%s" % (name, s_f, h_f))
    check("marinated" not in detect_forms("不含调味鸡胸"),
          "否定前缀守卫：不含调味不得识别 marinated")
    check("whole" in detect_forms("整块鸡胸") and "cut_pieces" not in detect_forms("整块鸡胸"),
          "整块守卫：整块归 whole 不归 cut_pieces")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round73 商品语义判定单一来源化全部通过")
