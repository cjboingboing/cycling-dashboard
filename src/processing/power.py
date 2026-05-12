"""
power.py
--------
Power-based analysis: zones, power curve, intensity factor.

Power zones follow the Coggan 7-zone model (% of FTP):
    Z1  Active Recovery   < 55%
    Z2  Endurance         55–75%
    Z3  Tempo             76–90%
    Z4  Threshold         91–105%
    Z5  VO2max            106–120%
    Z6  Anaerobic         121–150%
    Z7  Neuromuscular     > 150%

Usage:
    from src.processing.power import PowerAnalyser
    pa = PowerAnalyser(ftp=320)
    zones_df   = pa.zone_distribution(activities_df)
    curve_df   = pa.power_curve(power_streams)   # list of pd.Series
"""

from math import erf, sqrt as _msqrt

import numpy as np
import pandas as pd


COGGAN_ZONES = [
    ("Z1 Recovery",    0,     0.55),
    ("Z2 Endurance",   0.55,  0.75),
    ("Z3 Tempo",       0.75,  0.90),
    ("Z4 Threshold",   0.90,  1.05),
    ("Z5 VO2max",      1.05,  1.20),
    ("Z6 Anaerobic",   1.20,  1.50),
    ("Z7 Neuromuscular",1.50, 9.99),
]


