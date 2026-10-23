# -*- coding: utf-8 -*-
"""round78（2026-09-21）：稳定规则 ID 注册表 + 合并语料助手（ADR 0006）。

断言：
- 注册表解析：references/rule-index.md 为唯一人工源，条目 ≥18、ID 唯一且格式合法；
- 每条规则的细则路径都存在，且规则 ID 至少出现在一个 owner 文件中；
- 弃用规则不得被 SKILL.md 引用；
- 镜像一致性：SKILL.md 提及的每个规则 ID 必须已登记（且由 owner 包含该 ID 的校验覆盖）；
- 语料助手：与 SKILL.md + 三份规则文件的顺序拼接等价，且每份文件只出现一次
  （历史上四处把三元组连拼两遍）；
- 十个历史语料测试已改用统一助手（防回退）。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rule_index import load_registry, rule_ids, get  # noqa: E402
import rule_corpus  # noqa: E402

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ---------- 1) 注册表完整性 ----------
reg = load_registry()
check(len(reg) >= 18, "规则条目应 ≥18（实际 %d）" % len(reg))
ids = [r["rule_id"] for r in reg]
check(len(ids) == len(set(ids)), "规则 ID 重复：%s" % [i for i in set(ids) if ids.count(i) > 1])
for r in reg:
    rid = r["rule_id"]
    check(re.fullmatch(r"[A-Z][A-Z0-9-]*\d{3}", rid) is not None, "ID 格式非法：%s" % rid)
    check(bool(r["topic"]), "%s 缺主题" % rid)
    check(bool(r["rule"]), "%s 缺一句话规则" % rid)
    check(bool(r["owners"]), "%s 缺细则位置" % rid)
check(get("MEAL-STATE-001") is not None, "get() 未命中已登记 ID")
check(get("NO-SUCH-001") is None, "get() 对未登记 ID 应返回 None")

# ---------- 2) owner 存在且包含规则 ID ----------
for r in reg:
    rid = r["rule_id"]
    texts = []
    for owner in r["owners"]:
        p = os.path.join(ROOT, owner.replace("/", os.sep))
        check(os.path.exists(p), "%s 的细则位置不存在：%s" % (rid, owner))
        if os.path.exists(p):
            texts.append(read(owner))
    check(any(rid in t for t in texts), "%s 未出现在任何 owner 文件中" % rid)

# ---------- 3) 弃用规则不得被 SKILL.md 引用 ----------
skill_text = read("SKILL.md")
for r in reg:
    if r.get("deprecated"):
        check(r["rule_id"] not in skill_text, "已弃用规则仍被 SKILL.md 引用：%s" % r["rule_id"])

# ---------- 4) 镜像一致性：SKILL.md 提及的 ID 必须已登记 ----------
mentioned = set(re.findall(r"(?<![A-Za-z0-9-])([A-Z][A-Z0-9-]*\d{3})(?![A-Za-z0-9-])",
                           skill_text))
unregistered = sorted(mentioned - set(ids))
check(not unregistered, "SKILL.md 引用了未登记的规则 ID：%s" % unregistered)
check(len(mentioned) >= 8, "SKILL.md 应至少镜像 8 个规则 ID（实际 %d）" % len(mentioned))

# ---------- 5) 语料助手：等价且无重复段 ----------
expect = (read("SKILL.md")
          + read("references/runtime-rules.md")
          + read("references/nutrition-routing.md")
          + read("references/output-policy.md"))
corpus = rule_corpus.load_corpus()
check(corpus == expect, "合并语料与顺序拼接不等价")
check(rule_corpus.read("references/runtime-rules.md") == read("references/runtime-rules.md"),
      "rule_corpus.read 读取异常")
for marker in ("# 月食运行规则（runtime-rules）",
               "# 月食营养路由（nutrition-routing）",
               "# 月食输出策略（output-policy）"):
    check(corpus.count(marker) == 1, "语料出现重复段：%s（%d 次）" % (marker, corpus.count(marker)))

# ---------- 6) 历史语料测试已统一接入 ----------
CORPUS_TESTS = ["test_accepted_batch_semantics.py", "test_meal_coverage.py",
                "test_nutrition_gate_before_render.py", "test_performance.py",
                "test_preselection_coverage.py", "test_recipe_steps.py",
                "test_round28_cycle_stage.py", "test_round31_finalization.py",
                "test_round32_entry_hardening.py", "test_unselected_ingredient_reason.py"]
for f in CORPUS_TESTS:
    src = read(os.path.join("tests", f))
    check("load_corpus" in src, "%s 未使用 tests/rule_corpus.py" % f)

if failures:
    print("FAIL")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("PASS: round78 规则注册表（%d 条 / %d 镜像）与合并语料助手全部通过" % (
    len(reg), len(mentioned)))
