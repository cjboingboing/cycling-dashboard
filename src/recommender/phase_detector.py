"""
phase_detector.py
-----------------
Infer the athlete's current training phase from PMC history.

Phases (Bompa & Haff periodisation model, adapted for power-based cycling):

    base  — aerobic foundation; CTL building from low/moderate base;
             TSB mildly negative (-5 to -15); priority: Z1/Z2 volume
    build — progressive overload; CTL actively rising; TSB more negative
             (-15 to -25); priority: threshold and VO2max work
    peak  — race-specific sharpening; CTL stable at a high level; TSB
             recovering toward 0; priority: intensity quality, reduced volume
    taper — pre-race shedding of fatigue; CTL declining; TSB positive
             (+5 to +15); priority: activation only

Hysteresis: phases are computed for each of the last 14 days and the
majority-vote result is returned. A phase transition requires ≥8 of 14
days pointing to the new state, preventing oscillation from single-day
TSS anomalies (hard race day, rest day etc).

Science:
    Bompa & Haff (2009) — Periodization: Theory and Methodology of Training
    Coggan & Allen (2010) — Training and Racing with a Power Meter
"""

from collections import Counter
from dataclasses import dataclass

import pandas as pd


@dataclass
class PhaseResult:
    phase: str               # "base" | "build" | "peak" | "taper"
    explanation: str         # one-sentence rationale
    ctl_weekly_trend: float  # CTL change per week (14-day window)
    atl_ctl_ratio: float     # ATL/CTL ratio today
    confidence: float        # 0.0–1.0: fraction of last 14 days in majority phase


def detect_phase(pmc_df: pd.DataFrame) -> PhaseResult:
    """
    Determine the current training phase from PMC history.

    Parameters
    ----------
    pmc_df : output of compute_pmc() — must include columns [date, ctl, atl, tsb]

    Returns
    -------
    PhaseResult
    """
    n = len(pmc_df)

    if n < 7:
        return PhaseResult(
            phase="base",
            explanation="Insufficient PMC history — defaulting to base phase.",
            ctl_weekly_trend=0.0,
            atl_ctl_ratio=1.0,
            confidence=0.5,
        )

    # Compute raw phase signal for each of the last 14 days (hysteresis window)
    window = min(14, n)
    raw_phases: list[str] = []

    for offset in range(window, 0, -1):
        i = n - offset  # absolute row index
        ctl_now = float(pmc_df.iloc[i]["ctl"])
        tsb_now = float(pmc_df.iloc[i]["tsb"])
        atl_now = float(pmc_df.iloc[i]["atl"])

        # 14-day and 28-day lookback CTL for trend computation
        i_14 = max(0, i - 14)
        i_28 = max(0, i - 28)
        ctl_14d = float(pmc_df.iloc[i_14]["ctl"])
        ctl_28d = float(pmc_df.iloc[i_28]["ctl"])

        days_14 = i - i_14
        days_28 = i - i_28
        ctl_trend_2w = (ctl_now - ctl_14d) / (days_14 / 7) if days_14 > 0 else 0.0
        ctl_trend_4w = (ctl_now - ctl_28d) / (days_28 / 7) if days_28 > 0 else 0.0

        raw_phases.append(_classify_snapshot(ctl_now, tsb_now, atl_now, ctl_trend_2w, ctl_trend_4w))

    counts = Counter(raw_phases)
    majority_phase, majority_count = counts.most_common(1)[0]
    confidence = round(majority_count / window, 2)

    # Current-day metrics for output
    ctl_now  = float(pmc_df.iloc[-1]["ctl"])
    atl_now  = float(pmc_df.iloc[-1]["atl"])
    tsb_now  = float(pmc_df.iloc[-1]["tsb"])
    ctl_14d  = float(pmc_df.iloc[max(0, n - 15)]["ctl"])
    ctl_weekly_trend = round((ctl_now - ctl_14d) / 2, 2)
    atl_ctl_ratio    = round(atl_now / ctl_now, 3) if ctl_now > 0 else 1.0

    return PhaseResult(
        phase            = majority_phase,
        explanation      = _explain(majority_phase, ctl_now, tsb_now, ctl_weekly_trend, atl_ctl_ratio),
        ctl_weekly_trend = ctl_weekly_trend,
        atl_ctl_ratio    = atl_ctl_ratio,
        confidence       = confidence,
    )


def _classify_snapshot(
    ctl: float,
    tsb: float,
    atl: float,
    ctl_trend_2w: float,   # CTL change per week over last 14 days
    ctl_trend_4w: float,   # CTL change per week over last 28 days
) -> str:
    """
    Classify a single PMC snapshot into a training phase.

    Priority: taper → peak → build → base.
    Higher-priority phases are checked first to avoid misclassification.
    """
    atl_ctl_ratio = atl / ctl if ctl > 0.1 else 1.0

    # Taper: TSB has turned clearly positive AND CTL is actively declining.
    # Dropping CTL + rising TSB is the signature of intentional volume reduction.
    if tsb > 5 and ctl_trend_2w < -1.0:
        return "taper"

    # Peak: CTL is high and has plateaued; TSB is recovering toward 0.
    # Volume is dropping but intensity stays up — sharpening for a target event.
    if ctl >= 65 and abs(ctl_trend_2w) <= 1.5 and -15 < tsb < 10:
        return "peak"

    # Build: CTL is actively rising with meaningful training load present.
    # ATL/CTL > 1 confirms the athlete is accumulating fatigue (loading).
    if ctl_trend_4w > 0.3 or (ctl_trend_2w > 1.0 and tsb < -5):
        return "build"

    # Base: low CTL, early season rebuild, or ambiguous signal.
    return "base"


def _explain(
    phase: str,
    ctl: float,
    tsb: float,
    ctl_weekly: float,
    atl_ctl_ratio: float,
) -> str:
    if phase == "taper":
        return (
            f"CTL falling {abs(ctl_weekly):.1f} pts/week with TSB positive ({tsb:+.0f}) — "
            "volume is down, fatigue shedding for a target event."
        )
    elif phase == "peak":
        direction = f"{ctl_weekly:+.1f}" if abs(ctl_weekly) > 0.2 else "≈ stable"
        return (
            f"CTL at {ctl:.0f} ({direction}/week) and TSB {tsb:+.0f} — "
            "fitness banked, sharpening intensity while reducing volume."
        )
    elif phase == "build":
        return (
            f"CTL {ctl:.0f} rising {ctl_weekly:+.1f}/week, ATL/CTL ratio {atl_ctl_ratio:.2f} — "
            "progressive overload block; TSB negative is expected and manageable."
        )
    else:  # base
        return (
            f"CTL at {ctl:.0f} — building aerobic base; prioritise Z1/Z2 volume "
            "and limit grey-zone tempo work."
        )
