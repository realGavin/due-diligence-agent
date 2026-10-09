# Holdout: does the agent team add anything the scorecard doesn't?

Generated 2026-10-08 by `python -m holdout analyze`. Model: Claude Sonnet 4.5, whose training data ends July 2025.
Sample: US-listed non-financial companies worth at least $300M that filed a 10-K after that cutoff; the
hypotheses, outcomes and decision rules were fixed in advance in `holdout/PREREGISTRATION.md`. The model
never saw these filings or what followed, and web research is off, so nothing after the filing reaches it.

## Primary: what happened to the business (265 companies)

Outcomes from the company's next two quarterly reports, each against the same quarter a year earlier (see `holdout/outcomes.py`). A deterioration is a margin drop of 3+ points or a growth slowdown of 10+ points.

### Operating margin change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 243 | -0.028 | -0.173 to 0.102 |
| Single prompt: score 0-100 | 243 | 0.016 | -0.119 to 0.158 |
| Agent team: PM score 0-100 | 243 | -0.003 | -0.122 to 0.137 |
| Single prompt: verdict | 243 | -0.012 | -0.101 to 0.169 |
| Agent team: PM verdict | 243 | 0.032 | -0.121 to 0.139 |
| Agent team: high-severity red-team objections (fewer = better) | 243 | -0.047 | -0.204 to 0.059 |

### Revenue growth change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 264 | -0.091 | -0.214 to 0.043 |
| Single prompt: score 0-100 | 264 | -0.151 | -0.291 to -0.020 |
| Agent team: PM score 0-100 | 264 | -0.139 | -0.263 to -0.015 |
| Single prompt: verdict | 264 | -0.111 | -0.249 to 0.006 |
| Agent team: PM verdict | 264 | -0.080 | -0.223 to 0.022 |
| Agent team: high-severity red-team objections (fewer = better) | 264 | 0.047 | -0.093 to 0.150 |

### Spotting deterioration (base rate 27%)

AUC: the chance a deteriorating company got a worse signal than a healthy one. 0.50 = no information.

| Signal | Companies | AUC | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 265 | 0.627 | 0.550 to 0.701 |
| Single prompt: score 0-100 | 265 | 0.567 | 0.479 to 0.653 |
| Agent team: PM score 0-100 | 265 | 0.555 | 0.470 to 0.636 |
| Single prompt: verdict | 265 | 0.561 | 0.486 to 0.636 |
| Agent team: PM verdict | 265 | 0.535 | 0.478 to 0.590 |
| Agent team: high-severity red-team objections (fewer = better) | 265 | 0.479 | 0.398 to 0.556 |

### Beyond the scorecard (H1, H2)

Outcome regressed on the scorecard and one model signal, both as percentile ranks (0-1); margin change also as a percentile rank, deterioration as 0/1. Robust t-statistics. A coefficient of 0.2 on margin change means going from the lowest to the highest signal moves a company 20 percentiles up the margin-change ranking. The hypothesis holds if the model signal's t is above 1.96 in the predicted direction.

| Outcome | Model signal | Companies | Model coefficient (t) | Scorecard t |
|---|---|---|---|---|
| margin_change | Agent team: PM score 0-100 | 243 | 0.025 (0.3) | -0.6 |
| margin_change | Agent team: high-severity red-team objections (fewer = better) | 243 | -0.080 (-1.2) | -0.6 |
| margin_change | Single prompt: score 0-100 | 243 | 0.041 (0.5) | -0.7 |
| margin_change | Agent team: PM verdict | 243 | 0.033 (0.3) | -0.6 |
| deteriorated | Agent team: PM score 0-100 | 265 | 0.004 (0.0) | -2.9 |
| deteriorated | Agent team: high-severity red-team objections (fewer = better) | 265 | 0.048 (0.5) | -3.2 |
| deteriorated | Single prompt: score 0-100 | 265 | -0.028 (-0.2) | -2.7 |
| deteriorated | Agent team: PM verdict | 265 | -0.049 (-0.3) | -3.0 |

### Operating margin forecasts (H3; 243 companies)

The forecast change (next-year forecast minus the filed year) ranked against the realized change, compared with mean reversion fitted on the dev split. Direction accuracy uses the same bands as the outcomes (margin ±1 point, growth ±2 points).

| Forecaster | Rank correlation (95% CI) | vs mean reversion (95% CI) | Direction accuracy |
|---|---|---|---|
| Baseline: mean reversion | 0.150 |  | 40% |
| Baseline: most common outcome in dev |  |  | 47% |
| Agent team (PM) | 0.180 (0.026 to 0.329) | +0.040 (-0.056 to +0.135) | 41% |
| Single prompt | 0.165 (0.021 to 0.321) | +0.015 (-0.083 to +0.118) | 44% |

### Revenue growth forecasts (secondary; 264 companies)

The forecast change (next-year forecast minus the filed year) ranked against the realized change, compared with mean reversion fitted on the dev split. Direction accuracy uses the same bands as the outcomes (margin ±1 point, growth ±2 points).

| Forecaster | Rank correlation (95% CI) | vs mean reversion (95% CI) | Direction accuracy |
|---|---|---|---|
| Baseline: mean reversion | 0.483 |  | 50% |
| Baseline: most common outcome in dev |  |  | 46% |
| Agent team (PM) | 0.504 (0.384 to 0.611) | +0.022 (-0.048 to +0.094) | 53% |
| Single prompt | 0.447 (0.320 to 0.567) | -0.036 (-0.133 to +0.051) | 51% |

