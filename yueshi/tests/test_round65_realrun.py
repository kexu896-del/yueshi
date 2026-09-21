#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round65（yueshi-1.4.2 基线）真实运行问题回归：
早餐自炊语义分离 / 蛋白候选角色与冷却 / 商品形态门 / 预算三态 / 核心食材误报 / 预选可追溯。"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
import candidate_roles, product_forms, selection_change_log  # noqa: E401

fails = []


def check(cond, msg):
    if cond:
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  x FAIL", msg)


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


# ---- P0a 早餐语义：自己做 ≠ 快手 ----
def test_breakfast_self_cook_maps_to_planned():
    q = read("references/questionnaire.md")
    r = read("references/runtime-rules.md")
    check("工作日早餐自己做" in q, "test_breakfast_self_cook_maps_to_planned：问卷示例改为自己做")
    check("自己做 / 自己解决（无时间或做法条件） | planned" in r
          and "preparation_location=home" in r and "preparation_owner=self" in r,
          "test_breakfast_self_cook_maps_to_planned：映射为 planned + home/self")


def test_breakfast_self_cook_does_not_imply_quick():
    r = read("references/runtime-rules.md")
    check("MEAL-SELFCOOK-001" in r and "不得仅凭\"自己做\"推断难度" in r
          and "明确时间或做法证据" in r,
          "test_breakfast_self_cook_does_not_imply_quick：quick 需显式证据")
    q = read("references/questionnaire.md")
    check("不附带 `quick_self_prepare`" in q and "早餐大概几分钟" in q,
          "test_time_limit_requires_explicit_evidence：缺时间条件合并追问")


def test_simple_breakfast_not_guidance_only():
    r = read("references/runtime-rules.md")
    check("不得路由为 guidance_only" in r
          and "只有\"只给原则/不用安排/不纳入这份计划\"类明确表达才允许 guidance_only" in r,
          "test_simple_breakfast_does_not_downgrade_to_guidance_only")


# ---- P0b 候选角色与冷却 ----
def test_candidate_roles_slots():
    rules = candidate_roles.load_rules()
    check(rules["mandatory_aquatic_slot"] is False, "不强制水产占位")
    check(rules["slots"] == {"total": 5, "minimum_staple": 3, "maximum_exploratory": 1},
          "槽位 5/3/1")
    check(candidate_roles.candidate_role("鸡蛋", rules) == "staple"
          and candidate_roles.candidate_role("蛤蜊", rules) == "exploratory"
          and candidate_roles.candidate_role("虾", rules) == "rotation",
          "角色枚举 staple/rotation/exploratory")


def test_exploratory_requires_authorization():
    rules = candidate_roles.load_rules()
    check(not candidate_roles.exploratory_allowed("蛤蜊", {}, 5, rules),
          "探索型默认不进核心")
    check(candidate_roles.exploratory_allowed(
        "蛤蜊", {"exploratory_signals": ["user_open_to_exploration"]}, 5, rules),
        "用户愿意尝试 → 允许")
    check(candidate_roles.exploratory_allowed(
        "蛤蜊", {"exploratory_signals": ["positive_personal_history"],
                 "positive_history": ["蛤蜊"]}, 5, rules),
        "正向个人历史 → 允许")
    check(candidate_roles.exploratory_allowed("蛤蜊", {}, 2, rules),
          "staple 候选不足 → 允许")


def test_cooldown_cycle():
    rules = candidate_roles.load_rules()
    # 首次核心删除 → 冷却 4 周、可作替代
    st = candidate_roles.suppression_state(
        "蛤蜊", {"core_deletion_history": {"蛤蜊": [10]}}, 12, rules)
    check(st["suppress_from_core"] and st["allow_as_alternative"]
          and st["cooldown_weeks"] == 2 and st["reason_code"] == "first_deletion_cooldown",
          "首次删除冷却 4 周（剩 2 周）可作替代")
    # 冷却期满 → 恢复
    st = candidate_roles.suppression_state(
        "蛤蜊", {"core_deletion_history": {"蛤蜊": [10]}}, 14, rules)
    check(not st["suppress_from_core"], "冷却期满恢复")
    # 8 周内第二次删除 → 8 周且不可替代
    st = candidate_roles.suppression_state(
        "蛤蜊", {"core_deletion_history": {"蛤蜊": [2, 9]}}, 10, rules)
    check(st["suppress_from_core"] and not st["allow_as_alternative"]
          and st["reason_code"] == "repeat_deletion_cooldown",
          "8 周内第二次删除 → 8 周且不可作替代")
    # 用户点名覆盖冷却
    st = candidate_roles.suppression_state(
        "蛤蜊", {"core_deletion_history": {"蛤蜊": [2, 9]},
                 "explicit_requests": ["蛤蜊"]}, 10, rules)
    check(not st["suppress_from_core"] and st["reason_code"] == "explicit_user_request",
          "用户点名要求覆盖冷却")


