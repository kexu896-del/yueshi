# -*- coding: utf-8 -*-
# round 58 验收：逐周必显选答 / 营养目标预编译与两轮上限 / CSS 换行与分页正式合入 /
# 封面四卡恢复 / 查价清单精简结构 / 运行记录耗时字段 / 食材规则回写。
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RM = read("README.md")
RR = read("references/runtime-rules.md")
Q = read("references/questionnaire.md")
PF = read("workflows/planning-flow.md")
NR = read("references/nutrition-routing.md")
OP = read("references/output-policy.md")
PP = read("references/price-provider-policy.md")
VS = read("references/visual-spec.md")
OS = read("references/output-schema.md")
PRINT = read("styles/print.css")
RP = read("scripts/render_plan.py")


def _plan(stats):
    return {"plan": {"date_range": "2026-09-12 至 2026-09-18",
                     "subtitle": "排卵期 → 能量期 · 减重目标 · 一人食",
                     "stats": stats},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "x",
                          "runtime_rules_version": "x", "nutrition_rules_version": "x",
                          "output_policy_version": "x", "recipe_manifest_version": "x",
                          "effective_parameters_version": "x", "price_data_version": "x"},
            "profile": {},
            "shopping": {"items": [{"ingredient": "鸡腿", "category": "肉蛋水产与豆制品",
                                    "required_quantity": "500g",
                                    "reference_price": "¥15–18",
                                    "substitutes": "鸭腿",
                                    "leftover_action": "冷冻"}]},
            "prep": {"leftover_verification": [
                {"ingredient": "鸡腿", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周六 9/12", "window": "进食 07:30–19:30",
                      "meals": [{"time": "12:00", "name": "午餐", "dishes": "烤鸡腿",
                                 "grams": "鸡腿200g", "status": "自炊"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}


FOUR = {"天数": "7 天", "模式": "周期切换", "进食窗口": "07:30–19:30",
        "预算": "约 ¥231"}


def _render_html(plan):
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "plan.json")
        op = os.path.join(td, "out.html")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "render_html.py"),
                            "--input", ip, "--output", op],
                           capture_output=True)
        out = r.stdout.decode() + r.stderr.decode()
        html = io.open(op, encoding="utf-8").read() if os.path.exists(op) else ""
        return r.returncode, html, out


def test_weekly_choice_semantics():
    # 逐计划周期必显选答，不再是"默认否、不追问"
    assert "逐计划周期必显选答" in SK and "不跨周" in SK
    assert "不静默判定为" in SK
    assert "默认否、不追问" not in SK
    # 旧话术只能以"禁止"形式出现在 runtime-rules（防复现说明）
    for doc in (SK, Q, PF, RM):
        assert "本周默认不生成叮咚查价清单" not in doc
    assert '禁止"本周默认不生成叮咚查价清单' in RR
    # 状态机与不跨周继承
    for n in ("dingdong_price_choice", "pending", "use_helper", "use_estimate",
              "不跨周继承", "只对本次"):
        assert n in RR, f"runtime-rules 缺 {n}"
    assert "pending" in Q and "不单独再追问一轮" in Q
    assert "不填默认 B" not in Q
    assert "pending" in PF and "不单独再追问一轮" in PF
    # 首轮明确不重复问
    assert "已选择）" in SK and "不重复" in SK
    # README 口径同步（round71：用户可见文案，不暴露内部状态词）
    assert "每次制定新计划时选择一次" in RM and "不会自行默认" in RM
    assert "默认否、不追问" not in RM


def test_daily_target_compiler():
    # 脚本存在且冒烟可跑：hormone 减重日净碳水上限=100 在第 0 步进入矩阵
    rc, out = _run_compiler()
    assert rc == 0, out
    assert "预编译完成" in out
    # 缺字段 fail-closed（rc=3）
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "bad.json")
        json.dump({"days": [{"day_index": i} for i in range(7)]},
                  open(bad, "w", encoding="utf-8"))
        r = subprocess.run([sys.executable,
                            os.path.join(BASE, "scripts", "daily_target_compiler.py"),
                            "--check", bad], capture_output=True)
        assert r.returncode == 3 and "缺字段" in r.stderr.decode()
    # 文档口径
    assert "daily_target_compiler.py" in PF and "11.5" in PF
    assert "daily_targets.json" in NR and "禁止第三轮才发现" in NR
    assert "最终复核（只读检查" in NR and "不计轮次" in NR
    assert "热量粗筛" in PF and "热量粗筛" in NR
    # 克数变化强制局部重算
    assert "局部重算当天营养" in NR and "更新 `nutrition_snapshot_hash`" in NR
    assert "采购剩余安排" in NR or "剩余去向、不改变菜单克数" in NR


