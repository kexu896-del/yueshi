#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_plan.py — 月食固定组件渲染器（三层架构第二层）

用法：python scripts/render_plan.py --input plan.json --output plan.html

规则（硬约束，见 SKILL.md「渲染架构」）：
- 输入只有一份校验过的 plan.json；本脚本不重新编菜单、不重算营养。
- 固定组件函数渲染：cover / profile / shopping_table / day_card / recipe_steps / disclaimer。
- 不使用全局占位符 replace 充当模板引擎；缺字段立即报错停止。
- HTML 只渲染一次；PDF 由 render_pdf.py 打印一次生成（本脚本只产 HTML）。
- 渲染后执行完整性门禁：无 {{ }} / PLACEHOLDER / undefined / None / [object Object]；
  恰好一个 <main> 与一个 cover；每天一个 day-card；无空 section。
- round74：门禁唯一实现在 render_gates.py（enforce + validate_html），本文件只做组件渲染。
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# round74：共享辅助与门禁收敛——本文件只做 HTML 组件渲染；
# 门禁唯一实现在 render_gates.py，跨格式辅助在 common/render_shared.py。
from common.render_shared import (CATEGORY_ORDER, clean,  # noqa: E402
                                  display_price as _display_price,
                                  load_cafeteria_templates,
                                  normalize_provider_name as _normalize_provider_name,
                                  window_no_fasting as _window_no_fasting)
from render_gates import (BANNED_EXCLUDED_DAY_PHRASES, BANNED_PATTERNS,  # noqa: E402,F401
                          BANNED_TITLE_TERMS, BANNED_USER_FACING_PHRASES,
                          EXCLUDED_DAY_STANDARD_COPY, HOUSEHOLD_PLAN_MODES,
                          PIPELINE_COMPONENTS, PLAN_META_FIELDS, PLAN_SCHEMA_VERSION,
                          REQUIRED_PLAN_KEYS, check_plan_meta, check_provider_name_leak,
                          compute_pipeline_bundle_hash, compute_rules_bundle_hash,
                          enforce, enforce_tips, validate_html)


def esc(text):
    return clean(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def moon_phase(dt):
    """真实月相：返回 (照亮比例 0~1, 是否盈月, 相位名)。仅用于日期视觉记录，不参与健康判断。"""
    import math
    from datetime import datetime, timezone
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)  # 参考新月
    if not hasattr(dt, "hour"):  # date → datetime
        from datetime import datetime as _dt
        dt = _dt(dt.year, dt.month, dt.day, 12)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (dt - ref).total_seconds() / 86400.0
    age = days % 29.530588853
    illum = (1 - math.cos(2 * math.pi * age / 29.530588853)) / 2
    waxing = age < 29.530588853 / 2
    # round39：满月/新月窗口收窄（各约 ±0.8 天），避免一周轨道出现 3 至 4 天同名相位
    names = [(1.02, "新月"), (6.40, "娥眉月"), (8.15, "上弦月"), (13.97, "盈凸月"),
             (15.57, "满月"), (21.40, "亏凸月"), (22.85, "下弦月"), (28.51, "残月"), (29.54, "新月")]
    name = next(n for lim, n in names if age <= lim)
    return illum, waxing, name


def _moon_svg(illum, waxing, today=False):
    """月相图标：暗底圆 + 亮部单一连续 path（半圆弧 + terminator 椭圆弧），无碎片叠加。
    亮面 #fff8df、暗面 #2f2b23；盈月右侧亮、亏月左侧亮。"""
    r = 10
    ex = round(abs(2 * illum - 1) * r, 2)
    if illum <= 0.02:
        light = ""
    elif illum >= 0.98:
        light = f'<circle cx="12" cy="12" r="{r}" fill="#fff8df"/>'
    else:
        outer = 1 if waxing else 0
        inner = outer if illum > 0.5 else 1 - outer
        light = (f'<path d="M12 {12-r} A{r} {r} 0 0 {outer} 12 {12+r} '
                 f'A{ex} {r} 0 0 {inner} 12 {12-r} Z" fill="#fff8df"/>')
    cls = "moon-phase moon-today" if today else "moon-phase"
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="26" height="26">'
            f'<circle cx="12" cy="12" r="{r}" fill="#2f2b23"/>{light}'
            f'<circle cx="12" cy="12" r="{r}" fill="none" stroke="rgba(255,248,223,.36)"/></svg>')