def test_preselector_integration():
    basket = {"weekly_basket": {"proteins": ["鸡蛋", "鸡腿", "猪里脊", "豆腐", "蛤蜊"],
                                "vegetables": [], "carbohydrates": [], "flavor_bases": []}}
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "b.json"); cp = os.path.join(td, "c.json")
        json.dump(basket, open(bp, "w"))
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "scripts", "ingredient_preselector.py"),
                            "--build-candidates", "--basket", bp, "--month", "9",
                            "--export-json", cp], capture_output=True, text=True)
        check(r.returncode == 0, "预选器运行成功")
        c = json.load(open(cp, encoding="utf-8"))
        names = [e["normalized_name"] for e in c["layers"]["protein"]]
        check("蛤蜊" not in names and all(
            e.get("candidate_role") == "staple" for e in c["layers"]["protein"]),
            "蛤蜊被准入条件拦截，核心全为 staple")
        check(any("蛤蜊" in n for n, _ in c["dropped_before_selection"]),
              "拦截记录进入 dropped_before_selection")


# ---- P0c 商品形态门 ----
def test_form_gate_real_failures():
    cases = [("鸡蛋", "鸡蛋软饼", "rejected"),
             ("红薯", "甘梅地瓜条", "rejected"),
             ("红薯", "地瓜叶 300g", "rejected"),
             ("猪里脊", "香炸黑猪里脊小方", "rejected"),
             ("鸡蛋", "鲜鸡蛋 30枚", "exact"),
             ("红薯", "六鳌蜜薯 地瓜 2.5kg", "exact"),
             ("猪里脊", "冰鲜猪里脊 400g", "exact")]
    for ing, title, want in cases:
        got = product_forms.match_product(ing, title)["verdict"]
        check(got == want, "形态门 %s「%s」→ %s（实得 %s）" % (ing, title, want, got))


def test_catalog_profiles_and_versions():
    cat = product_forms.load_catalog()
    d = product_forms.load_dictionary()
    check(cat["catalog_version"] == "1.6.0", "目录版本 1.6.0")
    check(d["form_dictionary_version"] == "1.4.0", "形态词典 1.4.0")
    for ing in ("红薯", "猪里脊", "鸡蛋"):
        qp = cat["items"][ing].get("query_profile") or {}
        check(qp.get("excluded_states"), "%s 有 excluded_states" % ing)


def test_validator_p09():
    import price_result_validator as prv
    cand = {"product_name": "香炸黑猪里脊小方 200g", "observed_at": "t",
            "reference_grams": 200, "price_type": "regular",
            "regular_price_yuan": 15.9, "availability": "available"}
    v = prv.check_candidate_gates(cand, {"ingredient_id": "猪里脊", "query": "猪里脊"},
                                  delivery_context_confirmed=True)
    check(any(x.startswith("P09_FORM_") for x in v)
          and cand["eligible_for_purchase"] is False and cand["form_match"] == "rejected",
          "validator P09 拒绝炸里脊并置不可购")
    cand2 = dict(cand, product_name="冰鲜猪里脊 400g", eligible_for_purchase=True)
    v2 = prv.check_candidate_gates(cand2, {"ingredient_id": "猪里脊", "query": "猪里脊"},
                                   delivery_context_confirmed=True)
    check(not any(x.startswith("P09_") for x in v2) and cand2["form_match"] == "exact",
          "生鲜里脊通过形态门")


def test_helper_snapshot_synced():
    # 2026-09-18：兼容两种源码包布局（平铺 src/ 或嵌套一层 yueshi-dingdong-helper/src/）。
    base = os.path.join(ROOT, "..", "yueshi-dingdong-helper")
    cands = [os.path.join(base, "src", "config.py"),
             os.path.join(base, "yueshi-dingdong-helper", "src", "config.py")]
    hcfg = next((p for p in cands if os.path.exists(p)), cands[0])
    src = open(hcfg, encoding="utf-8").read()
    check('FORM_DICTIONARY_VERSION = "1.4.0"' in src
          and 'CATALOG_RULES_VERSION = "1.6.0"' in src, "助手版本快照同步")
    for ing in ('"鸡蛋"', '"红薯"', '"猪里脊"'):
        check(ing + ": {" in src, "助手 CATALOG_RULES 含 %s" % ing)


# ---- P1a 预选可追溯 ----
def test_score_breakdown_and_decision():
    basket = {"weekly_basket": {"proteins": ["鸡蛋", "鸡腿", "猪里脊", "豆腐"],
                                "vegetables": [], "carbohydrates": [], "flavor_bases": []}}
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "b.json"); cp = os.path.join(td, "c.json")
        json.dump(basket, open(bp, "w"))
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "ingredient_preselector.py"),
                        "--build-candidates", "--basket", bp, "--month", "9",
                        "--export-json", cp], capture_output=True, text=True)
        c = json.load(open(cp, encoding="utf-8"))
        sb = c["layers"]["protein"][0]["score_breakdown"]
        need_keys = {"availability", "convenience", "package", "budget",
                     "recipe_support", "diversity", "familiarity", "history", "final"}
        check(need_keys <= set(sb), "score_breakdown 九分项齐全")
        sd = c.get("selection_decision") or {}
        check("selected" in sd and "top_rejected_candidates" in sd
              and "rejected_count" in sd, "selection_decision 结构齐全")


