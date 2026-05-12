# Metrics Reference Guide

A plain-English explanation of every metric used in the cycling dashboard.

---

## Training Load Metrics (PMC)

The Performance Management Chart (PMC) is the backbone of the dashboard. It tracks
three related metrics — CTL, ATL, and TSB — all derived from your daily TSS.

### TSS — Training Stress Score
**Range:** 0–300+ per session  
**What it is:** A single number that quantifies how hard a training session was,
accounting for both intensity and duration.  
**How it's calculated:**
```
TSS = (duration_s × NP × IF) / (FTP × 3600) × 100
```
Where:
- `NP` = Normalised Power (weighted average power, accounts for variability)
- `IF` = Intensity Factor = NP / FTP
- `FTP` = Functional Threshold Power (the power you can hold for ~1 hour)

**Rule of thumb:**
| TSS | Effort |
|-----|--------|
| < 50 | Easy recovery ride |
| 50–100 | Moderate training day |
| 100–150 | Hard day |
| 150–250 | Very hard / long ride |
| 250+ | Extreme (e.g. gran fondo, race day) |

**Recovery time:** ~1 day per 100 TSS as a rough guide.

---

### CTL — Chronic Training Load (Fitness)
**Range:** 0–150+ for trained cyclists  
**Time constant:** 42 days  
**What it is:** A rolling exponentially weighted average of your daily TSS over
the past ~6 weeks. Think of it as your current fitness level — it takes weeks
to build and weeks to lose.  
**How it's calculated:** EWMA with decay α = 1 - exp(-1/42)  
**Interpretation:**
| CTL | Level |
|-----|-------|
| < 30 | Recreational |
| 30–60 | Trained amateur |
| 60–90 | Competitive amateur |
| 90–120 | Serious racer |
| 120+ | Elite / full-time athlete |

CTL rises slowly with consistent training and falls slowly during rest.
A drop of ~1 CTL point per day during complete rest is typical.

---

### ATL — Acute Training Load (Fatigue)
**Range:** Mirrors daily TSS, responds quickly  
**Time constant:** 7 days  
**What it is:** A rolling exponentially weighted average of your daily TSS over
the past ~1 week. Think of it as your current fatigue level — it responds
quickly to hard training and drops quickly with rest.  
**How it's calculated:** EWMA with decay α = 1 - exp(-1/7)  
**Interpretation:** ATL spikes after hard days and drops rapidly with rest.
A high ATL relative to CTL means you are currently fatigued.

---

### TSB — Training Stress Balance (Form)
**Formula:** TSB = CTL - ATL  
**What it is:** The difference between your fitness and your fatigue.
Positive TSB means you are fresh (rested); negative TSB means you are fatigued.
Also called "form" in TrainingPeaks terminology.

**Interpretation:**
| TSB | State |
|-----|-------|
| > +10 | Very fresh — peak performance possible |
| 0 to +10 | Fresh — good form |
| -10 to 0 | Neutral — normal training state |
| -10 to -30 | Fatigued — in a training block |
| < -30 | Very fatigued — risk of overtraining |

**Key insight:** You cannot have high fitness (CTL) AND be fresh (positive TSB)
at the same time during heavy training. The goal of a taper is to let ATL drop
(fatigue clears) while CTL stays high (fitness retained), pushing TSB positive
just before a target event.

---

### NP — Normalised Power
**Units:** Watts  
**What it is:** A weighted average power that accounts for the physiological
cost of variable effort. Riding at variable power (surges, hills, sprints) is
more taxing than steady power at the same average — NP captures this.  
**How it's calculated:** 30-second rolling average of power raised to the 4th
power, averaged, then taken to the 1/4 power.  
**Why it matters:** NP is used instead of average power for TSS calculation
because it better reflects actual physiological stress.

---

### IF — Intensity Factor
**Formula:** IF = NP / FTP  
**Range:** 0.5 (very easy) to 1.05+ (all-out effort)  
**What it is:** How hard a session was relative to your threshold.
An IF of 1.0 means you rode at exactly FTP for the whole session.

| IF | Zone |
|----|------|
| < 0.75 | Easy endurance (Z1-Z2) |
| 0.75–0.85 | Tempo (Z3) |
| 0.85–0.95 | Sweet spot / threshold (Z3-Z4) |
| 0.95–1.05 | Threshold (Z4) |
| > 1.05 | Above threshold (only possible for short durations) |

---

### FTP — Functional Threshold Power
**Units:** Watts  
**What it is:** The highest average power you can sustain for approximately
60 minutes. It is the reference point for all power-based training zones
and metrics.  
**How to test:** 20-minute all-out effort × 0.95, or a dedicated ramp test.  
**Note:** FTP is set in your `.env` file and used across all calculations.
Update it whenever you retest.