def render_cover(plan):
    from datetime import date, timedelta
    import re as _re
    p = plan["plan"]
    # round58：封面摘要卡固定四卡（天数/模式/进食窗口/预算），阶段变化写入副标题
    stats_map = p.get("stats", {})
    if stats_map and list(stats_map.keys()) != ["天数", "模式", "进食窗口", "预算"]:
        raise SystemExit("封面摘要卡契约错误：stats 必须固定为 天数/模式/进食窗口/预算 "
                         "四张等宽卡（阶段变化写入 subtitle，不进卡片）")
    # 从 date_range 解析起始日，生成当周真实月相轨道；解析失败退回均匀占位
    moons = ""
    m = _re.search(r"(\d{4})-(\d{2})-(\d{2})", str(p.get("date_range", "")))
    if m:
        start = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        today = date.today()
        for i in range(7):
            d = start + timedelta(days=i)
            illum, waxing, name = moon_phase(d)
            moons += f'<div class="moon-cell">{_moon_svg(illum, waxing, d == today)}<span>{d.month}/{d.day} {name}</span></div>'
    else:
        moons = "".join('<div class="moon-cell">' + _moon_svg(0.5, True) + "<span></span></div>" for _ in range(7))
    stats = "".join(f'<div class="cover-stat"><div class="cover-stat-value">{esc(v)}</div>'
                    f'<div class="cover-stat-label">{esc(k)}</div></div>'
                    for k, v in stats_map.items())
    return f"""
<section class="cover-hero">
  <div class="cover-kicker">{esc(p.get('kicker', '月食'))} · PERSONALIZED EATING PLAN</div>
  <h1 class="cover-title">饮食计划</h1>
  <div class="cover-date-range">{esc(p['date_range'])}</div>
  <div class="cover-subtitle">{esc(p.get('subtitle', ''))}</div>
  <div class="cover-meta">{stats}</div>
  <div class="moon-track">{moons}</div>
  <div class="moon-note">月相仅作日期视觉记录，与身体周期无因果映射。</div>
</section>"""


def render_profile(profile):
    # 章节白名单：用户基本信息仅内部计算，不呈现在交付文件中
    return ""


def render_stage(ov):
    """01 本周阶段：当前周期位置 + 本周策略 + 未来三周展望。"""
    rows = "".join(f"<tr><td>{esc(w['time'])}</td><td>{esc(w['stage'])}</td><td>{esc(w['plan'])}</td></tr>"
                   for w in ov.get("weeks", []))
    note = f"<p class='stage-note'>{esc(ov['note'])}</p>" if ov.get("note") else ""
    return (f'<section class="page-section" id="stage"><h2>本周阶段</h2>'
            f"<p><strong>当前周期位置</strong>：{esc(ov['current'])}</p>"
            f"<p><strong>本周策略</strong>：{esc(ov['strategy'])}</p>"
            f"<table class='stage-table'><thead><tr><th>时间</th><th>阶段</th><th>饮食策略</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>{note}</section>")


def _parse_price_yuan(s):
    """从"26元/袋""约8.5元/500g"解析数值；失败返回 None。"""
    m = re.search(r'(\d+(?:\.\d+)?)\s*元', s or "")
    return float(m.group(1)) if m else None


def _ingredient_cell(item) -> str:
    """食材列双行显示（方案 §5.2）：主行标准食材名；
    有叮咚商品名时第二行小字浅灰「（叮咚：…）」。
    provider_product_name 只允许出现在采购清单，绝不进入菜谱层。"""
    html = esc(item["ingredient"])
    ppn = (item.get("provider_product_name") or "").strip()
    if ppn:
        html += (f'<span class="provider-product-name">'
                 f'（叮咚：{esc(_normalize_provider_name(ppn))}）</span>')
    return html


def _meal_usage_count(allocation: str) -> int:
    """从 meal_allocation 文本估算使用餐次数（顿号/分号/逗号分隔）。"""
    if not allocation:
        return 0
    return len([p for p in re.split(r"[、;；,，/]+", allocation) if p.strip()])


