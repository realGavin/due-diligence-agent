# Planted-error eval

Source: 5 real runs (ANET, BYND, COST, NKE, NVDA); 440 claims that passed the gate, corrupted and re-checked. Seed 7, no model calls.

Control: 440/440 unmodified claims pass the current gate.

| Corruption | Caught | Rate |
|---|---|---|
| wrong_number | 593/607 | 98% |
| wrong_source (claims with numbers) | 297/305 | 97% |
| wrong_source (qualitative claims) | 0/135 | 0% |
| no_source | 440/440 | 100% |
| phantom_source | 440/440 | 100% |

Qualitative claims (no numbers) with a swapped source pass by design: the gate checks numbers and ids, not meaning. That row is here so the limit is visible.

## Misses (corrupted claims that got through)

- ANET · wrong_number: Extreme customer concentration is the largest company-specific risk: two end customers represented 26% and 16% of FY2025 revenue, with the s ['S28', 'S39']
- ANET · wrong_number: According to BofA's read of the company's 8-K, Microsoft made up 26% of Arista's 2025 revenue, while Meta accounted for 16% ['W27']
- ANET · wrong_number: 67% year over year, translating to roughly $2 billion in incremental revenue for Arista ['W34']
- BYND · wrong_number: $2.5 million in expenses related to the suspension and substantial cessation of the Company's operational activities in China. ['W24']
- BYND · wrong_source (claims with numbers): Gross profit in the third quarter of 2025 was $7.2 million, or gross margin of 10.3%, compared to gross profit of $14.3 million, or gross ma ['W27']
- BYND · wrong_number: $2.4 million in non-cash charges arising from incremental provision for excess and obsolete inventory as a result of SKU rationalization and ['W29']
- BYND · wrong_number: gross profit and gross margin in 2025 included $5.6 million in accelerated depreciation and $0.4 million in inventory write-offs related to  ['W31']
- BYND · wrong_number: on January 10, 2026, a First Supplemental Indenture modified the 2030 Notes Indenture to provide for the guarantee by Beyond Meat BV, secure ['W50']
- BYND · wrong_source (claims with numbers): "an 11.2% decrease in volume of products sold" ['W34']
- COST · wrong_source (claims with numbers): The warehouse model's efficiency depends on carrying fewer than 4,000 active SKUs per warehouse, concentrating reliance on a limited set of  ['S22', 'S1']
- COST · wrong_number: management is targeting 32 net new openings for fiscal 2026, with a longer-term plan of 30-plus annually ['W42']
- COST · wrong_number: 18 Weeks/52 Weeks: Total Company comp 5.7%/6.4% adjusted (Q4), 5.9%/7.6% adjusted (fiscal year). ['W37']
- COST · wrong_number: +9.1% Growth, +7.4% Comparable Sales, +10.1% Adjusted Comparable Sales. ['W38']
- NKE · wrong_number: The 'flat' $46.4B vs $46.3B revenue narrative masks a currency-neutral decline of 2%, with Greater China, Converse, and EMEA each subtractin ['S24', 'F4', 'F3']
- NKE · wrong_source (claims with numbers): traffic in Nike Direct, digital and physical, has softened because "we've lacked newness in product," adding that the retailer has "become f ['W26']
- NKE · wrong_number: a 12% year-over-year decline in Nike Digital sales — the 8th consecutive quarterly decline ['W11', 'W12']
- NKE · wrong_number: a 12% year-over-year decline in Nike Digital sales — the 12th consecutive quarterly decline ['W11', 'W12']
- NVDA · wrong_source (claims with numbers): a handful of Chinese companies have been approved by the U.S. Commerce Department to purchase H200s, including Alibaba, Tencent, ByteDance a ['W39']
- NVDA · wrong_source (claims with numbers): halted production of China-configured H200 units in March 2026 and moved the freed TSMC capacity to Vera Rubin, judging near-term China reve ['W5']
- NVDA · wrong_source (claims with numbers): "the Chinese market could be worth $50 billion per year" ['W11']
- NVDA · wrong_number: incremental annual debt rose from 9% of capex in FY24 to 32% LTM by mid-2026, and equity has now returned to the funding mix: Alphabet price ['W57']
- NVDA · wrong_source (claims with numbers): up to a 10x reduction in cost per token compared to Blackwell ['W25']
