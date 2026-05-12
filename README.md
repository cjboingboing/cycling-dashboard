# Cycling Performance Dashboard

A personal cycling analytics dashboard built on Garmin Connect export data and the Strava API.
No black boxes — every metric and recommendation is computed from first principles with transparent, interpretable logic.

The statistical methods behind the zone estimation models are documented in [`zone_estimation.qmd`](zone_estimation.qmd), which can be rendered to a PDF using [Quarto](https://quarto.org).

## Features

- **Performance Management Chart** — CTL, ATL, TSB computed from scratch using Coggan/Banister EWMA model
- **Power Zone Analysis** — time-in-zone with a three-tier estimation pipeline:
  1. Garmin device per-zone data (exact, from raw power stream)
  2. Bayesian Dirichlet regression (learned from Garmin ground-truth, predicts for Strava rides)
  3. Gaussian moment-matching fallback (analytic, zero training data required)
- **Power Curve** — mean-maximal power across all durations from 5 s to 2 h
- **Recovery Tracking** — HRV trend, sleep, Garmin Body Battery, composite recovery score
- **Session Recommendations** — rule-based engine driven by TSB, HRV, sleep, training phase, and polarised intensity audit
- **Training Phase Detection** — base / build / peak / taper inferred from CTL trajectory with hysteresis
- **Polarised Training Audit** — flags grey-zone (Z3–Z4) accumulation against Seiler's 80:20 target
- **Strava Sync** — incremental refresh button in the sidebar; fetches only new activities

## Stack

- **Python 3.11+**
- `pandas` / `numpy` — all processing
- `scikit-learn` — TSS and recovery score ML estimators
- `pymc` — Bayesian Dirichlet regression (optional; graceful fallback if not installed)
- `stravalib` — Strava API client
- `garth` — Garmin SSO auth (for live API; not needed for bulk export)
- `streamlit` + `plotly` — dashboard UI

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/cycling-dashboard.git
cd cycling-dashboard
pip install -r requirements.txt
```

> **PyMC is optional.** If you skip it, the Bayesian zone model is disabled and the
> Gaussian moment-matching fallback is used automatically — no code changes needed.

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your credentials
```

#### Strava

1. Create an app at <https://www.strava.com/settings/api>
2. Set `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in `.env`
3. Run the one-time OAuth flow to get a refresh token:

```python
from src.ingestion.strava import StravaClient
StravaClient.exchange_code_for_token(client_id="...", client_secret="...", code="...")
```

4. Add the resulting `STRAVA_REFRESH_TOKEN` to `.env`

#### Garmin (bulk export — recommended)

1. Go to Garmin Connect → Account Settings → Data Management → Export Your Data
2. Request and download the GDPR export ZIP
3. Extract into `data/raw/garmin/`

No credentials needed for the bulk export path. The `GARMIN_EMAIL` / `GARMIN_PASSWORD`
fields are only required if you want live Garmin API access via `garth`.

### 3. Build the dataset

```bash
jupyter notebook notebooks/01_build_dataset.ipynb
```

This ingests Garmin and Strava data, merges and deduplicates, fills missing TSS via the
ML estimator, computes PMC and recovery metrics, and writes four parquet files to
`data/processed/`.

### 4. Run the dashboard

```bash
streamlit run src/dashboard/app.py
```

Use the **Refresh from Strava** button in the sidebar to pull new activities incrementally.

## Project Structure

```
cycling-dashboard/
├── data/
│   ├── raw/
│   │   ├── garmin/DI_CONNECT/   ← Garmin GDPR export (not committed)
│   │   └── strava/              ← cached Strava API responses (not committed)
│   └── processed/               ← parquet files output by notebook (not committed)
├── src/
│   ├── ingestion/
│   │   ├── garmin.py            ← parse Garmin bulk export JSON
│   │   └── strava.py            ← Strava OAuth2 API client + incremental sync
│   ├── processing/
│   │   ├── pmc.py               ← CTL/ATL/TSB (Coggan/Banister EWMA)
│   │   ├── power.py             ← Coggan zones, Gaussian zone distribution, power curve
│   │   ├── bayesian_power.py    ← Bayesian Dirichlet regression zone model (PyMC)
│   │   └── recovery.py          ← HRV signals, composite recovery score
│   ├── recommender/
│   │   ├── rules.py             ← recommendation engine (TSB, HRV, phase, polarisation)
│   │   ├── phase_detector.py    ← training phase inference from PMC history
│   │   └── workout_library.py   ← 14 structured workout definitions
│   ├── ml/
│   │   ├── tss_estimator.py     ← fills missing TSS via Random Forest
│   │   ├── train.py             ← retrains TSS model
│   │   ├── recovery_estimator.py← fills missing recovery score
│   │   └── train_recovery.py    ← retrains recovery model
│   └── dashboard/
│       ├── app.py               ← Streamlit entry point
│       └── plots.py             ← Plotly chart functions
├── notebooks/
│   └── 01_build_dataset.ipynb  ← ingestion → processing → save parquets
├── tests/
├── zone_estimation.qmd          ← Quarto source for the methodology paper
├── references.bib               ← bibliography for the paper
├── refresh.py                   ← CLI script for incremental Strava sync
├── .env.example                 ← credential template (copy to .env)
└── requirements.txt
```

## Methodology

The zone estimation models are described in detail in [`zone_estimation.qmd`](zone_estimation.qmd).
Render it to PDF with:

```bash
quarto render zone_estimation.qmd
```

Topics covered:
- Performance Management Chart (Banister impulse-response model)
- Coggan 7-zone power model
- Normalised power as an L⁴ norm
- Gaussian moment-matching for zone distribution estimation
- Bayesian Dirichlet regression with PyMC
- Seiler's polarised training model and the grey-zone audit

## Science Foundation

| Concept | Reference |
|---|---|
| Impulse-response model (CTL/ATL/TSB) | Banister (1975); Coggan & Allen (2010) |
| 7-zone power model | Coggan & Allen (2010) |
| Polarised training distribution | Seiler & Kjerland (2006) |
| Polarised vs threshold RCT | Stöggl & Sperlich (2014) |
| VO₂max interval duration | Billat (2001) |
| Bayesian inference | Gelman et al. (2013) |

## License

MIT — see [LICENSE](LICENSE).
