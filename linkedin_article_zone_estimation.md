# Your Average Power Is Lying to You

## How I built a statistical model to recover the training information that Strava doesn't give you

---

When I started building a personal cycling performance dashboard, I hit an immediate problem.

The dashboard needed to monitor training polarisation — whether I was following the 80/20 intensity split that Seiler and Kjerland's research identifies as optimal for endurance adaptation. That means knowing how much time I spend in each power zone across every ride.

Garmin devices record this perfectly. The cycling computer sees every watt, every second, and stores exact time-in-zone from the raw power stream. The problem: getting that data out of Garmin programmatically requires going through an API approval process that, as of writing, lists its application form as "coming soon." Not ideal for a side project.

Strava's API, by contrast, is open and free. But Strava activity exports carry only summary statistics: average power, normalised power, and duration. No zone data. Just two numbers and a time.

So the question became: **given only average power, normalised power, and duration, can you estimate how ride time was distributed across the seven Coggan power zones?**

It turns out you can — and the math is surprisingly clean.

---

## The naïve approach fails badly

The obvious first attempt is to look at average power, find which zone it falls in, and assign the entire ride there.

For a ride averaging 220W at an FTP of 333W, that's 66% of FTP — solidly Zone 2. So the algorithm says: 100% of this ride was Zone 2.

When I applied this across four weeks of training, the result was 98.8% Zone 1/Zone 2, with 0% in any zone above Z2. Every ride, regardless of whether it included intervals, a group ride sprint finish, or a hard climb, collapsed into a single zone bucket.

This is useless for monitoring training intensity. A threshold interval session averaging 220W because of long rest periods looks identical to a flat endurance spin at 220W.

---

## Normalised Power encodes the spread

Here's the insight that makes a better model possible.

Normalised power (NP) is not just a fatigue-adjusted average. Mathematically, it's the ℒ4 norm of the power distribution — the 4th root of the mean 4th power of instantaneous power. Because of the 4th power weighting, NP amplifies high-power spikes far more aggressively than average power does.

The ratio VI = NP / AP (the variability index) encodes how spread out the power distribution was during the ride:

- **VI ≈ 1.02**: Nearly constant power. A flat TT or steady Zwift ride. All time near average power.
- **VI ≈ 1.15–1.25**: Highly variable. Intervals, group rides, hilly terrain. Time scattered across zones.

This gives us a way in. If we assume instantaneous power is approximately Gaussian, we can use AP as the mean and derive σ from the relationship between the 4th moment and NP.

The derivation is a quadratic in σ²:

```
3σ⁴ + 6μ²σ² − (NP⁴ − μ⁴) = 0
```

Solving for the positive root:

```
σ = √( max(0, (−3μ² + √(6μ⁴ + 3·NP⁴)) / 3) )
```

With μ and σ in hand, the fraction of time in each zone is just the probability mass under the Gaussian between the zone's FTP boundaries — computed with the standard normal CDF.

This requires no training data, no fitting, no parameters beyond FTP. It runs analytically in milliseconds.

---

## Results: a very different picture

Applying the Gaussian model to the same four weeks of training that produced the 98.8% Z1/Z2 estimate:

| Zone | % of total time |
|------|----------------|
| Z1 Recovery | 32.0% |
| Z2 Endurance | 22.7% |
| Z3 Tempo | 24.9% |
| Z4 Threshold | 11.0% |
| Z5 VO2max | 4.6% |
| Z6 Anaerobic | 3.6% |
| Z7 Neuromuscular | 1.2% |

Grey zone total (Z3 + Z4): **35.9%** — more than double Seiler's 15% target.

That's actually useful information. The dashboard now correctly flags excess grey-zone time and recommends either more Zone 2 endurance work or proper VO2max intervals to restore polarisation. The naïve approach would have told me everything was fine.

---

## Extending with a Bayesian model

The Gaussian approach has a known limitation: real interval sessions are bimodal, not Gaussian. Long easy recovery periods between hard work intervals create two clusters — one near Zone 1, one near Zone 5 — which a single Gaussian misses, overestimating grey-zone time and underestimating the extremes.

For rides where Garmin data is available (which records exact per-zone seconds from the raw power stream), I have ground truth to learn from. I trained a Bayesian Dirichlet regression model on this data.

Why Dirichlet? Zone time fractions are compositional data — non-negative values summing to 1. The Dirichlet distribution is the natural model for this space, avoiding the broken assumptions of treating fractions with a multivariate normal.

The regression maps two features to the Dirichlet concentration parameters:
- **Intensity** q = AP / FTP
- **Log variability index** v = log(NP / AP)

```
log α_k = β₀_k + β₁_k · q + β₂_k · v
```

Posterior inference via NUTS in PyMC. The fitted β₂ coefficients confirm what the physics suggests: higher variability (larger v) concentrates time toward Z5–Z7 and away from Z1–Z2.

The dashboard applies a three-level fallback:
1. **Garmin device data** — exact per-zone seconds when available
2. **Bayesian prediction** — when the model is fitted and Garmin data is absent
3. **Gaussian fallback** — when neither is available

---

## Why this matters for training monitoring

The polarised training framework (Seiler & Kjerland, 2006; Stöggl & Sperlich, 2014) is one of the more robust findings in endurance sports science. The evidence consistently shows that trained athletes who distribute ~80% of training in Zone 1/2 and ~15–20% in Zone 5+ outperform those who accumulate grey-zone volume.

But you can only audit your intensity distribution if you can measure it. For athletes training across multiple platforms — Garmin outdoors, Zwift indoors, occasional Strava-only imports — a model that estimates zone distributions from summary statistics alone makes continuous monitoring practical without requiring raw power streams for every session.

---

## A note on how this was written

This paper and post were developed with assistance from Claude (Anthropic) as a writing tool, based on my own model designs, mathematical derivations, and experimental results. The models, the data, and the decisions about what to build were mine — Claude helped translate them into coherent prose and LaTeX. I think being transparent about that matters, particularly in a technical community still working out the norms around AI-assisted writing.

The full paper, including the complete mathematical appendix and Python implementations, is available on request.

---

*Xavier Boingboing is a final-year data science student at an Australian university, building toward graduate roles in data and AI. The cycling dashboard described here is an open-source personal project.*
