"""
bayesian_power.py
-----------------
Bayesian Dirichlet regression model for predicting time-in-zone fractions.

Extends PowerAnalyser from power.py.  Garmin rides supply ground-truth per-zone
times (power_z1..power_z7); the fitted model fills in Strava rides that have
only avg_power_w and np_w.

Model
-----
For ride i with zone-time fraction vector z_i = (z_i1,...,z_i7):

    z_i ~ Dirichlet(α_i)
    log(α_ik) = β₀k + β₁k·(AP_i/FTP) + β₂k·log(VI_i)

where:
    AP_i/FTP  = avg_power / ftp           (intensity fraction, ∈ [0,1])
    VI_i      = np / avg (clipped ≥ 1)    (variability index)
    log(VI_i) captures the spread of the power distribution

#| Note on the Gaussian fallback link:
#| Normalised power is defined as the 4th-root of the mean 4th power of
#| instantaneous power.  For X ~ N(μ, σ²) the 4th raw moment is
#|     E[X⁴] = μ⁴ + 6μ²σ² + 3σ⁴
#| so NP = (μ⁴ + 6μ²σ² + 3σ⁴)^(1/4).  The variability index VI = NP/AP
#| therefore encodes σ implicitly; log(VI) enters the Dirichlet regression
#| as a smooth proxy for the power-distribution spread, connecting the two
#| models through the same 4th-moment relationship exploited by the Gaussian
#| approximation in _gaussian_zone_times().

Priors: β₀k, β₁k, β₂k ~ Normal(0, 1)
"""

from __future__ import annotations

import datetime
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.processing.power import COGGAN_ZONES, PowerAnalyser

# ---------------------------------------------------------------------------
# Optional PyMC import — graceful degradation
# ---------------------------------------------------------------------------
try:
    import pymc as pm
    import pytensor.tensor as pt
    _PYMC_AVAILABLE = True
except ImportError:
    _PYMC_AVAILABLE = False


_GARMIN_ZONE_COLS = [f"power_z{i}" for i in range(1, 8)]
_ZONE_NAMES = [z[0] for z in COGGAN_ZONES]
_N_ZONES = len(_ZONE_NAMES)  # 7


