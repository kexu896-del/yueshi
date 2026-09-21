# -*- coding: utf-8 -*-
# round 39 回归：月相连续算法 / 日期派生校验 / 一行一食材 / 预算双口径 / 功效断言门禁 / plan_mode 路由
import datetime, io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
SR = read("references/safety-rules.md")


def _plan(**kw):
    plan = json.loads(read("data/golden/golden-sample-plan.json"))
    plan.update({k: v for k, v in kw.items() if k in plan})
    if "shopping_items" in kw:
        plan["shopping"]["items"] = kw["shopping_items"]
    if "prep" in kw:
        plan["prep"] = kw["prep"]
    return plan


def _render(plan):
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "p.json"), os.path.join(td, "o.html")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_html.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        if r.returncode == 0:
            return 0, open(op, encoding="utf-8").read()
        return r.returncode, r.stderr + r.stdout


def test_moon_phase_dates():
    import render_plan
    # 2026 年 8 月满月在 8/28 前后：8/28 必须标满月，8/25 不得标满月
    assert render_plan.moon_phase(datetime.date(2026, 8, 28))[2] == "满月"
    assert render_plan.moon_phase(datetime.date(8 * 0 + 2026, 8, 25))[2] != "满月"
    # 任意连续 7 天轨道内"满月"不得超过 2 天（收窄窗口）
    for start in (datetime.date(2026, 8, 25), datetime.date(2026, 9, 1), datetime.date(2026, 3, 10)):
        names = [render_plan.moon_phase(start + datetime.timedelta(days=i))[2] for i in range(7)]
        assert names.count("满月") <= 2, (start, names)
    assert "满月/新月窗口收窄" in OP or "±0.8 天" in OP


def test_prep_advice_dates_derived():
    # golden 样本日期正确 → 通过
    rc, out = _render(_plan())
    assert rc == 0, out
    # 星期与日期不符 → 渲染失败（2026-08-25 实为周二，写成周三必须拦截）
    bad = _plan()
    bad["prep"]["purchase_day"] = {"label": "周三 8/25 晚", "tasks": ["采购"]}
    rc, out = _render(bad)
    assert rc != 0 and "日期与星期不符" in out
    assert "日期文案必须从 plan.json 派生" in out or "派生" in OP


def test_one_row_one_ingredient():
    bad = _plan()
    bad["shopping"]["items"].append({"ingredient": "排骨+玉米", "category": "其他",
                                     "required_quantity": "1份", "acceptable_package": "1份",
                                     "reference_price": "10元/份", "substitutes": [],
                                     "leftover_action": "0 剩余"})
    rc, out = _render(bad)
    assert rc != 0 and "一行一食材" in out
    assert "一行一食材" in OP


def test_inventory_dual_budget():
    rc, out = _render(_plan())
    assert rc == 0
    # 排骨为库存且参考价 32 元 → 双口径行
    assert "含库存全口径约" in out and "128" in out and "160" in out  # 128+32=160
    assert "库存（参考 32元/盒）" in out
    assert "预算双口径" in OP


def test_efficacy_claim_gate():
    bad = _plan()
    bad["wisdom"]["paragraphs"][0] = "这样吃对骨骼与血脂更友好。"
    rc, out = _render(bad)
    assert rc != 0 and "功效表述" in out
    assert "功效断言门禁" in OP


def test_plan_mode_route_and_menopause_safety():
    assert "plan_mode" in SK and "shared_meal_personalized" in SK
    assert "不静默降级" in SK
    assert "1.1g/kg" in SR and "钙来源" in SR


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
