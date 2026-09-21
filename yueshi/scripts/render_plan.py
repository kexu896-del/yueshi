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
# 家庭模式集合（与 SKILL.md household_plan_modes 一致；禁止用 "shared_*" 前缀匹配）
HOUSEHOLD_PLAN_MODES = ("shared_uniform", "shared_meal_personalized", "split_safety_required")
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
    if rbh and rbh != compute_rules_bundle_hash(plan.get("plan_mode")):
        raise SystemExit("rules_bundle_hash 与当前规则文件不一致（生成规则包与渲染环境错配），停止渲染")


def compute_rules_bundle_hash(plan_mode=None):
    """runtime-rules + nutrition-routing + output-policy + safety-rules + effective-parameters + library-manifest 组合哈希。
    plan_mode ∈ HOUSEHOLD_PLAN_MODES 时追加家庭规则与契约清单（家庭规则/Schema 变更即触发 mismatch）。"""
    import hashlib
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    parts = ["references/runtime-rules.md", "references/nutrition-routing.md",
             "references/output-policy.md", "references/safety-rules.md",
             "data/effective-parameters.json", "data/library-manifest.json"]
    if plan_mode in HOUSEHOLD_PLAN_MODES:
        parts += ["references/household-runtime-rules.md",
                  "workflows/household-planning-flow.md",
                  "data/household-limits.json",
                  "schemas/household/shared-definitions.schema.json",
                  "schemas/household/household-base-plan.schema.json",
                  "schemas/household/household-overrides.schema.json",
                  "schemas/household/household-effective-plan.schema.json",
                  "schemas/household/household-schemas.bundle.json"]
    h = hashlib.sha1()
    for rel in parts:
        fp = os.path.join(base, rel)
        h.update(rel.encode())
        h.update(open(fp, "rb").read() if os.path.exists(fp) else b"<missing>")
    return h.hexdigest()[:16]


# 执行组件清单（pipeline_bundle_hash 输入：生成器/合并器/校验器/渲染器，与规则包哈希分工）
PIPELINE_COMPONENTS = [
    "scripts/render_plan.py", "scripts/render_html.py", "scripts/render_pdf.py",
    "scripts/render_markdown.py", "scripts/render_docx.py", "scripts/render_output.py",
    "scripts/household_override_merger.py", "scripts/household_reference_validator.py",
    "scripts/household_components.py", "scripts/nutrition_adjuster.py",
    "scripts/basket_builder.py", "scripts/build_adjustment_options.py",
    "scripts/price_result_validator.py", "scripts/price_provider_router.py",
]


def compute_pipeline_bundle_hash():
    """执行组件组合哈希：区分"规则错配"（rules_bundle_hash）与"执行组件错配"（本哈希）。"""
    import hashlib
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    h = hashlib.sha1()
    for rel in PIPELINE_COMPONENTS:
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


CATEGORY_ORDER = ["肉蛋水产与豆制品", "蔬菜与菌菇", "谷物薯类与主食", "乳品与油脂", "水果", "调味与干货", "其他"]

# 价格三层口径（与 SKILL.md「采购输出」一致）：直采公开价直接显示，估算价统一加"约"前缀
ESTIMATE_PRICE_BASIS = ("category_estimate", "historical_estimate")


def _display_price(item):
    """按 price_basis 渲染价格：库存食材显示"库存"并附参考价（预算双口径，round39）；
    direct_public_price 原样；估算层缺"约"前缀时补上。"""
    price = (item.get("reference_price") or "").strip()
    if item.get("purchase_status") == "from_inventory":
        if price and not price.startswith("0元"):
            return f"库存（参考 {price}）"
        return "库存"
    if price.startswith("0元"):
        return "库存"
    if item.get("price_basis") in ESTIMATE_PRICE_BASIS and price and not price.startswith("约"):
        return "约" + price
    return price


def _parse_price_yuan(s):
    """从"26元/袋""约8.5元/500g"解析数值；失败返回 None。"""
    m = re.search(r'(\d+(?:\.\d+)?)\s*元', s or "")
    return float(m.group(1)) if m else None


def _normalize_provider_name(name: str) -> str:
    """叮咚商品名标点规范化（方案 §5.2/§六）：内部括号改为逗号，
    避免「猪里脊（新鲜猪大里脊（去筋膜））」嵌套括号；外层只保留一个（叮咚：…）。"""
    out = (name.replace("（", "，").replace("）", "")
           .replace("(", "，").replace(")", ""))
    return out.strip("，, ·、")


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

def _window_no_fasting(window):
    """每日卡片标题行不得出现“禁食/空腹”：只保留进食窗口部分。"""
    w = re.split(r"[·;；]", str(window))[0].strip()
    w = re.sub(r"禁食[^·;；]*", "", w).strip()
    return w


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


def check_provider_name_leak(plan):
    """字段泄漏门禁（round54，方案 §5.1）：provider_product_name（叮咚商品名）
    只允许出现在 shopping.items / price_snapshot；菜谱、餐次、做法等可见层
    出现即渲染失败，防止商品名污染七天菜单。"""
    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "provider_product_name":
                    raise SystemExit(
                        "字段泄漏门禁：provider_product_name 出现在菜谱层"
                        f"（{path}），只允许在采购清单/价格快照中")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for n, v in enumerate(node):
                walk(v, f"{path}[{n}]")
    for key in ("days", "recipes", "meals", "menu"):
        if key in plan:
            walk(plan[key], key)
    # 值级泄漏：采购层登记的商品名不得以原文混进菜单/餐次可见文本。
    names = [it.get("provider_product_name")
             for it in plan.get("shopping", {}).get("items", [])
             if it.get("provider_product_name")]
    if names:
        visible = json.dumps({k: plan[k] for k in ("days", "recipes", "meals", "menu")
                              if k in plan}, ensure_ascii=False)
        for nm in names:
            if nm in visible:
                raise SystemExit(
                    f"字段泄漏门禁：叮咚商品名「{nm}」出现在菜单/餐次文本，"
                    "只允许出现在采购清单双行（provider-product-name）中")