---

## Power Zones (Coggan 7-Zone Model)

All zones are expressed as a percentage of FTP.

| Zone | Name | % FTP | Feel |
|------|------|-------|------|
| Z1 | Active Recovery | < 55% | Trivially easy, conversational |
| Z2 | Endurance | 55–75% | Comfortable, could ride all day |
| Z3 | Tempo | 75–90% | Moderately hard, breathing elevated |
| Z4 | Threshold | 90–105% | Hard, sustainable for ~1 hour |
| Z5 | VO2max | 105–120% | Very hard, 3–8 minute efforts |
| Z6 | Anaerobic | 120–150% | Extremely hard, < 3 minutes |
| Z7 | Neuromuscular | > 150% | Maximum sprint, seconds only |

**Polarised training** targets most volume in Z1-Z2 with hard sessions in Z5+,
avoiding the "grey zone" of Z3-Z4 for base training.

---

## Recovery & Wellness Metrics

### HRV — Heart Rate Variability (RMSSD)
**Units:** Milliseconds (ms)  
**What it is:** The variation in time between consecutive heartbeats.
Counterintuitively, more variability = better recovery. A high HRV indicates
your autonomic nervous system is well-recovered; a low HRV suggests stress,
fatigue, or illness.  
**RMSSD** (Root Mean Square of Successive Differences) is the specific HRV
metric Garmin measures — it reflects parasympathetic (recovery) nervous system
activity.  
**How to use it:** Don't compare your absolute HRV to others — it is highly
individual. Instead track your own 7-day baseline and look for deviations.
A drop of >1 standard deviation below your baseline is a meaningful signal.

### HRV Baseline
**What it is:** A 7-day rolling median of your HRV. The median is used instead
of the mean because it is more robust to outliers (e.g. a bad night's sleep
with the watch slipping).

### HRV Deviation
**Formula:** (today's HRV - 7-day baseline) / 7-day rolling std deviation  
**Units:** Standard deviations (z-score)  
**What it is:** How far today's HRV is from your recent normal, expressed in
standard deviations. Easier to interpret than raw RMSSD because it accounts
for your individual baseline.

| Deviation | Interpretation |
|-----------|---------------|
| > +1.0 | Well recovered, nervous system fresh |
| -0.5 to +1.0 | Normal range |
| -1.0 to -0.5 | Slightly suppressed, monitor |
| < -1.0 | Significantly suppressed, consider easy day |
| < -1.5 | Flag for rest — body under stress |

### Resting HR
**Units:** BPM  
**What it is:** Your heart rate at complete rest, typically measured on waking.
An elevated resting HR (>5 BPM above your normal) is a sign of accumulated
fatigue, illness, or stress — similar signal to low HRV.

### Respiration Rate
**Units:** Breaths per minute  
**What it is:** Your breathing rate at rest, measured overnight by the Garmin
optical sensor. Elevated respiration rate can indicate illness or high stress.
Normal range at rest is 12–20 breaths/min.

---

## Composite Recovery Score
**Range:** 0–100  
**What it is:** A weighted combination of available recovery signals into a
single daily score. Higher = better recovered.

**Weights:**
| Signal | Weight |
|--------|--------|
| HRV deviation | 40% |
| TSB (form) | 30% |
| Sleep hours | 20% |
| Body Battery | 10% |

If a signal is unavailable (e.g. no HRV on days you don't wear the watch),
the score is computed from whatever signals are available, or returns NaN
if fewer than 2 signals are present.

### Readiness Flag
A simplified traffic-light summary of the recovery score:

| Flag | Score | Recommendation |
|------|-------|---------------|
| 🟢 Go | ≥ 70 | Hard session or race effort |
| 🟡 Normal | 50–70 | Moderate training |
| 🟠 Easy | 30–50 | Zone 2 or active recovery |
| 🔴 Rest | < 30 | Complete rest or very light spin |

---

## Power Curve (Mean-Maximal Power)
**Also known as:** MMP curve, peak power curve  
**What it is:** For every possible duration (5 seconds, 1 minute, 20 minutes,
etc.), your best ever average power over that duration across all rides in your
history. It represents your absolute power ceiling at each time scale.  
**Why it matters:** The shape of your power curve reveals your physiological
profile:
- Steep drop-off at short durations → more endurance-oriented
- Relatively high short-duration power → more punch/sprint ability
- The 20-minute power ÷ 0.95 is one way to estimate FTP from the curve