## Secondary: stock returns (low statistical power; see PREREGISTRATION.md)

### Six-month returns: 326 companies (10-Ks filed 2025-08-01 to 2026-03-31)

Median company return: 0.9%; SPY over the median window: 12.4%.

#### Which signal ranked the next six months best?

| Signal | Companies | Rank correlation with 6-month return | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 326 | 0.003 | -0.111 to 0.112 |
| Single prompt: verdict | 326 | 0.083 | -0.024 to 0.207 |
| Single prompt: conviction 1-5 | 326 | 0.048 | -0.101 to 0.126 |
| Agent team: PM verdict | 326 | -0.006 | -0.118 to 0.109 |
| Agent team: scorecard incl. red-team penalty | 326 | -0.002 | -0.115 to 0.112 |

#### By verdict

| Signal | Verdict | Companies | Beat the median | Median return vs SPY |
|---|---|---|---|---|
| Scorecard | Dig deeper | 103 | 50% | -11.5% |
| Scorecard | Watch | 123 | 51% | -9.6% |
| Scorecard | Pass | 100 | 49% | -14.8% |
| Single prompt | Dig deeper | 59 | 58% | -7.8% |
| Single prompt | Watch | 185 | 50% | -11.4% |
| Single prompt | Pass | 82 | 45% | -17.2% |
| Agent team (PM) | Dig deeper | 10 | 30% | -42.3% |
| Agent team (PM) | Watch | 252 | 51% | -11.2% |
| Agent team (PM) | Pass | 64 | 50% | -11.7% |

#### Does the model add anything beyond the scorecard?

Return vs SPY (winsorized 1%) regressed on the scorecard and the model's verdict (0 Pass, 1 Watch, 2 Dig deeper); robust t-statistics.

| Model signal | Companies | Scorecard coefficient (t) | Model verdict coefficient (t) |
|---|---|---|---|
| Agent team (PM) | 326 | -0.028 (-0.2) | 2.7 pts per step (0.5) |
| Single prompt | 326 | -0.118 (-1.0) | 8.8 pts per step (1.8) |

#### When the PM and the scorecard disagreed

189 disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): PM right 17/36, scorecard right 84/165.

#### Do red-team red flags predict drawdowns?

Rank correlation between fewer high-severity objections and a smaller drawdown over the window: 0.030. Companies with two or more high-severity objections fell 30%+ from a peak 25% of the time (n = 177), against 12% for companies with none (n = 33).

### Twelve-month returns: 67 companies (10-Ks filed 2025-08-01 to 2025-09-26)

Median company return: 4.4%; SPY over the median window: 20.2%.

#### Which signal ranked the next twelve months best?

| Signal | Companies | Rank correlation with 12-month return | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 67 | 0.095 | -0.195 to 0.357 |
| Single prompt: verdict | 67 | 0.028 | -0.194 to 0.326 |
| Single prompt: conviction 1-5 | 67 | 0.009 | -0.345 to 0.173 |
| Agent team: PM verdict | 67 | -0.011 | -0.176 to 0.298 |
| Agent team: scorecard incl. red-team penalty | 67 | 0.129 | -0.148 to 0.390 |

#### By verdict

| Signal | Verdict | Companies | Beat the median | Median return vs SPY |
|---|---|---|---|---|
| Scorecard | Dig deeper | 25 | 56% | -13.2% |
| Scorecard | Watch | 28 | 50% | -15.2% |
| Scorecard | Pass | 14 | 36% | -36.7% |
| Single prompt | Dig deeper | 17 | 41% | -25.9% |
| Single prompt | Watch | 35 | 57% | -7.4% |
| Single prompt | Pass | 15 | 40% | -34.5% |
| Agent team (PM) | Dig deeper | 4 | 25% | -24.5% |
| Agent team (PM) | Watch | 50 | 52% | -13.7% |
| Agent team (PM) | Pass | 13 | 46% | -27.2% |

#### Does the model add anything beyond the scorecard?

Return vs SPY (winsorized 1%) regressed on the scorecard and the model's verdict (0 Pass, 1 Watch, 2 Dig deeper); robust t-statistics.

| Model signal | Companies | Scorecard coefficient (t) | Model verdict coefficient (t) |
|---|---|---|---|
| Agent team (PM) | 67 | -1.295 (-0.9) | 36.8 pts per step (1.2) |
| Single prompt | 67 | -1.200 (-1.1) | -2.9 pts per step (-0.1) |

#### When the PM and the scorecard disagreed

42 disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): PM right 4/12, scorecard right 19/34.

#### Do red-team red flags predict drawdowns?

Rank correlation between fewer high-severity objections and a smaller drawdown over the window: -0.117. Companies with two or more high-severity objections fell 30%+ from a peak 56% of the time (n = 34), against 50% for companies with none (n = 8).

## Limits

- One period: every company's window falls between late 2025 and September 2026, so a single market regime drives the result.
- A few hundred companies detect only a moderate effect; the confidence intervals show how wide the uncertainty is.
- The twelve-month group is small and tilted to June fiscal years (August-September filers).
- Web research is off in this test; the live tool uses it.
