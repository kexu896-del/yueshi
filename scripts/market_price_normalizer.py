#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜场参考价归一化（城市适配器的数据合并层）

输入：价格观测 CSV，列：
  item, variety, market, unit, price, date, source
  （unit 支持 斤/500g/kg/g；source 需在城市 yaml 的 sources 里配置 weight）

合并规则（对应 references/cities/<城市>-price-sources.yaml）：
  - 同 item 多来源且单位可对齐 → 按 yaml 权重加权（默认 时点0.5/周均0.3/行情0.2）
  - 单位或品种对不齐 → 输出区间 [min, max]，不强行平均
  - 置信度：3 源一致=高，2 源=中，单源=低
  - 数据超 7 天 → 标注"价格可能已过期"

用法：
  python market_price_normalizer.py prices.csv --city references/cities/nanjing-price-sources.yaml
输出：item 参考价（元/500g）+ 置信度 + 来源明细。
所有输出价格都是参考价，不代表用户附近摊位实际成交价。
"""
import argparse, csv, os, sys
from datetime import date, datetime

UNIT_TO_JIN = {"斤": 1.0, "500g": 1.0, "kg": 0.5, "公斤": 0.5, "g": 500.0, "两": 10.0}


def load_weights(city_yaml):
    """极简 yaml 解析：只取 sources 的 name/weight 与 cadence。失败则用默认权重。"""
    default = {"daily1": 0.5, "weekly": 0.3, "daily2": 0.2}
    if not city_yaml or not os.path.exists(city_yaml):
        return default
    weights, cur = {}, None
    for line in open(city_yaml, encoding="utf-8"):
        s = line.strip()
        if s.startswith("- name:"):
            cur = s.split(":", 1)[1].strip()
        elif s.startswith("weight:") and cur:
            try:
                weights[cur] = float(s.split(":", 1)[1].strip())
            except ValueError:
                pass
    return weights or default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prices", help="价格观测 CSV")
    ap.add_argument("--city", default=None, help="城市 yaml 路径")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD，默认今天")
    args = ap.parse_args()

    weights = load_weights(args.city)
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()

    items = {}
    for r in csv.DictReader(open(args.prices, encoding="utf-8-sig")):
        try:
            price = float(r["price"])
            factor = UNIT_TO_JIN.get(r.get("unit", "斤"), 1.0)
        except (KeyError, ValueError):
            continue
        per_jin = price / factor if factor > 1 else price * factor  # 折算到 元/斤
        d = r.get("date", "")
        stale = ""
        try:
            age = (today - datetime.strptime(d, "%Y-%m-%d").date()).days
            if age > 7:
                stale = "（价格可能已过期）"
        except ValueError:
            pass
        items.setdefault(r["item"], []).append({
            "variety": r.get("variety", ""), "market": r.get("market", ""),
            "per_jin": round(per_jin, 2), "date": d, "source": r.get("source", ""),
            "stale": stale,
        })

    print("参考价（元/500g）——仅供参考，不代表附近摊位实际成交价\n")
    for item, obs in items.items():
        # 批发价单独标记：批发价通常显著低于零售，混入会拉低均价
        wholesale = [o for o in obs if "批发" in o["source"] or "批发" in o.get("variety", "")]
        obs = [o for o in obs if o not in wholesale]
        # 异常值剔除：≥3 条观测时，偏离中位数超过 2 倍/0.5 倍的丢弃
        if len(obs) >= 3:
            vals = sorted(o["per_jin"] for o in obs)
            med = vals[len(vals) // 2]
            obs = [o for o in obs if 0.5 * med <= o["per_jin"] <= 2 * med]
        if not obs:
            print(f"  {item}: 无有效零售价（仅有批发价或异常值，不输出均价）")
            continue
        varieties = {o["variety"] for o in obs if o["variety"]}
        sources = {o["source"] for o in obs}
        conf = "高" if len(sources) >= 3 else ("中" if len(sources) == 2 else "低")
        if len(varieties) > 1:
            lo, hi = min(o["per_jin"] for o in obs), max(o["per_jin"] for o in obs)
            print(f"  {item}: {lo:.1f} ~ {hi:.1f} 元/斤（品种无法对齐，给区间；置信度{conf}）")
        else:
            wsum = sum(weights.get(o["source"], 0.2) for o in obs)
            val = sum(o["per_jin"] * weights.get(o["source"], 0.2) for o in obs) / (wsum or 1)
            stale = "".join(o["stale"] for o in obs if o["stale"])
            print(f"  {item}: {val:.1f} 元/斤（置信度{conf}）{stale}")
        for o in obs:
            print(f"      - {o['source']}｜{o['market'] or '-'}｜{o['per_jin']}｜{o['date']}")
        for o in wholesale:
            print(f"      - {o['source']}｜{o['market'] or '-'}｜{o['per_jin']}｜{o['date']}（批发价，仅供参考，不计入零售均价）")


if __name__ == "__main__":
    main()
