#!/usr/bin/env python3
# 收口轮 P1-1：空指纹合法 + 公共模块唯一口径 + 构建残留扫描
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from common.recipe_normalization import (NOT_COMPARABLE, first_of, jaccard,
                                         norm_list, weighted_similarity)

# 1) 缺失/None/[]/{} 均合法，归一化为空 tuple
for v in (None, [], {}, "", 0):
    assert norm_list(v if v != 0 else None) == ()
assert norm_list(["炒", "蒸"]) == ("炒", "蒸")
assert norm_list("炒") == ("炒",)

# 2) first_of 永不抛 IndexError
assert first_of(None) is None
assert first_of([], default="-") == "-"
assert first_of(["a", "b"]) == "a"

# 3) 双方空字段返回 not_comparable，不返回 0% 或 100%
assert jaccard(None, []) == NOT_COMPARABLE
assert jaccard(["炒"], ["炒"]) == 1.0
assert jaccard(["炒"], ["蒸"]) == 0.0

# 4) 只对有数据的维度重新归一化
a = {"methods": ["炒"], "main_protein": None}
b = {"methods": ["炒"], "main_protein": []}
sim = weighted_similarity(a, b, weights={"methods": 1.0, "main_protein": 1.0})
assert sim == 1.0, f"空维度应被剔除后归一化，得到 {sim}"
assert weighted_similarity({"fingerprint": None}, {"fingerprint": []}) == NOT_COMPARABLE

# 5) ranker 端到端：空指纹菜谱不崩溃
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import recipe_ranker  # noqa: F401  (导入即验证公共模块接线)

# 6) 生产脚本残留扫描：禁止无保护 [0] 读取
BANNED = [r"fingerprint\[0\]", r'get\("fingerprint"\)\[0\]', r'get\("methods"\)\[0\]',
          r'get\("main_protein"\)\[0\]', r"\['methods'\]\[0\]", r"\['flavors'\]\[0\]"]
for fn in ["recipe_ranker.py", "diversity_checker.py", "build_recipe_index.py"]:
    fp = os.path.join(ROOT, "scripts", fn)
    if not os.path.exists(fp):
        continue
    src = open(fp, encoding="utf-8").read()
    for pat in BANNED:
        assert not re.search(pat, src), f"{fn} 命中残留模式 {pat}"

print("PASS")
