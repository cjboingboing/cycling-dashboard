"""
pmc.py
------
Performance Management Chart calculations.

Core metrics:
    TSS  — Training Stress Score (input, per activity)
    ATL  — Acute Training Load  (fatigue),   τ = 7 days
    CTL  — Chronic Training Load (fitness),  τ = 42 days
    TSB  — Training Stress Balance (form)  = CTL - ATL

All three use exponential weighted moving averages (EWMA).
The decay constants follow the TrainingPeaks convention:
    α_ATL = 1 - exp(-1/7)
    α_CTL = 1 - exp(-1/42)

Usage:
    from src.processing.pmc import compute_pmc
    pmc_df = compute_pmc(activities_df)
"""

import numpy as np
import pandas as pd


# Standard time constants (days)
ATL_TAU = 7
CTL_TAU = 42

def estimate_tss(row: pd.Series, ftp: float):
    av_hr = row.get('avg_hr')
    
    pass


def compute_tss(row: pd.Series, ftp: float) -> float | None:
    np_w = row.get("np_w") or row.get("avg_power_w")  # fall back to avg power
    dur  = row.get("duration_s")
    if pd.isna(np_w) or pd.isna(dur) or ftp <= 0:
        return None
    intensity_factor = np_w / ftp
    return (dur * np_w * intensity_factor) / (ftp * 3600) * 100


def fill_missing_tss(df: pd.DataFrame, ftp: float) -> pd.DataFrame:
    """
    For cycling activities missing a TSS value, estimate from NP + duration.
    Non-cycling activities get a rough HR-based proxy (or 0 if no data).
    """
    df = df.copy()
    cycling_mask = df["type"].str.contains("cycling|ride|virtual", case=False, na=False)

    for idx, row in df[cycling_mask & df["tss"].isna()].iterrows():
        df.at[idx, "tss"] = compute_tss(row, ftp)

    # Non-cycling: rough proxy — 1 TSS per minute at moderate effort
    non_cycling_missing = ~cycling_mask & df["tss"].isna()
    df.loc[non_cycling_missing, "tss"] = (
        df.loc[non_cycling_missing, "duration_s"].fillna(0) / 60
    )

    return df


def compute_pmc(
    activities_df: pd.DataFrame,
    ftp: float = 300,
    atl_tau: int = ATL_TAU,
    ctl_tau: int = CTL_TAU,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Build a daily PMC dataframe from an activities dataframe.

    Parameters
    ----------
    activities_df : DataFrame with columns [date, tss, type, np_w, duration_s]
    ftp           : Functional Threshold Power in watts
    atl_tau       : ATL time constant in days (default 7)
    ctl_tau       : CTL time constant in days (default 42)
    start_date    : Optional ISO date string to clip the range
    end_date      : Optional ISO date string to clip the range

    Returns
    -------
    DataFrame with columns [date, daily_tss, atl, ctl, tsb]
    """
    df = fill_missing_tss(activities_df, ftp)

    # Aggregate TSS by day (multiple rides in one day sum)
    daily = (
        df.groupby("date")["tss"]
          .sum()
          .rename("daily_tss")
          .reset_index()
    )

    # Build a continuous daily date range
    date_min = start_date or daily["date"].min()
    date_max = end_date   or daily["date"].max()
    full_range = pd.DataFrame({
        "date": pd.date_range(date_min, date_max, freq="D")
    })

    daily = full_range.merge(daily, on="date", how="left").fillna({"daily_tss": 0})

    # EWMA decay constants
    alpha_atl = 1 - np.exp(-1 / atl_tau)
    alpha_ctl = 1 - np.exp(-1 / ctl_tau)

    atl_vals = np.zeros(len(daily))
    ctl_vals = np.zeros(len(daily))

    for i, tss in enumerate(daily["daily_tss"]):
        if i == 0:
            atl_vals[i] = tss
            ctl_vals[i] = tss
        else:
            atl_vals[i] = atl_vals[i - 1] + alpha_atl * (tss - atl_vals[i - 1])
            ctl_vals[i] = ctl_vals[i - 1] + alpha_ctl * (tss - ctl_vals[i - 1])

    daily["atl"] = np.round(atl_vals, 2)
    daily["ctl"] = np.round(ctl_vals, 2)
    daily["tsb"] = np.round(ctl_vals - atl_vals, 2)
    daily["daily_tss"] = daily["daily_tss"].fillna(0).astype(float)

    return daily
