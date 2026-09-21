#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五运六气 + 时令计算脚本（纯标准库，无第三方依赖）

用法：
  python wuyun_liuqi.py 2026            # 输出某年五运六气全貌
  python wuyun_liuqi.py 2026-08-18      # 输出指定日期的节气/时令/当前所主之气与饮食提示
  python wuyun_liuqi.py                 # 默认今天

说明：
  1) 节气日期为近似值（±1 天，闰年可能有 1 天偏移），饮食计划不受影响。
  2) 客气以司天为三之气，按三阴三阳次序顺推。
  3) 输出面向饮食计划场景，不做临床诊断。
"""

import sys
from datetime import date

# 强制 UTF-8 输出，避免 Windows 终端 GBK/UTF-8 乱码
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------- 基础数据 ----------

TIANGAN = "甲乙丙丁戊己庚辛壬癸"
DIZHI = "子丑寅卯辰巳午未申酉戌亥"

# 天干化五运（中运）：甲己土、乙庚金、丙辛水、丁壬木、戊癸火
GAN_WUXING = {"甲": "土", "己": "土", "乙": "金", "庚": "金", "丙": "水",
              "辛": "水", "丁": "木", "壬": "木", "戊": "火", "癸": "火"}
# 阳干太过，阴干不及
YANG_GAN = set("甲丙戊庚壬")

# 地支定司天 / 在泉
SITIAN_INQUAN = {
    "子": ("少阴君火", "阳明燥金"),
    "午": ("少阴君火", "阳明燥金"),
    "丑": ("太阴湿土", "太阳寒水"),
    "未": ("太阴湿土", "太阳寒水"),
    "寅": ("少阳相火", "厥阴风木"),
    "申": ("少阳相火", "厥阴风木"),
    "卯": ("阳明燥金", "少阴君火"),
    "酉": ("阳明燥金", "少阴君火"),
    "辰": ("太阳寒水", "太阴湿土"),
    "戌": ("太阳寒水", "太阴湿土"),
    "巳": ("厥阴风木", "少阳相火"),
    "亥": ("厥阴风木", "少阳相火"),
}

# 三阴三阳次序（客气推算用，循环）
SANYIN_SANYANG = ["厥阴风木", "少阴君火", "太阴湿土",
                  "少阳相火", "阳明燥金", "太阳寒水"]

# 主气六步（固定），含起始节气近似日期
ZHUQI_STEPS = [
    ("初之气", "厥阴风木", (1, 20), "大寒"),     # 大寒→春分
    ("二之气", "少阴君火", (3, 20), "春分"),     # 春分→小满
    ("三之气", "少阳相火", (5, 21), "小满"),     # 小满→大暑
    ("四之气", "太阴湿土", (7, 22), "大暑"),     # 大暑→秋分
    ("五之气", "阳明燥金", (9, 23), "秋分"),     # 秋分→小雪
    ("终之气", "太阳寒水", (11, 22), "小雪"),    # 小雪→大寒
]

# 二十四节气近似日期（月, 日）
JIEQI = [
    ("小寒", 1, 5), ("大寒", 1, 20), ("立春", 2, 4), ("雨水", 2, 19),
    ("惊蛰", 3, 5), ("春分", 3, 20), ("清明", 4, 5), ("谷雨", 4, 20),
    ("立夏", 5, 5), ("小满", 5, 21), ("芒种", 6, 6), ("夏至", 6, 21),
    ("小暑", 7, 7), ("大暑", 7, 22), ("立秋", 8, 7), ("处暑", 8, 23),
    ("白露", 9, 7), ("秋分", 9, 23), ("寒露", 10, 8), ("霜降", 10, 23),
    ("立冬", 11, 7), ("小雪", 11, 22), ("大雪", 12, 7), ("冬至", 12, 22),
]

# 六气 → 饮食调整提示（含倪氏六淫主治的五味治则食物化）
LIUQI_FOOD = {
    "厥阴风木": "风气主令：宜疏风平肝——芹菜、菊花茶、薄荷、深绿叶菜；少熬夜，护肝。五味治则（六淫主治·风）：辛味为主（葱、姜、薄荷、香菜），配甘味缓之（山药、大枣）；少酸收。",
    "少阴君火": "君火主令：宜清心泻火——苦瓜、莲子、绿豆、冬瓜；忌辛辣厚味。五味治则（六淫主治·热）：苦味为主（苦瓜、莲子、绿茶），咸寒为辅（海带、紫菜），酸收佐之（乌梅、醋）。",
    "太阴湿土": "湿土主令：宜健脾祛湿——薏米、赤小豆、茯苓、山药、陈皮；少甜腻生冷。五味治则（六淫主治·湿）：苦味燥湿+微辛温（陈皮、生姜），淡味利湿（冬瓜、薏米）；少甜腻。",
    "少阳相火": "相火主令：宜清暑热——绿豆、苦瓜、丝瓜、梨；多补水，防上火。五味治则（六淫主治·火）：咸冷为主（海带、淡菜），苦辛佐之（苦瓜、绿茶、薄荷）。",
    "阳明燥金": "燥金主令：宜润燥养阴——银耳、百合、梨、蜂蜜、荸荠；忌过辛烤炸。五味治则（六淫主治·燥）：甘味滋润为主（银耳、蜂蜜、南瓜），辛味发散佐之（白萝卜、杏仁）；忌烤炸。",
    "太阳寒水": "寒水主令：宜温养防寒——姜、羊肉、桂圆、韭菜；忌生冷。五味治则（六淫主治·寒）：甘热+辛热为主（姜、桂皮、花椒、羊肉），苦辛佐之。",
}

# 岁运五行 → 饮食调整提示
YUN_FOOD = {
    "木": {"太过": "木运太过：宜平肝潜阳+健脾培土——芹菜、山药、小米。",
           "不及": "木运不及：宜养肝柔肝——枸杞、绿叶菜、黑芝麻。"},
    "火": {"太过": "火运太过：宜清心降火——莲子、苦瓜、绿豆。",
           "不及": "火运不及：宜温养心阳——桂圆、红枣、姜。"},
    "土": {"太过": "土运太过：宜健脾祛湿——薏米、冬瓜、茯苓。",
           "不及": "土运不及：宜健脾益气——小米、山药、南瓜。"},
    "金": {"太过": "金运太过：宜润肺防燥——银耳、百合、梨。",
           "不及": "金运不及：宜补肺气——百合、山药、杏仁。"},
    "水": {"太过": "水运太过：宜温肾化水——肉桂、茯苓、黑豆。",
           "不及": "水运不及：宜滋肾养阴——黑豆、黑芝麻、桑葚。"},
}

# 时令（五季）→ 养生与当令食材
SEASON_FOOD = {
    "春": {"principle": "春主生发，养肝为先，宜辛温发散、少酸多甘",
           "foods": "荠菜、菠菜、韭菜、豆芽、芹菜、草莓、春笋"},
    "夏": {"principle": "夏主长养，养心为先，宜清淡祛暑、补水",
           "foods": "苦瓜、冬瓜、黄瓜、丝瓜、西瓜、绿豆、番茄"},
    "长夏": {"principle": "长夏主化，健脾祛湿为先",
             "foods": "薏米、赤小豆、冬瓜、山药、玉米、荷叶"},
    "秋": {"principle": "秋主收敛，养肺为先，宜润燥滋阴",
           "foods": "银耳、百合、梨、莲藕、南瓜、山药、葡萄"},
    "冬": {"principle": "冬主收藏，养肾为先，宜温补御寒",
           "foods": "羊肉、牛肉、黑豆、核桃、栗子、萝卜、白菜"},
}


# ---------- 干支 ----------

def ganzhi(year):
    g = TIANGAN[(year - 4) % 10]
    z = DIZHI[(year - 4) % 12]
    return g + z


def wuyun_liuqi_of_year(year):
    gz = ganzhi(year)
    g, z = gz[0], gz[1]
    yun = GAN_WUXING[g]
    tai_guo = g in YANG_GAN
    yun_deg = "太过" if tai_guo else "不及"
    sitian, inquan = SITIAN_INQUAN[z]

    # 客气六步：司天为三之气
    idx = SANYIN_SANYANG.index(sitian)
    keqi_names = []
    for i in range(6):
        k = (idx + (i - 2)) % 6
        keqi_names.append(SANYIN_SANYANG[k])

    return {
        "year": year, "ganzhi": gz, "gan": g, "zhi": z,
        "zhongyun": yun, "zhongyun_degree": yun_deg,
        "sitian": sitian, "inquan": inquan,
        "keqi": keqi_names,  # 初之气..终之气
    }


# ---------- 节气 / 主气 ----------

def _jieqi_date(year, jq):
    name, m, d = jq
    return date(year, m, d)


def current_solar_term(d):
    """返回 (当前节气名, 起始日期)；跨年处理小寒/大寒在年初。"""
    y = d.year
    # 构造候选：去年12月~今年1月的“小寒、大寒”跨年 + 今年全部 + 明年小寒大寒
    cands = []
    for yc in (y - 1, y, y + 1):
        for jq in JIEQI:
            cands.append((_jieqi_date(yc, jq), jq[0]))
    cands.sort()
    cur = None
    for start, name in cands:
        if start <= d:
            cur = (name, start)
        else:
            break
    return cur  # (节气名, 起始日)


def zhuqi_of_date(d):
    """给定日期所在主气步：返回 (步名, 气名, 起始节气)。"""
    # 主气六步起点
    steps = []
    for step_name, qi, (m, dd), jq_name in ZHUQI_STEPS:
        start = date(d.year, m, dd)
        steps.append((start, step_name, qi, jq_name))
    # 终之气从11月22跨到次年1月20，需处理年初
    if d < steps[0][0]:
        return ("终之气", "太阳寒水", "小雪")
    cur = None
    for i, (start, step_name, qi, jq_name) in enumerate(steps):
        if start <= d:
            cur = (step_name, qi, jq_name)
    return cur


def season_of_date(d):
    """五季划分（按主气近似）：春/夏/长夏/秋/冬。"""
    m, dd = d.month, d.day
    if (m == 2 and dd >= 4) or m in (3, 4) or (m == 5 and dd < 5):
        return "春"
    if (m == 5 and dd >= 5) or m in (6,):
        return "夏"
    if m == 7 or (m == 8 and dd < 7):
        return "长夏"
    if (m == 8 and dd >= 7) or m in (9, 10) or (m == 11 and dd < 7):
        return "秋"
    return "冬"


# ---------- 输出 ----------

def render_year(y):
    info = wuyun_liuqi_of_year(y)
    print(f"【{y} 年（{info['ganzhi']}年）五运六气】")
    print(f"岁运（中运）：{info['zhongyun']}运{info['zhongyun_degree']}")
    print(f"司天：{info['sitian']}    在泉：{info['inquan']}")
    print(YUN_FOOD[info['zhongyun']][info['zhongyun_degree']])
    print()
    print("主气六步（固定）：")
    for i, (step, qi, (m, dd), jq) in enumerate(ZHUQI_STEPS):
        print(f"  {step} {qi}（{jq} ~ {ZHUQI_STEPS[(i+1)%6][3]}）")
    print("客气六步（随年变化）：")
    jq_names = [s[3] for s in ZHUQI_STEPS]
    for i, qi in enumerate(info["keqi"]):
        print(f"  {ZHUQI_STEPS[i][0]} {qi}（自{jq_names[i]}起）")
    print()
    print("【本年气候与饮食提要】")
    print(f"· {info['sitian']}司天 → 上半年气候偏{_qi_climate(info['sitian'])}，饮食：{_qi_food_short(info['sitian'])}")
    print(f"· {info['inquan']}在泉 → 下半年气候偏{_qi_climate(info['inquan'])}，饮食：{_qi_food_short(info['inquan'])}")
    print(f"· 岁运{info['zhongyun']}{info['zhongyun_degree']} → {YUN_FOOD[info['zhongyun']][info['zhongyun_degree']]}")


def _qi_climate(qi):
    m = {
        "厥阴风木": "风", "少阴君火": "热", "太阴湿土": "湿",
        "少阳相火": "暑热", "阳明燥金": "燥", "太阳寒水": "寒",
    }
    return m.get(qi, qi)


def _qi_food_short(qi):
    return LIUQI_FOOD.get(qi, "").split("——")[-1].split("；")[0]


def render_date(d):
    print(f"【{d.isoformat()} 时令与运气】")
    jq, jq_start = current_solar_term(d)
    season = season_of_date(d)
    step, zhuqi, jq_name = zhuqi_of_date(d)
    info = wuyun_liuqi_of_year(d.year)
    # 当前客气：找到主气步对应的客气
    step_idx = [s[0] for s in ZHUQI_STEPS].index(step)
    keqi_now = info["keqi"][step_idx]
    print(f"节气：{jq}（起于 {jq_start.isoformat()}，约 ±1 天）")
    print(f"时令：{season}季 —— {SEASON_FOOD[season]['principle']}")
    print(f"当令食材：{SEASON_FOOD[season]['foods']}")
    print(f"当前所主之气：主气 {zhuqi} + 客气 {keqi_now}")
    print(f"· 主气（{zhuqi}）：{LIUQI_FOOD[zhuqi]}")
    print(f"· 客气（{keqi_now}）：{LIUQI_FOOD[keqi_now]}")
    print(f"本年岁运：{info['zhongyun']}运{info['zhongyun_degree']}（{info['ganzhi']}年），"
          f"司天 {info['sitian']}，在泉 {info['inquan']}")
    print(YUN_FOOD[info['zhongyun']][info['zhongyun_degree']])
    print()
    print("【本周食谱落实建议】")
    print(f"1. 优先采购当令食材：{SEASON_FOOD[season]['foods']}（应季=便宜+顺天时）")
    print(f"2. 主气建议：{LIUQI_FOOD[zhuqi]}")
    print(f"3. 客气建议：{LIUQI_FOOD[keqi_now]}")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg is None:
        d = date.today()
        render_date(d)
    elif "-" in arg:
        y, m, dd = map(int, arg.split("-"))
        render_date(date(y, m, dd))
    else:
        render_year(int(arg))


if __name__ == "__main__":
    main()
