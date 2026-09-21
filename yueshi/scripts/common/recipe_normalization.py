"""菜谱指纹与列表字段规范化公共模块（唯一公共口径）。

硬规则（构建前残留搜索禁止出现）：
    fingerprint[0]   get("fingerprint")[0]   get("methods")[0]   get("main_protein")[0]

- fingerprint 缺失、None、[]、{} 均合法，归一化为 ()。
- 禁止无保护的 [0] 读取：取首元素一律用 first_of()。
- 双方均为空字段时比较返回 NOT_COMPARABLE，不返回 0% 或 100%。
- 相似度评分只对有数据的维度重新归一化。
"""

NOT_COMPARABLE = "not_comparable"

_LIST_FIELDS = ("fingerprint", "methods", "main_protein", "cuisine_tags", "flavor_tags")


def norm_list(value):
    """任意输入归一化为不可变 tuple。缺失/None/[]/{}/单值均合法。"""
    if value is None or value == "":
        return ()
    if isinstance(value, dict):
        return tuple(k for k, v in value.items() if v)
    if isinstance(value, (list, tuple, set)):
        return tuple(v for v in value if v is not None and v != "")
    return (value,)


def norm_recipe_fields(recipe):
    """返回 {field: tuple}，对 recipe 中已知列表字段统一归一化。"""
    recipe = recipe or {}
    return {f: norm_list(recipe.get(f)) for f in _LIST_FIELDS}


def first_of(value, default=None):
    """安全的"取首元素"：空字段返回 default，绝不抛 IndexError。"""
    items = norm_list(value)
    return items[0] if items else default


def jaccard(a, b):
    """两个列表字段的 Jaccard 相似度。

    双方均为空 → NOT_COMPARABLE（不参与评分，不返回 0 或 1）。
    """
    sa, sb = set(norm_list(a)), set(norm_list(b))
    if not sa and not sb:
        return NOT_COMPARABLE
    union = sa | sb
    if not union:
        return NOT_COMPARABLE
    return len(sa & sb) / len(union)


def weighted_similarity(recipe_a, recipe_b, weights=None):
    """多维度相似度：只对有数据的维度加权并重新归一化。

    weights: {field: weight}，缺省对全部已知列表字段等权。
    返回 0.0~1.0；所有维度均不可比较时返回 NOT_COMPARABLE。
    """
    fa, fb = norm_recipe_fields(recipe_a), norm_recipe_fields(recipe_b)
    weights = weights or {f: 1.0 for f in _LIST_FIELDS}
    total_w, acc = 0.0, 0.0
    for field, w in weights.items():
        sim = jaccard(fa.get(field), fb.get(field))
        if sim == NOT_COMPARABLE:
            continue
        total_w += w
        acc += sim * w
    if total_w == 0:
        return NOT_COMPARABLE
    return acc / total_w
