# -*- coding: utf-8 -*-
"""round79（2026-09-21）：体质食养的显式自述软偏置（ADR 0007）。

断言：
- 数据完整性：药食同源 106（87/6/9/4）、体质档案 10、规则 10、性味表 ≥60 且样例正确；
- 规则不含药材剂量/方剂/疗效类禁用语；prefer/avoid 性味枚举合法；
- 自述解析：阳虚/怕冷、湿气重、口苦、贫血、过敏体质、未知；
- 软偏置：阳虚对羊肉/韭菜/生姜为正、对苦瓜/黄瓜为负；湿热对辣椒/羊肉为负、对苦瓜为正；阴虚对梨为正；
- 菜谱级偏置与生活化复述（无体质判定/辨证/疗效词，通过渲染禁用词检查）；
- 预选器接线：--constitution 生效、候选集合不变、输出 constitution_context；
- 政策：不新增问卷问题、仅显式自述启用。
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import constitution as cons  # noqa: E402
import render_plan as rp  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ---------- 1) 数据完整性 ----------
mf = json.load(open(os.path.join(ROOT, "data", "medicine-food-catalog.json"), encoding="utf-8"))
check(mf.get("total") == 106 and len(mf.get("items") or {}) == 106, "药食同源应为 106 种")
batches = {}
for v in mf["items"].values():
    batches[v["batch"]] = batches.get(v["batch"], 0) + 1
check(batches == {2002: 87, 2019: 6, 2023: 9, 2024: 4}, "药食同源批次计数不符：%s" % batches)
for name in ("龙眼肉", "姜", "枣", "杏仁", "橘皮"):
    check(name in mf["items"], "药食同源缺 %s" % name)
check("桂圆" in mf["items"]["龙眼肉"]["aliases"], "龙眼肉别名缺桂圆")
check("藏红花" in mf["items"]["西红花"]["aliases"], "西红花别名缺藏红花（香辛料名）")

profiles = cons.load_profiles()
check(len(profiles) == 11, "体质档案应为 11（九种标准+血虚+阳盛）")
for key in ("balanced", "qi_deficiency", "yang_deficiency", "yin_deficiency",
            "phlegm_damp", "damp_heat", "blood_stasis", "qi_stagnation",
            "special", "blood_deficiency", "yang_excess"):
    check(key in profiles, "体质档案缺 %s" % key)
check(profiles["special"].get("safety_route") is True, "特禀质必须走安全路由")

rules = cons.load_rules()
check(len(rules.get("rules") or {}) == 11, "体质规则应为 11")
errs = cons.validate(rules)
check(not errs, "规则校验失败：%s" % errs[:3])
for key, rule in rules["rules"].items():
    for nat in (rule.get("prefer_natures") or []) + (rule.get("avoid_natures") or []):
        check(nat in ("寒", "凉", "平", "温", "热"), "%s 性味枚举非法：%s" % (key, nat))

nature = cons.load_nature()
check(len(nature) >= 60, "性味表条目过少：%d" % len(nature))
check(nature["山药"]["nature"] == "平" and "甘" in nature["山药"]["flavors"], "山药应甘平")
check(nature["苦瓜"]["nature"] == "寒" and "苦" in nature["苦瓜"]["flavors"], "苦瓜应苦寒")
check(nature["韭菜"]["nature"] == "温" and "辛" in nature["韭菜"]["flavors"], "韭菜应辛温")
check(nature["梨"]["nature"] == "凉", "梨应凉")
check(nature.get("燕麦片", {}).get("nature") == "平", "燕麦（2012 版）应甘平")

# ---------- 推断层（round79c：category_inference，半权重） ----------
inf = cons.load_inferred()
check(len(inf) >= 15, "推断层条目过少：%d" % len(inf))
check(inf["三文鱼"]["nature"] == "平" and inf["三文鱼"]["weight"] == 0.5,
      "三文鱼推断应为甘平/半权重")
check(inf["西兰花"]["nature"] == "凉", "西兰花推断应凉")
check(inf["咖喱粉"]["nature"] == "温", "咖喱粉推断应温")
check("茯苓" in inf and "茯苓" not in nature, "茯苓应为推断条目且不与教材冲突")
check(cons.bias_for("西兰花", "yang_deficiency")[0] == -0.5,
      "阳虚对西兰花（推断凉）应为 -0.5")
check(cons.bias_for("西兰花", "yang_excess")[0] == 0.5, "阳盛对西兰花应为 +0.5")
check(cons.bias_for("咖喱粉", "yang_deficiency")[0] == 0.5, "阳虚对咖喱粉（推断温）应为 +0.5")
check(cons.bias_for("三文鱼", "yang_deficiency")[0] == 0, "三文鱼甘平不触发阳虚偏置")

# ---------- 2) 自述解析 ----------
cases = {
    "我阳虚，最近怕冷": "yang_deficiency",
    "湿气重、舌苔腻": "phlegm_damp",
    "口苦、容易长痘": "damp_heat",
    "有点贫血": "blood_deficiency",
    "过敏体质": "special",
    "血瘀、容易瘀青": "blood_stasis",
    "容易紧张压力大": "qi_stagnation",
    "最近容易上火": "yang_excess",
}
for text, want in cases.items():
    check(cons.resolve(text) == want, "resolve(%r) ≠ %s" % (text, want))
check(cons.resolve("随便吃什么") is None, "未知描述应返回 None")
check(cons.resolve("又怕冷又怕热") is None, "两个方向同时出现应视为歧义（不猜测）")
check(cons.resolve_status("又怕冷又怕热")[1] == "ambiguous", "resolve_status 应报告歧义")
check(cons.resolve("我阳虚，但最近有点怕热") == "yang_deficiency", "明确体质名应优先于症状别名")
check(cons.load_nature() is cons.load_nature(), "性味数据应缓存（同对象）")

# ---------- 3) 软偏置 ----------
pos = cons.bias_for("羊肉卷", "yang_deficiency")[0]
check(pos >= 2, "阳虚对羊肉应为正（实际 %s）" % pos)
check(cons.bias_for("韭菜", "yang_deficiency")[0] >= 2, "阳虚对韭菜应为正")
check(cons.bias_for("生姜", "yang_deficiency")[0] >= 2, "阳虚对生姜应为正")
check(cons.bias_for("苦瓜", "yang_deficiency")[0] <= -1, "阳虚对苦瓜应为负")
check(cons.bias_for("黄瓜", "yang_deficiency")[0] <= -1, "阳虚对黄瓜应为负")
check(cons.bias_for("辣椒", "damp_heat")[0] <= -1, "湿热对辣椒应为负")
check(cons.bias_for("羊肉", "damp_heat")[0] <= -1, "湿热对羊肉应为负")
check(cons.bias_for("苦瓜", "damp_heat")[0] >= 1, "湿热对苦瓜应为正")
check(cons.bias_for("梨", "yin_deficiency")[0] >= 2, "阴虚对梨应为正")
check(cons.bias_for("虾", "yang_deficiency")[0] >= 2, "阳虚对虾应为正")
check(cons.bias_for("羊肉", "special")[0] == 0, "特禀质不做食养偏置")
check(cons.bias_for("苦瓜", "yang_excess")[0] >= 1, "阳盛对苦瓜应为正")
check(cons.bias_for("辣椒", "yang_excess")[0] <= -1, "阳盛对辣椒应为负")
check(cons.bias_for("牛肉", "yang_excess")[0] <= -1, "阳盛对牛肉（温热）应为负")

check(cons.recipe_bias({"original_name": "生姜羊肉汤", "core_ingredients": ["羊肉", "生姜"]},
                       "yang_deficiency") > 0, "阳虚菜谱偏置应为正")
check(cons.recipe_bias({"original_name": "凉拌苦瓜", "core_ingredients": ["苦瓜", "黄瓜"]},
                       "yang_deficiency") < 0, "阳虚苦瓜菜谱偏置应为负")
check(cons.recipe_score_bonus({"original_name": "凉拌双蔬", "core_ingredients": ["西兰花", "黄瓜"]},
                              "yang_deficiency") <= -1,
      "阳虚含推断凉性食材的菜谱应至少 -1（保留方向，不被四舍五入抹掉）")
check(cons.recipe_score_bonus({"original_name": "生姜羊肉汤", "core_ingredients": ["羊肉", "生姜"]},
                              "yang_deficiency") >= 1, "阳虚温性菜谱应为正")
import render_gates as _rg  # noqa: E402
check("scripts/common/constitution.py" in _rg.PIPELINE_COMPONENTS,
      "执行组件哈希应包含体质模块")

# ---------- 4) 生活化复述 ----------
line = cons.user_line("yang_deficiency", ["生姜", "羊肉"])
check("怕冷" in line and "生姜" in line and "羊肉" in line, "复述应含体感与实际食材：%s" % line)
for bad in ("阳虚质", "辨证", "证型", "治疗", "疗效", "处方", "剂量"):
    check(bad not in line, "复述含禁用语：%s" % bad)
for phrase in rp.BANNED_USER_FACING_PHRASES:
    check(phrase not in line, "复述触发渲染禁用词：%s" % phrase)
for term in rp.BANNED_TITLE_TERMS:
    check(term not in line, "复述含内部术语：%s" % term)
check(cons.user_line("yang_deficiency", []) == "", "无实际偏置时不应生成复述")

# ---------- 5) 预选器接线 ----------
basket = {"weekly_basket": {"proteins": ["鸡胸肉", "鸡蛋", "羊肉卷"],
                            "vegetables": ["苦瓜", "黄瓜", "冬瓜", "韭菜"],
                            "carbohydrates": ["土豆"], "flavor_bases": []}}
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
with tempfile.TemporaryDirectory() as td:
    bp = os.path.join(td, "basket.json")
    out_base = os.path.join(td, "base.json")
    out_cons = os.path.join(td, "cons.json")
    json.dump(basket, open(bp, "w", encoding="utf-8"), ensure_ascii=False)
    base_cmd = [sys.executable, "-X", "utf8",
                os.path.join(ROOT, "scripts", "ingredient_preselector.py"),
                "--build-candidates", "--basket", bp, "--month", "9",
                "--export-json"]
    r0 = subprocess.run(base_cmd + [out_base], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=env, timeout=300)
    check(r0.returncode == 0, "预选器基线运行失败：%s" % (r0.stderr[-200:]))
    r1 = subprocess.run(base_cmd + [out_cons, "--constitution", "阳虚怕冷"],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=env, timeout=300)
    check(r1.returncode == 0, "预选器体质运行失败：%s" % (r1.stderr[-200:]))
    a = json.load(open(out_base, encoding="utf-8"))
    b = json.load(open(out_cons, encoding="utf-8"))
    check(b.get("constitution_context", {}).get("declared") == "yang_deficiency",
          "输出未记录 constitution_context")
    names_a = {e["normalized_name"] for layer in a["layers"].values() for e in layer}
    names_b = {e["normalized_name"] for layer in b["layers"].values() for e in layer}
    check(names_a == names_b, "体质偏置改变了候选集合（不得改变集合）")
    b_map = {e["normalized_name"]: e for layer in b["layers"].values() for e in layer}
    a_map = {e["normalized_name"]: e for layer in a["layers"].values() for e in layer}
    if "羊肉卷" in a_map and "羊肉卷" in b_map:
        check(b_map["羊肉卷"]["score"] == a_map["羊肉卷"]["score"] + cons.bias_for(
            "羊肉卷", "yang_deficiency")[0], "羊肉卷得分未按偏置调整")
    if "苦瓜" in a_map and "苦瓜" in b_map:
        check(b_map["苦瓜"]["score"] < a_map["苦瓜"]["score"], "苦瓜得分未按偏置下调")

# ---------- 5b) S1 歧义与未识别：降级不偏置（行为测试） ----------
with tempfile.TemporaryDirectory() as td:
    bp2 = os.path.join(td, "basket2.json")
    json.dump(basket, open(bp2, "w", encoding="utf-8"), ensure_ascii=False)
    pre_cmd = [sys.executable, "-X", "utf8",
               os.path.join(ROOT, "scripts", "ingredient_preselector.py"),
               "--build-candidates", "--basket", bp2, "--month", "9", "--export-json"]
    out_amb = os.path.join(td, "amb.json")
    r_amb = subprocess.run(pre_cmd + [out_amb, "--constitution", "又怕冷又怕热"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=300)
    check(r_amb.returncode == 0, "歧义自述不应导致运行失败")
    check("多个体质方向" in r_amb.stderr, "歧义自述应提示无法确定单一方向")
    amb = json.load(open(out_amb, encoding="utf-8"))
    check("constitution_context" not in amb, "歧义时不得写入 constitution_context")

    out_unk = os.path.join(td, "unk.json")
    r_unk = subprocess.run(pre_cmd + [out_unk, "--constitution", "随便吃什么"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=300)
    check(r_unk.returncode == 0 and "未识别体质描述" in r_unk.stderr,
          "未识别自述应提示且不失败")
    unk = json.load(open(out_unk, encoding="utf-8"))
    check("constitution_context" not in unk, "未识别时不得写入 constitution_context")

# ---------- 5c) S2 排序器：阳虚 → 温性菜谱升、寒凉菜谱降（行为测试） ----------
def _rank_scores(extra):
    rank = [sys.executable, "-X", "utf8",
            os.path.join(ROOT, "scripts", "recipe_ranker.py"),
            "--basket", "羊肉卷,韭菜,苦瓜,黄瓜", "--mode", "hormone", "--limit", "30"] + extra
    r = subprocess.run(rank, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=300)
    check(r.returncode == 0, "排序器运行失败：%s" % (r.stderr or "")[-200:])
    scores = {}
    for line in (r.stdout or "").splitlines():
        m = re.match(r"\s*\[\s*(\d+)\]\s+(.+?)（", line)
        if m:
            scores[m.group(2).strip()] = int(m.group(1))
    return scores


rank_base = _rank_scores([])
rank_cons = _rank_scores(["--constitution", "阳虚怕冷"])
common_rank = set(rank_base) & set(rank_cons)
check("韭菜炒蛋" in common_rank and rank_cons["韭菜炒蛋"] > rank_base["韭菜炒蛋"],
      "阳虚应提升含韭菜菜谱得分（base=%s cons=%s）" % (
          rank_base.get("韭菜炒蛋"), rank_cons.get("韭菜炒蛋")))
check("羊肉汤" in common_rank and rank_cons["羊肉汤"] > rank_base["羊肉汤"],
      "阳虚应提升羊肉菜谱得分（base=%s cons=%s）" % (
          rank_base.get("羊肉汤"), rank_cons.get("羊肉汤")))
check("凉拌黄瓜" in common_rank and rank_cons["凉拌黄瓜"] < rank_base["凉拌黄瓜"],
      "阳虚应降低寒凉菜谱得分（base=%s cons=%s）" % (
          rank_base.get("凉拌黄瓜"), rank_cons.get("凉拌黄瓜")))

# ---------- 6) 政策 ----------
rr = read("references/runtime-rules.md")
check("constitution_context" in rr and "软偏置" in rr and "不新增问卷" in rr,
      "runtime-rules 缺体质软偏置政策")
q = read("references/questionnaire.md")
check("体质不做问卷项" in q, "questionnaire 未声明不做体质问卷")
schema = read("references/output-schema.md")
check("constitution_context" in schema, "output-schema 缺 constitution_context 契约")
tcm = read("references/tcm-food-style.md")
check("背景速查" in tcm and "仅在用户" in tcm, "tcm-food-style 定位未更新")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round79 体质食养软偏置（数据/解析/偏置/复述/接线/政策）全部通过")
