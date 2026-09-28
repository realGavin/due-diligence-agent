# Does the scorecard predict anything?

Point-in-time backtest of the scorecard, generated 2026-09-28 by `python -m backtest`.

Every June 30 from 2012 to 2025, each US-listed non-financial company worth at least $300M was scored with the same code the memos use, on only the 10-K data public that day, and grouped by verdict. Portfolios are held twelve months. 14,514 company-years, 1,686 companies. No model is involved: the red-team penalty is zero.

## Absolute rubric (one threshold for every industry)

| | Dig deeper | Watch | Pass |
|---|---|---|---|
| Return, equal-weighted (annualized) | 16.9% | 15.9% | 18.3% |
| Return, value-weighted (annualized) | 17.5% | 16.4% | 12.6% |
| Beat the median stock next 12 months | 53% | 50% | 46% |
| Names per year (avg) | 392 | 376 | 268 |

| Dig deeper minus Pass | Equal-weighted | Value-weighted |
|---|---|---|
| Spread, annualized (t) | -1.3% (-0.5) | 4.4% (0.8) |
| Alpha after FF5 + momentum, annualized (t) | -0.3% (-0.2) | 6.6% (1.4) |
| Loading on RMW (t) | 0.61 (7.8) | 0.20 (0.6) |
| Loading on HML (t) | 0.08 (1.6) | -0.58 (-1.7) |
| Loading on SMB (t) | -0.25 (-3.9) | -0.50 (-2.0) |
| Loading on Mom (t) | -0.02 (-0.3) | 0.11 (1.1) |

Rank correlation of the score with the next 12 months' return: mean 0.055 (t = 2.3), positive in 10 of 14 years.

## Sector-relative rubric (scored against industry peers)

| | Dig deeper | Watch | Pass |
|---|---|---|---|
| Return, equal-weighted (annualized) | 17.0% | 16.3% | 17.7% |
| Return, value-weighted (annualized) | 18.6% | 14.0% | 12.8% |
| Beat the median stock next 12 months | 54% | 49% | 47% |
| Names per year (avg) | 326 | 435 | 276 |

| Dig deeper minus Pass | Equal-weighted | Value-weighted |
|---|---|---|
| Spread, annualized (t) | -0.6% (-0.3) | 5.2% (1.1) |
| Alpha after FF5 + momentum, annualized (t) | 0.4% (0.4) | 7.0% (1.5) |
| Loading on RMW (t) | 0.47 (7.6) | 0.24 (0.8) |
| Loading on HML (t) | 0.09 (2.1) | -0.58 (-1.8) |
| Loading on SMB (t) | -0.26 (-5.2) | -0.37 (-1.4) |
| Loading on Mom (t) | -0.01 (-0.3) | 0.18 (1.8) |

Rank correlation of the score with the next 12 months' return: mean 0.049 (t = 2.4), positive in 9 of 14 years.

## Caveats

- **Survivorship.** Prices come from today's listings, so companies that were later acquired or went bankrupt are missing. Their fundamentals are not: scored on the dimensions that need no price, 48% of a sample of no-longer-listed company-years would have been Pass, against 31% for companies still listed. Because the missing names skew toward Pass, and many of them failed, their absence most likely makes Pass look better than it was, which works against the spread above.
- **Thresholds were set before this test** (v0.2) and not tuned on it. The sector-relative cut-offs (top, middle, bottom third) are the obvious default, not fitted.
- **Market cap** is cover-page shares outstanding times the price quoted at formation. Microcaps under the size floor and financials (SIC 6000-6799) are excluded.
- **Costs** are ignored; turnover is annual, so they are small relative to the spreads.
- The red-team penalty and the PM's view are not tested here. The verdict ledger (`ddagent-grade`) tracks them going forward.

Peer tables for live memos (`peers.json`) come from the 2026 formation.
