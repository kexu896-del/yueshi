#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月食家庭版 · 渲染组件（round41 / RC2-6 前置）。

只覆盖家庭模式增量组件，其余组件继承 solo 渲染器（render_plan.py）：
  - member_nutrition_block：成员营养块（每位精算成员独立行，禁止竖线拼接）
  - portion_block：份量块（按 portion_method 展示各人份量 / 实际分配比例）
  - shopping_three_ledger_row：采购三本账行（家庭需求 / 库存取用 / 新购）

输入一律为 effective_plan（经 household_override_merger 合并后的派生物）中的
meal / member / shopping item 字典；输出 HTML 片段字符串。
"""
from html import escape

# 用户可见术语（与 SKILL.md 术语门禁显示转换一致）
PORTION_METHOD_LABEL = {
    "exact_split": "分别称重",
    "component_split": "关键组件分别称量",
    "ratio_split": "按比例盛取",
    "equal_split": "均分",
    "separate_before_seasoning": "先盛出后补味",
    "separate_cookware": "分锅制作",
}
CONFIDENCE_LABEL = {"high": "估算精确", "medium": "区间估算", "low": "区间估算"}


def _esc(x):
    return escape(str(x), quote=True)


def member_nutrition_block(member, day_totals):
    """成员营养块：独立行组件。day_totals = {"calories_kcal":..,"protein_g":..,...}。"""
    label = _esc(member.get("display_label") or member.get("member_id"))
    t = member.get("nutrition_target") or {}
    rows = []

    def _row(name, actual, target, unit):
        if actual is None and not target:
            return
        tgt = ""
        if target:
            tgt = " / 目标 %s%s" % (_esc(target), unit)
        rows.append('<div class="hh-nut-row"><span class="hh-nut-name">%s</span>'
                    '<span class="hh-nut-val">%s%s%s</span></div>'
                    % (name, _esc(actual) if actual is not None else "—", unit, tgt))

    _row("热量", day_totals.get("calories_kcal"), t.get("calories_target_kcal") or t.get("calories_kcal"), " kcal")
    _row("蛋白质", day_totals.get("protein_g"), t.get("protein_target_g"), " g")
    _row("净碳水", day_totals.get("net_carbs_g"), t.get("net_carbs_g"), " g")
    _row("脂肪", day_totals.get("fat_g"), t.get("fat_g"), " g")
    conf = CONFIDENCE_LABEL.get(member.get("nutrition_confidence"), "")
    conf_html = ('<span class="hh-nut-conf">%s</span>' % conf) if conf else ""
    return ('<div class="hh-member-nut"><div class="hh-member-label">%s%s</div>%s</div>'
            % (label, conf_html, "".join(rows)))


def portion_block(meal):
    """份量块：每餐各人份量。ratio_split 显示实际分配比例（selected_pct）。"""
    method = meal.get("portion_method")
    method_label = PORTION_METHOD_LABEL.get(method, _esc(method or ""))
    parts = ['<div class="hh-portion"><div class="hh-portion-method">盛取方式：%s</div>'
             % method_label]
    ratios = {r.get("member_id"): r for r in meal.get("portion_ratios", [])}
    for b in meal.get("member_portions", []):
        mid = _esc(b.get("member_id"))
        grams = b.get("grams")
        if grams is None and b.get("items"):
            grams = sum((it.get("quantity") or {}).get("canonical_grams") or 0
                        for it in b["items"]) or None
        line = '<div class="hh-portion-row"><span class="hh-portion-member">%s</span>' % mid
        if grams is not None:
            line += '<span class="hh-portion-grams">约%s g</span>' % _esc(grams)
        r = ratios.get(b.get("member_id"))
        if r and r.get("selected_pct") is not None:
            line += '<span class="hh-portion-pct">实际分配比例 %s%%</span>' % _esc(r["selected_pct"])
        line += "</div>"
        parts.append(line)
    parts.append("</div>")
    return "".join(parts)


def shopping_three_ledger_row(item):
    """采购三本账行：家庭需求 / 库存取用 / 新购分列。"""
    def _amt(q):
        if not q:
            return "—"
        g = q.get("canonical_grams")
        return ("%s g" % _esc(g)) if g is not None else _esc(q.get("display", "—"))

    name = _esc(item.get("ingredient_name") or item.get("name") or item.get("ingredient_id"))
    cond = item.get("purchase_condition")
    cond_html = ('<span class="hh-shop-cond">%s</span>' % _esc(cond)) if cond else ""
    return ('<tr class="hh-shop-row"><td>%s%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (name, cond_html,
               _amt(item.get("household_required_amount")),
               _amt(item.get("inventory_used_amount")),
               _amt(item.get("new_purchase_amount"))))


def render_household_html(effective):
    """家庭有效计划最小自包含 HTML（统一渲染器家庭入口的最小实现）。
    输入必须为已通过 effective Schema 校验的 effective_plan；base/overrides 不进表现层。"""
    meta = effective.get("plan_meta", {})
    parts = ["<!DOCTYPE html><html lang=zh-CN><head><meta charset=utf-8>",
             "<title>家庭一周饮食计划</title>",
             "<style>body{font-family:sans-serif;margin:2em;line-height:1.6}"
             ".hh-member-nut,.hh-portion{border:1px solid #ddd;border-radius:8px;padding:.6em;margin:.5em 0}"
             "table{border-collapse:collapse}td{border:1px solid #ccc;padding:.3em .8em}</style>",
             "</head><body>",
             "<h1>家庭一周饮食计划</h1>",
             "<p>构建：%s ｜ 模式：家庭模式 ｜ 成员：%d 人</p>"
             % (_esc(meta.get("build_id", "")), len(effective.get("members", [])))]

    # 成员营养块（独立行）
    parts.append("<h2>成员营养目标</h2>")
    for m in effective.get("members", []):
        parts.append(member_nutrition_block(m, {}))

    # 每餐份量块
    parts.append("<h2>餐次与各人份量</h2>")
    for meal in effective.get("shared_meals", []):
        parts.append("<h3>%s（%s %s）</h3>" % (
            _esc(meal.get("title", meal.get("meal_id"))),
            _esc(meal.get("date", "")), _esc(meal.get("meal_type", ""))))
        parts.append(portion_block(meal))

    # 采购三本账
    if effective.get("shopping"):
        parts.append("<h2>采购清单（家庭需求 / 库存取用 / 新购）</h2><table>"
                     "<tr><th>食材</th><th>家庭需求</th><th>库存取用</th><th>新购</th></tr>")
        for item in effective["shopping"]:
            parts.append(shopping_three_ledger_row(item))
        parts.append("</table>")

    em = effective.get("effective_meta", {})
    parts.append("<p style='color:#888;font-size:.9em'>已应用就餐变化：%d 项 ｜ 基础构建：%s</p>"
                 % (len(em.get("applied_override_ids", [])), _esc(em.get("base_build_id", ""))))
    parts.append("</body></html>")
    return "".join(parts)


if __name__ == "__main__":
    demo_meal = {
        "portion_method": "ratio_split",
        "member_portions": [{"member_id": "primary", "grams": 165},
                            {"member_id": "secondary", "grams": 240}],
        "portion_ratios": [{"member_id": "primary", "selected_pct": 40.0},
                           {"member_id": "secondary", "selected_pct": 60.0}],
    }
    print(portion_block(demo_meal))
