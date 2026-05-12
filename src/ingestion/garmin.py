"""
garmin.py
---------
Parse activity and wellness data from a Garmin Connect bulk export.

Garmin export structure (from account settings > Data Export):
  DI_CONNECT/
    DI-Connect-Fitness/          <- .fit activity files
    DI-Connect-User/
      user_biometrics_*.json     <- resting HR, weight
    DI-Connect-Fitness-Extras/
      wellness-*.json            <- daily HRV, sleep, Body Battery
      summarizedActivities.json  <- summary of all activities

Usage:
    from src.ingestion.garmin import GarminExportParser
    parser = GarminExportParser("data/raw/garmin/")
    activities_df = parser.load_activities()
    wellness_df   = parser.load_wellness()
"""

import os
import json
import glob
from pathlib import Path

import pandas as pd
import numpy as np
from fitparse import FitFile


class GarminExportParser:
    def __init__(self, export_dir: str):
        self.export_dir = Path(export_dir)

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def load_activities(self) -> pd.DataFrame:
        """
        Load the summarisedActivities.json from the export.
        Falls back to parsing individual .fit files if not found.
        Returns one row per activity with columns:
            activity_id, date, name, type, duration_s, distance_m,
            elevation_m, avg_power_w, np_w, tss, avg_hr, calories
        """
        summary_path = self._find_file("summarizedActivities*.json")
        if summary_path:
            return self._parse_activity_summary(summary_path)
        else:
            print("No summarizedActivities file found — falling back to .fit parsing")
            return self._parse_fit_files()

    def _parse_activity_summary(self, path: Path) -> pd.DataFrame:
        with open(path) as f:
            raw = json.load(f)

        # Drill into nested structure
        activities_raw = raw[0]['summarizedActivitiesExport']

        records = []
        for entry in activities_raw:
            records.append({
                "activity_id":  entry.get("activityId"),
                "date":         pd.to_datetime(entry.get("startTimeLocal"), unit="ms"),
                "name":         entry.get("name"),
                "type":         entry.get("sportType", "").lower(),
                "duration_s":   entry.get("duration") / 1000 if entry.get("duration") else None, # convert from ms to s 
                "distance_m":   entry.get("distance",     0) / 10000,  # Garmin native unit → m
                "elevation_m":  entry.get("elevationGain", 0) / 10000,  # Garmin native unit → m
                "avg_power_w":  entry.get("avgPower"),
                "np_w":         entry.get("normPower"),
                "tss":          None, # Garmin returns some dodgy values, recompute tss to Coggan
                "avg_hr":       entry.get("avgHr"),
                "calories":     entry.get("calories"),
                "source":       "garmin",
                "power_z1": entry.get("powerTimeInZone_1") / 1000 if entry.get("powerTimeInZone_1") else None,
                "power_z2": entry.get("powerTimeInZone_2") / 1000 if entry.get("powerTimeInZone_2") else None,
                "power_z3": entry.get("powerTimeInZone_3") / 1000 if entry.get("powerTimeInZone_3") else None,
                "power_z4": entry.get("powerTimeInZone_4") / 1000 if entry.get("powerTimeInZone_4") else None,
                "power_z5": entry.get("powerTimeInZone_5") / 1000 if entry.get("powerTimeInZone_5") else None,
                "power_z6": entry.get("powerTimeInZone_6") / 1000 if entry.get("powerTimeInZone_6") else None,
                "power_z7": entry.get("powerTimeInZone_7") / 1000 if entry.get("powerTimeInZone_7") else None,
            })

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df.sort_values("date").reset_index(drop=True)

    def _parse_fit_files(self) -> pd.DataFrame:
        """Parse individual .fit files when summary JSON is unavailable."""
        fit_files = list(self.export_dir.rglob("*.fit"))
        if not fit_files:
            raise FileNotFoundError(f"No .fit files found under {self.export_dir}")

        records = []
        for fit_path in fit_files:
            try:
                record = self._parse_single_fit(fit_path)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"  Skipping {fit_path.name}: {e}")

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df.sort_values("date").reset_index(drop=True)

    def _parse_single_fit(self, path: Path) -> dict | None:
        ff = FitFile(str(path))
        session = next(
            (m for m in ff.get_messages("session")), None
        )
        if session is None:
            return None

        data = {f.name: f.value for f in session.fields}
        return {
            "activity_id": path.stem,
            "date":        data.get("start_time"),
            "name":        str(path.stem),
            "type":        str(data.get("sport", "")).lower(),
            "duration_s":  data.get("total_elapsed_time"),
            "distance_m":  data.get("total_distance"),
            "elevation_m": data.get("total_ascent"),
            "avg_power_w": data.get("avg_power"),
            "np_w":        data.get("normalized_power"),
            "tss":         data.get("training_stress_score"),
            "avg_hr":      data.get("avg_heart_rate"),
            "calories":    data.get("total_calories"),
        }

    # ------------------------------------------------------------------
    # Wellness (HRV, sleep, Body Battery)
    # ------------------------------------------------------------------

    def load_wellness(self) -> pd.DataFrame:
        wellness_files = list(self.export_dir.rglob("*healthStatusData*.json"))
        if not wellness_files:
            print("No health status files found.")
            return pd.DataFrame()

        records = []
        for wf in wellness_files:
            with open(wf) as f:
                entries = json.load(f)
            for entry in entries:
                # pivot the metrics list into a dict
                metrics = {m['type']: m.get('value') for m in entry['metrics']}
                records.append({
                    "date":            pd.to_datetime(entry['calendarDate']),
                    "hrv_rmssd":       metrics.get('HRV'),
                    "resting_hr":      metrics.get('HR'),
                    "respiration_rate": metrics.get('RESPIRATION'),
                    "spo2":            metrics.get('SPO2'),
                })

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return (
            df.drop_duplicates("date")
            .sort_values("date")
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_file(self, pattern: str) -> Path | None:
        matches = list(self.export_dir.rglob(pattern))
        return matches[0] if matches else None

    @staticmethod
    def _sleep_hours(seconds) -> float | None:
        if seconds is None:
            return None
        return round(seconds / 3600, 2)
