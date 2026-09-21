# -*- coding: utf-8 -*-
"""round59 回归：v1.3.0 增量改进（查询库接线 / request_id 规则 / Schema 开放 /
状态转移表 / 字段收敛 / README 助手节 / 回退链 / P2 小项）。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []


def need(path, needle, label):
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle not in text:
        fails.append(f"{label}：{path} 缺少「{needle}」")


# 1. P0-1 查询项生成规则（policy §9.3）
need("references/price-provider-policy.md", "## 9.3 查询项生成规则与字典兜底（round59 定稿）", "P0-1")
need("references/price-provider-policy.md", "新食材首次查价不需要手工编写排除词", "P0-1")
need("references/price-provider-policy.md", "低置信度", "P0-1")
need("references/price-provider-policy.md", "dictionary_suggestions", "P0-1")
need("references/price-provider-policy.md", "只建议，不自动回写主库", "P0-1")

# 2. G01 追加字典文件完整性检查（SKILL.md）
need("SKILL.md", "data/ingredient-catalog.json", "G01")
need("SKILL.md", "data/product-form-dictionary.json", "G01")
need("SKILL.md", "ingredient_catalog_missing", "G01")
need("SKILL.md", "form_dictionary_missing", "G01")

# 3. P0-2 request_id 规则 + G13 防串用
need("references/price-provider-policy.md", "request_id = {计划起始日期 YYYY-MM-DD}-{shopping_demand_hash 前 8 位}", "P0-2")
need("references/price-provider-policy.md", "同一日期两版不同菜单必然产生不同 request_id", "P0-2")
need("references/price-provider-policy.md", "不串用旧价格", "P0-2")
need("SKILL.md", "shopping_demand_hash 前 8 位", "P0-2")

# 4. P0-3 Schema 开放：根级与 query_result additionalProperties 放开
schema = json.loads((ROOT / "schemas/price-result.schema.json").read_text(encoding="utf-8"))
if schema.get("additionalProperties") is not True:
    fails.append("P0-3：price-result 根级 additionalProperties 未放开")
if schema["definitions"]["query_result"].get("additionalProperties") is not True:
    fails.append("P0-3：query_result additionalProperties 未放开")
# definitions 内部仍严格
for name in ("product_candidate", "suggested_purchase"):
    if schema["definitions"][name].get("additionalProperties") is not False:
        fails.append(f"P0-3：definitions.{name} 应保持严格")
need("references/price-provider-policy.md", "不因助手新增了 Schema 未登记的字段而拒绝", "P0-3")
need("references/price-provider-policy.md", "必需字段齐全 + request_id 一致", "P0-3")

# 5. P0-3 既有字段已登记（助手新增字段在契约内）
qr_props = schema["definitions"]["query_result"]["properties"]
for f in ("suggested_purchase", "dictionary_suggestions", "substitution_notice"):
    if f not in qr_props:
        fails.append(f"P0-3：query_result 缺已登记字段 {f}")
for f in ("price_changes", "catalog_version", "form_dictionary_version"):
    if f not in schema["properties"]:
        fails.append(f"P0-3：根级缺已登记字段 {f}")

# 6. P1-1 状态转移表：六态 + 两易漏转移
need("references/price-provider-policy.md", "### 4.3 状态转移表（round59 定稿）", "P1-1")
policy = (ROOT / "references/price-provider-policy.md").read_text(encoding="utf-8")
for state in ("pending", "use_helper", "use_estimate", "awaiting_price_result",
              "price_result_received", "opt_out_after_query"):
    if f"`{state}`" not in policy:
        fails.append(f"P1-1：状态转移表缺状态 {state}")
need("references/price-provider-policy.md", "用户中途放弃查价", "P1-1")
need("references/price-provider-policy.md", "助手无法运行", "P1-1")
need("references/price-provider-policy.md", "均为合法转移，不判失败", "P1-1")
need("SKILL.md", "状态转移表", "P1-1")

# 7. P1-2 字段收敛
need("references/price-provider-policy.md", "唯一写入字段", "P1-2")
need("references/price-provider-policy.md", "派生只读字段", "P1-2")
need("references/price-provider-policy.md", "以 `dingdong_price_choice` 为准", "P1-2")
need("references/runtime-rules.md", "派生只读字段", "P1-2")

# 8. P1-3 README
need("README.md", "适用 SKILL 版本：1.4.3", "P1-3")
need("README.md", "叮咚查价助手使用说明", "P1-3")
need("README.md", "解压并保留完整文件夹", "P1-3")
need("README.md", "不加购、不下单、不支付、不领券、不改地址", "P1-3")
need("README.md", "以叮咚结算页为准", "P1-3")

# 9. P1-4 回退链一行
need("SKILL.md", "direct_public_price → category_estimate → historical_estimate → 替换同功能食材（须回菜单营养层）", "P1-4")

# 10. P2 小项
need("SKILL.md", "下周四可能不在家吃晚饭", "P2-H04")
need("MAINTENANCE.md", "最多并排展示 3 名成员", "P2-家庭")
need("MAINTENANCE.md", "先读 `CHANGELOG.md`", "P2-维护者")
need("MAINTENANCE.md", "缺失不影响普通估价流程", "P2-维护者")
need("references/output-policy.md", "叮咚没查到价，已按当地参考价估算", "P2-话术")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: round59 全部探针命中")
sys.exit(0)
