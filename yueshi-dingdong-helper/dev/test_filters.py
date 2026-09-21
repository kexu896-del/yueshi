"""发布门禁回归：排除词与否定前缀（对应改进方案 §七 发布门禁）。

用法：python dev\\test_filters.py
失败即非零退出。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from network_capture import _is_hard_excluded  # noqa: E402

CASES = [
    # (商品名, 硬排除词, 期望是否被排除)
    # 门禁用例：猪瘦肉查询下，预制品必须被排除
    ("猪肉馅饼 460g", ["熟食", "预制", "腌制", "馅"], True),
    ("即食午餐肉", ["即食", "熟食"], True),
    ("熟食拼盘", ["熟食"], True),
    ("预制菜调理包", ["预制"], True),
    # 否定前缀不误伤
    ("免腌制鸡胸肉", ["腌制"], False),
    ("无腌制牛排", ["腌制"], False),
    ("未腌制猪里脊", ["腌制"], False),
    ("不含防腐剂火腿", ["防腐"], False),
    # 正常生鲜不误伤
    ("新鲜后腿精肉 约240g", ["熟食", "预制", "腌制", "馅"], False),
    ("冷鲜猪瘦肉 300g", ["熟食", "预制"], False),
]


def main() -> int:
    failed = 0
    for name, terms, expected in CASES:
        got = _is_hard_excluded(name, terms)
        mark = "ok " if got == expected else "FAIL"
        if got != expected:
            failed += 1
        print(f"{mark} {name}  排除词={terms}  期望={'排除' if expected else '保留'}  实际={'排除' if got else '保留'}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
