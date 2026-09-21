# -*- coding: utf-8 -*-
# round 37 定版回归：字段数量措辞修正 / yueshi-1.0.0 定版标记 / 维护口径冻结入口
import io, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
OP = read("references/output-policy.md")
MM = read("developer/maintenance-map.md")


def test_version_field_count_wording():
    # 不再出现数量不准确的"八个明细版本字段"
    assert "八个明细版本字段" not in SK
    assert "八个明细版本字段" not in OP
    assert "八个版本字段" not in OP
    assert "各明细版本字段用于日志与排错" in SK


def test_stable_version_marked():
    # round44 曾切换正式版 yueshi-1.1.0；round46 起版本随语义变更滚动，
    # 此处只要求 frontmatter 声明语义化版本（允许新开发周期的 -rc 标记）。
    import re
    fm = SK.split("---")[1]
    assert re.search(r"^version:\s*yueshi-\d+\.\d+\.\d+(-rc\d*)?$", fm, re.M), fm


def test_freeze_maintenance_policy():
    assert "定版维护口径" in MM and "yueshi-1.0.0" in MM
    assert "不再把具体渲染、菜谱或测试细节追加到 SKILL.md" in MM
    for route in ("runtime-rules.md", "nutrition-routing.md", "output-policy.md", "CHANGELOG.md"):
        assert route in MM, route


def test_description_unchanged_trigger_scope():
    desc = SK.split("---")[1]
    assert "不自动启动完整 15 步周计划" in desc


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
