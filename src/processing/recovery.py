"""
recovery.py
-----------
Compute recovery and readiness signals from wellness data.

Metrics produced:
    hrv_baseline   — rolling 7-day median RMSSD
    hrv_deviation  — today's HRV vs baseline (z-score)
    recovery_score — composite 0–100 score
    flag           — "rest", "easy", "normal", "go"
"""

import numpy as np
import pandas as pd


HRV_WINDOW      = 7    # days for HRV baseline
SLEEP_OPTIMAL   = 8.0  # hours
SLEEP_MINIMUM   = 6.0


def compute_recovery(wellness_df: pd.DataFrame, pmc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge wellness and PMC data and compute daily recovery signals.

    Parameters
    ----------
    wellness_df : output of GarminExportParser.load_wellness()
    pmc_df      : output of compute_pmc()

    Returns
    -------
    DataFrame with one row per day including all input columns plus:
        hrv_baseline, hrv_deviation, sleep_score_norm,
        body_battery_norm, recovery_score, readiness_flag
    """
    df = pmc_df.merge(wellness_df, on="date", how="left")

    df = _compute_hrv_signals(df)
    df = _compute_composite_score(df)

    return df


def _compute_hrv_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "hrv_rmssd" not in df.columns or df["hrv_rmssd"].isna().all():
        df["hrv_baseline"]  = np.nan
        df["hrv_deviation"] = np.nan
        return df

    # Rolling median as baseline (more robust than mean for HRV)
    df["hrv_baseline"] = (
        df["hrv_rmssd"]
          .rolling(HRV_WINDOW, min_periods=3)
          .median()
    )

    # Z-score vs rolling std
    rolling_std = df["hrv_rmssd"].rolling(HRV_WINDOW, min_periods=3).std()
    df["hrv_deviation"] = (
        (df["hrv_rmssd"] - df["hrv_baseline"]) / rolling_std.clip(lower=0.1)
    ).round(2)

    return df


def _compute_composite_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Composite recovery score (0–100) weighted from available signals.
    Weights: HRV 40%, TSB 30%, Sleep 20%, Body Battery 10%
    All components normalised to 0–1 before weighting.
    """
    df = df.copy()
    components = pd.DataFrame(index=df.index)

    # HRV component: deviation clamped to [-2, +2] then scaled
    if "hrv_deviation" in df.columns:
        components["hrv"] = ((df["hrv_deviation"].clip(-2, 2) + 2) / 4)
    else:
        components["hrv"] = np.nan

    # TSB component: TSB of -30 → 0, TSB of +20 → 1 (linear)
    if "tsb" in df.columns:
        components["tsb"] = ((df["tsb"].clip(-30, 20) + 30) / 50)
    else:
        components["tsb"] = np.nan

    # Sleep component: hours vs optimal
    if "sleep_hours" in df.columns:
        components["sleep"] = (
            df["sleep_hours"].clip(SLEEP_MINIMUM, SLEEP_OPTIMAL) - SLEEP_MINIMUM
        ) / (SLEEP_OPTIMAL - SLEEP_MINIMUM)
    else:
        components["sleep"] = np.nan

    # Body Battery component: already 0–100
    if "body_battery_high" in df.columns:
        components["battery"] = df["body_battery_high"].clip(0, 100) / 100
    else:
        components["battery"] = np.nan

    weights = {"hrv": 0.40, "tsb": 0.30, "sleep": 0.20, "battery": 0.10}

    def weighted_score(row):
        total_w = sum(w for k, w in weights.items() if not np.isnan(row.get(k, np.nan)))
        if total_w == 0:
            return np.nan
        return sum(
            row[k] * w for k, w in weights.items()
            if not np.isnan(row.get(k, np.nan))
        ) / total_w * 100

    df["recovery_score"] = components.apply(weighted_score, axis=1).round(1)
    df["readiness_flag"] = df["recovery_score"].apply(_flag)

    return df


def _flag(score: float) -> str:
    if np.isnan(score):
        return "unknown"
    if score >= 70:
        return "go"
    elif score >= 50:
        return "normal"
    elif score >= 30:
        return "easy"
    else:
        return "rest"
