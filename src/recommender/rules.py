"""
rules.py
--------
Rule-based activity recommendation engine.

Takes today's recovery metrics plus optional PMC history and activity data
to produce a ranked list of 2-3 structured workout recommendations with:
  - current training phase
  - polarised intensity audit (last 4 weeks)
  - weekly TSS progression vs target

All logic is deterministic Python — no API calls.

Science:
    Seiler & Kjerland (2006) — polarised training distribution
    Stöggl & Sperlich (2014) — polarised vs threshold RCT
    Coggan & Allen (2010) — TSB-based readiness
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.recommender.workout_library import WORKOUT_LIBRARY, Workout
from src.recommender.phase_detector import detect_phase, PhaseResult


# ---------------------------------------------------------------------------
# Recommendation dataclass
# New fields have defaults → fully backward-compatible with existing callers.
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    session_type: str         # top workout name (or fallback string)
    intensity: str            # "high" | "moderate" | "low" | "none"
    tss_target: int | None    # midpoint of top workout TSS range
    rationale: list[str]      # plain-English signal evaluation
    flags: list[str]          # warning flags raised
    # Extended fields
    phase: str                         = "base"
    phase_explanation: str             = ""
    workout_options: list[Workout]     = field(default_factory=list)
    polarised_audit: dict              = field(default_factory=dict)
    weekly_tss_target: int | None      = None
    weekly_tss_actual: int | None      = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend(
    tsb:                    float | None = None,
    hrv_deviation:          float | None = None,
    sleep_hours:            float | None = None,
    recovery_score:         float | None = None,
    consecutive_hard_days:  int          = 0,
    days_since_rest:        int          = 0,
    pmc_df:                 pd.DataFrame | None = None,
    activities_df:          pd.DataFrame | None = None,
    ftp:                    int          = 300,
) -> Recommendation:
    """
    Recommend a session type and ranked workout options.

    Core decision hierarchy (highest to lowest priority):
        1. Hard override: rest if ≥3 negative signals simultaneously
        2. Consecutive hard days: mandatory easy after 3+ hard days
        3. HRV crash alone → reduce to easy day
        4. TSB-based intensity gating
        5. Phase-filtered workout selection from WORKOUT_LIBRARY

    Progressive overload:
        Build phase  → target 5–8% weekly TSS increase
        Peak phase   → hold steady
        Taper phase  → reduce ~40% from preceding week
        Base phase   → target ~5% weekly increase

    Polarised audit (Seiler 80:20 principle):
        Z1+Z2 should be ~80% of time; Z3+Z4 (grey zone) < 10–15%;
        Z5+ ~15–20%. Flag if grey zone exceeds 15% and bias workout
        selection away from tempo/sweet-spot toward Z2 or VO2max.
    """
    # 1. Evaluate recovery signals → intensity_allowed
    intensity_allowed, reasons, flags = _evaluate_signals(
        tsb, hrv_deviation, sleep_hours, recovery_score,
        consecutive_hard_days, days_since_rest,
    )

    # 2. Phase detection (requires ≥7 days of PMC history)
    phase_result: PhaseResult | None = None
    if pmc_df is not None and len(pmc_df) >= 7:
        phase_result = detect_phase(pmc_df)
    phase = phase_result.phase if phase_result else "base"
    phase_explanation = phase_result.explanation if phase_result else ""

    # 3. Polarised intensity audit from last 4 weeks of activities
    audit = _polarised_audit(activities_df, ftp)
    grey_zone_flag = audit.get("grey_zone_flag", False)

    # 4. Weekly TSS progression
    weekly_actual, weekly_target = _weekly_tss_stats(pmc_df, phase)

    # 5. Daily TSS target estimate
    _intensity_default_tss = {"none": 20, "low": 40, "moderate": 70, "high": 100}
    if weekly_target:
        daily_tss_target = max(20, weekly_target // 5)
    else:
        daily_tss_target = _intensity_default_tss.get(intensity_allowed, 60)

    # 6. Select and rank workouts
    if intensity_allowed == "none":
        workouts = [w for w in WORKOUT_LIBRARY if w.name == "Active Recovery Spin"]
    else:
        workouts = _select_workouts(phase, intensity_allowed, daily_tss_target, grey_zone_flag)

    # 7. Derive top-level fields from leading workout
    top = workouts[0] if workouts else None
    session_type = top.name if top else "Rest / active recovery"
    tss_target   = int((top.tss_min + top.tss_max) / 2) if top else daily_tss_target
    intensity    = top.intensity if top else intensity_allowed

    return Recommendation(
        session_type      = session_type,
        intensity         = intensity,
        tss_target        = tss_target,
        rationale         = reasons,
        flags             = flags,
        phase             = phase,
        phase_explanation = phase_explanation,
        workout_options   = workouts,
        polarised_audit   = audit,
        weekly_tss_target = weekly_target,
        weekly_tss_actual = weekly_actual,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _evaluate_signals(
    tsb, hrv_deviation, sleep_hours, recovery_score,
    consecutive_hard_days, days_since_rest,
) -> tuple[str, list[str], list[str]]:
    """
    Evaluate recovery signals and return (intensity_allowed, reasons, flags).

    intensity_allowed: "none" | "low" | "moderate" | "high"
    """
    flags:   list[str] = []
    reasons: list[str] = []
    negatives = 0
    hrv_bad   = False
    sleep_bad = False

    # HRV
    if hrv_deviation is not None and not np.isnan(float(hrv_deviation)):
        hrv_deviation = float(hrv_deviation)
        if hrv_deviation < -1.5:
            flags.append("HRV significantly below baseline")
            reasons.append(f"HRV is {hrv_deviation:.1f} SD below your 7-day baseline — body signalling stress")
            negatives += 1
            hrv_bad = True
        elif hrv_deviation < -0.8:
            reasons.append(f"HRV slightly suppressed ({hrv_deviation:.1f} SD below baseline) — worth monitoring")
        else:
            reasons.append(f"HRV looks normal ({hrv_deviation:+.1f} SD vs baseline)")

    # Sleep
    if sleep_hours is not None and not np.isnan(float(sleep_hours)):
        sleep_hours = float(sleep_hours)
        if sleep_hours < 6.0:
            flags.append(f"Poor sleep ({sleep_hours:.1f}h)")
            reasons.append(f"Only {sleep_hours:.1f}h sleep — adaptation is impaired; avoid hard training")
            negatives += 1
            sleep_bad = True
        elif sleep_hours < 7.0:
            reasons.append(f"Sleep slightly short ({sleep_hours:.1f}h) — manageable")
        else:
            reasons.append(f"Good sleep ({sleep_hours:.1f}h)")

    # TSB
    if tsb is not None and not np.isnan(float(tsb)):
        tsb = float(tsb)
        if tsb < -25:
            reasons.append(f"TSB {tsb:.0f} — carrying significant fatigue; protect recovery")
            negatives += 1
        elif tsb < -10:
            reasons.append(f"TSB {tsb:.0f} — moderate fatigue; typical of a build block")
        elif tsb < 5:
            reasons.append(f"TSB {tsb:.0f} — roughly neutral form")
        elif tsb < 15:
            reasons.append(f"TSB {tsb:.0f} — good form; freshening up nicely")
        else:
            reasons.append(f"TSB {tsb:.0f} — very fresh; ideal for a quality session")

    # Consecutive hard days
    if consecutive_hard_days >= 3:
        flags.append(f"{consecutive_hard_days} consecutive hard days")
        reasons.append(
            f"{consecutive_hard_days} hard days in a row — mandatory easy regardless of other signals"
        )
        negatives += 2

    # --- Intensity gating ---
    if negatives >= 3 or (hrv_bad and sleep_bad):
        intensity = "none"
    elif consecutive_hard_days >= 3:
        intensity = "low"
    elif hrv_bad:
        intensity = "low"
    elif tsb is None or np.isnan(float(tsb)):
        intensity = "moderate"
    elif float(tsb) > 10:
        intensity = "high"
    elif float(tsb) > -10:
        intensity = "moderate"
    elif float(tsb) > -20:
        intensity = "low"
    else:
        intensity = "none"

    return intensity, reasons, flags


def _polarised_audit(activities_df: pd.DataFrame | None, ftp: int) -> dict:
    """
    Compute polarised zone distribution from the last 4 weeks of rides.

    Returns a dict with Z1/Z2, grey-zone, and Z5+ percentages, plus flags.
    Seiler's 80:20 target: ~80% easy, ~10% grey zone max, ~15-20% hard.
    """
    if activities_df is None or activities_df.empty:
        return {}

    try:
        from src.processing.power import PowerAnalyser
    except ImportError:
        return {}

    four_weeks_ago = pd.Timestamp.now() - pd.Timedelta(weeks=4)
    recent = activities_df[activities_df["date"] >= four_weeks_ago]
    if recent.empty or recent["avg_power_w"].isna().all():
        return {}

    try:
        pa    = PowerAnalyser(ftp=ftp)
        zones = pa.zone_distribution(recent)
    except Exception:
        return {}

    easy_names  = {"Z1 Recovery", "Z2 Endurance"}
    grey_names  = {"Z3 Tempo", "Z4 Threshold"}
    hard_names  = {"Z5 VO2max", "Z6 Anaerobic", "Z7 Neuromuscular"}

    z12  = float(zones[zones["zone"].isin(easy_names)]["pct"].sum())
    z34  = float(zones[zones["zone"].isin(grey_names)]["pct"].sum())
    z5p  = float(zones[zones["zone"].isin(hard_names)]["pct"].sum())

    grey_flag     = z34 > 15.0
    not_hard_flag = z5p < 5.0    # too little high-intensity
    not_easy_flag = z12 < 65.0   # too much overall intensity

    rec_msg = ""
    if grey_flag:
        rec_msg = (
            "Grey zone is high — push easy rides to stay firmly in Z2, "
            "and make hard sessions genuinely hard (Z5+)."
        )
    elif not_hard_flag:
        rec_msg = "Very little high-intensity work — consider adding a weekly VO2max session."

    return {
        "z12_pct":        round(z12, 1),
        "z34_pct":        round(z34, 1),
        "z5plus_pct":     round(z5p, 1),
        "grey_zone_flag": grey_flag,
        "not_hard_flag":  not_hard_flag,
        "not_easy_flag":  not_easy_flag,
        "recommendation": rec_msg,
    }


def _weekly_tss_stats(pmc_df: pd.DataFrame | None, phase: str) -> tuple[int | None, int | None]:
    """
    Return (actual_7d_tss, target_7d_tss) based on current phase.

    Progressive overload targets:
        build → +6.5% from previous week
        peak  → hold (0%)
        taper → 60% of two-weeks-ago (pre-taper reference)
        base  → +5% from previous week
    """
    if pmc_df is None or len(pmc_df) < 7:
        return None, None

    n         = len(pmc_df)
    last_7    = int(pmc_df.tail(7)["daily_tss"].fillna(0).sum())
    prev_7    = int(pmc_df.iloc[-14:-7]["daily_tss"].fillna(0).sum()) if n >= 14 else last_7

    if phase == "taper" and n >= 21:
        # Reference the week before taper started (3 weeks ago)
        ref      = int(pmc_df.iloc[-21:-14]["daily_tss"].fillna(0).sum())
        target   = int(ref * 0.60)
    elif phase == "peak":
        target   = prev_7
    elif phase == "build":
        target   = int(prev_7 * 1.065)
    else:  # base
        target   = int(prev_7 * 1.05)

    return last_7, max(target, 10)


def _select_workouts(
    phase:             str,
    intensity_allowed: str,
    daily_tss_target:  int,
    grey_zone_flag:    bool,
) -> list[Workout]:
    """
    Filter and rank workouts from WORKOUT_LIBRARY for current conditions.

    Filtering
    ---------
    1. Must include current phase in applicable_phases.
    2. Intensity must be ≤ intensity_allowed.

    Scoring (higher is better)
    --------------------------
    +3  exact intensity match
    +1  intensity one level below allowed (conservative choice)
     0  intensity > allowed → excluded by filter
    +2  TSS midpoint within 15 of daily target
    +1  TSS midpoint within 35 of daily target
    +1  polarised bias: non-grey workout when grey_zone_flag is set
    -1  polarised bias: grey-zone workout (Z3/Z4 focus) when flag is set
    """
    intensity_order = {"low": 0, "moderate": 1, "high": 2}
    allowed_level   = intensity_order.get(intensity_allowed, 0)

    grey_zones = {"Z3 Tempo", "Z4 Threshold"}

    # Filter
    candidates = [
        w for w in WORKOUT_LIBRARY
        if phase in w.applicable_phases
        and intensity_order.get(w.intensity, 0) <= allowed_level
    ]

    # Fallback: any low-intensity workout
    if not candidates:
        candidates = [w for w in WORKOUT_LIBRARY if w.intensity == "low"]

    def score(w: Workout) -> float:
        s = 0.0
        workout_level = intensity_order.get(w.intensity, 0)

        # Intensity match
        if workout_level == allowed_level:
            s += 3
        elif workout_level == allowed_level - 1:
            s += 1

        # TSS closeness
        tss_mid = (w.tss_min + w.tss_max) / 2
        diff    = abs(tss_mid - daily_tss_target)
        if diff <= 15:
            s += 2
        elif diff <= 35:
            s += 1

        # Polarised audit bias
        if grey_zone_flag:
            has_grey = any(z in grey_zones for z in w.zone_focus)
            s += -1 if has_grey else 1

        return s

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[:3]
