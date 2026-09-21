from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PackageInfo:
    package_text: str | None
    reference_grams: float | None
    reference_milliliters: float | None
    package_count: int | None
    warnings: list[str]


def parse_price(
    text: str | int | float | None,
    unit: str | None = None,
) -> float | None:
    """
    unit 仅允许 "yuan" 或 "cent"，且必须来自 config.PRICE_FIELD_UNITS
    的显式登记。数值型价格未登记单位时返回 None，
    由调用方标记 PRICE_UNIT_UNCONFIRMED。禁止启发式换算。
    """
    if text is None:
        return None

    if isinstance(text, (int, float)):
        value = float(text)
        if value < 0:
            return None

        if unit == "yuan":
            return value
        if unit == "cent":
            return value / 100

        # 未确认字段单位，不能自行猜测或除以 100。
        return None

    cleaned = str(text).replace(",", "").strip()
    match = re.search(r"(?:¥|￥)?\s*(\d+(?:\.\d{1,2})?)", cleaned)

    if not match:
        return None

    value = float(match.group(1))
    if value < 0:
        return None

    # 字符串价格通常来自页面展示文本（元）。
    # 若该字段已显式登记为 cent，则按登记换算。
    if unit == "cent":
        return value / 100

    return value


def parse_package(text: str | None) -> PackageInfo:
    if not text:
        return PackageInfo(
            package_text=None,
            reference_grams=None,
            reference_milliliters=None,
            package_count=None,
            warnings=["PACKAGE_TEXT_MISSING"],
        )

    normalized = (
        text.lower()
        .replace("克", "g")
        .replace("千克", "kg")
        .replace("公斤", "kg")
        .replace("毫升", "ml")
        .replace("升", "l")
        .replace("×", "x")
        .replace("*", "x")
        .replace(" ", "")
    )

    warnings: list[str] = []
    count = 1

    count_match = re.search(r"x(\d+)(?:盒|袋|瓶|罐|包|个|份)?", normalized)
    if count_match:
        count = int(count_match.group(1))

    value_match = re.search(r"(\d+(?:\.\d+)?)(kg|g|ml|l)", normalized)
    if not value_match:
        return PackageInfo(
            package_text=text,
            reference_grams=None,
            reference_milliliters=None,
            package_count=count,
            warnings=["PACKAGE_WEIGHT_UNRESOLVED"],
        )

    value = float(value_match.group(1))
    unit = value_match.group(2)

    grams = None
    milliliters = None

    if unit == "kg":
        grams = value * 1000 * count
    elif unit == "g":
        grams = value * count
    elif unit == "l":
        milliliters = value * 1000 * count
    elif unit == "ml":
        milliliters = value * count

    return PackageInfo(
        package_text=text,
        reference_grams=grams,
        reference_milliliters=milliliters,
        package_count=count,
        warnings=warnings,
    )


def normalize_text(value: object) -> str:
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()