def render_document(plan, fmt: str = "html"):
    include_steps = plan["plan"].get("include_recipe_steps") is True
    if fmt == "pdf":
        tips = plan.get("execution_tips") or []
        if len(tips) > 5:
            raise SystemExit(
                "PDF 执行提醒最多 5 条（references/output-policy.md「用户表达层」）："
                "当前 %d 条，请收敛到 5 条以内" % len(tips))
    check_provider_name_leak(plan)
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

# round67 用户表达层：这些内部表达不得出现在任何用户可见文字（见 output-policy.md）
BANNED_USER_FACING_PHRASES = [
    "新版试跑", "试跑", "江淮时令覆盖层", "时令覆盖层", "蛋白角色对齐", "角色对齐",
    "热量补偿", "自动追加", "主餐口径", "不计入碳水上限", "不计上限",
    "降权保留", "评分过程", "构建状态", "纠错记录", "校验通过", "门禁结果",
]

# 非做饭日标准文案（round45）：excluded 日只此一种表述
EXCLUDED_DAY_STANDARD_COPY = "今天不在家用餐，本计划不安排菜单，也不计入本周采购与营养合计"
BANNED_EXCLUDED_DAY_PHRASES = ["三餐自行解决", "无人在家吃饭"]

# 用户可见标题禁用内部术语（见 references/output-policy.md「用户可见术语门禁」；
# 仅扫描可见文字字段/最终用户文件可见文字，不扫描 plan.json 内部字段与日志）
BANNED_TITLE_TERMS = ["周期协议", "source_verified", "audit_status", "source_rule_id",
                      "protocol_version", "effective_parameters", "safety_policy",
                      "reason_code", "accepted_batch", "locked_basket",
                      "provisional_locked_basket", "plan.json", "gate_result",
                      "low confidence", "runtime-rules", "nutrition-routing",
                      # round57 扩充：Round55/56 新增内部状态与字段
                      "awaiting_price_result", "price_result_received",
                      "opt_out_after_query", "dingdong_helper_opt_in",
                      "menu_snapshot_hash", "nutrition_snapshot_hash",
                      "shopping_demand_hash", "price_result_hash",
                      "migration_log", "provider_product_name",
                      "shopping_meal_usage_map"]


def validate_html(html, plan):
    errs = []
    for pat in BANNED_PATTERNS:
        if pat in html:
            errs.append(f"残留占位符/异常值: {pat}")
    for phrase in BANNED_USER_FACING_PHRASES:
        if phrase in html:
            errs.append(f"用户可见文字出现内部表达: {phrase}")
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
    # 采购清单"一行一食材"硬门禁（round39）：食材名不得合并多项
    for i in plan["shopping"].get("items", []):
        name = i.get("ingredient", "")
        if re.search(r'[、，,+＋/]|\s和\s|及', name):
            errs.append(f"采购项合并了多个食材（违反一行一食材）: {name}")
    # 备餐/建议日期派生校验（round39）：标签中"周X M/D"必须与真实星期一致
    year_m = re.search(r'(\d{4})', plan["plan"].get("date_range", ""))
    if year_m:
        import datetime as _dtm
        y = int(year_m.group(1))
        wk = "一二三四五六日"
        prep = plan.get("prep", {})
        for key in ("purchase_day", "prep_day"):
            lbl = str(prep.get(key, {}).get("label", ""))
            m = re.search(r'周([一二三四五六日])\D*(\d{1,2})/(\d{1,2})', lbl)
            if m:
                try:
                    real = _dtm.date(y, int(m.group(2)), int(m.group(3))).weekday()
                    if wk[real] != m.group(1):
                        errs.append(f"{key} 日期与星期不符（{lbl}，实际为周{wk[real]}）——日期文案必须从 plan.json 派生")
                except ValueError:
                    errs.append(f"{key} 日期非法: {lbl}")
    # 非做饭日文案门禁（round45）：禁止"三餐自行解决/无人在家吃饭"，用标准文案
    for ph in BANNED_EXCLUDED_DAY_PHRASES:
        if ph in html:
            errs.append(f"非做饭日文案不合规（含 {ph!r}），应使用标准文案：{EXCLUDED_DAY_STANDARD_COPY}")
    # 大米生熟口径硬门禁（round45）：采购表米类必须以生米汇总并标注对应熟米饭量
    for i in plan["shopping"].get("items", []):
        blob = json.dumps(i, ensure_ascii=False)
        if re.search(r'大米|糙米|香米|粳米|籼米', i.get("ingredient", "")):
            if "生米" not in blob:
                errs.append(f"采购项 {i.get('ingredient')} 未以生米口径汇总（禁止以熟饭重充当生米/库存米重量）")
            elif "熟米饭" not in blob and "熟重" not in blob:
                errs.append(f"采购项 {i.get('ingredient')} 缺对应熟米饭量标注（生米约Xg 对应熟米饭约Yg）")
    # 功效断言门禁（round39）：可见文字不得出现未标注来源层级的功效表述
    for pat in (r'对(骨骼|血脂|代谢|激素|血糖).{0,8}(更友好|有益|改善)',
                r'(延缓衰老|治疗|治愈|降三高)'):
        if re.search(pat, html):
            errs.append(f"出现未经来源标注的功效表述: {pat}")
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
    html = render_document(plan, fmt=args.format)
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
