"""
app.py
------
Streamlit dashboard entry point.

Run with:
    streamlit run src/dashboard/app.py

Expects:
    data/processed/activities.parquet
    data/processed/wellness.parquet
    data/processed/pmc.parquet
    data/processed/recovery.parquet
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.dashboard.plots import (
    plot_hrv_trend,
    plot_pmc,
    plot_power_curve,
    plot_weekly_tss,
    plot_zone_distribution,
)
from src.recommender.rules import recommend

load_dotenv()
FTP = int(os.getenv("FTP", 300))

st.set_page_config(
    page_title="CyclingOS",
    page_icon="⚡",
    layout="wide",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Base ── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"],
.main .block-container {
    background-color: #09090f !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
[data-testid="stHeader"] {
    background-color: #09090f !important;
    border-bottom: 1px solid #16162a;
}
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1440px !important;
}
p, li, .stMarkdown {
    color: #c8c8e0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #111120 !important;
    border: 1px solid #1e1e38 !important;
    border-radius: 14px !important;
    padding: 1.4rem 1.6rem !important;
    transition: border-color 0.18s ease;
}
[data-testid="metric-container"]:hover {
    border-color: #e8541a !important;
}
[data-testid="stMetricLabel"] div {
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.14em !important;
    color: #50507a !important;
}
[data-testid="stMetricValue"] div {
    color: #ffffff !important;
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    font-variant-numeric: tabular-nums !important;
    letter-spacing: -0.03em !important;
    line-height: 1.1 !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #111120 !important;
    border: 1px solid #1e1e38 !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary {
    color: #707090 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}

/* ── Alert boxes ── */
[data-testid="stAlert"] {
    background: #111120 !important;
    border: 1px solid #1e1e38 !important;
    border-radius: 10px !important;
    color: #c8c8e0 !important;
}

/* ── Divider ── */
hr {
    border-color: #16162a !important;
    margin: 1.75rem 0 !important;
}

/* ── Caption ── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #50507a !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.05em;
}

/* ─────── Custom components ─────── */

.dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #16162a;
    margin-bottom: 2rem;
}
.dash-wordmark {
    font-size: 1.5rem;
    font-weight: 900;
    letter-spacing: -0.05em;
    color: #ffffff;
    text-transform: uppercase;
    line-height: 1;
}
.dash-wordmark span { color: #e8541a; }
.dash-tagline {
    font-size: 0.65rem;
    color: #383858;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin-top: 0.3rem;
}
.dash-date {
    font-size: 0.72rem;
    color: #383858;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: right;
}

.section-label {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin: 2.25rem 0 1rem;
    font-size: 0.65rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #e8541a;
    width: 100%;
}
.section-label::before {
    content: '';
    display: block;
    width: 16px;
    height: 2px;
    background: #e8541a;
    border-radius: 1px;
    flex-shrink: 0;
}
.section-label::after {
    content: '';
    display: block;
    flex: 1;
    height: 1px;
    background: #16162a;
}

.rec-block {
    background: #111120;
    border: 1px solid #1e1e38;
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin: 0.75rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 1.25rem;
}
.rec-pip {
    width: 6px;
    height: 52px;
    border-radius: 3px;
    flex-shrink: 0;
}
.rec-session {
    font-size: 1.35rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.rec-meta {
    font-size: 0.68rem;
    color: #50507a;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-top: 0.3rem;
}
.readiness-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-left: 0.6rem;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)


# ─── Data loading ─────────────────────────────────────────────────────────────

REFRESH_SCRIPT = Path(__file__).parent.parent.parent / "refresh.py"

@st.cache_data
def load_data():
    processed = Path(__file__).parent.parent.parent / "data" / "processed"
    return {
        "activities": pd.read_parquet(processed / "activities.parquet"),
        "wellness":   pd.read_parquet(processed / "wellness.parquet"),
        "pmc":        pd.read_parquet(processed / "pmc.parquet"),
        "recovery":   pd.read_parquet(processed / "recovery.parquet"),
    }


# ─── Strava refresh ───────────────────────────────────────────────────────────
# Only shown when Strava credentials are present in the environment.
# On the public demo deployment the parquet files are a static snapshot.

_strava_configured = bool(os.getenv("STRAVA_CLIENT_SECRET"))

with st.sidebar:
    if _strava_configured:
        st.markdown("### Strava Sync")
        if st.button("Refresh from Strava", use_container_width=True):
            with st.spinner("Syncing from Strava…"):
                result = subprocess.run(
                    [sys.executable, str(REFRESH_SCRIPT)],
                    capture_output=True,
                    text=True,
                    cwd=str(REFRESH_SCRIPT.parent),
                )
            if result.returncode == 0:
                st.success("Done!")
                st.text(result.stdout)
                load_data.clear()
                st.rerun()
            else:
                st.error("Refresh failed")
                st.text(result.stdout)
                st.text(result.stderr)
    else:
        st.caption("📊 Demo — sample data snapshot")


# ─── Header ───────────────────────────────────────────────────────────────────

from datetime import date
today_str = date.today().strftime("%d %b %Y").upper()

st.markdown(f"""
<div class="dash-header">
    <div>
        <div class="dash-wordmark">Cycling<span>OS</span></div>
        <div class="dash-tagline">Performance Intelligence</div>
    </div>
    <div class="dash-date">{today_str}</div>