def render_meal_usage_map(items, fmt: str, mode: str) -> str:
    """「对应菜单及用量」映射组件（round56 定稿：格式差异化）。

    - HTML：完整可折叠（details），完整列出无截断；
    - PDF：固定 hidden——不生成章节标题、表头、残留行或空容器；
    - mode=summary 仅供内部预留，正式配置中 PDF 不得使用 full/summary/auto。
    任何模式都不读取 provider_product_name；禁止"见网页版展开"式截断。
    """
    if mode == "hidden":
        return ""
    alloc = [i for i in items if i.get("meal_allocation")]
    if not alloc:
        return ""
    if mode == "summary":
        rows = "".join(
            f"<tr><td>{esc(i['ingredient'])}</td>"
            f"<td>{esc(i.get('required_quantity', ''))}</td>"
            f"<td>用于 {_meal_usage_count(i['meal_allocation'])} 餐</td></tr>"
            for i in alloc)
        return ("<table class='menu-map-table menu-map-summary'><thead><tr><th>食材</th>"
                "<th>总需求量</th><th>使用情况</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>")
    rows = "".join(
        f"<tr><td>{esc(i['ingredient'])}</td>"
        f"<td>{esc(i.get('required_quantity', ''))}</td><td>{esc(i['meal_allocation'])}</td></tr>"
        for i in alloc)
    table = ("<table class='menu-map-table'><thead><tr><th>食材</th><th>总需求量</th>"
             f"<th>对应菜单及用量</th></tr></thead><tbody>{rows}</tbody></table>")
    return ("<details class='menu-map'><summary>查看食材和对应菜谱<span class='menu-map-hint'>"
            "（展开核对采购数量如何分配到七天）</span></summary>"
            f"{table}</details>")


def _meal_map_mode(plan, fmt: str) -> str:
    """解析 output_options.meal_usage_map（round56 定稿）。

    缺省：html/docx/markdown=full；**pdf 固定 hidden**——完整展开约占 3 页、
    与七天菜单重复，PDF 不再支持 auto/full/summary 试排与降级，也不输出
    映射表评估日志。显式把 pdf 配成非 hidden 即渲染失败。
    """
    opts = (plan.get("output_options") or {}).get("meal_usage_map") or {}
    if fmt == "pdf":
        mode = str(opts.get("pdf", "hidden")).lower()
        if mode != "hidden":
            raise SystemExit("meal_usage_map 配置错误：PDF 固定 hidden，"
                             "不再支持 full/summary/auto（对应菜单及用量只在 "
                             "HTML/Word/Markdown 展示）")
        return "hidden"
    mode = str(opts.get(fmt, "full")).lower()
    if mode not in ("full", "summary", "hidden"):
        raise SystemExit(f"output_options.meal_usage_map.{fmt} 非法取值: {mode}"
                         "（可选 full/summary/hidden）")
    return mode


def render_shopping(shopping, fmt: str = "html", meal_map_mode: str = "full"):
    items = shopping.get("items", [])
    groups = {}
    for i in items:
        if not (i.get("reference_price") or "").strip():
            raise SystemExit(f"价格硬门禁：{i.get('ingredient')} 缺参考价，停止渲染（走 data/price-estimates.json 估算补全）")
        groups.setdefault(i.get("category") or "其他", []).append(i)
    order = [c for c in CATEGORY_ORDER if c in groups] + [c for c in groups if c not in CATEGORY_ORDER]
    body = []
    for cat in order:
        body.append(f'<tr class="shopping-category"><td colspan="7">{esc(cat)}</td></tr>')
        for i in groups[cat]:
            subs = esc("、".join(i.get("substitutes", []))) or "—"
            body.append(
                "<tr>"
                f'<td class="ingredient-name">{_ingredient_cell(i)}</td>'
                f"<td>{esc(i.get('required_quantity', ''))}</td>"
                f"<td>{esc(i.get('acceptable_package', ''))}</td>"
                f"<td>{esc(_display_price(i))}</td>"
                f"<td>{esc(i.get('purchase_note', ''))}</td>"
                f"<td>{subs}</td>"
                f"<td>{esc(i.get('leftover_action', ''))}</td>"
                "</tr>")
    total = f"<p class='shopping-total'>本周预计支出：{esc(shopping['total'])}</p>" if shopping.get("total") else ""
    # 预算双口径（round39）：库存食材按参考价单独标注，防止真实开支被"库存"隐形
    inv_items = [i for i in items if i.get("purchase_status") == "from_inventory"]
    inv_sum = sum(v for v in (_parse_price_yuan(i.get("reference_price")) for i in inv_items) if v)
    if inv_items and inv_sum > 0:
        base = _parse_price_yuan(shopping.get("total", ""))
        if base is not None:
            total += (f"<p class='shopping-total-dual'>本周实际支出（不含库存）：{esc(shopping['total'])}；"
                      f"含库存全口径约：{round(base + inv_sum, 1)}元"
                      f"（其中库存食材参考价合计约 {round(inv_sum, 1)}元）</p>")
        else:
            total += (f"<p class='shopping-total-dual'>另：库存食材参考价合计约 "
                      f"{round(inv_sum, 1)}元，不计入本周支出</p>")
    note = f"<p class='shopping-note'>{esc(shopping['price_note'])}</p>" if shopping.get("price_note") else ""
    # 食材↔菜谱映射表（round56 格式差异化）：HTML 可折叠完整版 / PDF 完整展开
    # （版面不合格时可切 summary/hidden）；数据始终完整保留在 plan.json。
    mmap = render_meal_usage_map(items, fmt, meal_map_mode)
    return ("<section class='page-section' id='shop'><h2>采购清单</h2>"
            "<table class='shopping-table'><thead><tr><th>食材</th><th>需要量</th><th>建议购买规格</th><th>参考价</th><th>购买备注</th><th>替代</th><th>剩余去向</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>{total}{note}{mmap}</section>")


