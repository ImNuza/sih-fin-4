# Explainability and FEAT fairness check (15 Nov 2026)

Deliverable #8 of the brief asks how AI and data are used, and the brief's must-haves say "any AI
decisions must be explainable". Its constraint adds that pricing must not price out the groups
that most need cover. MAS's FEAT Principles (Fairness, Ethics, Accountability, Transparency in
the use of AI and data analytics, November 2018) ask that a model does not systematically
disadvantage a group without a justification, and that customers can get an explanation.

## 1. Explainability: every quote now says why it costs what it costs

`POST /api/quote` now returns, for every quote (code: `premium_build_up` and `quote` in
`api/calculator.py`):

- `loss_day_parts`: days of full loss in an average year, per hazard (haze, rain, heat, flood,
  closure). They add up to `expected_loss_days`.
- `product_factor`: the share of a bad day's normal sales the product loses for good.
- per tier, `build_up`: expected payouts, the 15% uncertainty load, the 10% catastrophe load, the
  insurer's 25% expenses and 9% GST. The steps add up to the yearly premium to the cent.

No price moved: all 120 region-product-tier prices are the same before and after the change.

The buy flow (`/buy/`, Cover step) shows this as "Why this price?" in plain words, and says that
no personal data goes into the price. The price is a public formula over public NEA data. There
is no AI model in the price or in the payout trigger. The only AI step is the shop reader on the
map, which suggests a product and a place, and the owner confirms both.

## 2. Fairness: how far the same cover's price moves between places

`uv run scripts/feat_price_spread.py` prices every product and tier in the 5 PSI regions and at
each of the 103 hawker centres, from each centre's own nearest stations and its own PSI region.
Since Deval's commit `16ec056`, that centre price is what a hawker is charged
(`business_quote` in `api/main.py`). A shop pays its postcode area's price, and a platform
worker pays its region's price. Output:
`data/processed/price_spread.csv`. Rent is the median NEA cooked-food bid per centre
(`data/processed/hawker_rent.csv`, 81 centres with bids), used as a rough stand-in for how well
off a centre's stallholders are.

Tier 1, weekly premium in SGD:

| Product | Region cheapest to dearest | Centre cheapest | Centre median | Centre dearest | Dearest / cheapest centre |
| --- | --- | ---: | ---: | ---: | ---: |
| Cooked food | 3.63 to 6.57 | 2.85 | 3.98 | 6.99 | 2.45 |
| General goods | 0.39 to 0.71 | 0.30 | 0.43 | 2.12 | 7.07 |
| Platform work | 1.52 to 2.76 | 1.19 | 1.67 | 6.99 | 5.87 |

Cooked food at Tier 4: centres run from S$14.25 to S$98.20 a week (6.89 times), median S$19.88.

Findings:

1. **Hawkers see the centre spread.** Cooked food Tier 1 runs from S$2.85 to S$6.99 a week at the
   103 centres (2.45 times). Tier 4 runs from S$14.25 to S$98.20 (6.89 times). Between regions,
   which platform workers pay, prices differ 1.8 times.
2. **Most centres would pay less at their own place.** The median centre price is 0.76 of its
   region's price, for every product. The region price pools the region's riskiest stations.
3. **One centre is far above its region.** Telok Blangah Rise Blk 36 is the dearest centre for
   every product and tier except cooked food Tier 1. Its price is 2.99 times its region's for general goods and
   cooked food at Tier 4. Of its 3.04 loss-days a year (general goods), 2.52 come from heat at one
   WBGT station, S142, which gets 98.7% of the weight (`local_risks` in its place quote).
4. **A short station history gets a high weight.** Commonwealth Crescent Market's heat station,
   S138, has 73 days of readings in the price history and still gets 92.9% of the weight. The
   credibility formula gives a station high weight when stations in a region differ a lot, even
   with little history.
5. **Many cooked-food premiums are above the yearly cap.** At Tier 1, 59 of the 103 centres pay
   more a year than the S$200 the tier can ever pay out. At Tier 2, 9 centres pay more than
   S$600. Tier 3 and Tier 4 have 1 centre each (Telok Blangah Rise). An average year at these
   centres uses nearly all of the tier's capped days, and the loads, expenses and GST come on
   top. A customer there pays more than SafeDay can pay back
   (`centres_premium_over_yearly_cap` in `price_spread.csv`). In region prices, cooked food Tier 1
   is above the cap in 4 of 5 regions (south: S$341.61 a year).
6. **Lower-rent centres pay slightly more.** The rank correlation between centre price and rent is
   -0.16 to -0.17. For cooked food Tier 1, the lowest-rent quarter's median is S$4.22 a week and
   the highest-rent quarter's is S$3.80 (11% more). The link is weak, and it comes from place
   weather, not from who the customer is.
7. **Heat drives the spread, and heat is the noisiest trigger.** The basis-risk note
   (`docs/notes/basis-risk-2026-11-15.md`) shows that WBGT stations rarely agree on hours at 32 °C
   or more. So a price that follows one station's heat readings follows noise as much as risk.

## 3. Recommendations (no change made to the product)

1. Fix the premiums above the yearly cap before the deck. Options: more capped days for Tier 1
   and Tier 2, or no sale of a tier where its premium passes its cap. A judge will ask why
   anyone buys cover that costs more than it can pay.
2. Cap a centre's premium at 1.5 times its region's. Today that touches one centre (Telok
   Blangah Rise) for every product and tier except cooked food Tier 1.
3. Before a station's heat readings drive a place price, require a minimum history (for example
   one full year), or price heat from the region. This also answers finding 4.
4. Show the "Why this price?" build-up in the deck as the answer to "explainable". It is a formula
   anyone can check, with no personal data and no AI in it.

These touch pricing, so they go to Deval's "SafeDay pricing for review" page before any change.