# ---- P1b 变更日志 ----
def test_selection_change_log():
    rec = selection_change_log.log_change(
        "猪里脊", {"product_name": "香炸黑猪里脊小方"}, {"product_name": "冰鲜猪里脊"},
        ["product_form_correction", "prepared_food_rejected"])
    check(rec["selection_changed"] and rec["change_category"] == "correction", "纠错归类")
    rec2 = selection_change_log.log_change("鸡蛋", "30枚装", "10枚装", ["smaller_package"])
    check(rec2["change_category"] == "packaging_optimization", "包装优化归类")
    stats = selection_change_log.summarize([rec, rec2])
    check(stats["correction"] == 2 and stats["packaging_optimization"] == 1
          and stats["changed"] == 2, "纠错与包装优化分开统计")
    try:
        selection_change_log.log_change("x", "a", "b", ["not_a_code"])
        check(False, "未知 reason_code 应拒绝")
    except ValueError:
        check(True, "未知 reason_code 拒绝")


# ---- P1c 预算三态 ----
def _run_aggregator(extra):
    with tempfile.TemporaryDirectory() as td:
        menu = os.path.join(td, "m.csv")
        # 2026-09-18：fixture 显式 UTF-8 写入（脚本按 utf-8-sig 读取），
        # 避免 GBK 区域机器上写读编码不一致导致脚本崩溃。
        open(menu, "w", encoding="utf-8").write(
            "date,meal,dish,food,grams,unit,storage,kind,category\n"
            "2026-09-17,晚餐,炒蛋,鸡蛋,120,g,冷藏,fresh,\n"
            "2026-09-17,晚餐,红薯,红薯,200,g,常温,fresh,\n")
        prices = os.path.join(td, "p.csv")
        open(prices, "w", encoding="utf-8").write(
            "food,price_per_unit,unit,confidence\n鸡蛋,10,500g,high\n红薯,8,500g,high\n")
        # 2026-09-18：脚本 stdout 为 UTF-8（入口 reconfigure），显式按 UTF-8 解码，
        # 避免 GBK 区域机器上中文断言全部误失败。
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "shopping_aggregator.py"),
             "--menu", menu, "--prices", prices] + extra, capture_output=True,
            text=True, encoding="utf-8", errors="replace")


def test_budget_three_states():
    r = _run_aggregator(["--budget", "1", "--budget-type", "hard_cap"])
    check(r.returncode == 2 and "未经用户明确批准不得定稿" in r.stdout,
          "hard_cap 超支退出码 2 阻止定稿")
    r = _run_aggregator(["--budget", "1", "--budget-type", "flexible_target"])
    check(r.returncode == 0 and "弹性参考" in r.stdout and "允许超出: 15%" in r.stdout,
          "flexible_target 默认允许 15% 不阻断")
    r = _run_aggregator(["--budget", "100", "--budget-type", "preferred_target"])
    check(r.returncode == 0 and "优先目标" in r.stdout and "预算内" in r.stdout,
          "preferred_target 预算内")
    q = read("references/questionnaire.md")
    check("A. 硬上限" in q and "B. 优先目标" in q and "C. 弹性参考" in q,
          "问卷预算三态问法")
    check("BUDGET-001" in read("references/runtime-rules.md")
          and "只有金额没有类型时，一律视为信息缺失" in read("references/runtime-rules.md"),
          "BUDGET-001 规则落文档")


# ---- P1d 核心食材误报 ----
def test_core_count_catalog_fallback():
    r = _run_aggregator(["--meals-per-day", "1"])
    check("核心食材 2 种" in r.stdout and "核心食材 0 种" not in r.stdout,
          "缺 category 时按目录回填分区，不再误报 0 种")


# ---- 版本与文档 ----
def test_versions_and_docs():
    check("version: yueshi-1.4.3" in read("SKILL.md"), "SKILL 版本 1.4.3")
    check("适用 SKILL 版本：1.4.3" in read("README.md"), "README 版本同步")
    check("本周预算类型、预算金额和已有库存" in read("README.md"), "README 八项第 6 项")
    idx = read("references/rule-index.md")
    for rid in ("MEAL-SELFCOOK-001", "ROLE-001", "FORM-001", "BUDGET-001", "CHANGE-001"):
        check(rid in idx, "rule-index 含 %s" % rid)
    check("yueshi-1.4.3" in read("CHANGELOG.md").split("\n")[2], "CHANGELOG 最新条目 1.4.3")


if __name__ == "__main__":
    for name, fn in sorted([(k, v) for k, v in globals().items()
                            if k.startswith("test_")]):
        print("==", name)
        fn()
    if fails:
        print("\nFAILED:", len(fails))
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("\nPASS: round65 全部探针命中")
