# Planted-error eval

Source: 3 real runs (ANET, COST, NVDA); 122 claims that passed the gate, corrupted and re-checked. Seed 7, no model calls.

Control: 120/122 unmodified claims pass the current gate. The other 2 were accepted by the older gate that produced these runs and are now rejected (listed below); they are excluded from the corruption trials.

| Corruption | Caught | Rate |
|---|---|---|
| wrong_number | 197/202 | 98% |
| wrong_source (claims with numbers) | 102/102 | 100% |
| wrong_source (qualitative claims) | 0/18 | 0% |
| no_source | 120/120 | 100% |
| phantom_source | 120/120 | 100% |

Qualitative claims (no numbers) with a swapped source pass by design: the gate checks numbers and ids, not meaning. That row is here so the limit is visible.

## Claims the older gate wrongly accepted

- COST: number '14' not supported by cited evidence ['S29', 'S1'] · International renewal rates are meaningfully weaker than the U.S./Canada core (89.8% worldwide vs. 92.3% U.S./Canada), and as the company ex
- COST: number '14' not supported by cited evidence ['S29', 'S1'] · As Costco continues international expansion (914 warehouses across 14 countries/territories, up from 861 two years prior), the weaker 89.8% 

## Misses (corrupted claims that got through)

- ANET · wrong_number: Arista's software-enabled networking platform delivered 28.6% YoY revenue growth to $9.0B with 64.1% gross margin, 42.8% operating margin, a ['F46', 'F4', 'F41', 'F42', 'F49', 'F48', 'F45', 'F36', 'S28', 'S39', 'S24', 'S31', 'S48', 'F28', 'F27', 'S44']
- COST · wrong_number: Ancillary businesses—gasoline (approximately 10% of total net sales in 2025, operated through 747 gas stations), e-commerce (approximately 1 ['S8', 'S9', 'S10']
- COST · wrong_number: Compensation and benefits is Costco's largest expense after merchandise cost, covering 341,000 employees worldwide with roughly 4% unionized ['S30', 'F37']
- COST · wrong_number: Gasoline, a low-margin and price-volatile category, represented approximately 8% of total net sales in 2025; large swings in fuel prices cou ['S23', 'F40']
- COST · wrong_number: The thesis acknowledges labor risk but understates its bite: compensation and benefits is explicitly Costco's largest expense after merchand ['S30', 'F37']
