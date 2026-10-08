# Holdout: does the agent team add anything the scorecard doesn't?

Generated 2026-10-08 by `python -m holdout analyze`. Model: Claude Sonnet 4.5, whose training data ends July 2025.
Sample: US-listed non-financial companies worth at least $300M that filed a 10-K after that cutoff; the
hypotheses, outcomes and decision rules were fixed in advance in `holdout/PREREGISTRATION.md`. The model
never saw these filings or what followed, and web research is off, so nothing after the filing reaches it.

## Primary: what happened to the business (57 companies)

Outcomes from the company's next two quarterly reports, each against the same quarter a year earlier (see `holdout/outcomes.py`). A deterioration is a margin drop of 3+ points or a growth slowdown of 10+ points.

### Operating margin change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 54 | -0.010 | -0.318 to 0.275 |
| Single prompt: score 0-100 | 54 | 0.064 | -0.241 to 0.359 |
| Agent team: PM score 0-100 | 54 | 0.141 | -0.186 to 0.375 |
| Single prompt: verdict | 54 | -0.007 | -0.240 to 0.327 |
| Agent team: PM verdict | 54 | 0.035 | -0.243 to 0.304 |
| Agent team: high-severity red-team objections (fewer = better) | 54 | -0.144 | -0.418 to 0.150 |

### Revenue growth change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 56 | -0.085 | -0.347 to 0.215 |
| Single prompt: score 0-100 | 56 | -0.274 | -0.520 to 0.004 |
| Agent team: PM score 0-100 | 56 | -0.271 | -0.477 to 0.018 |
| Single prompt: verdict | 56 | -0.211 | -0.390 to 0.125 |
| Agent team: PM verdict | 56 | -0.226 | -0.334 to 0.193 |
| Agent team: high-severity red-team objections (fewer = better) | 56 | -0.160 | -0.351 to 0.154 |

### Spotting deterioration (base rate 16%)

AUC: the chance a deteriorating company got a worse signal than a healthy one. 0.50 = no information.

| Signal | Companies | AUC | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 57 | 0.509 | 0.296 to 0.722 |
| Single prompt: score 0-100 | 57 | 0.583 | 0.372 to 0.787 |
| Agent team: PM score 0-100 | 57 | 0.525 | 0.306 to 0.747 |
| Single prompt: verdict | 57 | 0.664 | 0.503 to 0.825 |
| Agent team: PM verdict | 57 | 0.546 | 0.410 to 0.698 |
| Agent team: high-severity red-team objections (fewer = better) | 57 | 0.347 | 0.137 to 0.609 |

### Beyond the scorecard (H1, H2)

Outcome regressed on the scorecard and one model signal, both as percentile ranks (0-1); margin change also as a percentile rank, deterioration as 0/1. Robust t-statistics. A coefficient of 0.2 on margin change means going from the lowest to the highest signal moves a company 20 percentiles up the margin-change ranking. The hypothesis holds if the model signal's t is above 1.96 in the predicted direction.

| Outcome | Model signal | Companies | Model coefficient (t) | Scorecard t |
|---|---|---|---|---|
| margin_change | Agent team: PM score 0-100 | 54 | 0.132 (0.9) | -0.4 |
| margin_change | Agent team: high-severity red-team objections (fewer = better) | 54 | -0.163 (-1.1) | -0.1 |
| margin_change | Single prompt: score 0-100 | 54 | 0.083 (0.6) | -0.3 |
| margin_change | Agent team: PM verdict | 54 | 0.074 (0.3) | -0.2 |
| deteriorated | Agent team: PM score 0-100 | 57 | -0.041 (-0.2) | -0.0 |
| deteriorated | Agent team: high-severity red-team objections (fewer = better) | 57 | 0.261 (1.3) | -0.1 |
| deteriorated | Single prompt: score 0-100 | 57 | -0.141 (-0.8) | 0.2 |
| deteriorated | Agent team: PM verdict | 57 | -0.166 (-0.6) | -0.1 |

### Operating margin forecasts (H3; 54 companies)

The forecast change (next-year forecast minus the filed year) ranked against the realized change, compared with mean reversion fitted on the same rows (no dev split available). Direction accuracy uses the same bands as the outcomes (margin ±1 point, growth ±2 points).

