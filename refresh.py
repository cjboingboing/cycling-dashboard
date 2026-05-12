"""
refresh.py
----------
Incremental Strava sync — fetches only rides newer than what's already
in the parquets, recomputes TSS / PMC / recovery, and saves in place.

Usage:
    python refresh.py

Takes ~5 seconds for a typical daily refresh vs ~30 seconds for the
full notebook rebuild.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()

FTP       = int(os.getenv("FTP", 333))
PROCESSED = PROJECT_ROOT / "data" / "processed"

from src.ingestion.strava       import StravaClient
from src.processing.pmc         import fill_missing_tss, compute_pmc
from src.processing.recovery    import compute_recovery
from src.ml.tss_estimator       import TSSEstimator


# ── 1. Load existing parquets ─────────────────────────────────────────────────

activities_df = pd.read_parquet(PROCESSED / "activities.parquet")
wellness_df   = pd.read_parquet(PROCESSED / "wellness.parquet")

# ── 2. Determine sync cutoff ──────────────────────────────────────────────────

strava_rows = activities_df[activities_df["source"] == "strava"]

if strava_rows.empty:
    after_ts = None
    print("No existing Strava activities — performing full fetch.")
else:
    last_date = strava_rows["date"].max()
    # Go back one full day before the last known ride so we always re-check
    # it and catch same-day activities. Strava filters by start_date (UTC)
    # so this also absorbs any timezone offset between start_date_local
    # and UTC. Deduplication handles the overlap.
    cutoff = last_date - pd.Timedelta(days=1)
    after_ts = int(cutoff.timestamp())
    print(f"Last Strava activity : {last_date.date()}")
    print(f"Fetching activities after {cutoff.date()}...")

# ── 3. Fetch only new activities from Strava ──────────────────────────────────

client     = StravaClient()
new_strava = client.load_activities(max_activities=200, after=after_ts)

if new_strava.empty:
    print("No new Strava activities found — already up to date.")
else:
    print(f"Found {len(new_strava)} new activit{'y' if len(new_strava) == 1 else 'ies'}")

    # ── 4. Filter to cycling and compute TSS ──────────────────────────────────

    cycling_mask  = new_strava["type"].str.contains(
        "cycling|ride|virtualride", case=False, na=False
    )
    new_cycling = new_strava[cycling_mask].copy()

    if not new_cycling.empty:
        new_cycling = fill_missing_tss(new_cycling, ftp=FTP)

        # Reset zero-TSS rows that have valid duration so the estimator fills them
        zero_mask = (new_cycling["tss"] == 0) & (new_cycling["duration_s"] > 0)
        new_cycling.loc[zero_mask, "tss"] = None

        new_cycling = TSSEstimator().predict(new_cycling)

        estimated = new_cycling["tss"].notna().sum()
        print(f"TSS computed for {estimated} / {len(new_cycling)} cycling activities")

        # ── 5. Append and deduplicate ─────────────────────────────────────────

        combined = pd.concat([activities_df, new_cycling], ignore_index=True)
        combined["_dur_bucket"] = (combined["duration_s"] / 1000).round() * 1000
        activities_df = (
            combined
            .sort_values("source")                        # garmin < strava → garmin wins
            .drop_duplicates(subset=["date", "_dur_bucket"], keep="first")
            .drop(columns="_dur_bucket")
            .sort_values("date")
            .reset_index(drop=True)
        )
    else:
        print("No new cycling activities (non-cycling rides skipped).")

# ── 6. Recompute PMC and recovery from full history ───────────────────────────
#
# PMC is a running EWMA so it must be computed from the beginning of history.
# It's fast (~4 000 rows, pure NumPy) so there's no value in trying to
# hot-start from the last known CTL/ATL.

pmc_df      = compute_pmc(activities_df, ftp=FTP)
recovery_df = compute_recovery(wellness_df, pmc_df)

# ── 7. Save ───────────────────────────────────────────────────────────────────

activities_df.to_parquet(PROCESSED / "activities.parquet", index=False)
pmc_df.to_parquet(        PROCESSED / "pmc.parquet",        index=False)
recovery_df.to_parquet(   PROCESSED / "recovery.parquet",   index=False)

latest = pmc_df.iloc[-1]
print(f"\nPMC updated through {pmc_df['date'].max().date()}")
print(f"  CTL (fitness) : {latest['ctl']:.1f}")
print(f"  ATL (fatigue) : {latest['atl']:.1f}")
print(f"  TSB (form)    : {latest['tsb']:+.1f}")
