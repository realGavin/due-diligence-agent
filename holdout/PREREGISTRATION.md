# Preregistration: does the agent team add anything the scorecard doesn't?

Written 2026-10-08, before any model call on the test split (revised the same day; see Revision below). The test split runs once, on the committed code; every result row records the git commit and this file's hash (`code_version` in `holdout/run.py`). Anything run after the test split is labeled exploratory.

## Question

ddagent's agents (three analysts, a PM, a red team) read a company's 10-K and judge the business. Do those judgments contain information about what happens to the business next that the code-only scorecard, built from the same filing, does not?

## Sample

- US-listed non-financial companies (SIC outside 6000–6799) worth at least $300M at the month-end before filing, with a 10-K filed between 2025-08-01 and 2026-03-31.
- Every August–September 2025 filer is included (the only twelve-month return group). The rest are a random draw with a fixed seed, chosen before any filing is downloaded (`holdout/sample.py`).
- Split by a hash of the ticker (`split_of`): about 20% **dev**, 80% **test**. The dev split may be used to fix bugs and revise prompts. The test split is run once, after this file and the code are committed.

## Model and evidence

- Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`), training data through July 2025, so the filings and everything after them are unseen.
- Evidence: the 10-K's XBRL facts as of the filing date, excerpts from the 10-K, and a market cap computed from the price at the month-end before filing. Web research is off.

## Signals

1. **Scorecard**: the code-only rubric's score (0–100%).
2. **Single prompt score**: one call on the same evidence gives a 0–100 attractiveness score (50 = a typical US-listed company) and point forecasts of next fiscal year's revenue growth (%) and operating margin (%).
3. **Agent team, PM score**: the PM's 0–100 score and the same two forecasts.
4. **Agent team, red flags**: the number of high-severity red-team objections that passed the grounding gate.
5. **Forecast change**: a forecast minus the filed year's value (margin forecast minus filed margin; growth forecast minus filed growth), in points.
6. Secondary: the categorical verdicts (Pass = 0, Watch = 1, Dig deeper = 2) from the single prompt and the PM.

## Primary outcomes

From the company's first two quarterly reports after the fiscal year in the filing, each against the same quarter a year earlier (`holdout/outcomes.py`), from an SEC companyfacts snapshot taken at analysis time:

- **Margin change**: operating margin in those two quarters minus the same two quarters a year earlier, in points.
- **Growth change**: their revenue growth minus the filed year's revenue growth, in points.
- **Deterioration**: margin change ≤ −3 points, or growth change ≤ −10 points.
- **Realized direction**: the two changes mapped onto the forecast bands above.

Companies without two reported quarters and a year-ago comparison are excluded from these outcomes, which is decided by data availability, not results.

## Hypotheses (test split)

- **H1.** The PM score predicts margin change beyond the scorecard: in `rank(margin change) ~ rank(scorecard) + rank(PM score)` (percentile ranks, robust standard errors), the PM coefficient is positive with t > 1.96.
- **H2.** Red flags predict deterioration beyond the scorecard: in `deterioration ~ rank(scorecard) + rank(−red flags)` (linear probability model, percentile-rank regressors, robust standard errors), the red-flag coefficient is negative with t < −1.96. In plain terms, more high-severity objections mean more deterioration.
- **H3.** The PM's forecast margin change ranks the realized margin change: the rank correlation's 95% bootstrap interval is above zero, and it beats mean reversion (forecast change = dev-split median margin minus the filed margin), with the paired bootstrap interval of the difference in rank correlations above zero.

The same tests are reported for the single prompt, the categorical verdicts and the growth forecast, as secondary results, along with direction accuracy against two baselines (the dev split's most common direction, and mean reversion). With three primary hypotheses, a result is called robust only at t > 2.4 (Bonferroni, α = 0.05/3); results between 1.96 and 2.4 are reported as suggestive.

## Secondary outcomes

Six-month returns (all companies) and twelve-month returns (August–September 2025 filers), against SPY and the sample median. These are expected to be low-powered: with roughly 300 companies, only a rank correlation near 0.16 or larger is reliably detectable, against about 0.05 for typical signals. They are reported, but not used to judge the agents.

## What gets reported

Every table in `RESULTS_test.md` is reported whatever it shows. If H1–H3 fail, the README states that the agents added no measurable information beyond the scorecard on this sample, with the confidence intervals. If they hold, it states the effect size and its interval, and notes that this is one period (late 2025 to 2026) and one model.

## Revision (2026-10-08, before the test split)

The first version used the PM's categorical verdict for H1 and categorical forecasts (expand / stable / compress) for H3. A dev-split run on 23 companies showed those outputs had too little spread to test anything: the PM said Watch for 16 of 23 and never forecast accelerating growth. The signals were changed to the numeric score and point forecasts above. The decision used only the distribution of the model's outputs; the model's outputs were never compared with any outcome before the change (the earlier dry run computed outcomes, but only against stub signals). The categorical verdicts stay as secondary signals. Those 23 runs are kept in `holdout/results/runs_dev_v1_categorical.jsonl` and are not used in any analysis.

Second change, same day, after the full dev split (74 companies). H1 and H2 used raw values with the outcome winsorized at 1%. On dev, pre-revenue companies had margin changes of several hundred to over 1,600 points (operating margins near −2,000% moving toward −500%), and a 1% winsorization of about 55 rows clips nothing, so three companies set the regression coefficients. H1 and H2 now use percentile ranks, like the rank correlations and H3 already did. The dev split's signal results were visible when this change was made. Rank regression was picked because it matches the other primary tests and is the standard fix for extreme values, and it was the only alternative considered; no other specification was run on dev to compare.

What was seen before the test run: the dry run (`RESULTS_dryrun.md`, `summary_dryrun.json`) computed outcomes for all 400 companies, test split included, but only in aggregate and only against the code-only scorecard and stub model outputs; no model ran on a test-split company. The scorecard was not changed after the dry run. The model was run only on the 74 dev companies.

