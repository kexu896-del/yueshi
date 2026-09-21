# -*- coding: utf-8 -*-
# golden sample 基准比对（round39）：人工确认过的 plan.json + 期望输出片段
# 每次改版跑一次，防止渲染输出静默漂移。
import os, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(BASE, "data/golden/golden-sample-plan.json")

EXPECTED_SNIPPETS = [
    "能量期 · 减重目标 · 月经期转卵泡期",   # 副标题
    "蒜蓉菠菜200g",                          # 晚餐内容
    "食堂点餐：",                            # 食堂模板渲染
    "库存（参考 32元/盒）",                  # 库存参考价
    "含库存全口径约",                        # 预算双口径
    "本周实际支出（不含库存）",
    "食材流转核验",
    "本周怎么安排", "本周执行要点",
    'class="document-footer disclaimer"',
    "周二 9/1 晚",                           # 备餐日标签（星期与日期一致）
]

FORBIDDEN_SNIPPETS = ["周期协议", "audit_status", "locked_basket", "plan.json",
                      "对骨骼与血脂更友好", "代谢最佳状态"]


def test_golden_sample_baseline():
    with tempfile.TemporaryDirectory() as td:
        op = os.path.join(td, "golden.html")
        r = subprocess.run([sys.executable, os.path.join(BASE, "scripts/render_html.py"),
                            "--input", GOLDEN, "--output", op], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        html = open(op, encoding="utf-8").read()
    for s in EXPECTED_SNIPPETS:
        assert s in html, f"golden 期望片段缺失: {s}"
    for s in FORBIDDEN_SNIPPETS:
        assert s not in html, f"golden 出现禁语: {s}"
    assert html.count('class="day-card"') == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"全部 {len(fns)} 项通过")
