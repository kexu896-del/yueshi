# -*- coding: utf-8 -*-
"""规则语料助手（round78）

SKILL.md + 三份规则文件（runtime-rules / nutrition-routing / output-policy）
的合并文本，供规则类测试断言使用——拼接只写一份，避免各测试手抄
（历史上四处把三元组连拼两遍，导致断言在重复语料上失真）。

    import rule_corpus
    corpus = rule_corpus.load_corpus()
    text = rule_corpus.read("references/runtime-rules.md")
"""
import functools
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULE_FILES = ("references/runtime-rules.md",
              "references/nutrition-routing.md",
              "references/output-policy.md")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


@functools.lru_cache(maxsize=1)
def load_corpus():
    """返回合并语料（顺序固定：SKILL.md → runtime-rules → nutrition-routing → output-policy）。"""
    return read("SKILL.md") + "".join(read(p) for p in RULE_FILES)