</div>
""", unsafe_allow_html=True)

try:
    data = load_data()
except FileNotFoundError:
    st.error(
        "Processed data not found. Run `notebooks/01_build_dataset.ipynb` first "
        "to ingest and process your Garmin / Strava data."
    )
    st.stop()

recovery_df = data["recovery"]
today_row   = recovery_df.iloc[-1]


# ─── Readiness panel ──────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Today\'s Readiness</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Recovery Score",  f"{today_row.get('recovery_score', 0):.0f} / 100")
col2.metric("TSB — Form",      f"{today_row.get('tsb', 0):.1f}")
col3.metric("CTL — Fitness",   f"{today_row.get('ctl', 0):.1f}")
col4.metric("ATL — Fatigue",   f"{today_row.get('atl', 0):.1f}")

rec = recommend(
    tsb            = today_row.get("tsb"),
    hrv_deviation  = today_row.get("hrv_deviation"),
    sleep_hours    = today_row.get("sleep_hours"),
    recovery_score = today_row.get("recovery_score"),
    pmc_df         = data["pmc"],
    activities_df  = data["activities"],
    ftp            = FTP,
)

readiness = today_row.get("readiness_flag", "unknown")

# ── Phase badge ────────────────────────────────────────────────────────────────
_phase_color = {"base": "#3b82f6", "build": "#f59e0b", "peak": "#a855f7", "taper": "#22c55e"}
_phase_label = {"base": "BASE", "build": "BUILD", "peak": "PEAK", "taper": "TAPER"}
ph_color = _phase_color.get(rec.phase, "#50507a")
ph_label = _phase_label.get(rec.phase, rec.phase.upper())

st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.75rem;margin:1rem 0 0.75rem;">
    <span style="background:{ph_color}22;color:{ph_color};border:1px solid {ph_color}55;
                 border-radius:999px;padding:0.25rem 0.75rem;font-size:0.57rem;
                 font-weight:800;letter-spacing:0.16em;white-space:nowrap;">
        {ph_label} PHASE
    </span>
    <span style="color:#707090;font-size:0.70rem;line-height:1.4;">
        {rec.phase_explanation}
    </span>
</div>
""", unsafe_allow_html=True)

# ── Readiness recommendation block ─────────────────────────────────────────────
pip_color = {
    "go":      "#22c55e",
    "normal":  "#f59e0b",
    "easy":    "#f97316",
    "rest":    "#ef4444",
    "unknown": "#383858",
}.get(readiness, "#383858")

