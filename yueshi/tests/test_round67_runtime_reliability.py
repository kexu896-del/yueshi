# -*- coding: utf-8 -*-
"""round67（2026-09-18）：运行可靠性回归（合并幂等 / PDF 存在性 / 窗口诊断）。

- 合并补丁幂等：相同输入重复执行 → 内容哈希一致、提示不重复；
- render_pdf 产物存在性校验与目录路径显式失败（在 round67 用户表达层测试中覆盖）；
- 助手窗口模式精简诊断：源码含 run-summary 写入与阶段映射；
- price-provider-policy 含大品类召回/三态/选择层契约。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
from plan_patch import apply_patch, content_hash  # noqa: E402

fails = []

plan = json.loads(open(os.path.join(ROOT, "data/golden/golden-sample-plan.json"),
                       encoding="utf-8").read())
patch = {
    "shopping": plan.get("shopping"),
    "price_snapshot_meta": {"provider": "dingdong_web", "result_hash": "sha256:x"},
    "execution_tips": list(plan.get("execution_tips") or []) + ["新提示：按需加餐"],
}
h0 = content_hash(plan)
apply_patch(plan, patch)
h1 = content_hash(plan)
apply_patch(plan, patch)
h2 = content_hash(plan)
apply_patch(plan, patch)
h3 = content_hash(plan)
if not (h1 == h2 == h3):
    fails.append("合并补丁非幂等：哈希 %s -> %s -> %s" % (h1, h2, h3))
tips = plan.get("execution_tips") or []
if len(tips) != len(set(tips)):
    fails.append("执行提示重复插入")
if tips.count("新提示：按需加餐") != 1:
    fails.append("同一提示被重复插入")

# 助手窗口诊断：源码级探针（兼容平铺 src/ 与嵌套 yueshi-dingdong-helper/src/ 两种布局）
_hbase = os.path.join(ROOT, "..", "yueshi-dingdong-helper")
_hcands = [os.path.join(_hbase, "src", "app.py"),
           os.path.join(_hbase, "yueshi-dingdong-helper", "src", "app.py")]
helper_app = open(next((p for p in _hcands if os.path.exists(p)), _hcands[0]),
                  encoding="utf-8").read()
for needle in ("run-summary.json", "write_run_summary", "search_not_triggered",
               "review_required_only"):
    if needle not in helper_app:
        fails.append("助手窗口诊断缺：%s" % needle)

# 契约文档
policy = open(os.path.join(ROOT, "references", "price-provider-policy.md"),
              encoding="utf-8").read()
for needle in ("大品类召回", "accepted", "review_required", "purchase_selector"):
    if needle not in policy:
        fails.append("price-provider-policy 缺：%s" % needle)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round67 运行可靠性（合并幂等 / 窗口诊断 / 契约文档）全部通过")
