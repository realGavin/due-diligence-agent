# Holdout: does the agent team add anything the scorecard doesn't?

Generated 2026-10-08 by `python -m holdout analyze`. Model: Claude Sonnet 4.5, whose training data ends July 2025.
Sample: US-listed non-financial companies worth at least $300M that filed a 10-K after that cutoff; the
hypotheses, outcomes and decision rules were fixed in advance in `holdout/PREREGISTRATION.md`. The model
never saw these filings or what followed, and web research is off, so nothing after the filing reaches it.

## Primary: what happened to the business (322 companies)

Outcomes from the company's next two quarterly reports, each against the same quarter a year earlier (see `holdout/outcomes.py`). A deterioration is a margin drop of 3+ points or a growth slowdown of 10+ points.

### Operating margin change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 297 | -0.024 | -0.155 to 0.096 |

### Revenue growth change (pts): rank correlation with each signal

| Signal | Companies | Rank correlation | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 320 | -0.079 | -0.206 to 0.032 |

### Spotting deterioration (base rate 25%)

AUC: the chance a deteriorating company got a worse signal than a healthy one. 0.50 = no information.

| Signal | Companies | AUC | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 322 | 0.613 | 0.538 to 0.678 |

### Revenue growth direction forecast, next two quarters (H3; 320 companies)

Compared against the better baseline (mean reversion); baselines fitted on the same rows (no dev split available).

| Forecaster | Accuracy | vs best baseline | 95% CI |
|---|---|---|---|
| Agent team (PM) | 21% | -32.5 pts | -41.6 to -23.8 |
| Single prompt | 21% | -32.5 pts | -41.2 to -23.8 |
| Baseline: most common outcome in dev | 48% |  |  |
| Baseline: mean reversion | 53% |  |  |

### Operating margin direction forecast, next two quarters (H3; 297 companies)

Compared against the better baseline (most common outcome in dev); baselines fitted on the same rows (no dev split available).

| Forecaster | Accuracy | vs best baseline | 95% CI |
|---|---|---|---|
| Agent team (PM) | 26% | -21.9 pts | -31.3 to -12.8 |
| Single prompt | 26% | -21.9 pts | -31.0 to -12.1 |
| Baseline: most common outcome in dev | 47% |  |  |
| Baseline: mean reversion | 41% |  |  |

## Secondary: stock returns (low statistical power; see PREREGISTRATION.md)

### Six-month returns: 400 companies (10-Ks filed 2025-08-01 to 2026-03-31)

Median company return: 1.6%; SPY over the median window: 12.4%.

#### Which signal ranked the next six months best?

| Signal | Companies | Rank correlation with 6-month return | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 400 | 0.062 | -0.033 to 0.169 |
| Agent team: scorecard incl. red-team penalty | 400 | 0.062 | -0.033 to 0.169 |

#### By verdict

| Signal | Verdict | Companies | Beat the median | Mean return vs SPY |
|---|---|---|---|---|
| Scorecard | Dig deeper | 124 | 49% | -1.0% |
| Scorecard | Watch | 153 | 54% | 2.5% |
| Scorecard | Pass | 123 | 46% | 2.6% |
| Single prompt | Watch | 400 | 50% | 1.4% |
| Agent team (PM) | Watch | 400 | 50% | 1.4% |

#### When the PM and the scorecard disagreed

247 disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): PM right 0/0, scorecard right 128/247.

#### Do red-team red flags predict drawdowns?

Rank correlation between fewer high-severity objections and a smaller drawdown over the window: 0.038. Companies with two or more high-severity objections fell 30%+ from a peak n/a of the time (n = 0), against 23% for companies with none (n = 400).

### Twelve-month returns: 78 companies (10-Ks filed 2025-08-01 to 2025-09-29)

Median company return: 4.0%; SPY over the median window: 20.2%.

#### Which signal ranked the next twelve months best?

| Signal | Companies | Rank correlation with 12-month return | 95% CI |
|---|---|---|---|
| Scorecard (code only) | 78 | 0.109 | -0.158 to 0.353 |
| Agent team: scorecard incl. red-team penalty | 78 | 0.109 | -0.158 to 0.353 |

#### By verdict

| Signal | Verdict | Companies | Beat the median | Mean return vs SPY |
|---|---|---|---|---|
| Scorecard | Dig deeper | 30 | 57% | -1.7% |
| Scorecard | Watch | 33 | 52% | 26.8% |
| Scorecard | Pass | 15 | 33% | 195.2% |
| Single prompt | Watch | 78 | 50% | 48.3% |
| Agent team (PM) | Watch | 78 | 50% | 48.3% |

#### When the PM and the scorecard disagreed

45 disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): PM right 0/0, scorecard right 27/45.

#### Do red-team red flags predict drawdowns?

Rank correlation between fewer high-severity objections and a smaller drawdown over the window: -0.257. Companies with two or more high-severity objections fell 30%+ from a peak n/a of the time (n = 0), against 55% for companies with none (n = 78).

## Limits

- One period: every company's window falls between late 2025 and September 2026, so a single market regime drives the result.
- A few hundred companies detect only a moderate effect; the confidence intervals show how wide the uncertainty is.
- The twelve-month group is small and tilted to June fiscal years (August-September filers).
- Web research is off in this test; the live tool uses it.
