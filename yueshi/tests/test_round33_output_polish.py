# -*- coding: utf-8 -*-
# round 33 回归：术语门禁 / 字体一致 / 食堂内容完整 / 餐次状态一致 / 建议贴卡 / 库存显示 / menu-map 压缩
import io, json, os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
PRINT = read("styles/print.css")
RP = read("scripts/render_plan.py")


def _plan(subtitle="能量期 · 减重目标 · 月经期转卵泡期", breakfast_status="自备 · 免煮",
          breakfast_grams=None, extra=None):
    plan = {"plan": {"date_range": "2026-09-01 至 2026-09-07", "subtitle": subtitle, "stats": {}},
            "plan_meta": {"plan_schema_version": "1", "skill_version": "x", "runtime_rules_version": "x",
                          "nutrition_rules_version": "x", "output_policy_version": "x",
                          "recipe_manifest_version": "x", "effective_parameters_version": "x",
                          "price_data_version": "x"},
            "profile": {},
            "shopping": {"items": [{"ingredient": "虾", "category": "肉蛋水产与豆制品",
                                    "required_quantity": "300g", "acceptable_package": "300g/袋",
                                    "reference_price": "26元/袋", "price_basis": "category_estimate",
                                    "substitutes": [], "leftover_action": "0 剩余"}]},
            "prep": {"leftover_verification": [
                {"ingredient": "虾", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "豆腐", "purchase_vs_use": "1:1", "result": "0 剩余"},
                {"ingredient": "菠菜", "purchase_vs_use": "1:1", "result": "0 剩余"}]},
            "days": [{"label": "周二 9/1", "window": "进食 07:30–19:30",
                      "meals": [{"time": "07:30", "name": "早餐", "dishes": "蒸玉米150g",
                                 "status": breakfast_status,
                                 **({"grams": breakfast_grams} if breakfast_grams else {})},
                                {"time": "12:00", "name": "午餐", "meal_source": "cafeteria",
                                 "order_template": "balanced_standard", "status": "外食 · 区间估算"}]}],
            "disclaimer": "本计划为一般性健康饮食建议。"}
    if extra:
        plan.update(extra)
    return plan


def _render(plan):
    """返回 (returncode, html或错误信息)"""
    with tempfile.TemporaryDirectory() as td:
        ip, op = os.path.join(td, "p.json"), os.path.join(td, "o.html")
        json.dump(plan, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_html.py"),
                            "--input", ip, "--output", op], capture_output=True, text=True)
        if r.returncode == 0:
            return 0, open(op, encoding="utf-8").read()
        return r.returncode, r.stderr + r.stdout


def test_banned_title_terms_gate():
    assert "BANNED_TITLE_TERMS" in RP and "周期协议" in RP
    assert "用户可见术语门禁" in OP
    rc, out = _render(_plan(subtitle="能量期 · 经前一周（周期协议）"))
    assert rc != 0 and "内部术语" in out
    rc, out = _render(_plan())
    assert rc == 0 and "周期协议" not in out.split("<title>")[1]


def test_wisdom_font_consistency():
    assert "#why p, #why ul, #why li { font-size: 10.5pt; line-height: 1.6" in PRINT
    assert "#why { break-inside: avoid" in PRINT
    assert "章节字体一致性" in OP and "禁止列表继承浏览器默认字号" in OP
    assert ".disclaimer { font-size: 9pt; line-height: 1.55" in PRINT


def test_cafeteria_content_gate():
    assert '无 display 内容' in RP  # 模板缺失直接报错
    rc, out = _render(_plan())
    assert rc == 0 and "食堂点餐：荤菜半份 + 素菜2份 + 米饭半碗 + 清汤" in out
    assert "餐次内容完整性" in OP


def test_meal_status_consistency_gate():
    assert "餐次状态一致性" in OP
    # 有克数却标自行处理 → 门禁失败
    rc, out = _render(_plan(breakfast_status="自行处理", breakfast_grams="玉米150g"))
    assert rc != 0 and "自行处理" in out
    # planned 早餐标自备 · 免煮 → 通过
    rc, out = _render(_plan(breakfast_status="自备 · 免煮", breakfast_grams="玉米150g"))
    assert rc == 0


def test_day_advice_pinned_css():
    assert ".day-advice { break-before: avoid" in PRINT


def test_inventory_price_display():
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    from render_plan import _display_price
    assert _display_price({"purchase_status": "from_inventory", "reference_price": "0元（库存）"}) == "库存"
    assert _display_price({"reference_price": "0元（库存）"}) == "库存"
    assert "purchase_status" in OP and "库存" in OP


def test_menu_map_print_compression():
    # round 56 格式差异化：menu-map 恢复——HTML 可折叠完整版（无截断、
    # 无"见网页版展开"提示），PDF 完整展开为可见表格。
    assert "menu-map-extra" not in RP and "menu-map-print-note" not in RP
    assert "menu-map-extra" not in PRINT and "menu-map-print-note" not in PRINT
    alloc = [{"ingredient": f"食材{n}", "category": "其他", "required_quantity": "1",
              "acceptable_package": "1", "reference_price": "1元", "meal_allocation": "周一午1",
              "leftover_action": "0剩余"} for n in range(12)]
    plan = _plan(extra={})
    plan["shopping"]["items"] = alloc
    rc, out = _render(plan)
    assert rc == 0 and "<details class='menu-map'>" in out
    assert out.count("周一午1") == 12 and "见网页版展开" not in out


def test_meal_structure_note_rendered():
    plan = _plan()
    plan["days"][0]["meals"].append(
        {"time": "18:30", "name": "晚餐", "dishes": "清蒸鳕鱼配蒸生菜", "grams": "鳕鱼100g",
         "status": "自炊 · 蒸锅组合",
         "meal_structure": {"type": "synchronized_one_cooker", "equipment_count": 1,
                            "simultaneous": True, "structure_note": "同一蒸锅上下层完成"}})
    rc, out = _render(plan)
    assert rc == 0 and "同一蒸锅上下层完成" in out
    assert "meal_structure" in OP


def test_stage_two_weeks_only():
    assert "只保留\"本周 + 下周\"两行" in OP or "本周 + 下周" in OP


if __name__ == "__main__":
    fails = []
    for name, fn in sorted([(k, v) for k, v in globals().items()
                            if k.startswith("test_") and callable(v)]):
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            fails.append(name)
            print(f"FAIL {name}: {e}")
    print("round33:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
