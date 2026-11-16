# Planted-error eval

Source: 5 real runs (ANET, BYND, COST, NKE, NVDA), 440 unique claims. Seed 7, no model calls.

## What the gate catches

Corruptions are applied to the 427 claims that pass the current gate. *Before* is the numbers-and-ids gate alone; *after* adds the support check (a direct quote must appear in the cited passage; a qualitative claim must share enough of its distinctive words with the passages it cites, cutoff 20%).

| Corruption | Before | After |
|---|---|---|
| wrong_number | 584/599 (97%) | 584/599 (97%) |
| wrong_source (claims with numbers) | 299/304 (98%) | 300/304 (99%) |
| wrong_source (qualitative claims) | 0/123 (0%) | 111/123 (90%) |
| no_source | 427/427 (100%) | 427/427 (100%) |
| phantom_source | 427/427 (100%) | 427/427 (100%) |

## What it rejects in the published memos

Of the 440 claims in the published runs that passed the original gate, the support check rejects 13. Each one was read against its cited passage; see the list below. The PM's thesis and verdict rationale summarize findings that already passed the gate, so they get the quote check but not the word-overlap check.

| Hand review | Claims |
|---|---|
| wrong passage: the claim's content isn't in it | 6 |
| can't verify: the quote runs past where the stored passage was cut off | 4 |
| misquote: two sentences spliced into one quote, with added words | 1 |
| misquote: the quoted words aren't in the passage | 2 |

- *wrong passage: the claim's content isn't in it* · **ANET** ['W7'] · claim isn't supported by the cited passage(s) (word support 8%)
  - Claim: linked to Broadcom, which is Arista's primary chip source as it builds its platforms on top of Broadcom's Jericho and Tomahawk Ethernet chips
- *can't verify: the quote runs past where the stored passage was cut off* · **ANET** ['W9'] · quote “the semiconductor side in particular, the merchant silicon v” is not in the cited passage(s)
  - Claim: "the semiconductor side in particular, the merchant silicon versus in-house silicon isn't actually the big issue because the bottleneck isn't the chip designer, the bottleneck is the fab"
- *can't verify: the quote runs past where the stored passage was cut off* · **ANET** ['W18'] · quote “the CFO attributed 20 to 30 basis points of the result versu” is not in the cited passage(s)
  - Claim: "the CFO attributed 20 to 30 basis points of the result versus guidance to a tariff refund, and management says price increases do not reach reported margin until late 2026 or 2027."
- *wrong passage: the claim's content isn't in it* · **ANET** ['W26'] · claim isn't supported by the cited passage(s) (word support 3%)
  - Claim: product deferred revenue qualification cycles have extended from two to four quarters to six to even eight quarters, due to customer acceptance pieces and new product testing requirements
- *wrong passage: the claim's content isn't in it* · **ANET** ['W48'] · claim isn't supported by the cited passage(s) (word support 0%)
  - Claim: Arista has three contract manufacturers and three distribution facilities across the U.S., Asia and Mexico
- *wrong passage: the claim's content isn't in it* · **BYND** ['W52'] · claim isn't supported by the cited passage(s) (word support 9%)
  - Claim: prior to obtaining stockholder approval, the Company was permitted to satisfy conversion obligations only via cash settlement
- *misquote: two sentences spliced into one quote, with added words* · **BYND** ['W35'] · quote “primarily driven by weak category demand, in the U.S. retail” is not in the cited passage(s)
  - Claim: "primarily driven by weak category demand, in the U.S. retail and foodservice channels... by reduced points of distribution in the U.S. retail channel and by lower sales of burger products to QSR customers in the interna
- *can't verify: the quote runs past where the stored passage was cut off* · **BYND** ['W36'] · quote “stocking activity in the year ago period in anticipation of ” is not in the cited passage(s)
  - Claim: "stocking activity in the year ago period in anticipation of potential tariffs."
