#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能医学规则库（round70.1，2026-09-21）

data/functional-medicine-rules.json：round70 五书精读 A 级 84 条的结构化落地。
本模块负责加载、校验与执行提示选择：

- load_registry()：读取规则库；
- validate_registry()：完整性门禁（字段/枚举/提示长度与用词/数值不入生产参数）；
- select_tips(mode, context, limit)：按模式与情境选择 auto_tip 候选提示，
  tip_key 去重、确定性顺序；协议类、安全转介、监测与认知类永不进入；
- CLI：python scripts/functional_medicine_rules.py --mode keto_biologic --context menopause

口径（见 references/runtime-rules.md「功能医学行为规则」）：
- auto_tip=true 的提示每份计划至多采纳 2 条，总数仍受 output-policy 执行提示上限约束；
- 数值型主张仅作参考（numeric_policy=reference_only），不进入 data/effective-parameters.json；
- 消除-回添等协议、自免/备孕/哺乳等安全相关规则必须用户主动发起并经安全路由。
"""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, "data", "functional-medicine-rules.json")

REQUIRED_FIELDS = ("rule_id", "book", "category", "applies_to", "auto_tip",
                   "tip_key", "tip_text", "note")
ALLOWED_TAGS = ("*", "keto_biologic", "hormone_balance", "self_immunity", "gut_repair",
                "preconception", "lactation", "menopause", "vegetarian", "weight_loss")
TIP_LEN_RANGE = (10, 26)
# 数值型主张不得出现在自动提示文案（阈值/剂量/检验值一律走规则说明或批准参数）
TIP_BANNED_PATTERNS = (r"g/kg", r"µU", r"HOMA", r"mg", r"mmol", r"kcal", r"%", r"阈值", r"剂量")
# 自动提示文案不得包含内部表达（与 render_plan.BANNED_USER_FACING_PHRASES 同源抽查）
TIP_INTERNAL_TERMS = ("试跑", "覆盖层", "角色对齐", "热量补偿", "主餐口径", "不计上限",
                      "降权保留", "评分过程", "构建状态", "纠错记录", "门禁结果")


def load_registry(path=None):
    with open(path or REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_registry(reg=None):
    """返回错误列表；空列表 = 通过。"""
    reg = reg or load_registry()
    errors = []
    if reg.get("numeric_policy") != "reference_only":
        errors.append("numeric_policy 必须为 reference_only")
    books = set((reg.get("books") or {}).keys())
    categories = set(reg.get("categories") or [])
    seen_ids = set()
    for rule in reg.get("rules") or []:
        rid = rule.get("rule_id", "?")
        for field in REQUIRED_FIELDS:
            if field not in rule:
                errors.append("%s 缺字段 %s" % (rid, field))
        if rid in seen_ids:
            errors.append("%s 重复" % rid)
        seen_ids.add(rid)
        if rule.get("book") not in books:
            errors.append("%s 书源未知：%s" % (rid, rule.get("book")))
        if rule.get("category") not in categories:
            errors.append("%s 分类未知：%s" % (rid, rule.get("category")))
        tags = rule.get("applies_to") or []
        if not tags or any(t not in ALLOWED_TAGS for t in tags):
            errors.append("%s applies_to 非法：%s" % (rid, tags))
        for forbidden in ("parameter_id", "effective_parameter_id"):
            if forbidden in rule:
                errors.append("%s 不得写入生产参数字段 %s（numeric_policy=reference_only）" % (rid, forbidden))
        if rule.get("auto_tip"):
            text = rule.get("tip_text") or ""
            key = rule.get("tip_key") or ""
            if not key:
                errors.append("%s auto_tip 缺 tip_key" % rid)
            lo, hi = TIP_LEN_RANGE
            if not (lo <= len(text) <= hi):
                errors.append("%s 提示长度 %d 不在 %d-%d：%s" % (rid, len(text), lo, hi, text))
            for pat in TIP_BANNED_PATTERNS:
                if re.search(pat, text):
                    errors.append("%s 提示含数值型主张（%s）：%s" % (rid, pat, text))
            for term in TIP_INTERNAL_TERMS:
                if term in text:
                    errors.append("%s 提示含内部表达（%s）：%s" % (rid, term, text))
            # 跨书同义 tip_key 合法：同一行为建议由多本书独立印证，由 select_tips 去重
        else:
            if rule.get("tip_text"):
                errors.append("%s auto_tip=false 不应带 tip_text" % rid)
    return errors


def select_tips(mode=None, context=None, limit=0, reg=None):
    """按模式/情境选择候选提示（auto_tip 且匹配适用标签）。

    返回 [{"rule_id", "book", "category", "tip_key", "tip_text"}]，
    确定性顺序（注册表顺序），tip_key 去重；limit>0 时截断。
    """
    reg = reg or load_registry()
    tags = set(context or [])
    if mode:
        tags.add(mode)
    out, used_keys = [], set()
    for rule in reg.get("rules") or []:
        if not rule.get("auto_tip"):
            continue
        applies = set(rule.get("applies_to") or [])
        if "*" not in applies and not (applies & tags):
            continue
        key = rule.get("tip_key")
        if key in used_keys:
            continue
        used_keys.add(key)
        out.append({"rule_id": rule["rule_id"], "book": rule["book"],
                    "category": rule["category"], "tip_key": key,
                    "tip_text": rule["tip_text"]})
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="功能医学规则库：候选执行提示")
    ap.add_argument("--mode", default=None, help="keto_biologic / hormone_balance")
    ap.add_argument("--context", action="append", default=[],
                    help="情境标签，可重复：self_immunity/gut_repair/preconception/lactation/menopause/vegetarian/weight_loss")
    ap.add_argument("--limit", type=int, default=0, help="最多输出条数（0=全部候选）")
    ap.add_argument("--validate", action="store_true", help="只做规则库校验")
    args = ap.parse_args()
    reg = load_registry()
    if args.validate:
        errs = validate_registry(reg)
        for e in errs:
            print("FAIL:", e)
        print("registry: %d rules | errors: %d" % (len(reg.get("rules") or []), len(errs)))
        sys.exit(1 if errs else 0)
    tips = select_tips(args.mode, args.context, args.limit, reg)
    print(json.dumps(tips, ensure_ascii=False, indent=2))
    print("候选提示 %d 条（tip_key 去重；每份计划至多采纳 2 条）" % len(tips), file=sys.stderr)


if __name__ == "__main__":
    main()
