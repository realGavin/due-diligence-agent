# Meaning-check eval

Runs: `memos_fresh` (fresh memos, generated with the meaning check off; nothing in the judge's instructions was tuned on them).

Judge model: `claude-haiku-5-5`. Word overlap = the cutoff check in `verify.py`. Both run after the code checks (ids, numbers, verbatim quotes). Rerun with `python eval/support_judge.py --offline`.

| Set | Should be | Word overlap | Model judge |
|---|---|---|---|
| published claims | accepted (not flagged in hand review) | 186/186 accepted | 146/186 accepted |
| published claims | rejected (hand-reviewed as wrong) | 0/0 rejected | 0/0 rejected |
| swapped | rejected | 183/186 (98%) | 185/186 (99%) |

## Published claims the judge rejects that hand review hadn't flagged (read each one)

- **CMG** ['S9', 'S37'] · cited passage(s) don't support the claim: The sources confirm the 36.7% and 35.1% digital sales figures and the 257-of-334 Chipotlane openings, but they say nothing about the Rewards program expanding; they only mention Rewards revenue deferrals.
  - Claim: Digital sales, Chipotle's key differentiator, grew to 36.7% of food and beverage revenue in 2025 from 35.1% in 2024, supported by continued Chipotlane buildout (257 of 334 new restaurants opened in 2025 included a Chipotlane) and an expandi
- **CMG** ['S36'] · cited passage(s) don't support the claim: The passage gives 2026 comps guidance of 'about flat,' which is an improvement from the 1.7% decline, and it says nothing about transactions or traffic persisting; the claim that the traffic-driven slowdown will persist and not reverse is not supported and runs against the guidance's direction.
  - Claim: Comparable restaurant sales declined 1.7% in FY2025, driven by a 2.9% drop in transactions only partially offset by a 1.2% increase in average check, and management's 2026 guidance anticipates comps 'about flat' — the traffic-driven slowdow
- **CMG** ['S36', 'F45', 'F11', 'F12'] · cited passage(s) don't support the claim: The sources give the EPS figures, the 2.5% share count decline and flat net income, but never state that the share reduction came from buybacks, which is a causal fact the claim asserts.
  - Claim: Diluted EPS growth of only 2.7% (to $1.14 from $1.11) was driven mainly by a 2.5% reduction in diluted share count from buybacks rather than operating improvement, since net income itself was flat.
- **CMG** ['S24', 'S18'] · cited passage(s) don't support the claim: The passages support the 16% delivery figure, the third-party delivery risks, and the food safety quote, but nothing in them states that Chipotle lacks segment diversification, which is a factual claim the sources don't provide.
  - Claim: Over 16% of 2025 food and beverage revenue came from third-party delivery, a channel the filing flags as exposing Chipotle to platform fee changes and service-quality issues attributed to the brand, and the company states it 'may have highe
- **CMG** ['S36'] · cited passage(s) don't support the claim: The passage supports the flat 2026 comparable sales guidance, but a flat outlook after a 1.7% decline implies improvement, not that the 2025 deceleration will persist; the claim's conclusion reverses that direction.
  - Claim: Management guidance for 2026 anticipates comparable restaurant sales to be about flat, indicating the traffic/comp deceleration seen in 2025 is expected to persist rather than reverse.
- **CMG** ['S18'] · cited passage(s) don't support the claim: The filing says Chipotle 'may have higher risk' than 'some' competitors, a hedged possibility, while the claim states as fact that the practices create higher risk versus competitors, dropping the hedge and the qualifier.
  - Claim: Company-specific food-safety exposure is elevated because Chipotle uses fresh, unprocessed produce, handles raw chicken in-restaurant, and avoids frozen ingredients/artificial preservatives — practices the filing states create higher food-s
- **CMG** ['S18'] · cited passage(s) don't support the claim: The passage supports the food-safety risk factors and the delivery/catering exposure, but it says nothing about a single-format concentration thesis or about the company lacking segment diversification, which the claim relies on as a fact.
  - Claim: The single-format concentration thesis ignores that the format itself carries elevated company-specific food-safety exposure: the filing states Chipotle 'may have higher risk for food safety incidents than some of our competitors' because i
- **CMG** ['S36', 'F11', 'F12', 'F45'] · cited passage(s) don't support the claim: The EPS, net income, and share count figures match the sources, but the sources never attribute the 2.5% share reduction to buybacks and never mention a capital-returns narrative or unit expansion, so those causal and contextual claims are not stated or directly implied.
  - Claim: EPS growth presented as a sign of financial health is largely mechanical: diluted EPS grew only 2.7% (to $1.14 from $1.11) while net income was flat at $1.5B in both FY2024 and FY2025, with the gain attributable mainly to a 2.5% reduction i
- **CMG** ['W60'] · cited passage(s) don't support the claim: The passage is cut off mid-sentence at 'But delive', so it does not show that delivery is still growing year-over-year or that it is growing more slowly than other digital channels, though it does support the Chipotlanes and catering-outcomping parts.
  - Claim: 1,500 Chipotlanes are driving order-ahead behavior, catering is out-comping delivery, and delivery is still seeing growth year-over-year, just not as much as the other digital channels
- **CMG** ['W73'] · cited passage(s) don't support the claim: The passage cuts off at 'After be...' so it only supports the advice to check for and not serve recalled peppers; it does not show that Chipotle and QDOBA stopped serving affected peppers or that CDC and FDA consider there to be no current risk from them.
  - Claim: CDC is advising businesses to check for and not serve recalled jalapeño peppers while the investigation is ongoing, and after being notified, Chipotle and QDOBA stopped serving affected peppers, so CDC and FDA do not consider there to be a 
- **CMG** ['W75'] · cited passage(s) don't support the claim: The passage is truncated before the restaurant location, and it does not mention Roseville, genetic testing, or a multistate outbreak, so those claims cannot be verified; it also presents the symptoms as the woman's own account ('says'), which the claim states as fact.
  - Claim: she fainted, spiked a 102-degree fever, and was hospitalized with sepsis three days after eating a chicken burrito bowl at a Chipotle in Roseville, and genetic testing connected her case to a multistate outbreak
- **CMG** ['W78'] · cited passage(s) don't support the claim: The passage supports the share drop and lack of recovery but never states the date, so the bracketed 'Aug 5, 2026' is an unsupported factual addition (and Aug 5, 2026 falls on a Wednesday, not a Tuesday).
  - Claim: shares of Chipotle tumbled nearly 10% on Tuesday [Aug 5, 2026] and have not recovered
- **CRWD** ['F1', 'F4', 'S47'] · cited passage(s) don't support the claim: The passage gives ARR figures that match the claim, but the only gross profit data is two endpoints, so 'scaled consistently' over the years is not established, and the passage never mentions a land-and-expand model.
  - Claim: Gross profit has scaled consistently from $1.6B (FY2023) to $3.6B (FY2026), and ARR grew 24% YoY to $5.3B in FY2026 with $1.0B of net new ARR added, evidence the land-and-expand subscription model continues to add scale.
- **CRWD** ['F43', 'F28', 'F32', 'S7'] · cited passage(s) don't support the claim: The figures give only the FY2026 long-term debt of $745.5M with no prior-year value, so the claim that debt is 'roughly flat' is not supported by the sources; the passage only mentions the 33 modules and says nothing about R&D funding.
  - Claim: The balance sheet carries low leverage and a large net cash position (-$4.5B net debt in FY2026, cash of $5.2B vs. long-term debt roughly flat near $745.5M), giving flexibility to keep funding R&D and the 33-module platform.
- **CRWD** ['S5', 'S14', 'S9'] · cited passage(s) don't support the claim: The sources support the single sensor, data reuse, and network effect, but nowhere state that the company presents these as a 'durable' competitive advantage; they describe a 'fundamental differentiator' and a 'powerful network effect', so 'durable' is an added attribution.
  - Claim: The business model relies on a single lightweight sensor that ingests data once and reuses it across multiple security modules, feeding an 'AI Security Cloud' that the company claims creates a network effect: more data strengthens AI models
- **CRWD** ['F13', 'F16', 'S7'] · cited passage(s) don't support the claim: The R&D figures are verified and the 33-module platform is in Passage 1, but the passage says nothing about the company emphasizing continuous AI model training, so that part of the claim is unsupported.
  - Claim: R&D spend has scaled aggressively alongside the platform strategy, rising from $608.4M in FY2023 to $1.4B in FY2026, consistent with the company's emphasis on continuous AI model training and expanding its 33-module platform.
- **CRWD** ['S45'] · cited passage(s) don't support the claim: The sources support the commitment-package effects on contraction, upsell, and sales cycles, but they state it is not reasonably possible to quantify the precise impact, which contradicts the claim's 'quantifiable' drag, and they never mention ARR specifically or a comparison to generic competitive risk.
  - Claim: Post-incident customer commitment packages (discounting, extra modules, flexible payment terms, subscription extensions) have resulted in increased contraction and decreased upsell dollar values, and sales cycles have elongated due to delay
- **CRWD** ['F1', 'F4', 'F12', 'F11', 'F10', 'S29'] · cited passage(s) don't support the claim: The sources confirm the net income figures and the $1.3 billion accumulated deficit, and the figures confirm the FY2023 and FY2026 gross profit endpoints, but nothing in the sources shows gross profit rising steadily across the intervening years.
  - Claim: Despite steadily rising gross profit ($1.6B in FY2023 to $3.6B in FY2026), CrowdStrike swung back to a net loss of $162.5M in FY2026 after a $15.2M loss in FY2025 and a rare profitable year of $72.2M in FY2024, with an accumulated deficit o
- **CRWD** ['W6'] · cited passage(s) don't support the claim: The passage confirms the shareholders agreed to drop the derivative action after Judge Pitman dismissed a class lawsuit, but it is truncated and says nothing about whether an appeal was filed or the appeal deadline.
  - Claim: shareholders agreeing to drop the consolidated derivative action after Judge Pitman dismissed the related class lawsuit, with no appeal filed within the statutory deadline
- **CRWD** ['W8', 'W9', 'W10'] · cited passage(s) don't support the claim: The sources confirm the September 14 petition, docket No. 26-355, and the October 16 response deadline for CrowdStrike, but none of the passages name the case as 'del Rio v. CrowdStrike'.
  - Claim: petitioned the Supreme Court on September 14, 2026, in del Rio v. CrowdStrike, No. 26-355, with CrowdStrike's response due October 16
- **CRWD** ['W11'] · cited passage(s) don't support the claim: The passage presents the more-than-$500-million figure as Delta's allegation in its lawsuit, not as an established fact, and the claim states the amount without that attribution.
  - Claim: more than $500 million
- **CRWD** ['W30'] · cited passage(s) don't support the claim: The passage confirms that GAAP operating income, net income, and EPS guidance was not disclosed, but it cuts off mid-sentence before stating anything about gross margin being withheld and never mentions breakdowns by region or product.
  - Claim: guidance for GAAP-based operating income, net income, and EPS has not been disclosed, and guidance for GAAP-based gross margin, capital expenditures, and breakdowns by region or product is also not provided
- **CRWD** ['W33'] · cited passage(s) don't support the claim: The passage confirms that net and gross retention improved sequentially, but it is cut off at 'All-time record n' and never states the quarter, so the all-time record in new-logo net new ARR and the Q2 FY2027 timing cannot be verified.
  - Claim: both net and gross dollar-based retention rates improved sequentially in Q2 FY2027, with all-time record net new ARR from new logos
- **CRWD** ['W50'] · cited passage(s) don't support the claim: The passage confirms the 7%-8% capital expenditure guidance for fiscal 2027 and the focus on scaling cloud architecture, but it cuts off at 'high-s', so the claimed purpose of 'high-speed data processing and real-time analytics' is not stated in the sources.
  - Claim: management anticipates capital expenditures to be 7%-8% of revenue in fiscal 2027, with a primary focus on scaling its cloud architecture for high-speed data processing and real-time analytics
- **DE** ['F16', 'F15', 'F38', 'S4', 'S5'] · cited passage(s) don't support the claim: The figures support the R&D numbers and the passages link R&D to the technology stack, but nothing in the sources mentions a downturn, so the claim that spending was sustained 'through the downturn' rests on an unsupported factual premise.
  - Claim: R&D spend has held at $2.3B (5.1% of revenue) in FY2025, matching FY2024 dollar levels, indicating management is sustaining investment in the Smart Industrial Operating Model's technology stack (automation, connectivity, data platforms) rat
- **DE** ['S6', 'S7'] · cited passage(s) don't support the claim: The sources describe an integrated aftermarket and lifecycle support model aimed at enhancing customer value, but they say nothing about revenue diversification, capturing value, or reduced cyclicality of new-unit sales, which the claim asserts.
  - Claim: Deere's moat extends beyond equipment sales into an integrated aftermarket, parts, and lifecycle services model plus a dealer channel intended to capture value across the full ownership life of equipment, diversifying revenue beyond new-uni
- **DE** ['S9', 'S17'] · cited passage(s) don't support the claim: The 45% PPA share is in Passage 1 and the farm-cash, trade-policy, interest-rate and weather drivers are in Passage 2, but neither source mentions a downturn, a two-year trough, or how long any downturn could last, so that part of the claim is unsupported.
  - Claim: PPA alone represents 45% of equipment operations net sales and is explicitly exposed to farm cash receipts, commodity prices, government trade policy, interest rates, and weather — uncontrollable macro factors that could extend the downturn
- **DE** ['F16', 'F38', 'S4', 'S5'] · cited passage(s) don't support the claim: The sources give the FY2025 R&D figures ($2.3B, 5.1% of revenue) and describe the technology stack and pillars, but nothing in them states that R&D was consistent with FY2024 levels.
  - Claim: Deere is sustaining R&D investment at roughly 5.1% of revenue in FY2025 ($2.3B), consistent with FY2024 levels, underpinning its 'Smart Industrial Operating Model' strategy centered on technology stack investments (hardware, embedded softwa
- **DE** ['S9', 'S17'] · cited passage(s) don't support the claim: The 45% PPA share and the listed exposures to farm cash receipts, commodity prices, trade policy, interest rates and weather are in the passages, but the sources say nothing about a downturn or about the hold thesis's 'two years then recovery' base case, which the claim relies on.
  - Claim: The thesis does not weigh structural concentration risk: PPA alone is 45% of equipment operations net sales and is explicitly exposed to farm cash receipts, commodity prices, government trade policy, interest rates, and weather — uncontroll
- **DE** ['W30'] · cited passage(s) don't support the claim: The passage shows net sales rising 10% (from $4,305M to $4,740M), so describing the change as a decline of 5 to 10% reverses the direction stated in the source.
  - Claim: down 5 to 10%
- **DE** ['W11'] · cited passage(s) don't support the claim: The passage is cut off after 'acreage plant' and mentions only commodity prices and acreage, so the claimed factors of crop yields, government policies, and macroeconomic uncertainty are not in the source.
  - Claim: the agricultural market is affected by various factors including commodity prices, acreage planted, crop yields, government policies, and uncertainty in macroeconomic trends
- **DE** ['W16'] · cited passage(s) don't support the claim: The passage only states that new U.S. tariffs were imposed in 2025 and that other countries retaliated; it says nothing about tariffs affecting product or component costs or continuing into 2026.
  - Claim: in 2025, new tariffs were imposed in the U.S., and incremental import tariffs adversely affected the cost of products and components beginning in 2025 and continue to do so in 2026
- **DE** ['W18'] · cited passage(s) don't support the claim: The passage confirms the $40 billion expectation for 2025 but cuts off at 'with the majority o', so nothing in the sources states that the majority of payments go to row crop producers.
  - Claim: U.S. government support for farmers is expected to exceed $40 billion in 2025, with the majority of payments going to row crop producers
- **DE** ['W19'] · cited passage(s) don't support the claim: The passage cuts off at "provides help with" and never mentions near-term liquidity challenges facing growers, so that part of the claim is not stated or implied by the source.
  - Claim: while farm balance sheets remain healthy, with land values supportive of good debt-to-equity ratios, additional government support provides help with near-term liquidity challenges facing growers
- **DE** ['W21'] · cited passage(s) don't support the claim: The passage is truncated and only supports the claim's opening about stronger farm balance sheets and $10 billion in emergency payments; it says nothing about a poor 2024 crop year, expected farm liquidity or stable crop prices, or tariff mitigation for the rest of 2025.
  - Claim: Deere attributed higher sales, in part, to stronger farm balance sheets as the U.S. government distributes $10 billion in emergency payments to farmers following a poor 2024 crop year, and expected increased farm liquidity and more stable c
- **DE** ['W22'] · cited passage(s) don't support the claim: The passage is cut off after 'farm i' and only states that the agricultural business cycle is unpredictable and affected by factors such as farm income, so the specific factors listed in the claim (international trade, world grain stocks, crop yields, fertilizer, government programs, transport, etc.) are not stated in the source.
  - Claim: risks related to the agricultural business cycle, which can be unpredictable and is affected by factors such as farm income, international trade, world grain stocks, crop yields, available farm acres, soil conditions, prices for commodities
- **DE** ['W47'] · cited passage(s) don't support the claim: The passage reports provision for credit losses as a percentage of receivables and cites elevated delinquencies and market conditions, but it says nothing about the allowance balance remaining flat in Q3 or increasing in the first nine months, nor ties any allowance change to agriculture and turf accounts.
  - Claim: the allowance for credit losses remained relatively flat in the third quarter and increased in the first nine months of 2025, primarily due to higher expected losses on agricultural and turf customer accounts as a result of elevated delinqu
- **DE** ['W48'] · cited passage(s) don't support the claim: The only source passage is a single 2024-10-27 balance of 219 for retail notes and financing leases, with nothing about the allowance for credit losses, any first-quarter 2026 change, or its causes.
  - Claim: the allowance for credit losses on retail notes and financing lease receivables decreased in the first quarter of 2026, primarily due to a decline in the balance of financing receivables
- **DE** ['W50'] · cited passage(s) don't support the claim: The only passage is a fragmentary table showing allowance figures and 'Retail Notes' and 'Revolving' labels, with no mention of construction accounts, the reasons for any change, or a clear slight increase in the second quarter and first six months of 2026.
  - Claim: the allowance for credit losses increased slightly in the second quarter and first six months of 2026 due to higher expected losses on construction retail accounts
- **DE** ['W51'] · cited passage(s) don't support the claim: The passage is a credit quality and aging table for agriculture and turf receivables and does not discuss allowance changes, construction retail accounts, or the drivers of allowance increases in 2025 or 2026.
  - Claim: the allowance for credit losses on retail notes and financing lease receivables remained relatively flat in the third quarter of 2026 and increased slightly in the first nine months of 2026, due to higher expected losses on construction ret

## Published claims hand review flagged that the judge accepts

None.

## Paraphrases the judge wrongly rejects

None.

## Reversals the judge misses

None.

## Swapped citations the judge misses

- **DE** ['W40'] · 
  - Claim: farm income remains pressured, and producers continue to navigate uncertainty around input expenses and crop demand

## A random sample of 25 claims the judge accepts (read each one)

- **DE** ['F32', 'F28', 'S22', 'S23'] · 
  - Claim: The thesis asserts the balance sheet 'strengthened' citing equity up to $25.9B and cash to $8.3B, but this ignores segment-specific risk disclosed in filings: PPA and SAT must finance inventory and dealer sales significantly ahead of season
- **DE** ['W52'] · 
  - Claim: $22,836 million in FY2024 to $25,950 million in FY2025
- **DE** ['W32'] · 
  - Claim: full-year forecast for the segment's operating margin... narrowed and now between 11% and 12%
- **DE** ['W55'] · 
  - Claim: $(3,706) million to $(3,032) million
- **DE** ['W10'] · 
  - Claim: Used combines declined over 10% sequentially in that quarter, a nearly 25% decrease from their spring 2024 peak.
- **CMG** ['W55'] · 
  - Claim: approximately 19% of 2022 food and beverage revenue
- **CMG** ['W54'] · 
  - Claim: approximately 21.5% of total revenue in 2021
- **DE** ['W12'] · 
  - Claim: results support Deere's view that fiscal 2026 represents the bottom of the agricultural equipment cycle, though any recovery in 2027 is expected to be measured rather than sharp.
- **DE** ['W34'] · 
  - Claim: between 14.5% and 15.5%
- **DE** ['W26'] · 
  - Claim: current outlook assumes no further refund activity during the balance of the fiscal year
- **CMG** ['W30'] · 
  - Claim: "the equipment high equipment high equipment package has margin savings that we are reinvesting at present"
- **DE** ['S22', 'S23'] · 
  - Claim: Significant seasonal and early-order-driven production patterns mean the PPA and SAT segments must finance inventory and dealer sales well ahead of seasonal retail demand, creating working-capital and cash-flow timing risk tied to weather-d
- **CRWD** ['W12'] · 
  - Claim: the lawsuit moving into the discovery phase, focused on gross negligence and computer trespass
- **CMG** ['W38', 'W39'] · 
  - Claim: cash-on-cash returns of 50% to 60% for full-volume stores and a payback period of just under two years... suggesting higher returns on investment than most competitive QSR concepts, which tend to see payback in four to six years
- **CMG** ['W29'] · 
  - Claim: approximately 2% full-year pricing in 2026, with the pricing contribution reaching approximately 3% in the fourth quarter
- **CMG** ['F47', 'F48', 'F49', 'F40', 'F41', 'S36'] · 
  - Claim: At current pricing (P/E 31.18x, P/FCF 33.08x, FCF yield 3.0%) the stock embeds continued growth, yet FY2025 revenue growth slowed to 5.4% (vs. 11.4% 3-yr CAGR) alongside negative comparable sales, creating valuation risk if the deceleration
- **CRWD** ['W65'] · 
  - Claim: "$377 million of free cash flow sat beside $399 million of stock compensation and related payroll taxes"
- **DE** ['W49'] · 
  - Claim: the allowance for credit losses decreased in the first quarter of 2026 primarily due to lower Receivables outstanding.
- **CMG** ['W43'] · 
  - Claim: During the first quarter we opened 49 company-owned restaurants, of which 42 included a Chipotlane
- **CRWD** ['W14'] · 
  - Claim: an ending balance of $13,139 thousand
- **CMG** ['S37'] · 
  - Claim: Unit growth continues at scale: 334 company-owned restaurants opened in 2025, with 350–370 planned for 2026 (including 10–15 international partner-operated units), extending the capital-light partner-operated expansion model into new region
- **CRWD** ['W52', 'W53'] · 
  - Claim: CrowdStrike positions itself as mission-critical infrastructure — securing AI across every layer from GPU to agent to prompt — scaling toward a $20 billion ending ARR goal in FY36
- **CRWD** ['S45'] · 
  - Claim: Customer commitment packages introduced after the incident have caused 'increased contraction' and 'decreased upsell dollar values,' and sales cycles 'may be elongated in future periods' — a direct threat to the durability of the land-and-e
- **CMG** ['F11', 'F12', 'S36', 'F45'] · 
  - Claim: Net income was flat at $1.5B in both FY2024 and FY2025 while diluted EPS grew only 2.7% (to $1.14 from $1.11), with the EPS growth attributable mainly to a 2.5% reduction in diluted share count from buybacks rather than operating improvemen
- **CMG** ['S36', 'F4', 'F40'] · 
  - Claim: Comparable restaurant sales decreased 1.7% in FY2025, driven by a 2.9% decline in transactions that was only partially offset by a 1.2% increase in average check — a traffic-driven slowdown that occurred even as total revenue grew 5.4% to $