badge_bg = {
    "go":      "rgba(34,197,94,0.15)",
    "normal":  "rgba(245,158,11,0.15)",
    "easy":    "rgba(249,115,22,0.15)",
    "rest":    "rgba(239,68,68,0.15)",
    "unknown": "rgba(56,56,88,0.3)",
}.get(readiness, "rgba(56,56,88,0.3)")

tss_meta = f"Target TSS &nbsp;·&nbsp; ~{rec.tss_target}" if rec.tss_target is not None else "No TSS target"

st.markdown(f"""
<div class="rec-block">
    <div class="rec-pip" style="background:{pip_color};"></div>
    <div>
        <div class="rec-session">{rec.session_type}
            <span class="readiness-badge" style="background:{badge_bg};color:{pip_color};">{readiness}</span>
        </div>
        <div class="rec-meta">{tss_meta}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Workout options cards ──────────────────────────────────────────────────────
if rec.workout_options:
    st.markdown('<div class="section-label">Workout Options</div>', unsafe_allow_html=True)
    _int_color  = {"low": "#3b82f6", "moderate": "#f59e0b", "high": "#ef4444"}
    _rank_label = ["#1 Pick", "#2 Option", "#3 Option"]
    opt_cols    = st.columns(len(rec.workout_options))

    for i, (col, w) in enumerate(zip(opt_cols, rec.workout_options)):
        with col:
            border    = "#e8541a" if i == 0 else "#1e1e38"
            ic        = _int_color.get(w.intensity, "#50507a")
            zones_str = " · ".join(z.split(" ", 1)[-1] for z in w.zone_focus[:2])
            desc_short = w.description[:110].rsplit(" ", 1)[0] + "…"
            st.markdown(f"""
<div style="background:#111120;border:1px solid {border};border-radius:14px;
            padding:1.1rem 1.25rem;height:100%;">
    <div style="font-size:0.52rem;font-weight:800;text-transform:uppercase;
                letter-spacing:0.16em;color:#50507a;margin-bottom:0.35rem;">
        {_rank_label[i]}
    </div>
    <div style="font-size:0.98rem;font-weight:800;color:#fff;line-height:1.2;
                margin-bottom:0.2rem;">{w.name}</div>
    <div style="font-size:0.60rem;color:#707090;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:0.55rem;">{zones_str}</div>
    <div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.6rem;">
        <span style="background:#1e1e38;color:#c8c8e0;border-radius:5px;
                     padding:0.12rem 0.45rem;font-size:0.58rem;white-space:nowrap;">
            TSS {w.tss_min}–{w.tss_max}
        </span>
        <span style="background:#1e1e38;color:#c8c8e0;border-radius:5px;
                     padding:0.12rem 0.45rem;font-size:0.58rem;white-space:nowrap;">
            {w.duration_min_h:.1f}–{w.duration_max_h:.1f}h
        </span>
        <span style="background:{ic}22;color:{ic};border-radius:5px;
                     padding:0.12rem 0.45rem;font-size:0.58rem;font-weight:700;">
            {w.intensity.upper()}
        </span>
    </div>
    <div style="font-size:0.63rem;color:#50507a;line-height:1.45;">
        {desc_short}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Polarised audit + weekly TSS ───────────────────────────────────────────────
_has_audit = bool(rec.polarised_audit)
_has_tss   = rec.weekly_tss_target is not None and rec.weekly_tss_actual is not None

if _has_audit or _has_tss:
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    audit_col, tss_col = st.columns(2)

    with audit_col:
        if _has_audit:
            a         = rec.polarised_audit
            z12_pct   = a.get("z12_pct", 0)
            z34_pct   = a.get("z34_pct", 0)
            z5p_pct   = a.get("z5plus_pct", 0)
            grey_flag = a.get("grey_zone_flag", False)
            grey_c    = "#ef4444" if grey_flag else "#22c55e"
            grey_icon = "⚠" if grey_flag else "✓"
            audit_note = (
                f"<div style='margin-top:0.65rem;font-size:0.60rem;color:#ef4444;"
                f"line-height:1.4;'>{a['recommendation']}</div>"
                if a.get("recommendation") else ""
            )
            st.markdown(f"""
<div style="background:#111120;border:1px solid #1e1e38;border-radius:14px;padding:1.1rem 1.3rem;">
    <div style="font-size:0.55rem;font-weight:800;text-transform:uppercase;
                letter-spacing:0.14em;color:#50507a;margin-bottom:0.75rem;">
        Polarised Audit — last 4 weeks
    </div>
    <div style="display:flex;flex-direction:column;gap:0.45rem;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="color:#3b82f6;font-size:0.68rem;font-weight:600;">Z1/Z2 Easy</span>
            <span style="color:#fff;font-size:0.88rem;font-weight:800;">
                {z12_pct:.0f}%
                <span style="color:#383858;font-size:0.55rem;"> / 80% target</span>
            </span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="color:{grey_c};font-size:0.68rem;font-weight:600;">{grey_icon} Z3–Z4 Grey</span>
            <span style="color:#fff;font-size:0.88rem;font-weight:800;">
                {z34_pct:.0f}%
                <span style="color:#383858;font-size:0.55rem;"> / &lt;10% target</span>
            </span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="color:#a855f7;font-size:0.68rem;font-weight:600;">Z5+ Hard</span>
            <span style="color:#fff;font-size:0.88rem;font-weight:800;">
                {z5p_pct:.0f}%
                <span style="color:#383858;font-size:0.55rem;"> / 15–20% target</span>
            </span>
        </div>
    </div>
    {audit_note}
</div>
""", unsafe_allow_html=True)

    with tss_col:
        if _has_tss:
            actual   = rec.weekly_tss_actual
            target   = rec.weekly_tss_target
            pct_done = int(actual / target * 100) if target > 0 else 0
            bar_w    = min(100, pct_done)
            bar_c    = "#22c55e" if actual >= target else "#e8541a"
            ph_full  = {"base": "Base", "build": "Build", "peak": "Peak", "taper": "Taper"}.get(rec.phase, "")
            st.markdown(f"""
<div style="background:#111120;border:1px solid #1e1e38;border-radius:14px;padding:1.1rem 1.3rem;">
    <div style="font-size:0.55rem;font-weight:800;text-transform:uppercase;
                letter-spacing:0.14em;color:#50507a;margin-bottom:0.75rem;">
        Weekly TSS — {ph_full} target
    </div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;
                margin-bottom:0.55rem;">
        <span style="color:#fff;font-size:2.0rem;font-weight:800;line-height:1;">{actual}</span>
        <span style="color:#50507a;font-size:0.68rem;">/ {target} target</span>
    </div>
    <div style="background:#1e1e38;border-radius:4px;height:5px;overflow:hidden;
                margin-bottom:0.4rem;">
        <div style="background:{bar_c};height:100%;width:{bar_w}%;border-radius:4px;"></div>
    </div>
    <div style="color:#707090;font-size:0.60rem;">{pct_done}% of weekly target</div>
</div>
""", unsafe_allow_html=True)

# ── Expander: rationale ────────────────────────────────────────────────────────
with st.expander("Why this recommendation?"):
    if rec.phase_explanation:
        st.markdown(f"**Training phase:** {rec.phase_explanation}")
    for reason in rec.rationale:
        st.markdown(f"- {reason}")
    if rec.flags:
        st.warning("⚠️ " + " | ".join(rec.flags))
    if rec.polarised_audit.get("grey_zone_flag"):
        st.info(
            "Polarised audit: grey-zone (Z3–Z4) time is above 15%. "
            "Try pushing easy rides firmly into Z2 and hard sessions into Z5+. "
            "Stöggl & Sperlich (2014) showed polarised distribution produces "
            "larger VO2max gains than a threshold-heavy approach."
        )

st.divider()


# ─── Weekly plan ──────────────────────────────────────────────────────────────

from datetime import date as _date
from src.recommender.weekly_planner import plan_week

st.markdown('<div class="section-label">Weekly Training Plan</div>', unsafe_allow_html=True)
st.caption("Wed = group ride  ·  Sat = long ride  ·  other days filled by recommender")

_garmin_configured = bool(os.getenv("GARMIN_EMAIL")) and bool(os.getenv("GARMIN_PASSWORD"))

try:
    from src.ingestion.garmin_push import push_workout as _push_workout, is_available as _garmin_push_ok
    _push_available = _garmin_push_ok() and _garmin_configured
except Exception:
    _push_available = False

week = plan_week(
    pmc_df         = data["pmc"],
    activities_df  = data["activities"],
    ftp            = FTP,
    tsb            = today_row.get("tsb"),
    hrv_deviation  = today_row.get("hrv_deviation"),
    sleep_hours    = today_row.get("sleep_hours"),
    recovery_score = today_row.get("recovery_score"),
)

_intensity_dot = {"low": "#22c55e", "moderate": "#f59e0b", "high": "#f45b3b", "none": "#6b7280"}
_day_cols = st.columns(7)

for col, day in zip(_day_cols, week):
    is_today = day.date == _date.today()
    border   = "#e8541a" if is_today else ("#3b82f6" if day.is_fixed else "#1e1e38")
    dot_c    = _intensity_dot.get(day.intensity, "#6b7280")
    label    = f"<b>{day.fixed_label}</b>" if day.is_fixed else (day.workout.name if day.workout else "Rest")
    tss_str  = f"~{day.tss_target} TSS"
    dur_str  = (
        f"{day.workout.duration_min_h:.1f}–{day.workout.duration_max_h:.1f}h"
        if day.workout else ""
    )
    lock_icon = " \U0001f512" if day.is_fixed else ""

    with col:
        st.markdown(f"""
<div style="background:#111120;border:1px solid {border};border-radius:12px;
            padding:0.75rem 0.65rem;min-height:140px;">
  <div style="color:#707090;font-size:0.65rem;font-weight:700;letter-spacing:0.08em;
              margin-bottom:0.2rem;">{day.day_name.upper()}&nbsp;{day.date.day} {day.date.strftime("%b")}{lock_icon}</div>
  <div style="display:flex;align-items:center;gap:0.3rem;margin-bottom:0.4rem;">
    <div style="width:7px;height:7px;border-radius:50%;background:{dot_c};flex-shrink:0;"></div>
    <div style="color:#e8e8f0;font-size:0.73rem;font-weight:600;line-height:1.2;">{label}</div>
  </div>
  <div style="color:#50507a;font-size:0.62rem;">{tss_str}</div>
  <div style="color:#50507a;font-size:0.62rem;">{dur_str}</div>
</div>
""", unsafe_allow_html=True)

        # Push to Garmin button
        if _push_available and day.workout and day.workout.steps:
            if st.button("Send to Garmin", key=f"push_{day.date}", use_container_width=True):
                with st.spinner("Pushing to Garmin Connect..."):
                    try:
                        wid = _push_workout(day.workout, FTP, schedule_date=day.date)
                        st.success(f"Scheduled! ID {wid}")
                    except Exception as e:
                        st.error(str(e))

# Step breakdown expander
with st.expander("Workout step details"):
    step_cols = st.columns(7)
    for col, day in zip(step_cols, week):
        with col:
            st.markdown(f"**{day.day_name}**")
            if day.workout and day.workout.steps:
                for s in day.workout.steps:
                    dur = f"{s.duration_s // 60}min" if s.duration_s else "open"
                    pwr = (
                        f"{int(s.power_target_low * 100)}-{int(s.power_target_high * 100)}%"
                        if s.power_target_low else ""
                    )
                    rpt = f" x{s.repeat_count}" if s.repeat_count > 1 else ""
                    st.markdown(
                        f"<div style='font-size:0.65rem;color:#9090b8;margin-bottom:2px;'>"
                        f"{s.name}{rpt} &middot; {dur} {pwr}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("<div style='font-size:0.65rem;color:#50507a;'>No steps defined</div>",
                            unsafe_allow_html=True)

st.divider()


# ─── Recent rides ─────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Recent Rides</div>', unsafe_allow_html=True)

def _fmt_duration(seconds):
    if pd.isna(seconds):
        return "—"
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"

n_rides = st.slider("Rides to show", 5, 30, 10, label_visibility="collapsed")

rides = (
    data["activities"]
    .sort_values("date", ascending=False)
    .head(n_rides)
    .copy()
)

rides["Duration"]   = rides["duration_s"].apply(_fmt_duration)
rides["Dist (km)"]  = (rides["distance_m"] / 1000).round(1)
rides["Elev (m)"]   = rides["elevation_m"].round(0).fillna(0).astype(int)
rides["NP (W)"]     = rides["np_w"].fillna(rides["avg_power_w"]).round(0)
rides["TSS"]        = rides["tss"].round(0)
rides["Date"]       = rides["date"].apply(lambda d: d.strftime("%d %b").lstrip("0"))
rides["Ride"]       = rides["name"].fillna("Untitled")

display_cols = ["Date", "Ride", "Dist (km)", "Duration", "Elev (m)", "NP (W)", "TSS"]

st.dataframe(
    rides[display_cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Date":      st.column_config.TextColumn("Date",      width="small"),
        "Ride":      st.column_config.TextColumn("Ride",      width="large"),
        "Dist (km)": st.column_config.NumberColumn("Dist (km)", format="%.1f km", width="small"),
        "Duration":  st.column_config.TextColumn("Duration",  width="small"),
        "Elev (m)":  st.column_config.NumberColumn("Elev (m)", format="%d m",    width="small"),
        "NP (W)":    st.column_config.NumberColumn("NP (W)",   format="%d W",    width="small"),
        "TSS":       st.column_config.ProgressColumn("TSS", min_value=0, max_value=300, format="%d", width="medium"),
    },
)

st.divider()


# ─── PMC chart ────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Performance Management Chart</div>', unsafe_allow_html=True)
weeks = st.slider("Weeks", 8, 52, 16, label_visibility="collapsed")
st.caption(f"Showing last {weeks} weeks  ·  CTL, ATL & TSB")
pmc_slice = data["pmc"].tail(weeks * 7)
st.plotly_chart(plot_pmc(pmc_slice), use_container_width=True)

st.divider()


# ─── Weekly TSS ───────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Weekly Training Load</div>', unsafe_allow_html=True)
st.plotly_chart(plot_weekly_tss(data["pmc"]), use_container_width=True)

st.divider()


# ─── Power analysis ───────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Power Analysis</div>', unsafe_allow_html=True)
pcol1, pcol2 = st.columns(2)

with pcol1:
    st.caption("Zone Distribution — last 6 weeks")
    from src.processing.power import PowerAnalyser
    pa            = PowerAnalyser(ftp=FTP)
    six_weeks_ago = pd.Timestamp.now() - pd.Timedelta(weeks=6)
    recent        = data["activities"][data["activities"]["date"] >= six_weeks_ago]
    zones         = pa.zone_distribution(recent)
    st.plotly_chart(plot_zone_distribution(zones), use_container_width=True)

with pcol2:
    st.caption("Power Curve — mean-maximal")
    if "power_curve" in data:
        st.plotly_chart(plot_power_curve(data["power_curve"], ftp=FTP), use_container_width=True)
    else:
        st.info("Power curve not available — fetch activity streams from Strava to enable this.")

st.divider()


# ─── HRV trend ────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">HRV & Recovery Trend</div>', unsafe_allow_html=True)

if "hrv_rmssd" in recovery_df.columns and recovery_df["hrv_rmssd"].notna().any():
    hrv_weeks = st.slider("HRV weeks", 4, 24, 8, key="hrv_slider", label_visibility="collapsed")
    st.caption(f"Showing last {hrv_weeks} weeks")
    hrv_slice = recovery_df.tail(hrv_weeks * 7)
    st.plotly_chart(plot_hrv_trend(hrv_slice), use_container_width=True)
else:
    st.info("No HRV data found. Export wellness data from Garmin Connect to enable this.")
