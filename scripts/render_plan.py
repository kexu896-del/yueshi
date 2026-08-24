#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_plan.py — 月食固定组件渲染器（三层架构第二层）

用法：python scripts/render_plan.py --input plan.json --format html|pdf --output plan.html|plan.pdf

规则（硬约束，见 SKILL.md「渲染架构」）：
- 输入只有一份校验过的 plan.json；本脚本不重新编菜单、不重算营养。
- 固定组件函数渲染：cover / profile / shopping_table / day_card / recipe_steps / disclaimer。
- 不使用全局占位符 replace 充当模板引擎；缺字段立即报错停止。
- HTML 只渲染一次；PDF 只转换一次（由外部打印工具完成，本脚本只产 HTML）。
- 渲染后执行完整性门禁：无 {{ }} / PLACEHOLDER / undefined / None / [object Object]；
  恰好一个 <main> 与一个 cover；每天一个 day-card；无空 section。
"""
import argparse, json, os, re, sys, unicodedata

REQUIRED_PLAN_KEYS = ["plan", "profile", "shopping", "days", "disclaimer"]

# plan.json 版本门禁（见 references/output-policy.md「plan_meta 版本契约」）
PLAN_SCHEMA_VERSION = "1"
PLAN_META_FIELDS = ["plan_schema_version", "skill_version", "runtime_rules_version",
                    "nutrition_rules_version", "output_policy_version",
                    "recipe_manifest_version", "effective_parameters_version", "price_data_version"]


def check_plan_meta(plan):
    """渲染前版本门禁：plan_meta 必须存在且 schema 版本与本渲染器一致，防止新旧混跑。
    plan_meta 带 rules_bundle_hash 时与当前规则文件组合哈希比对（防生成器与规则包错配）。"""
    meta = plan.get("plan_meta")
    if not meta:
        raise SystemExit("plan.json 缺 plan_meta 版本块，停止渲染（见 output-policy.md 版本门禁）")
    missing = [k for k in PLAN_META_FIELDS if k not in meta]
    if missing:
        raise SystemExit(f"plan_meta 缺字段: {missing}")
    if str(meta["plan_schema_version"]) != PLAN_SCHEMA_VERSION:
        raise SystemExit(f"plan_schema_version={meta['plan_schema_version']} 与渲染器支持版本 {PLAN_SCHEMA_VERSION} 不一致，停止渲染")
    rbh = meta.get("rules_bundle_hash")
    if rbh and rbh != compute_rules_bundle_hash():
        raise SystemExit("rules_bundle_hash 与当前规则文件不一致（生成规则包与渲染环境错配），停止渲染")


def compute_rules_bundle_hash():
    """runtime-rules + nutrition-routing + output-policy + safety-rules + effective-parameters + library-manifest 组合哈希。"""
    import hashlib
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    parts = ["references/runtime-rules.md", "references/nutrition-routing.md",
             "references/output-policy.md", "references/safety-rules.md",
             "data/effective-parameters.json", "data/library-manifest.json"]
    h = hashlib.sha1()
    for rel in parts:
        fp = os.path.join(base, rel)
        h.update(rel.encode())
        h.update(open(fp, "rb").read() if os.path.exists(fp) else b"<missing>")
    return h.hexdigest()[:16]


def clean(text):
    text = unicodedata.normalize("NFC", str(text))
    for ch in ["\u00ad", "\ufeff", "\u200b"]:
        text = text.replace(ch, "")
    return text


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
    names = [(1.85, "新月"), (5.54, "娥眉月"), (9.23, "上弦月"), (12.92, "盈凸月"),
             (16.61, "满月"), (20.30, "亏凸月"), (23.99, "下弦月"), (27.69, "残月"), (29.54, "新月")]
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
    # 从 date_range 解析起始日，生成当周真实月相轨道；解析失败退回均匀占位
    moons, names_row = "", ""
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
                    for k, v in p.get("stats", {}).items())
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


CATEGORY_ORDER = ["肉蛋水产与豆制品", "蔬菜与菌菇", "谷物薯类与主食", "乳品与油脂", "水果", "调味与干货", "其他"]

# 价格三层口径（与 SKILL.md「采购输出」一致）：直采公开价直接显示，估算价统一加"约"前缀
ESTIMATE_PRICE_BASIS = ("category_estimate", "historical_estimate")


def _display_price(item):
    """按 price_basis 渲染价格：库存食材显示"库存"；direct_public_price 原样；估算层缺"约"前缀时补上。"""
    if item.get("purchase_status") == "from_inventory":
        return "库存"
    price = (item.get("reference_price") or "").strip()
    if price.startswith("0元"):
        return "库存"
    if item.get("price_basis") in ESTIMATE_PRICE_BASIS and price and not price.startswith("约"):
        return "约" + price
    return price


def render_shopping(shopping):
    items = shopping.get("items", [])
    groups = {}
    for i in items:
        if not (i.get("reference_price") or "").strip():
            raise SystemExit(f"价格硬门禁：{i.get('ingredient')} 缺参考价，停止渲染（走 data/price-estimates.json 估算补全）")
        groups.setdefault(i.get("category") or "其他", []).append(i)
    order = [c for c in CATEGORY_ORDER if c in groups] + [c for c in groups if c not in CATEGORY_ORDER]
    body = []
    for cat in order:
        body.append(f'<tr class="shopping-category"><td colspan="6">{esc(cat)}</td></tr>')
        for i in groups[cat]:
            subs = esc("、".join(i.get("substitutes", []))) or "—"
            body.append(
                "<tr>"
                f'<td class="ingredient-name">{esc(i["ingredient"])}</td>'
                f"<td>{esc(i.get('required_quantity', ''))}</td>"
                f"<td>{esc(i.get('acceptable_package', ''))}</td>"
                f"<td>{esc(_display_price(i))}</td>"
                f"<td>{subs}</td>"
                f"<td>{esc(i.get('leftover_action', ''))}</td>"
                "</tr>")
    total = f"<p class='shopping-total'>本周预计支出：{esc(shopping['total'])}</p>" if shopping.get("total") else ""
    note = f"<p class='shopping-note'>{esc(shopping['price_note'])}</p>" if shopping.get("price_note") else ""
    # 食材↔菜谱对照：网页可折叠下拉，打印自动展开（无 JS）
    mmap = ""
    alloc = [i for i in items if i.get("meal_allocation")]
    if alloc:
        # 打印端只展示前 8 项重点（易腐/0剩余核验价值最高），完整映射网页版展开
        rows = "".join(
            f"<tr{' class=menu-map-extra' if n >= 8 else ''}><td>{esc(i['ingredient'])}</td>"
            f"<td>{esc(i.get('required_quantity', ''))}</td><td>{esc(i['meal_allocation'])}</td></tr>"
            for n, i in enumerate(alloc))
        extra = (f"<tr class='menu-map-print-note'><td colspan='3'>其余 {len(alloc)-8} 项食材映射见网页版展开</td></tr>"
                 if len(alloc) > 8 else "")
        mmap = ("<details class='menu-map'><summary>查看食材和对应菜谱<span class='menu-map-hint'>"
                "（展开核对采购数量如何分配到七天）</span></summary>"
                "<table class='menu-map-table'><thead><tr><th>食材</th><th>总需求量</th>"
                f"<th>对应菜单及用量</th></tr></thead><tbody>{rows}{extra}</tbody></table></details>")
    return ("<section class='page-section' id='shop'><h2>采购清单</h2>"
            "<table class='shopping-table'><thead><tr><th>食材</th><th>需要量</th><th>建议购买规格</th><th>参考价</th><th>替代</th><th>剩余去向</th></tr></thead>"
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

def _window_no_fasting(window):
    """每日卡片标题行不得出现“禁食/空腹”：只保留进食窗口部分。"""
    w = re.split(r"[·;；]", str(window))[0].strip()
    w = re.sub(r"禁食[^·;；]*", "", w).strip()
    return w


def render_days(days, include_steps):
    out = []
    for d in days:
        meals = "".join(render_meal_row(m, include_steps, _CAFETERIA_TEMPLATES) for m in d.get("meals", []))
        advice = f'<div class="day-advice">当日建议：{esc(d["advice"])}</div>' if d.get("advice") else ""
        total = f'<div class="day-total">{esc(d.get("nutrition_line", ""))}</div>' if d.get("nutrition_line") else ""
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


def render_document(plan):
    include_steps = plan["plan"].get("include_recipe_steps") is True
    global _CAFETERIA_TEMPLATES
    if _CAFETERIA_TEMPLATES is None:  # render_pdf 等直接调用路径也要加载模板
        _CAFETERIA_TEMPLATES = load_cafeteria_templates()
    parts = [render_cover(plan)]
    if plan.get("stage_overview"):
        parts.append(render_stage(plan["stage_overview"]))
    parts.append(render_shopping(plan["shopping"]))
    if plan.get("prep"):
        parts.append(render_prep(plan["prep"]))
    parts.append(render_days(plan["days"], include_steps))
    wisdom = render_wisdom(plan)
    if wisdom:
        parts.append(wisdom)
    parts.append(render_disclaimer(plan["disclaimer"]))
    body = "".join(parts)
    # 打印时展开所有 <details>（menu-map）；屏幕端保持可折叠，无其他交互
    unfold = ("<script>window.addEventListener('beforeprint',function(){"
              "document.querySelectorAll('details').forEach(function(d){d.open=true})});</script>")
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>饮食计划</title>" + inline_styles() +
            "</head><body><main>" + body + "</main>" + unfold + "</body></html>")


CAFETERIA_TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cafeteria-meal-templates.json")
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


def load_cafeteria_templates():
    try:
        return json.load(open(CAFETERIA_TEMPLATES_PATH, encoding="utf-8"))["templates"]
    except OSError:
        return {}


BANNED_PATTERNS = ["{{", "}}", "PLACEHOLDER", "undefined", "[object Object]", ">None<",
                   "暂无参考价", "实价为准", "本周档案"]

# 用户可见标题禁用内部术语（见 references/output-policy.md「用户可见术语门禁」；
# 仅扫描可见文字字段/最终用户文件可见文字，不扫描 plan.json 内部字段与日志）
BANNED_TITLE_TERMS = ["周期协议", "source_verified", "audit_status", "source_rule_id",
                      "protocol_version", "effective_parameters", "safety_policy",
                      "reason_code", "accepted_batch", "locked_basket",
                      "provisional_locked_basket", "plan.json", "gate_result",
                      "low confidence", "runtime-rules", "nutrition-routing"]


def validate_html(html, plan):
    errs = []
    for pat in BANNED_PATTERNS:
        if pat in html:
            errs.append(f"残留占位符/异常值: {pat}")
    if html.count("<main>") != 1:
        errs.append("main 数量不等于 1")
    if html.count('class="cover-hero"') != 1:
        errs.append("cover 数量不等于 1")
    days = len(plan["days"])
    if html.count('class="day-card"') != days:
        errs.append(f"day-card 数量({html.count('class=day-card')!r}) 与计划天数({days})不符")
    for m in re.finditer(r'class="meal-time"', html):
        pass
    if re.search(r'<section[^>]*>\s*</section>', html):
        errs.append("存在空 section")
    if re.search(r'<link[^>]+stylesheet', html):
        errs.append("存在 <link> 样式引用（交付 HTML 必须内联自包含）")
    if re.search(r'href=[\'"]styles/', html):
        errs.append("存在相对路径样式引用（交付 HTML 必须内联自包含）")
    # “禁食/空腹”只允许在末节（食养之理与执行提示）出现一次，日卡标题行禁止
    week = re.search(r'id="week"(.*?)<section', html, re.S)
    if week and ("禁食" in week.group(1) or "空腹" in week.group(1)):
        errs.append("七天菜单区出现“禁食/空腹”字样")
    # 日卡标题行之外（本周阶段/末节）允许出现“禁食/空腹”，不做全文计数限制
    for i in plan["shopping"].get("items", []):
        if not (i.get("reference_price") or "").strip():
            errs.append(f"采购项 {i.get('ingredient')} 缺参考价")
    if plan.get("prep") and len(plan["prep"].get("leftover_verification", [])) < 3:
        errs.append("流转核验不足 3 项")
    # 用户可见术语门禁：内部字段名不得出现在封面与各级标题
    title_text = " ".join(re.findall(r'<(?:h1|h2|h3)[^>]*>(.*?)</(?:h1|h2|h3)>', html, re.S))
    cover = re.search(r'class="cover-subtitle">(.*?)<', html, re.S)
    title_text += " " + (cover.group(1) if cover else "")
    for term in BANNED_TITLE_TERMS:
        if term in title_text:
            errs.append(f"标题出现内部术语: {term}")
    # 餐次状态一致性：带具体克数的餐次不得标"自行处理"（planned ≠ guidance_only）
    for d in plan.get("days", []):
        for m in d.get("meals", []):
            if m.get("grams") and "自行处理" in str(m.get("status", "")):
                errs.append(f"{d.get('label')} {m.get('name')}：有克数却标自行处理")
    # 免责声明必须是独立组件（footer.disclaimer），不得拼在执行提示列表尾部
    if 'class="document-footer disclaimer"' not in html:
        errs.append("免责声明不是独立组件")
    tips_block = re.search(r'<ul class="tips-list">(.*?)</ul>', html, re.S)
    if tips_block and str(plan.get("disclaimer", ""))[:10] in tips_block.group(1):
        errs.append("免责声明混入执行提示列表")
    # 渲染字段遗漏（数据齐全但没渲染出来）：只重跑渲染器，不重新计算菜单
    if re.search(r'食堂点餐：\s*<', html) or re.search(r'食堂点餐：\s*</', html):
        errs.append("MEAL_RENDER_FIELD_DROPPED：食堂点餐内容渲染为空")
    return errs


def main():
    global _CAFETERIA_TEMPLATES
    _CAFETERIA_TEMPLATES = load_cafeteria_templates()
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", default="html", choices=["html", "pdf"])
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    plan = json.load(open(args.input, encoding="utf-8"))
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        print(f"plan.json 缺字段，停止渲染: {missing}", file=sys.stderr)
        sys.exit(2)
    check_plan_meta(plan)
    html = render_document(plan)
    errs = validate_html(html, plan)
    if errs:
        print("渲染门禁未通过：" + "; ".join(errs), file=sys.stderr)
        sys.exit(3)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已渲染 {args.output}（include_recipe_steps={plan['plan'].get('include_recipe_steps')}）")
    if args.format == "pdf":
        print("提示：PDF 由外部打印工具对该 HTML 转换一次生成，本脚本不重复渲染。")


if __name__ == "__main__":
    main()
