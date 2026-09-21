"""规则矩阵回归（通用食材名称库与候选匹配改进方案 §十一）。

不再逐商品测试，而是为规则类型建立代表性矩阵：
每组给出「必须通过」与「必须拒绝」样例，任何词典/规则更新都跑全矩阵。

用法：python dev\\test_rule_matrix.py
失败即非零退出。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from models import PriceQueryItem  # noqa: E402
from network_capture import extract_candidates_from_json  # noqa: E402


def _payload(name: str, price: str = "10.0", grams: int = 400) -> dict:
    """构造一个最小 searchProduct 风格响应节点。"""
    return {"data": {"list": [{
        "product_id": f"p-{name}",
        "name": name,
        "price": price,
        "net_weight": grams,
        "net_weight_unit": "g",
        "stock_number": 5,
    }]}}


def _item(**kw) -> PriceQueryItem:
    kw.setdefault("ingredient_id", "t")
    kw.setdefault("query", "q")
    return PriceQueryItem(**kw)


def _kept(item: PriceQueryItem, name: str) -> bool:
    candidates, _stats, _dropped, _raw = extract_candidates_from_json(
        _payload(name), item, source_url="https://example/searchProduct")
    return any(c.product_name == name for c in candidates)


# (组名, 查询项, 通过样例, 拒绝样例)
MATRIX = [
    (
        "整鸡腿",
        _item(query="鸡腿", aliases=["琵琶腿"],
              allowed_forms=["whole_leg", "drumstick"],
              excluded_forms=["diced", "marinated", "cooked"]),
        ["冷鲜鸡琵琶腿 400g", "冰鲜整鸡腿 500g"],
        ["鸡腿肉丁 300g", "奥尔良鸡腿排 400g", "熟食烤鸡腿 1只",
         "冷鲜鸡腿块 400g"],
    ),
    (
        "叶菜",
        _item(query="上海青", aliases=["小青菜"], broad_terms=["青菜"],
              hard_excluded_terms=["腌菜", "酸菜", "泡菜"],
              excluded_forms=["cooked"]),
        ["上海青 300g", "小青菜 250g"],
        ["酸菜鱼调料包 300g", "腌菜 200g", "即食熟菜沙拉 150g"],
    ),
    (
        "鲜肉",
        _item(query="猪里脊", aliases=["里脊"],
              positive_terms=["里脊", "精肉"],
              hard_excluded_terms=["馅", "丸"],
              excluded_forms=["marinated", "sliced"]),
        ["冷鲜整块里脊 400g", "冰鲜后腿精肉 240g"],
        ["猪肉馅饼 460g", "猪肉丸 300g", "腌制肉片 250g"],
    ),
    (
        "鸡蛋",
        _item(query="鸡蛋", aliases=["鲜鸡蛋"],
              positive_terms=["鸡蛋", "鲜鸡蛋", "谷物蛋"],
              excluded_terms=["咸蛋", "皮蛋", "卤蛋", "蛋糕"]),
        ["鲜鸡蛋15枚 850g", "谷物蛋10枚 500g"],
        ["卤蛋 6枚", "咸蛋 4枚", "蛋糕预拌粉 300g"],
    ),
    (
        "鱼类",
        _item(query="带鱼", aliases=["鲜带鱼"],
              hard_excluded_terms=["罐头"],
              excluded_forms=["cooked", "patty"]),
        ["鲜带鱼段 500g", "冷冻带鱼 400g"],
        ["带鱼罐头 200g", "香煎带鱼熟食 300g", "调理鱼排 250g"],
    ),
    (
        "否定前缀",
        _item(query="牛排", aliases=["原切牛排"],
              excluded_forms=["marinated", "cooked"]),
        ["免腌原切牛排 200g", "未调味牛排 300g"],
        ["腌制牛排 200g", "黑椒调味牛排 180g", "预制调理牛肉 300g"],
    ),
]

# 匹配质量专项：宽泛上位词不得冒充精确命中。
QUALITY_CASES = [
    # (查询项, 商品名, 期望 match_quality 或 None=应被拒)
    (_item(query="上海青", aliases=["小青菜"], broad_terms=["青菜"]),
     "宁夏上海青苗 400g", "exact"),
    (_item(query="上海青", aliases=["小青菜"], broad_terms=["青菜"]),
     "高原青菜 500g", "category_fallback"),
    (_item(query="上海青", aliases=["小青菜"], broad_terms=["青菜"]),
     "小青菜 250g", "alias"),
]


def main() -> int:
    failed = 0
    total = 0
    for group, item, pass_cases, reject_cases in MATRIX:
        for name in pass_cases:
            total += 1
            if _kept(item, name):
                print(f"ok   [{group}] 通过样例保留：{name}")
            else:
                failed += 1
                print(f"FAIL [{group}] 通过样例被误拒：{name}")
        for name in reject_cases:
            total += 1
            if not _kept(item, name):
                print(f"ok   [{group}] 拒绝样例拦截：{name}")
            else:
                failed += 1
                print(f"FAIL [{group}] 拒绝样例漏入：{name}")

    for item, name, expected in QUALITY_CASES:
        total += 1
        candidates, _s, _d, _r = extract_candidates_from_json(
            _payload(name), item, source_url="https://example/searchProduct")
        got = candidates[0].match_quality if candidates else None
        if got == expected:
            print(f"ok   [匹配质量] {name} → {got}")
        else:
            failed += 1
            print(f"FAIL [匹配质量] {name} 期望 {expected} 实际 {got}")

    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