def _run_compiler():
    r = subprocess.run(
        [sys.executable, os.path.join(BASE, "scripts", "daily_target_compiler.py"),
         "--sex", "f", "--age", "28", "--height", "163", "--weight", "70",
         "--goal", "lose",
         "--modes", "keto,keto,hormone,hormone,hormone,hormone,hormone",
         "--stages", "power1,power1,power2,power2,nurture,nurture,nurture",
         "--start-date", "2026-09-12", "--out", os.path.join(
             tempfile.gettempdir(), "dt58.json")],
        capture_output=True)
    out = r.stdout.decode() + r.stderr.decode()
    if r.returncode == 0:
        d = json.load(open(os.path.join(tempfile.gettempdir(), "dt58.json"),
                           encoding="utf-8"))
        assert d["days"][2]["net_carb_max_g"] == 100.0, "hormone 减重上限必须为 100"
        assert d["days"][0]["net_carb_max_g"] == 50.0, "keto 上限必须为 50"
    return r.returncode, out


def test_css_wrapping_and_pagination():
    # ingredient-name 正式换行规则（不再需要临时补丁）
    assert ".shopping-table .ingredient-name { white-space: normal; overflow-wrap: anywhere; word-break: break-word; }" in PRINT
    assert "nowrap" not in [l for l in PRINT.splitlines()
                            if "ingredient-name" in l][0]
    # 采购表整行不跨页 + 分类标题绑定 + 表头重复
    assert ".shopping-table tr { break-inside: avoid" in PRINT
    assert "table-header-group" in PRINT
    assert ".shopping-category { break-after: avoid" in PRINT
    # 分页不得改业务文本
    assert "禁止为消除孤行" in read("scripts/render_pdf.py") or \
           "不得改变需求量" in OP or "分页修复不得改业务文本" in OP
    assert "分页修复不得改业务文本（round58）" in OP


def test_cover_four_cards():
    rc, html, out = _render_html(_plan(FOUR))
    assert rc == 0, out
    assert html.count('class="cover-stat"') == 4
    for label in ("天数", "模式", "进食窗口", "预算"):
        assert f'<div class="cover-stat-label">{label}</div>' in html
    # 阶段在副标题
    assert "排卵期 → 能量期" in html
    # 三卡/旧卡被拒
    rc, _, out = _render_html(_plan({"阶段": "能量期", "模式": "酮生物",
                                     "预算": "约 ¥231"}))
    assert rc != 0 and "封面摘要卡契约错误" in out
    # 契约与视觉规范同步
    assert "stats: {天数, 模式, 进食窗口, 预算}" in OS
    assert "封面摘要卡固定四张等宽" in VS
    assert "家庭模式同样固定四卡" in VS


def test_compact_query_schema_and_e_gates():
    d = json.loads(read("schemas/price-query.schema.json"))
    qi = d["definitions"]["query_item"]["properties"]
    assert "required_form" in qi
    assert "精简项目结构" in d["description"]
    assert "override" in d["description"]
    # policy：精简清单 + E01–E06 + 运行记录字段
    assert "9.1 精简查价清单与助手端词典展开" in PP
    for e in ("E01", "E02", "E03", "E04", "E05", "E06"):
        assert f"**{e}**" in PP, e
    assert "永不自动迁移为本周" in PP
    assert "结果文件格式不完整，请回到查价助手重新保存" in PP
    for f in ("daily_target_compile_ms", "nutrition_round_1_ms",
              "pdf_layout_retry_count", "candidate_manual_review_count",
              "nutrition_adjustment_rounds"):
        assert f in PP, f


def test_catalog_rules_written_back():
    cat = json.loads(read("data/ingredient-catalog.json"))
    fd = json.loads(read("data/product-form-dictionary.json"))
    assert cat["catalog_version"] == "1.6.0"
    assert fd["form_dictionary_version"] == "1.4.0"
    for form in ("cured", "sashimi"):
        assert form in fd["forms"] and fd["forms"][form]["restrictive"] is True
    leg = cat["items"]["鸡腿"]["query_profile"]
    assert "cured" in leg["excluded_states"]
    sal = cat["items"]["三文鱼"]["query_profile"]
    assert "sashimi" in sal["excluded_states"]
    corn = cat["items"]["玉米"]["query_profile"]
    assert any("茶" in t for t in corn["hard_excluded_terms"])
    cel = cat["items"]["芹菜"]["query_profile"]
    assert "牛肉丝" in cel["hard_excluded_terms"]


if __name__ == "__main__":
    mod = sys.modules[__name__]
    fails = 0
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
