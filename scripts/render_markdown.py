#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_markdown.py —— plan.json → Markdown 渲染器（四渲染器之一，只读 plan.json）。

用法：python scripts/render_markdown.py --input plan.json --output plan.md

规则（与 references/output-policy.md 一致）：
- 章节白名单固定顺序：本周阶段 → 采购清单 → 备餐任务 → 七天菜单 → 食养之理与执行说明 → 免责声明。
- 不重新编菜单、不重算营养；缺字段立即停止。
- 价格按 price_basis 三层口径显示（估算层加"约"前缀，与 render_plan 同一函数）。
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_plan import (REQUIRED_PLAN_KEYS, CATEGORY_ORDER, _display_price,  # noqa: E402
                         _window_no_fasting, clean, load_cafeteria_templates, check_plan_meta)


def _md(plan):
    p = plan["plan"]
    out = [f"# 饮食计划 {p['date_range']}", ""]
    if p.get("subtitle"):
        out += [p["subtitle"], ""]
    stats = p.get("stats") or {}
    if stats:
        out += [" · ".join(f"{k}：{v}" for k, v in stats.items()), ""]

    ov = plan.get("stage_overview")
    if ov:
        out += ["## 本周阶段", "", f"**当前周期位置**：{ov['current']}", "",
                f"**本周策略**：{ov['strategy']}", "",
                "| 时间 | 阶段 | 饮食策略 |", "|---|---|---|"]
        for w in ov.get("weeks", []):
            out.append(f"| {w['time']} | {w['stage']} | {w['plan']} |")
        if ov.get("note"):
            out += ["", ov["note"]]
        out.append("")

    shopping = plan["shopping"]
    items = shopping.get("items", [])
    for i in items:
        if not (i.get("reference_price") or "").strip():
            raise SystemExit(f"价格硬门禁：{i.get('ingredient')} 缺参考价，停止渲染")
    out += ["## 采购清单", ""]
    groups = {}
    for i in items:
        groups.setdefault(i.get("category") or "其他", []).append(i)
    order = [c for c in CATEGORY_ORDER if c in groups] + [c for c in groups if c not in CATEGORY_ORDER]
    out += ["| 品类 | 食材 | 需要量 | 建议购买规格 | 参考价 | 替代 | 剩余去向 |", "|---|---|---|---|---|---|---|"]
    for cat in order:
        for i in groups[cat]:
            subs = "、".join(i.get("substitutes", [])) or "—"
            out.append(f"| {cat} | {i['ingredient']} | {i.get('required_quantity','')} | "
                       f"{i.get('acceptable_package','')} | {_display_price(i)} | {subs} | {i.get('leftover_action','')} |")
    if shopping.get("total"):
        out += ["", f"**本周预计支出：{shopping['total']}**"]
    if shopping.get("price_note"):
        out += ["", shopping["price_note"]]
    alloc = [i for i in items if i.get("meal_allocation")]
    if alloc:
        out += ["", "### 食材和对应菜谱", "", "| 食材 | 总需求量 | 对应菜单及用量 |", "|---|---|---|"]
        for i in alloc:
            out.append(f"| {i['ingredient']} | {i.get('required_quantity','')} | {i['meal_allocation']} |")
    out.append("")

    prep = plan.get("prep")
    if prep:
        ver = prep.get("leftover_verification", [])
        if len(ver) < 3:
            raise SystemExit("流转核验硬门禁：至少 3 项食材的 0 剩余/去向验证")
        out += ["## 备餐任务", ""]
        for key, title in (("purchase_day", "主采购日"), ("prep_day", "备餐日")):
            if prep.get(key):
                out += [f"**{title}（{prep[key].get('label','')}）**"]
                out += [f"- {x}" for x in prep[key].get("tasks", [])] + [""]
        out += ["**食材流转核验**", "", "| 食材 | 购买量 vs 计划用量 | 核验结果 |", "|---|---|---|"]
        for v in ver:
            out.append(f"| {v['ingredient']} | {v.get('purchase_vs_use','')} | {v.get('result','')} |")
        out.append("")

    include_steps = p.get("include_recipe_steps") is True
    tpls = load_cafeteria_templates()
    out += ["## 七天菜单", ""]
    for d in plan["days"]:
        out += [f"### {d['label']}", ""]
        w = _window_no_fasting(d.get("window", ""))
        if w:
            out += [w, ""]
        for m in d.get("meals", []):
            if m.get("meal_source") == "cafeteria":
                tpl = tpls.get(m.get("order_template", "balanced_standard"), {})
                est = tpl.get("nutrition_estimate", {})
                est_line = (f"估算净碳水约{est['net_carbs_g']}g / 蛋白质约{est['protein_g']}g / 脂肪约{est['fat_g']}g"
                            if est else "")
                line = f"- {m.get('time','')} **{m.get('name','午餐')}** 食堂点餐：{tpl.get('display','')}（{est_line} {tpl.get('display_note','')}）"
            else:
                grams = f"（{m['grams']}）" if m.get("grams") else ""
                line = f"- {m.get('time','')} **{m.get('name','')}** {m.get('dishes','')}{grams}"
            if m.get("status"):
                line += f"  `{m['status']}`"
            out.append(line)
            ri = m.get("recipe_instruction")
            if include_steps and ri and ri.get("steps"):
                out.append("  做法：")
                out += [f"  {n}. {x}" for n, x in enumerate(ri["steps"], 1)]
        if d.get("nutrition_line"):
            out += ["", f"> {d['nutrition_line']}"]
        if d.get("advice"):
            out += ["", f"当日建议：{d['advice']}"]
        out.append("")

    wisdom = plan.get("wisdom") or {}
    paras = wisdom.get("paragraphs") or [wisdom[k] for k in ("shunshi", "wuwei", "ziran") if wisdom.get(k)]
    tips = plan.get("execution_tips") or []
    if paras or tips:
        out += ["## 食养之理与执行说明", ""]
        if paras:
            out += ["**本周怎么安排**", ""]
        out += [x for para in paras for x in (para, "")]
        if tips:
            out += ["**本周执行要点**", ""] + [f"- {x}" for x in tips] + [""]

    out += ["---", "", clean(plan["disclaimer"])]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    plan = json.load(open(a.input, encoding="utf-8"))
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        raise SystemExit(f"plan.json 缺字段: {missing}")
    check_plan_meta(plan)
    md = _md(plan)
    open(a.output, "w", encoding="utf-8").write(md)
    print(f"Markdown 已生成: {a.output}")


if __name__ == "__main__":
    main()
