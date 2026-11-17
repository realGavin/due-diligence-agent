# Hand review of the meaning check

Every claim the judge rejected in the fresh runs (`memos_fresh/`: Chipotle, Deere, CrowdStrike, generated with the meaning check off), plus the random 25 it accepted, read against the cited sources. The judge's reasons are in [`JUDGE_RESULTS_FRESH.md`](JUDGE_RESULTS_FRESH.md) in the same order. One reviewer, who also wrote the judge's instructions.

Labels: **right** (the claim says something its sources don't, or contradicts them) · **cut off** (right to reject, but only because the stored passage was truncated before the supporting text) · **too strict** (a reasonable reading of the sources that a careful analyst would accept).

## Fresh runs: the 40 rejections

| # | Claim (cited ids) | Label | Why |
|---|---|---|---|
| 1 | CMG digital sales and an "expanding Rewards program" (S9, S37) | right | Sources mention Rewards only as a revenue deferral, not expansion |
| 2 | CMG comps fell; flat 2026 guidance means the slowdown "will persist" (S36) | too strict | Flat after −1.7% is a fair reading of "persisting weakness" |
| 3 | CMG EPS growth "driven mainly by buybacks" (S36, F45, F11, F12) | right | Sources show the share count fell but never say why |
| 4 | CMG third-party delivery risk; "lacks segment diversification" (S24, S18) | too strict | The diversification point is the analyst's framing |
| 5 | CMG flat guidance means deceleration "persists rather than reverses" (S36) | too strict | Same as #2 |
| 6 | CMG food-safety practices "create higher risk" vs. competitors (S18) | right | Filing says "may have higher risk than some"; the hedge was dropped |
| 7 | CMG red-team objection to the "single-format concentration thesis" (S18) | too strict | Argues with the thesis, which the judge can't see |
| 8 | CMG EPS "largely mechanical", buybacks, "capital-returns narrative" (S36, F11, F12, F45) | too strict | Mostly argues with the thesis; the buyback cause is unsupported, as in #3 |
| 9 | CMG Chipotlanes, catering, delivery growth (W60) | cut off | Passage ends at "But delive" |
| 10 | CMG jalapeño recall; Chipotle stopped serving (W73) | cut off | Passage ends at "After be…" |
| 11 | CMG customer hospitalized; outbreak linked (W75) | cut off | Truncated; also states her account as fact |
| 12 | CMG shares fell "on Tuesday [Aug 5, 2026]" (W78) | right | The bracketed date isn't in the source, and Aug 5, 2026 is a Wednesday |
| 13 | CRWD gross profit "scaled consistently", land-and-expand (F1, F4, S47) | right | Only two endpoints cited; "consistently" isn't shown |
| 14 | CRWD long-term debt "roughly flat" (F43, F28, F32, S7) | right | Only one year of debt is cited |
| 15 | CRWD platform presented as a "durable" advantage (S5, S14, S9) | too strict | "Fundamental differentiator" vs. "durable" is a quibble |
| 16 | CRWD R&D "consistent with emphasis on continuous AI model training" (F13, F16, S7) | too strict | Analyst's reading; the figures and the platform are supported |
| 17 | CRWD commitment packages a "quantifiable" drag (S45) | right | Filing says it's "not reasonably possible to quantify" the impact |
| 18 | CRWD "steadily rising" gross profit (F1, F4, F12, F11, F10, S29) | right | Only two endpoints cited, as in #13 |
| 19 | CRWD derivative suit dropped, "no appeal filed" (W6) | cut off | Passage truncated before the appeal |
| 20 | CRWD Supreme Court petition "in del Rio v. CrowdStrike" (W8–W10) | right | No passage names the case |
| 21 | CRWD "more than $500 million" (W11) | right | That figure is Delta's allegation, stated as fact |
| 22 | CRWD guidance not provided for gross margin etc. (W30) | cut off | Passage ends mid-sentence |
| 23 | CRWD retention improved, record new-logo ARR (W33) | cut off | Passage ends at "All-time record n" |
| 24 | CRWD capex for "high-speed data processing" (W50) | cut off | Passage ends at "high-s" |
| 25 | DE R&D sustained "through the downturn" (F16, F15, F38, S4, S5) | too strict | The downturn is context from elsewhere in the memo |
| 26 | DE aftermarket model "diversifying revenue" (S6, S7) | too strict | Analyst's reading of the lifecycle-services model |
| 27 | DE PPA exposure "could extend the downturn" (S9, S17) | too strict | Same as #25 |
| 28 | DE R&D "consistent with FY2024 levels" (F16, F38, S4, S5) | right | The FY2024 figure isn't among the cited sources |
| 29 | DE red-team objection to the hold thesis's base case (S9, S17) | too strict | Argues with the thesis |
| 30 | DE "down 5 to 10%" (W30) | right | Passage shows net sales up 10% |
| 31 | DE factors affecting the ag market (W11) | cut off | Passage ends at "acreage plant" |
| 32 | DE tariffs "adversely affected costs… continue in 2026" (W16) | right | Passage only says tariffs were imposed |
| 33 | DE "majority of payments to row crop producers" (W18) | cut off | Passage ends at "with the majority o" |
| 34 | DE support helps "near-term liquidity challenges" (W19) | cut off | Passage ends at "provides help with" |
| 35 | DE higher sales after a "poor 2024 crop year" (W21) | cut off | Passage truncated |
| 36 | DE list of ag-cycle risk factors (W22) | cut off | Passage ends at "farm i" |
| 37 | DE allowance "flat in Q3, up in nine months" (W47) | right | Passage covers provisions, not the allowance balance |
| 38 | DE allowance decreased in Q1 2026 (W48) | right | Passage is an unrelated table row |
| 39 | DE allowance up on construction accounts (W50) | right | Passage is a fragmentary table |
| 40 | DE allowance flat/up in 2026 (W51) | right | Passage is an aging table for another segment |

**Totals:** right 17 · cut off 12 · too strict 11.

## Fresh runs: 25 random accepted claims

24 correct. One wrong: #23 in the sample (CMG, EPS growth "attributable mainly to… buybacks") was accepted although the sources never give the cause, and the judge rejected two near-identical versions (#3 and #8 above). The judge isn't fully consistent.

## The five sample memos

After the parsing fix, the judge rejects 54 of the 332 published claims that the word check accepted. Read by hand: about 33 right (overstatements such as "sole-source" for a vendor the filing calls "predominant", a proposal stated as done, an allegation stated as fact, claims the cited figures contradict, claims cited to the wrong passage), about 12 cut off, and 9 too strict (common context such as "gasoline is volatile", and objections that argue with the thesis). These memos informed the one revision of the judge's instructions, so they aren't an out-of-sample test; the fresh runs are.