- *misquote: the quoted words aren't in the passage* · **BYND** ['W42'] · quote “losing ground more slowly” is not in the cited passage(s)
  - Claim: "losing ground more slowly"
- *wrong passage: the claim's content isn't in it* · **COST** ['W17'] · claim isn't supported by the cited passage(s) (word support 4%)
  - Claim: This was driven by higher sales penetration in e-commerce and pharmacy, partially offset by a lower gross margin rate in gas
- *can't verify: the quote runs past where the stored passage was cut off* · **NKE** ['W36'] · quote “we are moving quickly against Greater China commerce and spo” is not in the cited passage(s)
  - Claim: "we are moving quickly against Greater China commerce and sportswear... We have new leaders in place"
- *wrong passage: the claim's content isn't in it* · **NKE** ['W25'] · claim isn't supported by the cited passage(s) (word support 3%)
  - Claim: the actions taken in Q3 and Q4 were the initial steps of reducing the number of facilities Nike operates, changing the size of its workforce, and changing how it flows product from factory to retail, with those costs lar
- *misquote: the quoted words aren't in the passage* · **NVDA** ['W71'] · quote “If the demand environment changes, you just slow down what i” is not in the cited passage(s)
  - Claim: the largest component of capex has shifted toward shorter-lived assets like CPUs and GPUs — "If the demand environment changes, you just slow down what is, in fact, the largest component."

## Choosing the cutoff

Qualitative factual claims citing passages, as published (134). *Swaps caught* is the wrong-source corruption on the claims that pass at the default cutoff. *Published claims rejected* is how many unmodified claims each cutoff drops, including quote failures, which don't depend on the cutoff. At the default, every one of them is in the hand-reviewed list above; stricter cutoffs start dropping claims that are genuinely supported. The cutoff was picked on these same five runs, so treat the table as a description of this data, not an out-of-sample result.

| Cutoff | Swaps caught | Published claims rejected |
|---|---|---|
| 10% | 89/122 | 12/134 |
| 15% | 98/122 | 12/134 |
| 20% | 111/122 | 12/134 |
| 25% | 114/122 | 14/134 |
| 30% | 118/122 | 14/134 |
| 40% | 119/122 | 22/134 |

The check verifies that a claim and its passage are about the same thing, not that the passage says what the claim says: a claim that reuses the passage's words and gets it wrong still passes.

## Misses (corrupted claims that got through the new gate)

