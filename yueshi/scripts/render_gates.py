#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染门禁唯一实现（round74）

背景：此前门禁散落在四个渲染入口——必填键三份、价格/流转门禁三处、
用户可见文字校验三档分化（HTML 硬门禁 / PDF 调而丢弃 / Markdown·Word 完全不查）。
本模块把全部计划级门禁与文字门禁收敛到一处：

- enforce(plan, fmt)：计划级门禁（必填键 / plan_meta 版本 / 商品名泄漏 /
  价格完整性 / 流转核验 / PDF 执行提醒条数）；四个渲染入口统一调用。
- validate_user_text(text)：Markdown/Word 产物文本门禁（内部表达、内部术语、
  非做饭日违禁文案、占位符异常值）。
- validate_html(html, plan)：HTML 结构门禁（从 render_plan 迁入；调用方为
  render_plan / render_pdf，错误必须显式失败，不得丢弃）。

render_plan 通过 re-export 保留旧名（REQUIRED_PLAN_KEYS、check_plan_meta、
compute_rules_bundle_hash、validate_html 等），既有调用与测试无需改动。
"""
import hashlib
import json
import os
import re

REQUIRED_PLAN_KEYS = ["plan", "profile", "shopping", "days", "disclaimer"]

# plan.json 版本门禁（见 references/output-policy.md「plan_meta 版本契约」）
PLAN_SCHEMA_VERSION = "1"
# 家庭模式集合（与 SKILL.md household_plan_modes 一致；禁止用 "shared_*" 前缀匹配）
HOUSEHOLD_PLAN_MODES = ("shared_uniform", "shared_meal_personalized", "split_safety_required")
PLAN_META_FIELDS = ["plan_schema_version", "skill_version", "runtime_rules_version",
                    "nutrition_rules_version", "output_policy_version",
                    "recipe_manifest_version", "effective_parameters_version", "price_data_version"]

# 执行组件清单（pipeline_bundle_hash 输入：生成器/合并器/校验器/渲染器，与规则包哈希分工）
PIPELINE_COMPONENTS = [
    "scripts/render_plan.py", "scripts/render_html.py", "scripts/render_pdf.py",
    "scripts/render_markdown.py", "scripts/render_docx.py", "scripts/render_output.py",
    "scripts/render_gates.py", "scripts/common/render_shared.py",
    "scripts/common/constitution.py",
    "scripts/household_override_merger.py", "scripts/household_reference_validator.py",
    "scripts/household_components.py", "scripts/nutrition_adjuster.py",
    "scripts/basket_builder.py", "scripts/build_adjustment_options.py",
    "scripts/price_result_validator.py", "scripts/price_provider_router.py",
]

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


def compute_rules_bundle_hash(plan_mode=None):
    """runtime-rules + nutrition-routing + output-policy + safety-rules + effective-parameters + library-manifest 组合哈希。
    plan_mode ∈ HOUSEHOLD_PLAN_MODES 时追加家庭规则与契约清单（家庭规则/Schema 变更即触发 mismatch）。"""
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


def compute_pipeline_bundle_hash():
    """执行组件组合哈希：区分"规则错配"（rules_bundle_hash）与"执行组件错配"（本哈希）。"""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    h = hashlib.sha1()
    for rel in PIPELINE_COMPONENTS:
        fp = os.path.join(base, rel)
        h.update(rel.encode())
        h.update(open(fp, "rb").read() if os.path.exists(fp) else b"<missing>")
    return h.hexdigest()[:16]


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


def validate_user_text(text):
    """Markdown/Word 产物文本门禁（round74）：内部表达、内部术语（仅标题行）、
    非做饭日违禁文案、占位符异常值。返回错误列表；空列表 = 通过。"""
    errs = []
    for pat in BANNED_PATTERNS:
        if pat in text:
            errs.append(f"残留占位符/异常值: {pat}")
    for phrase in BANNED_USER_FACING_PHRASES:
        if phrase in text:
            errs.append(f"用户可见文字出现内部表达: {phrase}")
    for ph in BANNED_EXCLUDED_DAY_PHRASES:
        if ph in text:
            errs.append(f"非做饭日文案不合规（含 {ph!r}），应使用标准文案：{EXCLUDED_DAY_STANDARD_COPY}")
    headings = " ".join(re.findall(r"(?m)^#{1,6}\s*(.*)$", text))
    for term in BANNED_TITLE_TERMS:
        if term in headings:
            errs.append(f"标题出现内部术语: {term}")
    return errs


def enforce_tips(plan, fmt):
    """用户表达层（round67）：PDF 执行提醒最多 5 条。
    独立导出供 render_document 直接调用（入口统一走 enforce）。"""
    if fmt == "pdf":
        tips = plan.get("execution_tips") or []
        if len(tips) > 5:
            raise SystemExit(
                "PDF 执行提醒最多 5 条（references/output-policy.md「用户表达层」）："
                "当前 %d 条，请收敛到 5 条以内" % len(tips))


def enforce(plan, fmt):
    """计划级门禁（四个渲染入口统一调用）：缺字段 / plan_meta / 商品名泄漏 /
    价格完整性 / 流转核验 / PDF 执行提醒条数。违反即 SystemExit。"""
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        raise SystemExit(f"plan.json 缺字段: {missing}")
    check_plan_meta(plan)
    check_provider_name_leak(plan)
    # 价格硬门禁：采购清单每行必须有参考价（估算层也算），不得留空。
    for i in plan["shopping"].get("items", []):
        if not (i.get("reference_price") or "").strip():
            raise SystemExit(f"价格硬门禁：{i.get('ingredient')} 缺参考价，停止渲染")
    # 流转核验硬门禁：至少 3 项食材的 0 剩余/去向验证。
    if plan.get("prep") and len(plan["prep"].get("leftover_verification", [])) < 3:
        raise SystemExit("流转核验硬门禁：至少 3 项食材的 0 剩余/去向验证")
    enforce_tips(plan, fmt)


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