class PowerAnalyser:
    def __init__(self, ftp: float):
        self.ftp = ftp
        self.zones = COGGAN_ZONES

    # ------------------------------------------------------------------
    # Zone classification
    # ------------------------------------------------------------------

    def classify_zone(self, watts: float) -> str:
        ratio = watts / self.ftp
        for name, lo, hi in self.zones:
            if lo <= ratio < hi:
                return name
        return "Z7 Neuromuscular"

    def zone_distribution(self, activities_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute time-in-zone across a set of activities.

        Per-ride method priority
        ------------------------
        1. Garmin power_z1..power_z7 columns — accurate per-zone time recorded
           on the device from actual second-by-second power data.
        2. Gaussian model from avg_power + np_w — the NP/AP variability index
           determines the standard deviation of the modelled power distribution,
           spreading ride time across zones realistically rather than bucketing
           the whole ride into whichever zone contains the average power.

        Returns a DataFrame with columns [zone, duration_hours, pct].
        """
        _garmin_cols = [f"power_z{i}" for i in range(1, 8)]
        has_garmin   = all(c in activities_df.columns for c in _garmin_cols)

        zone_seconds = {z[0]: 0.0 for z in self.zones}

        cycling = activities_df[
            activities_df["type"].str.contains("cycling|ride|virtual", case=False, na=False)
        ]

        for _, row in cycling.iterrows():
            # -- Method 1: Garmin per-zone time (preferred) ------------------
            if has_garmin:
                z_raw = [row.get(c) for c in _garmin_cols]
                z_f   = [float(v) for v in z_raw if v is not None and not pd.isna(v)]
                if z_f and any(v > 0 for v in z_f):
                    for i, (zone_name, _, _) in enumerate(self.zones):
                        v = z_raw[i]
                        if v is not None and not pd.isna(v):
                            zone_seconds[zone_name] += float(v)
                    continue

            # -- Method 2: Gaussian approximation from avg_power + np_w ------
            avg_p = row.get("avg_power_w")
            dur   = row.get("duration_s")
            if avg_p is None or pd.isna(avg_p) or dur is None or pd.isna(dur) or float(dur) <= 0:
                continue

            avg_p = float(avg_p)
            dur   = float(dur)
            np_p  = row.get("np_w")
            np_p  = float(np_p) if (np_p is not None and not pd.isna(np_p)) else avg_p
            np_p  = max(np_p, avg_p)   # NP >= AP by definition

            for zone_name, secs in self._gaussian_zone_times(avg_p, np_p, dur).items():
                zone_seconds[zone_name] += secs

        total   = sum(zone_seconds.values())
        records = [
            {
                "zone":           name,
                "duration_hours": round(zone_seconds[name] / 3600, 2),
                "pct":            round(zone_seconds[name] / total * 100, 1) if total > 0 else 0.0,
            }
            for name, _, _ in self.zones
        ]
        return pd.DataFrame(records)

    def _gaussian_zone_times(
        self,
        avg_power: float,
        np_power:  float,
        duration_s: float,
    ) -> dict[str, float]:
        """
        Estimate time-in-zone using a Gaussian power distribution.

        For X ~ N(μ, σ²) the 4th raw moment is:
            E[X⁴] = μ⁴ + 6μ²σ² + 3σ⁴

        Setting E[X⁴] = NP⁴ and solving the quadratic in s = σ²:
            3s² + 6μ²s − (NP⁴ − μ⁴) = 0
            s = (−3μ² + √(6μ⁴ + 3·NP⁴)) / 3

        This gives σ that reflects ride variability:
          - Steady Z2 ride (NP ≈ AP, VI ≈ 1.02): small σ → nearly all time in one zone.
          - Interval session (NP >> AP, VI ≈ 1.20+): large σ → time spread across Z1–Z5+.

        Limitation: assumes unimodal distribution. True bimodal interval sessions
        (hard work + easy recovery) will have their spread slightly underestimated,
        but the result is far more accurate than assigning the full ride to one zone.
        """
        mu    = avg_power
        inner = 6.0 * mu**4 + 3.0 * np_power**4
        s     = (-3.0 * mu**2 + _msqrt(inner)) / 3.0
        sigma = _msqrt(max(0.0, s))

        def cdf(x: float) -> float:
            if sigma <= 0.0:
                return 1.0 if x >= mu else 0.0
            return 0.5 * (1.0 + erf((x - mu) / (sigma * _msqrt(2.0))))

        result: dict[str, float] = {}
        for zone_name, lo_frac, hi_frac in self.zones:
            hi_cdf = 1.0 if hi_frac >= 9.0 else cdf(hi_frac * self.ftp)
            result[zone_name] = duration_s * max(0.0, hi_cdf - cdf(lo_frac * self.ftp))
        return result

    # ------------------------------------------------------------------
    # Power curve (mean-maximal power)
    # ------------------------------------------------------------------

    def power_curve(
        self,
        power_streams: list[pd.Series],
        durations: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Compute the power curve (best mean-maximal power) across all streams.

        Parameters
        ----------
        power_streams : list of pd.Series, each containing second-by-second watts
        durations     : durations in seconds to evaluate (default: standard set)

        Returns
        -------
        DataFrame with [duration_s, duration_label, best_power_w, wkg (if weight given)]
        """
        if durations is None:
            durations = self._default_durations()

        best = {}
        for stream in power_streams:
            s = pd.Series(stream).dropna().values
            for d in durations:
                if len(s) >= d:
                    mmp = self._rolling_mean_max(s, d)
                    best[d] = max(best.get(d, 0), mmp)

        records = [
            {"duration_s": d, "duration_label": self._fmt_duration(d), "best_power_w": round(best.get(d, np.nan), 1)}
            for d in durations
        ]
        return pd.DataFrame(records)

    @staticmethod
    def _rolling_mean_max(arr: np.ndarray, window: int) -> float:
        """Efficient rolling mean using cumsum."""
        cs = np.cumsum(arr)
        return (cs[window - 1:] - np.concatenate([[0], cs[:-window]])).max() / window

    @staticmethod
    def _default_durations() -> list[int]:
        return [
            5, 10, 30, 60,                              # seconds
            120, 300, 360, 600,                         # 2–10 min
            720, 1200, 1800, 2400, 3600, 5400, 7200,    # 12 min – 2 hr
        ]

    @staticmethod
    def _fmt_duration(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}min"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h{m:02d}m" if m else f"{h}h"

    # ------------------------------------------------------------------
    # Intensity Factor
    # ------------------------------------------------------------------

    def intensity_factor(self, np_w: float) -> float:
        return round(np_w / self.ftp, 3)
