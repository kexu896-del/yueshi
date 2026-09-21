# -*- coding: utf-8 -*-
# 导出契约回归（round54）：结果文件根级必填字段恒在，缺省字段不落地；
# 新增形态词典（蛋类）与 conditional_accept / purchase_note 行为。
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from config import (FORM_DICTIONARY_VERSION, RESTRICTIVE_FORMS, detect_forms,
                    detect_conditional_accept, conditional_accept_note)
from models import (PriceResultBatch, QueryResult, ProductCandidate,
                    SuggestedPurchase)
from app import save_result
import tempfile
from pathlib import Path


def _dump(batch):
    """走真实导出路径（含根级必填兜底与回读校验）。"""
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "r.json"
        save_result(batch, fp)
        return json.loads(fp.read_text(encoding="utf-8"))


def test_form_dictionary_version_bumped():
    assert FORM_DICTIONARY_VERSION == "1.4.0"


def test_new_egg_forms_restrictive():
    for f in ("pancake", "pastry", "cooked_egg", "salted_egg"):
        assert f in RESTRICTIVE_FORMS, f
    assert "shell_egg" not in RESTRICTIVE_FORMS


def test_detect_forms_egg_cases():
    assert "pancake" in detect_forms("鸡蛋软饼")
    assert "cooked_egg" in detect_forms("卤蛋茶叶蛋即食")
    assert "salted_egg" in detect_forms("松花皮蛋")
    assert "shell_egg" in detect_forms("带壳鲜鸡蛋10枚")
    assert "pancake" not in detect_forms("鲜鸡蛋30枚装")


def test_conditional_accept_detection():
    assert detect_conditional_accept("调味牛肉片（附调味包）")
    assert detect_conditional_accept("黑椒牛排 赠酱料包")
    assert not detect_conditional_accept("调味牛肉片")
    assert conditional_accept_note("原味鸡排含酱料包") == "附独立酱料包，可不用"
    assert conditional_accept_note("原味鸡排") == ""


def _mk_candidate(name="鲜鸡蛋10枚"):
    return ProductCandidate(
        ingredient_id="鸡蛋", query="鸡蛋", matched_query="鸡蛋",
        product_id="1", product_name=name, package_text="10枚/盒",
        reference_grams=500.0, listed_price_yuan=9.9, price_type="regular",
        availability="available", eligible_for_purchase=True)


def _mk_batch(**kw):
    r = QueryResult(
        ingredient_id="鸡蛋", query="鸡蛋", status="success",
        candidates=[_mk_candidate()], **kw)
    now = datetime.now(timezone(timedelta(hours=8)))
    return PriceResultBatch(
        schema_version="1.2", provider="dingdong_web", request_id="req-1",
        started_at=now, completed_at=now,
        delivery_context_confirmed_by_user=True, results=[r])


def test_export_root_fields_present():
    """根级必填字段恒在：schema_version / provider / request_id。"""
    out = _dump(_mk_batch())
    for k in ("schema_version", "provider", "request_id"):
        assert out.get(k), f"缺根级必填字段 {k}"


def test_export_slim_no_defaults():
    """缺省字段不落地（exclude_defaults）：conditional_accept=False 不出现。"""
    out = _dump(_mk_batch())
    cand = out["results"][0]["candidates"][0]
    assert "conditional_accept" not in cand
    assert "purchase_note" not in cand
    assert "product_url" not in cand and "observed_at" not in cand


def test_conditional_accept_serialized_when_set():
    c = _mk_candidate("调味牛肉片（附调味包）")
    c.conditional_accept = True
    c.purchase_note = "附独立调味包，可不用"
    r = QueryResult(ingredient_id="牛肉", query="牛肉", status="success",
                    candidates=[c],
                    suggested_purchase=SuggestedPurchase(
                        product_id="1", product_name=c.product_name, packages=1,
                        total_grams=500.0, total_price_yuan=9.9,
                        purchase_note="附独立调味包，可不用"))
    now = datetime.now(timezone(timedelta(hours=8)))
    b = PriceResultBatch(schema_version="1.2", provider="dingdong_web",
                         request_id="req-2", started_at=now, completed_at=now,
                         delivery_context_confirmed_by_user=True, results=[r])
    out = _dump(b)
    cand = out["results"][0]["candidates"][0]
    assert cand["conditional_accept"] is True
    assert cand["purchase_note"] == "附独立调味包，可不用"
    assert out["results"][0]["suggested_purchase"]["purchase_note"] \
        == "附独立调味包，可不用"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = []
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            fails.append(fn.__name__)
            print("FAIL", fn.__name__, e)
    print("导出契约回归:", "全部通过" if not fails else f"失败 {fails}")
    sys.exit(1 if fails else 0)