class BayesianPowerAnalyser:
    """
    Dirichlet regression model for cycling zone-time fractions.

    Call fit() on a DataFrame of Garmin rides (which carry per-zone seconds),
    then use zone_distribution() to get a combined table for any activities
    DataFrame — Garmin rides use device data, Strava rides use the posterior.
    """

    def __init__(self, ftp: float, garmin_zone_cols: list[str] | None = None):
        self.ftp = ftp
        self._garmin_zone_cols = garmin_zone_cols or _GARMIN_ZONE_COLS

        # Posterior means (set after fit)
        self._beta0: np.ndarray | None = None  # shape [7]
        self._beta1: np.ndarray | None = None
        self._beta2: np.ndarray | None = None

        # Posterior samples for uncertainty (optional, set with store_trace=True)
        self._beta0_samples: np.ndarray | None = None  # shape [n_samples, 7]
        self._beta1_samples: np.ndarray | None = None
        self._beta2_samples: np.ndarray | None = None

        # Training metadata
        self._n_training_rides: int = 0
        self._feature_means: dict[str, float] = {}
        self._date_fitted: str | None = None

        # Internal PowerAnalyser for Gaussian fallback
        self._pa = PowerAnalyser(ftp=self.ftp)

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        return self._beta0 is not None

    @property
    def training_summary(self) -> dict:
        return {
            "n_rides": self._n_training_rides,
            "feature_means": self._feature_means,
            "date_fitted": self._date_fitted,
        }

    # -----------------------------------------------------------------------
    # Fitting
    # -----------------------------------------------------------------------

    def fit(
        self,
        activities_df: pd.DataFrame,
        draws: int = 1000,
        tune: int = 500,
        store_trace: bool = True,
        random_seed: int = 42,
    ) -> "BayesianPowerAnalyser":
        """
        Train on Garmin rides with known per-zone time data.

        Parameters
        ----------
        activities_df : DataFrame with columns avg_power_w, np_w,
                        power_z1..power_z7, type
        draws         : posterior draws per chain (NUTS)
        tune          : tuning steps
        store_trace   : if True, keep per-sample betas for uncertainty queries
        random_seed   : reproducibility
        """
        if not _PYMC_AVAILABLE:
            raise ImportError(
                "PyMC is required for fitting.  Install it with:\n"
                "    conda install -c conda-forge pymc\n"
                "or\n"
                "    pip install pymc"
            )

        df = self._filter_training_rows(activities_df)
        if len(df) < 5:
            raise ValueError(
                f"Only {len(df)} usable Garmin rides found — need at least 5 to fit."
            )

        intensity, log_vi = self._compute_features(df)
        zone_fracs = self._compute_zone_fracs(df)

        self._feature_means = {
            "intensity_mean": float(np.mean(intensity)),
            "log_vi_mean": float(np.mean(log_vi)),
        }
        self._n_training_rides = len(df)
        self._date_fitted = datetime.datetime.now().isoformat(timespec="seconds")

        # ---- Build PyMC model ------------------------------------------------
        with pm.Model() as model:
            # Priors — one coefficient per zone (7 zones × 3 betas)
            beta0 = pm.Normal("beta0", mu=0.0, sigma=1.0, shape=_N_ZONES)
            beta1 = pm.Normal("beta1", mu=0.0, sigma=1.0, shape=_N_ZONES)
            beta2 = pm.Normal("beta2", mu=0.0, sigma=1.0, shape=_N_ZONES)

            # log(α_ik) = β₀k + β₁k·intensity_i + β₂k·log_vi_i
            intensity_t = pt.as_tensor_variable(intensity[:, None])   # [N, 1]
            log_vi_t    = pt.as_tensor_variable(log_vi[:, None])      # [N, 1]

            log_alpha = beta0 + beta1 * intensity_t + beta2 * log_vi_t  # [N, 7]
            alpha = pm.math.exp(log_alpha)  # [N, 7]

            # Likelihood
            obs = pm.Dirichlet("obs", a=alpha, observed=zone_fracs)  # noqa: F841

            trace = pm.sample(
                draws=draws,
                tune=tune,
                target_accept=0.90,
                random_seed=random_seed,
                progressbar=True,
                return_inferencedata=True,
            )

        # ---- Extract posterior means -----------------------------------------
        post = trace.posterior
        self._beta0 = post["beta0"].values.reshape(-1, _N_ZONES).mean(axis=0)
        self._beta1 = post["beta1"].values.reshape(-1, _N_ZONES).mean(axis=0)
        self._beta2 = post["beta2"].values.reshape(-1, _N_ZONES).mean(axis=0)

        if store_trace:
            self._beta0_samples = post["beta0"].values.reshape(-1, _N_ZONES)
            self._beta1_samples = post["beta1"].values.reshape(-1, _N_ZONES)
            self._beta2_samples = post["beta2"].values.reshape(-1, _N_ZONES)

        return self

    # -----------------------------------------------------------------------
    # Prediction
    # -----------------------------------------------------------------------

    def predict_zone_fracs(self, avg_power: float, np_power: float) -> np.ndarray:
        """
        Posterior mean zone fractions for a single ride.

        Returns array of shape [7] summing to 1.
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted — call fit() first.")

        intensity = avg_power / self.ftp
        log_vi = np.log(max(np_power / avg_power, 1.0))

        log_alpha = self._beta0 + self._beta1 * intensity + self._beta2 * log_vi
        alpha = np.exp(log_alpha)
        return alpha / alpha.sum()

    def predict_zone_fracs_with_uncertainty(
        self, avg_power: float, np_power: float
    ) -> dict[str, np.ndarray]:
        """
        Posterior predictive distribution over zone fractions.

        Requires store_trace=True during fit().

        Returns dict with keys 'mean', 'hdi_3%', 'hdi_97%', each shape [7].
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted — call fit() first.")
        if self._beta0_samples is None:
            raise RuntimeError(
                "No posterior samples stored.  Refit with store_trace=True."
            )

        intensity = avg_power / self.ftp
        log_vi = np.log(max(np_power / avg_power, 1.0))

        # [n_samples, 7]
        log_alpha = (
            self._beta0_samples
            + self._beta1_samples * intensity
            + self._beta2_samples * log_vi
        )
        alpha = np.exp(log_alpha)
        fracs = alpha / alpha.sum(axis=1, keepdims=True)

        mean = fracs.mean(axis=0)
        lo = np.percentile(fracs, 3, axis=0)
        hi = np.percentile(fracs, 97, axis=0)

        return {"mean": mean, "hdi_3%": lo, "hdi_97%": hi}

    # -----------------------------------------------------------------------
    # Zone distribution (same interface as PowerAnalyser)
    # -----------------------------------------------------------------------

    def zone_distribution(self, activities_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute time-in-zone across activities.

        Per-ride method priority
        ------------------------
        1. Garmin power_z1..power_z7 — exact device-recorded zone seconds.
        2. Bayesian model — predicted fractions × duration, if model is fitted.
        3. Gaussian approximation (PowerAnalyser._gaussian_zone_times) — fallback.

        Returns DataFrame with columns [zone, duration_hours, pct].
        """
        has_garmin_cols = all(
            c in activities_df.columns for c in self._garmin_zone_cols
        )

        zone_seconds = {z[0]: 0.0 for z in COGGAN_ZONES}

        cycling = activities_df[
            activities_df["type"].str.contains(
                "cycling|ride|virtual", case=False, na=False
            )
        ]

        for _, row in cycling.iterrows():
            # -- Method 1: Garmin per-zone time --------------------------------
            if has_garmin_cols:
                z_raw = [row.get(c) for c in self._garmin_zone_cols]
                z_f = [float(v) for v in z_raw if v is not None and not pd.isna(v)]
                if z_f and any(v > 0 for v in z_f):
                    for i, zone_name in enumerate(_ZONE_NAMES):
                        v = z_raw[i]
                        if v is not None and not pd.isna(v):
                            zone_seconds[zone_name] += float(v)
                    continue

            # -- Common: extract avg_power and duration ------------------------
            avg_p = row.get("avg_power_w")
            dur = row.get("duration_s")
            if (
                avg_p is None
                or pd.isna(avg_p)
                or dur is None
                or pd.isna(dur)
                or float(dur) <= 0
            ):
                continue

            avg_p = float(avg_p)
            dur = float(dur)
            np_p = row.get("np_w")
            np_p = float(np_p) if (np_p is not None and not pd.isna(np_p)) else avg_p
            np_p = max(np_p, avg_p)

            # -- Method 2: Bayesian model --------------------------------------
            if self.is_fitted:
                fracs = self.predict_zone_fracs(avg_p, np_p)
                for i, zone_name in enumerate(_ZONE_NAMES):
                    zone_seconds[zone_name] += dur * float(fracs[i])
                continue

            # -- Method 3: Gaussian fallback -----------------------------------
            for zone_name, secs in self._pa._gaussian_zone_times(
                avg_p, np_p, dur
            ).items():
                zone_seconds[zone_name] += secs

        total = sum(zone_seconds.values())
        records = [
            {
                "zone": name,
                "duration_hours": round(zone_seconds[name] / 3600, 2),
                "pct": round(zone_seconds[name] / total * 100, 1) if total > 0 else 0.0,
            }
            for name, _, _ in COGGAN_ZONES
        ]
        return pd.DataFrame(records)

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Save posterior means and metadata to a .npz file."""
        if not self.is_fitted:
            raise RuntimeError("Nothing to save — model has not been fitted.")

        path = Path(path)
        arrays: dict[str, np.ndarray] = {
            "beta0_mean": self._beta0,
            "beta1_mean": self._beta1,
            "beta2_mean": self._beta2,
            "ftp": np.array([self.ftp]),
            "zone_names": np.array(_ZONE_NAMES),
            "n_training_rides": np.array([self._n_training_rides]),
            "feature_stats": np.array(
                [
                    self._feature_means.get("intensity_mean", np.nan),
                    self._feature_means.get("log_vi_mean", np.nan),
                ]
            ),
        }

        if self._beta0_samples is not None:
            arrays["beta0_samples"] = self._beta0_samples
            arrays["beta1_samples"] = self._beta1_samples
            arrays["beta2_samples"] = self._beta2_samples

        if self._date_fitted is not None:
            arrays["date_fitted"] = np.array([self._date_fitted])

        np.savez(path, **arrays)

    @classmethod
    def load(cls, path: str | Path, ftp: float) -> "BayesianPowerAnalyser":
        """Load a previously fitted model from a .npz file."""
        path = Path(path)
        data = np.load(path, allow_pickle=True)

        obj = cls(ftp=ftp)
        obj._beta0 = data["beta0_mean"]
        obj._beta1 = data["beta1_mean"]
        obj._beta2 = data["beta2_mean"]
        obj._n_training_rides = int(data["n_training_rides"][0])

        if "feature_stats" in data:
            stats = data["feature_stats"]
            obj._feature_means = {
                "intensity_mean": float(stats[0]),
                "log_vi_mean": float(stats[1]),
            }

        if "date_fitted" in data:
            obj._date_fitted = str(data["date_fitted"][0])

        if "beta0_samples" in data:
            obj._beta0_samples = data["beta0_samples"]
            obj._beta1_samples = data["beta1_samples"]
            obj._beta2_samples = data["beta2_samples"]

        return obj

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _filter_training_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return cycling rows that have avg_power_w and non-zero Garmin zone data."""
        is_cycling = df["type"].str.contains(
            "cycling|ride|virtual", case=False, na=False
        )
        has_power = df["avg_power_w"].notna()

        has_garmin_cols = all(c in df.columns for c in self._garmin_zone_cols)
        if not has_garmin_cols:
            raise ValueError(
                "DataFrame is missing Garmin zone columns "
                f"({self._garmin_zone_cols}).  Only Garmin rides can be used "
                "for training."
            )

        garmin_mask = df[self._garmin_zone_cols].apply(
            lambda row: any(
                v is not None and not pd.isna(v) and float(v) > 0
                for v in row
            ),
            axis=1,
        )

        return df[is_cycling & has_power & garmin_mask].copy()

    def _compute_features(
        self, df: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (intensity, log_vi) arrays, shape [N]."""
        avg_p = df["avg_power_w"].astype(float).values
        np_p = df["np_w"].copy()
        np_p = np_p.where(np_p.notna(), other=pd.Series(avg_p, index=df.index))
        np_p = np_p.astype(float).values
        np_p = np.maximum(np_p, avg_p)

        intensity = avg_p / self.ftp
        vi = np.maximum(np_p / avg_p, 1.0)
        log_vi = np.log(vi)

        return intensity.astype(np.float64), log_vi.astype(np.float64)

    def _compute_zone_fracs(self, df: pd.DataFrame) -> np.ndarray:
        """Return zone fraction matrix, shape [N, 7], from Garmin zone columns."""
        zone_raw = df[self._garmin_zone_cols].astype(float).values  # [N, 7]

        # Add small epsilon to avoid zero entries (Dirichlet requires > 0)
        zone_raw = zone_raw + 1e-6

        # Rows with any NaN get replaced by uniform
        nan_rows = np.isnan(zone_raw).any(axis=1)
        zone_raw[nan_rows] = np.ones(_N_ZONES)

        row_sums = zone_raw.sum(axis=1, keepdims=True)
        return (zone_raw / row_sums).astype(np.float64)


# ---------------------------------------------------------------------------
# __main__ — fit on real data, print summary, save model
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    _HERE = Path(__file__).resolve().parent
    _DATA_DIR = _HERE.parent.parent / "data" / "processed"
    _PARQUET = _DATA_DIR / "activities.parquet"
    _MODEL_OUT = _DATA_DIR / "bayesian_power_model.npz"

    if not _PARQUET.exists():
        print(f"ERROR: parquet not found at {_PARQUET}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading activities from {_PARQUET} …")
    acts = pd.read_parquet(_PARQUET)
    print(f"  Total rows: {len(acts)}")

    FTP = 333.0
    bpa = BayesianPowerAnalyser(ftp=FTP)

    print("Fitting Bayesian model …")
    try:
        bpa.fit(acts, draws=1000, tune=500, store_trace=True)
    except ValueError as e:
        print(f"ERROR during fit: {e}", file=sys.stderr)
        sys.exit(1)

    summary = bpa.training_summary
    print("\n--- Training summary ---")
    print(f"  Rides used : {summary['n_rides']}")
    print(f"  Date fitted: {summary['date_fitted']}")
    print(f"  Feature means: {summary['feature_means']}")

    print("\n--- Posterior means ---")
    print(f"  β₀: {np.round(bpa._beta0, 3)}")
    print(f"  β₁: {np.round(bpa._beta1, 3)}")
    print(f"  β₂: {np.round(bpa._beta2, 3)}")

    # Quick sanity check: predict for a threshold ride (AP=300, NP=315)
    example_fracs = bpa.predict_zone_fracs(avg_power=300.0, np_power=315.0)
    print("\n--- Example prediction (AP=300 W, NP=315 W, FTP=333 W) ---")
    for zone_name, frac in zip(_ZONE_NAMES, example_fracs):
        print(f"  {zone_name:<22}: {frac * 100:5.1f}%")

    bpa.save(_MODEL_OUT)
    print(f"\nModel saved to {_MODEL_OUT}")