def render_prep(prep):
    """备餐任务节：主采购日 + 备餐日 + 食材流转核验（0 剩余验证）。"""
    blocks = []
    if prep.get("purchase_day"):
        items = "".join(f"<li>{esc(x)}</li>" for x in prep["purchase_day"].get("tasks", []))
        blocks.append(f'<div class="prep-block"><h4>主采购日（{esc(prep["purchase_day"].get("label", ""))}）</h4><ul>{items}</ul></div>')
    if prep.get("prep_day"):
        items = "".join(f"<li>{esc(x)}</li>" for x in prep["prep_day"].get("tasks", []))
        blocks.append(f'<div class="prep-block"><h4>备餐日（{esc(prep["prep_day"].get("label", ""))}）</h4><ul>{items}</ul></div>')
    ver = prep.get("leftover_verification", [])
    if len(ver) < 3:
        raise SystemExit("流转核验硬门禁：至少 3 项食材的 0 剩余/去向验证")
    rows = "".join(f"<tr><td>{esc(v['ingredient'])}</td><td>{esc(v.get('purchase_vs_use', ''))}</td>"
                   f"<td>{esc(v.get('result', ''))}</td></tr>" for v in ver)
    blocks.append('<div class="prep-block"><h4>食材流转核验</h4>'
                  '<table class="verify-table"><thead><tr><th>食材</th><th>购买量 vs 计划用量</th>'
                  f"<th>核验结果</th></tr></thead><tbody>{rows}</tbody></table></div>")
    return '<section class="page-section" id="prep"><h2>备餐任务</h2>' + "".join(blocks) + "</section>"


