"""
Public fields derived from the private input (birth date, height).
The birth date itself is never returned, only age / age group / birth quarter.
"""
import math
from datetime import date
from typing import Optional

from .config import HEIGHT_REF


def age_months(birth: date, today: Optional[date] = None) -> int:
    """Age in whole months from the birth YEAR + MONTH to the current month (the day is ignored).
    Born 2012-10 -> in 2026-11 that's 169 months = 14 y 1 m."""
    today = today or date.today()
    return (today.year - birth.year) * 12 + (today.month - birth.month)


def age_group(birth: date, today: Optional[date] = None) -> str:
    """By birth YEAR, as in Bosnian youth basketball: U16 = kids who turn 15 or 16 this year,
    U14 = 13-14, U12 = 11-12, U10 = 10 or younger, U18 = 17 or older.
    That's what makes a Q4 (Oct-Dec) birthday the youngest in its group."""
    today = today or date.today()
    years = today.year - birth.year            # age reached this calendar year
    for limit in (10, 12, 14, 16):
        if years <= limit:
            return f"U{limit}"
    return "U18"


def rank_group(gender: str, group: str) -> str:
    return f"{'Boys' if gender == 'boy' else 'Girls'} {group}"


def birth_quarter(birth: date) -> int:
    return (birth.month - 1) // 3 + 1


def avg_height_cm(gender: str, months: int) -> float:
    """Linear interpolation in HEIGHT_REF."""
    table = HEIGHT_REF[gender]
    years = min(max(months / 12, min(table)), max(table))
    lo = int(math.floor(years))
    hi = min(lo + 1, max(table))
    t = years - lo
    return table[lo] * (1 - t) + table[hi] * t


def height_diff_cm(gender: str, months: int, height: float) -> float:
    return round(height - avg_height_cm(gender, months), 1)


def mirwald_offset(gender: str, months: int, height: float,
                   sitting: Optional[float], weight: Optional[float]) -> Optional[float]:
    """Mirwald et al. (2002) maturity offset in years. None if inputs are missing."""
    if sitting is None or weight is None:
        return None
    age = months / 12
    leg = height - sitting
    if gender == "boy":
        v = (-9.236 + 0.0002708 * leg * sitting - 0.001663 * age * leg
             + 0.007216 * age * sitting + 0.02292 * (weight / height) * 100)
    else:
        v = (-9.376 + 0.0001882 * leg * sitting + 0.0022 * age * leg
             + 0.005841 * age * sitting - 0.002658 * age * weight
             + 0.07693 * (weight / height) * 100)
    return round(v, 2)
