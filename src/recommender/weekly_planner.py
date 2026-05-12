"""
weekly_planner.py
-----------------
Generate a 7-day structured training plan.

Fixed weekly constraints:
    Wednesday (weekday 2): group ride — hard unstructured day, ~90 TSS
    Saturday  (weekday 5): long Zone 2 — Long Zone 2 workout, ~125 TSS

Remaining days are filled by the existing recommend() engine with TSB
projected forward using planned TSS via the PMC EWMA formulas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from math import exp

import pandas as pd

from src.recommender.rules import recommend, Recommendation
from src.recommender.workout_library import WORKOUT_LIBRARY, Workout


_α_CTL = 1 - exp(-1 / 42)
_α_ATL = 1 - exp(-1 / 7)

_WED = 2
_SAT = 5

_LONG_RIDE   = next(w for w in WORKOUT_LIBRARY if w.name == "Long Zone 2")
_GROUP_RIDE  = next(w for w in WORKOUT_LIBRARY if w.name == "Zone 2 Endurance")
_GROUP_TSS   = 90
_LONG_TSS    = (_LONG_RIDE.tss_min + _LONG_RIDE.tss_max) // 2

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class DayPlan:
    date:        date
    day_name:    str
    workout:     Workout | None
    tss_target:  int
    is_fixed:    bool
    fixed_label: str           # "Group Ride" | "Long Ride" | ""
    rec:         Recommendation | None = None

    @property
    def intensity(self) -> str:
        if self.rec:
            return self.rec.intensity
        if self.is_fixed and self.fixed_label == "Group Ride":
            return "high"
        if self.is_fixed and self.fixed_label == "Long Ride":
            return "low"
        return "moderate"


def plan_week(
    pmc_df:         pd.DataFrame | None,
    activities_df:  pd.DataFrame | None,
    ftp:            int,
    tsb:            float | None,
    hrv_deviation:  float | None,
    sleep_hours:    float | None,
    recovery_score: float | None,
    start_date:     date | None = None,
) -> list[DayPlan]:
    """
    Build a 7-day plan starting from start_date (default: today).

    TSB is projected forward day-by-day using planned session TSS
    via the same EWMA formulas used in pmc.py.
    """
    today = start_date or date.today()

    # Seed CTL/ATL from latest PMC row
    if pmc_df is not None and len(pmc_df) >= 1:
        ctl = float(pmc_df.iloc[-1]["ctl"])
        atl = float(pmc_df.iloc[-1]["atl"])
    else:
        ctl = atl = 50.0

    plan: list[DayPlan] = []
    prev_hard = False

    for i in range(7):
        d  = today + timedelta(days=i)
        wd = d.weekday()

        # ── Wednesday: group ride ─────────────────────────────────────────────
        if wd == _WED:
            plan.append(DayPlan(
                date        = d,
                day_name    = _DAY_NAMES[wd],
                workout     = _GROUP_RIDE,
                tss_target  = _GROUP_TSS,
                is_fixed    = True,
                fixed_label = "Group Ride",
            ))
            planned_tss = _GROUP_TSS
            prev_hard   = True

        # ── Saturday: long ride ───────────────────────────────────────────────
        elif wd == _SAT:
            plan.append(DayPlan(
                date        = d,
                day_name    = _DAY_NAMES[wd],
                workout     = _LONG_RIDE,
                tss_target  = _LONG_TSS,
                is_fixed    = True,
                fixed_label = "Long Ride",
            ))
            planned_tss = _LONG_TSS
            prev_hard   = False

        # ── Flexible day ──────────────────────────────────────────────────────
        else:
            projected_tsb = ctl - atl

            if i == 0:
                # Today: use real recovery signals
                rec = recommend(
                    tsb                   = tsb,
                    hrv_deviation         = hrv_deviation,
                    sleep_hours           = sleep_hours,
                    recovery_score        = recovery_score,
                    consecutive_hard_days = _count_consecutive_hard(activities_df),
                    pmc_df                = pmc_df,
                    activities_df         = activities_df,
                    ftp                   = ftp,
                )
            else:
                # Future days: projected TSB only, no HRV/sleep data
                rec = recommend(
                    tsb                   = projected_tsb,
                    consecutive_hard_days = 1 if prev_hard else 0,
                    pmc_df                = pmc_df,
                    activities_df         = activities_df,
                    ftp                   = ftp,
                )

            top     = rec.workout_options[0] if rec.workout_options else None
            tss_mid = int((top.tss_min + top.tss_max) / 2) if top else (rec.tss_target or 40)

            plan.append(DayPlan(
                date        = d,
                day_name    = _DAY_NAMES[wd],
                workout     = top,
                tss_target  = tss_mid,
                is_fixed    = False,
                fixed_label = "",
                rec         = rec,
            ))
            planned_tss = tss_mid
            prev_hard   = tss_mid >= 70

        # Project CTL/ATL forward
        ctl = ctl * (1 - _α_CTL) + planned_tss * _α_CTL
        atl = atl * (1 - _α_ATL) + planned_tss * _α_ATL

    return plan


def _count_consecutive_hard(activities_df: pd.DataFrame | None) -> int:
    """Count consecutive hard days (TSS ≥ 70) running up to yesterday."""
    if activities_df is None or activities_df.empty:
        return 0
    yesterday = pd.Timestamp(date.today() - timedelta(days=1))
    recent = (
        activities_df[activities_df["date"] <= yesterday]
        .sort_values("date", ascending=False)
    )
    count = 0
    for _, row in recent.iterrows():
        if float(row.get("tss", 0) or 0) >= 70:
            count += 1
        else:
            break
    return count
