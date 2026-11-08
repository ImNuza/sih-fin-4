# Singapore India Hackathon Notes (Rafael)

> Converted from `rafael-research-notes.docx` (original file name: "Singapore India Hackathon Notes.docx"), shared 8 Nov 2026. Text is unchanged. Only headings and lists were rebuilt. The problem statement extracts (scope, frameworks, case study) are not repeated here: see `docs/problem-statements.md`, section 1.

**Problem statement:** How might we reimagine insurance, powered by data and AI, so that climate risk protection becomes affordable, accessible, and actionable for every vulnerable household and SME in Singapore?

## The hard, valuable problems

1. **Who pays**, which means designing for a payer whose own pain the product fixes.
2. **Does it pay when I'm actually hurt**, which comes down to basis risk, back-testing and honest disclosure.
3. **Can Income run it profitably at scale**, through distribution cost, automated claims, day caps and peril pooling.

## WBGT

WBGT stands for Wet Bulb Globe Temperature, a composite index used in Singapore to measure real environmental heat stress on the human body.

Unlike a standard air temperature reading from a regular thermometer or weather app, WBGT combines four key atmospheric factors into a single measurement:

- Air (Dry-bulb) temperature
- Humidity (Wet-bulb temperature, which affects sweat evaporation)
- Radiant heat (Globe temperature from the sun and surrounding surfaces)
- Wind speed and air movement

## Important Findings

### 1. You can't back-test heat from the WBGT API alone

NEA's WBGT dataset only runs from Feb 2025, reports a 15-minute average, and uses three heat-stress levels: low, moderate and high. That's under two years, while the brief asks for decades of history. Rainfall goes back to Dec 2016 and air temperature to May 2016, so even those are only about 10 years.

**Opportunity:** WBGT is calculated from temperature, humidity, wind and solar radiation. Rebuilding historical WBGT from older weather records is a real, explainable data/AI task, and it makes a strong demo moment. It's also worth checking MSS's historical daily station records for longer runs.

**Plan for gaps:** NEA warns the feed can have gaps from technical problems and may be corrected afterwards. You need a fallback station and a rule like "settle on corrected data after X hours".

### 2. MOM's heat rules mandate rest breaks, not stopping work, and those breaks are paid

At WBGT 32°C and above, employers must give a minimum 10-minute rest break every hour for heavy physical work. Longer breaks are only recommended at higher WBGT, and the 10 minutes must be continuous.

MOM says these rest breaks count as paid working hours.

This reframes the heat problem. For employed construction workers, the employer bears the cost of heat, not the worker. Heat cover for them is really employer productivity cover. The workers who actually lose income to heat are the self-employed, like delivery riders, who aren't employees and get no paid rest. That's your sharpest heat user.

### 3. MOM has already answered the worksite-vs-station gap

Only construction sites with contracts of $5 million or more, shipyards and the process industry need their own WBGT meter. Everyone else is told to use the WBGT readings in NEA's myENV app. So using NEA station readings as your trigger is the same reference regulators already accept.

### 4. Flood is a small, short peril in Singapore

- Flood-prone areas have shrunk about 99%, from roughly 3,200 hectares in the 1970s to under 25 hectares today.
- Flash floods are small, localised and usually last under an hour.
- PUB's Feb 2026 hotspot list has 19 locations, mostly road junctions and stretches, not housing estates.

## Pain Points

### Layer 1: The end user's pain

For each segment, the underlying need is liquidity at the moment of loss, not "insurance":

- **Platform and outdoor workers** face a forced choice between safety and income. When WBGT spikes or haze rolls in, stopping work means losing the day's pay. The new MOM heat-stress rules (mandatory from 1 Dec 2026) turn that into a formal, recurring income loss, and work-injury compensation doesn't cover it. Their job-to-be-done is being able to stop without missing rent.
- **Hawkers and small shops** lose revenue with no physical damage. Haze empties hawker centres and heavy rain kills footfall, but rent, staff and spoiling stock keep costing money. Their buffers are thin, so a bad week becomes a bad month. Today's products, including SmartBiz360, only pay business interruption if something physically broke.
- **Renters, seniors and lower-income households** in flood-prone areas usually don't buy voluntary home contents cover at all. Their pain is fast cash to recover in the first few days after an event.

The detail that matters for your product is timing. Money six to eight weeks later (as with SEWA) solves a different, lesser problem than money today.

### Layer 2: The demand problem

This is where almost every case in the brief died:

- **People won't pre-pay for a maybe.** Present bias beats probabilistic loss. Delhi workers wouldn't pre-pay, and KB Insurance had zero subscribers in ten months. Low-income users prioritise today's bills.
- **If it doesn't pay, it feels like a scam.** A first season with no payout (SEWA 2023, ZhongAn) breaks trust permanently. When your street flooded but the gauge two kilometres away didn't trigger, it feels like being cheated, and that is basis risk. China's regulator saw it as gambling.
- **Salience is backwards.** People only think about cover when the storm is forecast, which is exactly when an insurer can't sell it.

The real question here: who pays, and why would they? The answer is often not the beneficiary. A platform, employer, union or lender pays only if the product solves their own pain:

| Payer | Their pain |
|---|---|
| Platform | Rider retention, PR exposure, heat-rule pressure |
| Employer | Compliance costs from mandatory rest breaks |
| Union (NTUC) | Showing member value |
| Lender | Repayment defaults after bad-weather weeks |

### Layer 3: Income's own pain

Income is the actual customer of this hackathon, and it has business problems:

- **Unit economics.** The brief caps expenses at about 20% of premium. On a S$1-a-week product, a traditional agent sale or a manual claim wipes out the margin. Income needs near-zero-cost acquisition and servicing, which pushes toward embedded or group distribution and automated payouts.
- **Correlated catastrophe risk.** Haze hits every customer on the same day. One bad season can blow through capital, as in Haiti and MiCRO's 100% claims ratio. "Uninsurable" in the brief means this.
- **Claims operations that can't surge.** Loss adjusters don't scale when the whole island floods at once.
- **Regulatory and reputational exposure.** MAS fair-dealing, FEAT and insurable-interest rules apply. Income is NTUC's social enterprise, so a product that looks like gambling, or fails union members in their first season, is a brand risk, not just a product failure.
- **A product-line gap they've already named.** SmartBiz360 launched in October 2026 without non-damage business interruption cover. Droplet showed they'll try parametric, but it stayed niche. They want a scalable version.
- **No more subsidy dependency.** SEWA still relies on donors. "No permanent subsidy" means Income wants something that sustains itself commercially.