def render_meal_row(meal, include_steps, cafeteria_templates=None):
    t = f'<div class="meal-time">{esc(meal["time"])}</div>' if meal.get("time") else "<div></div>"
    s = f'<div class="meal-status">{esc(meal["status"])}</div>' if meal.get("status") else "<div></div>"
    # 食堂/外食：模板与营养估算统一从 data/cafeteria-meal-templates.json 读取，不在此拼接数字
    if meal.get("meal_source") == "cafeteria":
        # 餐次完整性门禁拆分（output-policy.md「餐次内容完整性」）：
        # 业务数据缺失（plan.json/模板缺字段）→ MEAL_DATA_MISSING，返回菜单装配层修复；
        # 数据齐全但渲染漏出 → MEAL_RENDER_FIELD_DROPPED，不重新计算菜单，只重跑渲染器。
        biz_missing = [k for k in ("time", "name", "status") if not str(meal.get(k, "")).strip()]
        if biz_missing:
            raise SystemExit(f"MEAL_DATA_MISSING：餐次业务字段缺失 {biz_missing}（{meal.get('name') or meal.get('order_template')}）")
        tpls = cafeteria_templates or {}
        tpl = tpls.get(meal.get("order_template", "balanced_standard"), {})
        if not tpl.get("display"):
            raise SystemExit(f"MEAL_DATA_MISSING：食堂模板 {meal.get('order_template')} 无 display 内容（返回菜单装配层修复）")
        est = tpl.get("nutrition_estimate", {})
        est_line = (f"估算净碳水约{est['net_carbs_g']}g / 蛋白质约{est['protein_g']}g / 脂肪约{est['fat_g']}g"
                    if est else "")
        note = tpl.get("display_note", "")
        dish = (f'<div class="dish"><strong>{esc(meal.get("name", "午餐"))}</strong> '
                f'食堂点餐：{esc(tpl.get("display", ""))}'
                f'<span class="grams">{esc(est_line)}{(" · " + esc(note)) if note else ""}</span></div>')
        return f'<div class="meal">{t}{dish}{s}</div>'

    steps_html = ""
    ri = meal.get("recipe_instruction")
    if include_steps and ri and ri.get("steps"):
        steps = "".join(f"<li>{esc(x)}</li>" for x in ri["steps"])
        meta = "；".join(x for x in [
            f"要点：{'、'.join(ri['preparation_notes'])}" if ri.get("preparation_notes") else "",
            f"火力：{ri['heat_or_temperature']}" if ri.get("heat_or_temperature") else "",
            f"熟度判断：{ri['doneness_signal']}" if ri.get("doneness_signal") else "",
            f"可提前：{ri['advance_prep']}" if ri.get("advance_prep") and ri.get("advance_prep") != "—" else "",
        ] if x)
        steps_html = f'<div class="recipe-steps">做法：<ol>{steps}</ol>{esc(meta)}</div>'
    grams = f'<span class="grams">{esc(meal.get("grams", ""))}</span>' if meal.get("grams") else ""
    ms = meal.get("meal_structure") or {}
    struct = (f'<span class="structure-note">{esc(ms["structure_note"])}</span>'
              if ms.get("structure_note") else "")
    dish = (f'<div class="dish"><strong>{esc(meal.get("name", ""))}</strong> {esc(meal.get("dishes", ""))}'
            f'{grams}{struct}{steps_html}</div>')
    return f'<div class="meal">{t}{dish}{s}</div>'


_CAFETERIA_TEMPLATES = None


def _day_nutrition_line(d, fmt):
    """每日营养行（round67）：PDF 只展示生活化摘要，不逐日展示计算口径；
    HTML/Markdown 保留参考估算行。旧 plan（无 nutrition_summary）向后兼容。"""
    if fmt == "pdf":
        ns = d.get("nutrition_summary") or {}
        if ns:
            return ns.get("user_line") or ""
        return d.get("nutrition_line", "")
    return d.get("nutrition_line", "")


def render_days(days, include_steps, fmt="html"):
    out = []
    for d in days:
        meals = "".join(render_meal_row(m, include_steps, _CAFETERIA_TEMPLATES) for m in d.get("meals", []))
        advice = f'<div class="day-advice">当日建议：{esc(d["advice"])}</div>' if d.get("advice") else ""
        line = _day_nutrition_line(d, fmt)
        total = f'<div class="day-total">{esc(line)}</div>' if line else ""
        window = _window_no_fasting(d.get("window", ""))
        out.append(f'<div class="day-card"><h3>{esc(d["label"])}</h3>'
                   f'<div class="window">{esc(window)}</div>{meals}{total}{advice}</div>')
    return '<section class="page-section" id="week"><h2>七天菜单</h2>' + "".join(out) + "</section>"


def render_wisdom(plan):
    """食养之理与执行说明：两个子区块（本周怎么安排 / 本周执行要点），同字号。"""
    wisdom = plan.get("wisdom") or {}
    parts = []
    paras = wisdom.get("paragraphs") or []
    if paras:
        parts.append("<h4 class='wisdom-subheading'>本周怎么安排</h4>")
    for para in paras:
        parts.append(f"<p class='wisdom-para'>{esc(para)}</p>")
    if not paras:  # 兼容旧 dict 形式
        for key in ("shunshi", "wuwei", "ziran"):
            if wisdom.get(key):
                parts.append(f"<p class='wisdom-para'>{esc(wisdom[key])}</p>")
    if not paras and plan.get("rationale"):
        items = "".join(f"<li>{esc(x)}</li>" for x in plan["rationale"])
        parts.append(f'<ul class="rationale-list">{items}</ul>')
    tips = plan.get("execution_tips") or []
    tips_html = ""
    if tips:
        items = "".join(f"<li>{esc(x)}</li>" for x in tips)
        tips_html = ("<h4 class='wisdom-subheading'>本周执行要点</h4>"
                     f'<ul class="tips-list">{items}</ul>')
    if not parts and not tips_html:
        return ""
    return ('<section class="page-section" id="why"><h2>食养之理与执行说明</h2>'
            + "".join(parts) + tips_html + "</section>")