| Forecaster | Rank correlation (95% CI) | vs mean reversion (95% CI) | Direction accuracy |
|---|---|---|---|
| Baseline: mean reversion | 0.153 |  | 39% |
| Baseline: most common outcome in dev |  |  | 48% |
| Agent team (PM) | 0.235 (-0.097 to 0.547) | +0.082 (-0.134 to +0.298) | 46% |
| Single prompt | 0.178 (-0.148 to 0.469) | +0.025 (-0.195 to +0.236) | 50% |

### Revenue growth forecasts (secondary; 56 companies)

The forecast change (next-year forecast minus the filed year) ranked against the realized change, compared with mean reversion fitted on the same rows (no dev split available). Direction accuracy uses the same bands as the outcomes (margin ±1 point, growth ±2 points).

| Forecaster | Rank correlation (95% CI) | vs mean reversion (95% CI) | Direction accuracy |
|---|---|---|---|
| Baseline: mean reversion | 0.183 |  | 45% |
| Baseline: most common outcome in dev |  |  | 57% |
| Agent team (PM) | 0.268 (-0.043 to 0.554) | +0.085 (-0.003 to +0.184) | 30% |
| Single prompt | 0.270 (-0.044 to 0.562) | +0.087 (-0.081 to +0.268) | 43% |

## Secondary: stock returns (low statistical power; see PREREGISTRATION.md)

### Six-month returns: 74 companies (10-Ks filed 2025-08-07 to 2026-03-31)

Median company return: 5.7%; SPY over the median window: 12.4%.

#### Which signal ranked the next six months best?

| Signal | Companies | Rank correlation with 6-month return | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 74 | 0.370 | 0.139 to 0.567 |
| Single prompt: verdict | 74 | 0.121 | -0.231 to 0.226 |
| Single prompt: conviction 1-5 | 74 | 0.074 | -0.181 to 0.295 |
| Agent team: PM verdict | 74 | -0.082 | -0.312 to 0.163 |
| Agent team: scorecard incl. red-team penalty | 74 | 0.374 | 0.136 to 0.571 |

#### By verdict

| Signal | Verdict | Companies | Beat the median | Median return vs SPY |
|---|---|---|---|---|
| Scorecard | Dig deeper | 21 | 62% | 5.6% |
| Scorecard | Watch | 30 | 60% | -4.2% |
| Scorecard | Pass | 23 | 26% | -24.3% |
| Single prompt | Dig deeper | 8 | 75% | 12.9% |
| Single prompt | Watch | 46 | 43% | -8.0% |
| Single prompt | Pass | 20 | 55% | 9.5% |
| Agent team (PM) | Dig deeper | 2 | 50% | -6.2% |
| Agent team (PM) | Watch | 58 | 48% | -7.6% |
| Agent team (PM) | Pass | 14 | 57% | 8.2% |

#### Does the model add anything beyond the scorecard?

Return vs SPY (winsorized 1%) regressed on the scorecard and the model's verdict (0 Pass, 1 Watch, 2 Dig deeper); robust t-statistics.

| Model signal | Companies | Scorecard coefficient (t) | Model verdict coefficient (t) |
|---|---|---|---|
| Agent team (PM) | 74 | 0.659 (4.0) | -14.9 pts per step (-1.6) |
| Single prompt | 74 | 0.745 (4.3) | -12.5 pts per step (-1.8) |

#### When the PM and the scorecard disagreed

46 disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): PM right 3/11, scorecard right 26/39.

#### Do red-team red flags predict drawdowns?

Rank correlation between fewer high-severity objections and a smaller drawdown over the window: 0.082. Companies with two or more high-severity objections fell 30%+ from a peak 22% of the time (n = 36), against 15% for companies with none (n = 13).

## Limits

- One period: every company's window falls between late 2025 and September 2026, so a single market regime drives the result.
- A few hundred companies detect only a moderate effect; the confidence intervals show how wide the uncertainty is.
- The twelve-month group is small and tilted to June fiscal years (August-September filers).
- Web research is off in this test; the live tool uses it.
