# Location pricing and perishable stock: how others do it (14 Nov 2026)

Notion todo: revisit location-sensitive pricing weights and the perishable-goods factor (perishables as inventory, not hard assets). This note collects how insurers and other countries handle both, with sources, before we change the pricing API.

No machine learning model is needed for either. Both are standard pricing calculations from historical data. A model only helps later, to estimate how much sales fall on a bad day, once we have real sales data (POS or platform).

## 1. Location: how insurers price by place

### The textbook method (property and motor insurance)

Werner and Modlin, *Basic Ratemaking*, 5th ed., Casualty Actuarial Society, 2016, ch. 11 "Territorial ratemaking" (pp. 188–190) and ch. 12 "Credibility" (pp. 220–221) ([PDF](https://casact.org/library/studynotes/Werner_Modlin_Ratemaking.pdf)):

- **Postal codes as units.** Price each small geographic unit, using "postal/zip codes, counties, census blocks". The unit should be "relatively homogenous … while still having some observations in most units".
- **Weather is a valid input.** Geographic risk includes "weather indices" and "average rainfall".
- **Small areas are noisy, so smooth them.** Two kinds of spatial smoothing:
  - Distance-based: weight nearby units by distance and credibility. The book says this "tends to be most appropriate for weather-related perils".
  - Adjacency-based: suited to perils driven by people, such as theft.
- **Credibility weighting** (Bühlmann): estimate = Z × own experience + (1 − Z) × prior mean, with Z = N ÷ (N + K). N is the number of observations. K is the ratio of the variance within a unit to the variance between units.

### How other countries' weather and parametric schemes do it

| Scheme | How location changes the cover | Source |
|---|---|---|
| World Bank guidance for weather index insurance | Premium = expected loss + risk margin + admin costs, with expected loss from the history at each station. Ideally 30 years of daily data. "There is no standard radius of insurable area around a weather station." | World Bank, *Weather Index Insurance for Agriculture*, 2011, Box 4.2 and Box 5.3 ([PDF](https://documents1.worldbank.org/curated/en/590721468155130451/pdf/662740NWP0Box30or0Ag020110final0web.pdf)) |
| India, Restructured Weather Based Crop Insurance Scheme | Each "Reference Unit Area" is tied to a "Reference Weather Station" and has its own actuarial rate. Farmers pay a capped share (2% Kharif, 1.5% Rabi, 5% commercial crops). Central and state governments subsidise the rest. | CAG audit report 7 of 2017, appendices ([PDF](https://cag.gov.in/uploads/download_audit_report/2017/Appendices%20of%20Report%20No.7%20of%202017%20-%20Performance%20audit%20Union%20Government%20Agriculture%20Crop%20Insurance%20Schemes%20Reports%20of%20Agriculture.pdf)), [RWBCIS summary](https://journalsofindia.com/restructured-weather-based-crop-insurance-scheme-rwbcis/?print=pdf) |
| Kenya, Index-Based Livestock Insurance | Premium differs by division. Actuarially fair rates ran from about 7% to 12.25% of cover across four divisions. | Jensen and Barrett, ILRI slides, 2014 ([link](https://es.slideshare.net/ILRI/barrett-ibli-june2014)) |
| Caribbean, Livelihood Protection Policy (CCRIF) | The **trigger** is set per location from that location's own rainfall history. The **premium** is a flat 11.5% of cover everywhere. | CCRIF LPP [how it works](https://ccriflpp.ccrif.org/how-it-works), Jamaica Q&A, Jan 2026 ([PDF](https://ccriflpp.ccrif.org/sites/default/files/lpp_publications/Jamaica_LPP_QandA_January2026.pdf)) |
| Weather index research | Price each station in a network the same way and compare. Spatial basis risk (station weather ≠ site weather) grows with distance. | Norton, Osgood and Turvey, AAEA 2010 ([PDF](https://ageconsearch.umn.edu/record/61734/files/Norton%20Osgood%20Turvey.Weather%20Index%20Insurance%20and%20the%20Pricing%20of%20Spatial%20Basis%20Risk%20_AAEA2010_.pdf)) |
| Descartes (parametric business interruption) | Price reflects "sector, location, built environment, risk mitigation measures". No public formula. | [Descartes PDBI](https://descartesunderwriting.com/solutions/property-damage-business-interruption-pdbi) |

So there are two working designs:

- **A. The price follows the location** (textbook, India, Kenya). The trigger is the same everywhere, and riskier places pay more.
- **B. The trigger follows the location** (Caribbean). Each place's trigger is set so it fires about equally often, and everyone pays the same price.

### Why it matters in Singapore

Trigger rates differ a lot between stations in the same region:
- **Data:** NEA gauges with a year or more of data and WBGT stations with 180 days or more, through 8 Nov 2026.
- **Script:** `scripts/region_hazard_readings.py` readings, analysed in this session. Not yet a repo script.

| Hazard | Region | Lowest station | Highest station |
|---|---|---|---|
| Rain: an hour of 20 mm or more in work hours | South | 2.7% of days | 7.4% of days |
| Heat: 2+ work hours at WBGT 32°C or more | South | 0% | 34.4% (Sentosa) |

Pricing by region, as the API does today, charges all of these stalls the same.

### Proposed method for SafeDay (design A)

1. The customer gives a postal code. OneMap turns it into coordinates.
2. Look up the nearest 3 rain gauges (median, matching the trigger rule in Bhoomi's doc), the nearest WBGT station, and the PSI region.
3. Use each station's trigger rate, blended with its region's rate by credibility: Z = N ÷ (N + K), with N = days of data. K is estimated from the spread within and between regions, as Werner and Modlin describe.
4. For flood, use PUB's list of flood-prone areas ([Nov 2025 PDF](https://www.pub.gov.sg/-/media/PUB/PDF/Flood-Management/List-of-Flood-Prone-Areas-as-at-Nov-2025.pdf)), until PUB shares its water level history.
5. Cap the price spread between areas. This follows MAS FEAT ("must not price out the groups that most need cover") and Bhoomi's doc ("zone price cap").

## 2. Perishable stock: inventory, not hard assets

### How business interruption insurance measures lost income

UK-form business interruption cover pays lost **gross profit**. Policies define it as turnover less purchases, stock movement and "uninsured working expenses", which are "true variable costs, i.e. costs that vary directly with turnover". The US form ("gross earnings") is similar. Source: Marsh, *Gross Profit – UK vs Gross Earnings – US*, 2012 ([PDF](https://www.marsh.com/content/dam/marsh/Documents/PDF/UK-en/gross%20profit%20vs%20gross%20earning%2005-2012.pdf)).

Purchases are taken out because a business that sells less buys less. That holds for dry goods. It doesn't hold for perishables already bought for the day: that stock is lost too.

### How insurers cover spoiled stock

Spoiled stock is a **separate cover**, "Deterioration of Stock", usually tied to refrigeration breakdown or power failure. Zurich UK notes that standard commercial policies "might not cover the value of stock lost". Sources:
- [Zurich UK](https://www.zurich.co.uk/broker/articles/deterioration-stock-cover-explained)
- [Zurich Malaysia](https://zurich.com.my/insurance-products/business/for-my-assets/engineering/deterioration-of-stocks-insurance)
- [Munich Re](https://www.munichre.com/specialty/global-markets-uk/en/solutions/construction-engineering-insurance/deterioration-of-stock-insurance.html)

Hard assets (the stall, equipment) are property cover, which Income already sells through Stallholder Insurance and SmartBiz 360. SafeDay must not pay for them.

### Proposed loss per bad day

Per S$1 of a normal day's sales:

**loss = demand drop × [margin × (1 − recovered share) + waste share × (1 − margin)]**

- **margin × (1 − recovered share):** lost gross profit on sales that never come back. This is the business interruption part.
- **waste share × (1 − margin):** the cost of stock that spoils before it can be sold. This is the deterioration-of-stock part. Waste share = restock days ÷ shelf life, at most 1, as in today's API.
- **Hard assets:** not in the formula.

**Margins from SingStat**, *Annual Survey of Services*, data.gov.sg datasets [d_38d62de582eb7ee2c58d1bba4cd4132d](https://data.gov.sg/datasets/d_38d62de582eb7ee2c58d1bba4cd4132d/view) (revenue by industry) and [d_4eb10d0ef99e56c2336c37d78b10c6bc](https://data.gov.sg/datasets/d_4eb10d0ef99e56c2336c37d78b10c6bc/view) (operating expenditure). 2024, S$ million:

| Industry | Operating revenue | Purchases of goods and materials | Purchases ÷ revenue | Margin used |
|---|---|---|---|---|
| Food & beverage services (SSIC 56) | 20,333.8 (accommodation & food 30,220.5 minus hotels 8,327.5 and other accommodation 1,559.2) | 6,688.7 | 32.9% | 0.67 |
| Retail trade (SSIC 47) | 55,012.8 | 37,387.4 | 68.0% | 0.32 |

Caveat: these are industry averages. SingStat's F&B Services Index excludes hawker stalls, and we haven't confirmed whether the annual survey includes them.

**Effect on today's products**, using the tariff's demand drop and waste share. Recovered share is 0 for cooked food (a meal not sold today is never sold later) and 0.5 for the rest, as now:

| Product | Waste share | Margin | Factor today | Factor with the new formula |
|---|---|---|---|---|
| Cooked food | 1.00 | 0.67 | 1.00 | 1.00 |
| Fresh produce | 0.33 | 0.32 | 0.60 | 0.35 |
| Flowers | 0.60 | 0.32 | 0.64 | 0.45 |
| Packaged food | 0.04 | 0.32 | 0.31 | 0.11 |
| General goods | 0.08 | 0.32 | 0.27 | 0.11 |

Today's formula treats a lost sale as a lost S$1, so it overstates the loss for anyone who can sell the stock later. The new one counts only what is really gone: the margin, plus the cost of stock that spoils.

## Still assumed, with no source yet

- **Demand drop per product** (1.0, 0.9, 0.8, 0.6, 0.5) and **recovered share** (0 or 0.5). These are the hazard "weights" problem: they need sales data to estimate. Possible sources: platform or POS data, or SingStat's monthly F&B and retail indices around past haze months, which are too coarse to be more than a sanity check.
- **K for credibility.** It can be estimated from our own station data, so this one doesn't need an outside source.
- **Business types.** They should follow SSIC codes, as decided in the meeting with Ashutosh on 14 Nov.