- ANET · wrong_number: Extreme customer concentration is the largest company-specific risk: two end customers represented 26% and 16% of FY2025 revenue, with the s ['S28', 'S39']
- ANET · wrong_number: According to BofA's read of the company's 8-K, Microsoft made up 26% of Arista's 2025 revenue, while Meta accounted for 16% ['W27']
- ANET · wrong_number: 67% year over year, translating to roughly $2 billion in incremental revenue for Arista ['W34']
- ANET · wrong_source (qualitative claims): has used merchant silicon since its founding and continues to work with Broadcom and other suppliers on advanced platforms, including Tomaha ['W8']
- ANET · wrong_source (qualitative claims): management also highlighted supply‑chain inflation and tighter memory and silicon markets as ongoing headwinds, which could further pressure ['W7']
- ANET · wrong_source (claims with numbers): Management confirmed one, possibly two new 10% customers — widely expected to be Google and Oracle — joining the roster alongside Meta and M ['W33']
- BYND · wrong_number: The balance sheet was genuinely de-risked (long-term debt cut from $1.1B to $415.7M, equity improved to -$997,000, net debt at $211.8M) and  ['F35', 'F36', 'F39', 'F40', 'F54', 'F55', 'F44', 'F4', 'F50', 'F12', 'F24', 'S37']
- BYND · wrong_number: on January 10, 2026, a First Supplemental Indenture modified the 2030 Notes Indenture to provide for the guarantee by Beyond Meat BV, secure ['W50']
- BYND · wrong_source (qualitative claims): Upon effectiveness, conversion rates of the 2030 Notes and 2027 Notes, the number of shares issuable upon exercise of outstanding warrants a ['W55']
- COST · wrong_number: Structurally thin margins (3.8% operating, 2.9% net) leave the model exposed to cost shocks: compensation and benefits are the largest expen ['F37', 'F38', 'S30', 'S8']
- COST · wrong_source (claims with numbers): Gasoline sales represented approximately 10% of total net sales in 2025, creating a concentration exposure to volatile fuel commodity prices ['S22', 'S10']
- COST · wrong_source (qualitative claims): Nov. 1, 2011 ['W17']
- COST · wrong_source (claims with numbers): U.S. and Canada members renewed at 92.1%, down just 10 basis points versus the prior year ['W63']
- COST · wrong_source (qualitative claims): core‑on‑core margins slipped 9 basis points as Costco invested in lower everyday prices on staples like eggs and beef and saw a mix shift to ['W67']
- COST · wrong_source (qualitative claims): comparable sales and comparable sales excluding impacts from changes in gasoline prices and foreign exchange are intended as supplemental in ['W38']
- COST · wrong_number: management is targeting 32 net new openings for fiscal 2026, with a longer-term plan of 30-plus annually ['W42']
- COST · wrong_number: traffic improved 3.1% worldwide and 2.6% in the United States, while the average transaction or ticket increased 2.6% both globally and in t ['W35']
- COST · wrong_number: net sales for the 52-week fiscal year ended August 30, 2026 were $297.3 billion, up 10.2%; comparable sales for the fiscal year were U.S. 6. ['W40']
- NKE · wrong_source (qualitative claims): The balance sheet is genuinely conservative and the tariff overhang looks largely resolved, but the reversal in cash-conversion quality (OCF ['F24', 'F41', 'F18', 'S26', 'S44', 'S48']
- NKE · wrong_number: Operating cash flow generation has weakened materially, falling from $7.4B in FY2024 to $3.7B in FY2025 and $2.9B in FY2026, while the compa ['F14', 'F15', 'F16', 'S35']
- NKE · wrong_number: NIKE Direct, particularly NIKE Brand Digital, is contracting as the company deliberately repositions Digital as a full-price platform: NIKE  ['S27']
- NKE · wrong_number: The thesis treats the 12% Digital decline as 'deliberate,' but the filing attributes NIKE Brand Digital's decline explicitly to 'reduced tra ['S27']
- NKE · wrong_source (qualitative claims): management expects digital traffic to decline double-digits in fiscal 2026 ['W42']
- NKE · wrong_source (claims with numbers): a 12% year-over-year decline in Nike Digital sales — the 10th consecutive quarterly decline ['W25', 'W29']
- NVDA · wrong_number: Gross margin compression from the $4.5B H20 charge and the Hopper-to-Blackwell mix shift, plus a widening unfavorable inventory-provision im ['S26', 'S30', 'S45', 'S18']
- NVDA · wrong_source (qualitative claims): The business is organized into two reportable segments: Compute & Networking (Data Center accelerated computing/AI, networking, and Automoti ['S35', 'S25']
- NVDA · wrong_source (qualitative claims): Hood guided full-year operating margins down less than 1 point and said Microsoft expects to remain free cash flow positive in FY27 ['W65']
- NVDA · wrong_source (qualitative claims): in fiscal year 2026, NVIDIA unveiled the Rubin platform, which is expected to commence production shipments in the second half of fiscal yea ['W35']
- NVDA · wrong_source (qualitative claims): production hardware delivered to partners in time for them to offer products and services in the second half of 2026 ['W63']
- NVDA · wrong_number: running GPT-4.0 and GPT-4 inference on MI300X through ONNX Runtime with no CUDA dependency ['W41']
- NVDA · wrong_number: exceeding 90%, while inference is 90-75% due to custom silicon and CPU competition ['W48']
