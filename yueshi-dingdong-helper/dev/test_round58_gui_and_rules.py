#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round58 助手端回归：
1. 形态词典 1.3.0：cured（腊制）/sashimi（刺身）进入限制性形态；
2. 目录规则快照展开：精简清单按 ingredient_id 展开，override 优先；
3. 导出门禁 E01–E05 自检（request_id 不匹配永不静默通过）；
4. 窗口与完成页结构：最小尺寸、固定底部操作栏、可滚动明细、键盘滚动。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import app  # noqa: E402
import config  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# 1. 形态词典
check(config.FORM_DICTIONARY_VERSION == "1.4.0", "词典版本未升到 1.3.0")
check(config.CATALOG_RULES_VERSION == "1.6.0", "目录快照版本未升到 1.3.0")
for f in ("cured", "sashimi"):
    check(f in config.FORM_KEYWORDS, f"FORM_KEYWORDS 缺 {f}")
    check(f in config.RESTRICTIVE_FORMS, f"RESTRICTIVE_FORMS 缺 {f}")
check("腊鸡腿" in "".join(config.FORM_KEYWORDS["cured"]) or any(
    "腊" in k for k in config.FORM_KEYWORDS["cured"]), "cured 缺腊字")
check(any("刺身" in k for k in config.FORM_KEYWORDS["sashimi"]), "sashimi 缺刺身")

# 四类人工剔除规则已回写快照
rules = config.CATALOG_RULES
check("腊鸡腿" in rules["鸡腿"]["hard_excluded_terms"], "鸡腿缺腊制排除")
check("cured" in rules["鸡腿"]["excluded_forms"], "鸡腿缺 cured 排除形态")
check("sashimi" in rules["三文鱼"]["excluded_forms"], "三文鱼缺 sashimi 排除形态")
check(any("茶" in t for t in rules["玉米"]["hard_excluded_terms"]), "玉米缺茶饮排除")
check("牛肉丝" in rules["芹菜"]["hard_excluded_terms"], "芹菜缺组合菜排除")

# 2. 精简清单展开 + override 优先
q = {"request_id": "r58t", "catalog_version": "1.3.0",
     "items": [{"ingredient_id": "鸡腿", "query": "鸡腿", "required_grams": 500},
               {"ingredient_id": "芹菜", "query": "芹菜"},
               {"ingredient_id": "玉米", "query": "玉米",
                "hard_excluded_terms": ["本周只要整根"]}]}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8") as f:
    json.dump(q, f, ensure_ascii=False)
    qp = f.name
batch = app.load_query(Path(qp))
leg, cel, corn = batch.items
check("腊鸡腿" in leg.hard_excluded_terms, "精简清单未展开鸡腿排除词")
check(leg.allowed_forms == ["whole_leg", "drumstick"], "鸡腿 allowed_forms 未展开")
check("牛肉丝" in cel.hard_excluded_terms, "芹菜排除词未展开")
check(corn.hard_excluded_terms == ["本周只要整根"], "override 未优先生效")
os.unlink(qp)

# 3. E01–E05 自检
res_ok = {"schema_version": "1.2", "provider": "dingdong_web",
          "request_id": "r58t", "started_at": "2026-09-11T10:00:00+08:00",
          "completed_at": "2026-09-11T10:05:00+08:00",
          "results": [{"ingredient_id": "鸡腿", "query": "鸡腿",
                       "status": "success", "candidates": []}]}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8") as f:
    json.dump(res_ok, f, ensure_ascii=False)
    rp = f.name
ck = app.export_selfcheck(Path(rp), "r58t")
check(all(ck[k] for k in ("E01", "E02", "E03", "E04", "E05")),
      f"自检应全过: {ck}")
ck2 = app.export_selfcheck(Path(rp), "other-week")
check(not ck2["E03"] and "request_id" in ck2["missing"],
      "request_id 不匹配必须 E03 失败")
os.unlink(rp)

# 4. 完成页与窗口结构（静态检查 gui.py 源码）
gui_src = Path(__file__).parent.parent.joinpath("src", "gui.py").read_text(
    encoding="utf-8")
for needle in ("查看全部结果 ▾", "收起结果 ▴", "detail_canvas", "detail_scroll",
               "结果已通过格式校验", "结果文件格式不完整，请回到查价助手重新保存",
               "window_geometry", 'root.minsize(600, 440)',
               '"<Prior>"', '"<Next>"', '"<Home>"', '"<End>"',
               'bar.pack(side="bottom"'):
    check(needle in gui_src, f"gui 缺: {needle}")
# 底部操作栏先于明细 pack（固定不随列表滚动）
check(gui_src.index('bar.pack(side="bottom"') >
      gui_src.index("self.detail_wrap = tk.Frame"),
      "底部操作栏应在明细容器之后定义并 side=bottom 固定")
# 完成页不显示技术字段（可见文案 text= 中不得出现 schema_version/provider/request_id）
done_ui = gui_src[gui_src.index("def _show_done"):gui_src.index("def save_result")]
import re as _re
visible_texts = _re.findall(r'text\s*=\s*(?:f?"([^"]*)"|f?\'([^\']*)\')', done_ui)
for shown, _ in visible_texts:
    for tech in ("schema_version", "request_id", "provider"):
        check(tech not in shown, f"完成页可见文案不应含技术字段: {tech} in {shown!r}")

if fails:
    for f_ in fails:
        print("FAIL:", f_)
    sys.exit(1)
print("round58 助手端回归：全部通过")