def render_disclaimer(disclaimer):
    return f'<footer class="document-footer disclaimer">{esc(disclaimer)}</footer>'


def render_document(plan, fmt: str = "html"):
    # round74：入口统一走 render_gates.enforce（缺字段/版本/价格/流转）。
    # 本函数作为内部渲染接口，保留其原有输出契约检查（泄漏 + PDF 提示条数），
    # 便于测试与 render_pdf 直接调用；不重复执行入口级门禁。
    check_provider_name_leak(plan)
    enforce_tips(plan, fmt)
    include_steps = plan["plan"].get("include_recipe_steps") is True
    global _CAFETERIA_TEMPLATES
    if _CAFETERIA_TEMPLATES is None:  # render_pdf 等直接调用路径也要加载模板
        _CAFETERIA_TEMPLATES = load_cafeteria_templates()
    parts = [render_cover(plan)]
    if plan.get("stage_overview"):
        parts.append(render_stage(plan["stage_overview"]))
    parts.append(render_shopping(plan["shopping"], fmt=fmt,
                                 meal_map_mode=_meal_map_mode(plan, fmt)))
    if plan.get("prep"):
        parts.append(render_prep(plan["prep"]))
    parts.append(render_days(plan["days"], include_steps, fmt=fmt))
    wisdom = render_wisdom(plan)
    if wisdom:
        parts.append(wisdom)
    parts.append(render_disclaimer(plan["disclaimer"]))
    body = "".join(parts)
    # 打印时展开所有 <details>；屏幕端保持可折叠，无其他交互
    unfold = ("<script>window.addEventListener('beforeprint',function(){"
              "document.querySelectorAll('details').forEach(function(d){d.open=true})});</script>")
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>饮食计划</title>" + inline_styles() +
            "</head><body><main>" + body + "</main>" + unfold + "</body></html>")


STYLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles")


def inline_styles():
    """交付 HTML 必须单文件自包含：读取 screen.css / print.css 内联为 <style>，
    不输出相对 CSS 路径，离开项目目录仍能完整显示。"""
    parts = []
    for name, media in [("screen.css", None), ("print.css", "print")]:
        fp = os.path.join(STYLES_DIR, name)
        if not os.path.exists(fp):
            raise SystemExit(f"缺少样式文件 {fp}，停止渲染")
        css = clean(open(fp, encoding="utf-8").read())
        attr = f" media='{media}'" if media else ""
        parts.append(f"<style{attr}>\n{css}\n</style>")
    return "".join(parts)


def main():
    global _CAFETERIA_TEMPLATES
    _CAFETERIA_TEMPLATES = load_cafeteria_templates()
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", default="html",
                    help="仅支持 html；PDF 请用 render_pdf.py 或 render_output.py")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    # round74：本脚本只产 HTML。此前 --format pdf 会把 HTML 写进 .pdf 命名的文件；
    # 现直接拒绝并指路（PDF 由 render_pdf.py 打印一次生成）。
    if args.format != "html":
        print("render_plan.py 只生成 HTML：PDF 请用 render_pdf.py，"
              "或经渲染总控 render_output.py --format pdf 调用。", file=sys.stderr)
        sys.exit(2)
    plan = json.load(open(args.input, encoding="utf-8"))
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        print(f"plan.json 缺字段，停止渲染: {missing}", file=sys.stderr)
        sys.exit(2)
    # round74：入口级统一门禁（版本/泄漏/价格/流转/提示条数）。
    enforce(plan, "html")
    html = render_document(plan, fmt="html")
    errs = validate_html(html, plan)
    if errs:
        print("渲染门禁未通过：" + "; ".join(errs), file=sys.stderr)
        sys.exit(3)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已渲染 {args.output}（include_recipe_steps={plan['plan'].get('include_recipe_steps')}）")


if __name__ == "__main__":
    main()
