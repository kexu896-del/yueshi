# -*- coding: utf-8 -*-
# round 40：RC2-4 Skill 联动（4 plan_mode 路由 / 合并问卷 / 计算节奏 / 门禁分级 / 渲染容量）
import io, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(BASE, p), encoding="utf-8").read()


SK = read("SKILL.md")
RR = read("references/runtime-rules.md")


def test_four_plan_modes_in_route():
    for m in ("solo", "shared_uniform", "shared_meal_personalized", "split_safety_required"):
        assert m in SK, m
    assert "直接进入本模式" in SK  # 安全冲突不降级


def test_family_intake_single_round():
    assert "一轮合并问卷" in RR
    for k in ("成员清单", "各成员限制", "共同餐次", "默认共锅策略", "份量精度"):
        assert k in RR, k
    assert "不逐成员反复追问" in RR


def test_compute_cadence():
    for k in ("只运行一次", "批量计算", "一次性求解", "最多两轮", "局部重算"):
        assert k in RR, k
    assert "不判 fatal" in RR  # 缺席重建记 warning 不判 fatal


def test_locked_basket_gate_split():
    # round43：G03 拆分为 G03a [user_input_required] / G03b [fatal]
    assert "G03a. [user_input_required] 预选尚未由用户确认" in SK
    assert "G03b. [fatal]" in SK and "生成失败、损坏或版本不匹配" in SK


def test_render_capacity():
    assert "3 名成员" in SK or "超过 3 人" in SK
    assert "摘要页" in SK and "成员附页" in SK
    assert "household_layout_gate" in RR


def test_household_files_present():
    for p in ("schemas/household/shared-definitions.schema.json",
              "schemas/household/household-base-plan.schema.json",
              "schemas/household/household-overrides.schema.json",
              "schemas/household/household-effective-plan.schema.json",
              "schemas/household/household-schemas.bundle.json",
              "scripts/household_reference_validator.py"):
        assert os.path.exists(os.path.join(BASE, p)), p


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
