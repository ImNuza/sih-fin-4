# Payung: parametric sales research (tier, premium, payout design)

Date: 2026-11-15
Scope: web research only. No code changed.
Product: Payung, weather income cover for Singapore hawkers, shops and platform workers. Pays a fixed daily amount on bad days (haze PSI, heavy rain, heat WBGT), up to a yearly day cap. Weekly premium of a few Singapore dollars. Proposed to Income Insurance.

Reading rules for this file:
- "Verified" means I read the page text in full or the relevant passage.
- "Snippet only" means I saw only the search-result excerpt. The page was blocked or not fetched.
- "Team assumption" means a number I derived or chose. It has no source.
- Where I did not find a source, I say so.

---

## 0. Short answer

1. Real microinsurance loss ratios are low. The MiN median claims ratio was 15% in 2020. Practitioners call 45-70% good value. Payung can aim at 55-70% of net premium.
2. Weather cover with frequent triggers cannot have a big "cover multiple". The best close comparable (SEWA heat cover, 2024) had a maximum payout of only 2.75 times the annual premium. Premium was 36% of the maximum.
3. Payout in a year raises renewal. Evidence: one rainfall-index study (India) and one Mali study (snippet only). SEWA's first year had no trigger at all.
4. Singapore buyers already see daily-price framing: Income says "from $0.30 per day" (Stallholder) and "from $0.64 a day" (PA Assurance).
5. Recommendation: 3 tiers, premium at 33-45% of the yearly maximum payout, expected loss ratio 55-70% on net premium, 65-80% chance of at least one payout per customer-year, plus a rebate in zero-payout years.

---

## 1. Loss ratios of real parametric and micro products

| Product or source | Number | Notes | Source |
|---|---|---|---|
| MiN Landscape of Microinsurance 2021 (data for 2020) | Median claims ratio 15% in 2020, down from 23% in 2019. Africa 17%, Asia 16%, LAC 12%. | "Some experts" gave a rough guide of 30-40% as the minimum expected. Low ratios may signal poor customer value and hurt trust and uptake. Verified. | Microinsurance Network, "Claims ratios: how low is too low?", https://microinsurancenetwork.org/posts/claims-ratios-how-low-is-too-low (post date not shown on fetched page; text refers to an October launch, so late 2021) |
| MiN Landscape 2020 | A third of products in all regions had claims ratios in single digits. African health policies averaged about 14%. | Verified. | Microinsurance Network, "Why are microinsurance claims ratios so low?", https://microinsurancenetwork.org/posts/why-are-microinsurance-claims-ratios-so-low (date not shown; refers to 2020 Landscape study) |
| ILO regional averages | Claims ratio: LAC 26%, Africa 44%, Asia 79%. | Snippet only. Older data. | ILO, "Emerging Insight: Latin America and the Caribbean in numbers", 9 Nov 2015, https://ilo.org/resource/article/emerging-insight-latin-america-and-caribbean-numbers |
| MicroEnsure target | Loss ratio 45-70%. Below 45% is "poor value". Above 70% is unlikely to be sustainable. | Weak source. It is a reader comment by a person who says they work at MicroEnsure, under a blog post. Verified text. | savings-revolution.org, "What we need to ask about micro-insurance", 10 Mar 2017, http://savings-revolution.org/homepage/2017/3/10/what-we-need-to-ask-about-micro-insurance |
| Same blog post, author | An insurance contact said micro-insurance payout ratios are typically below 50%. US ACA rule needs at least 80% in health. | Anecdote. Verified. | Same URL |
| FinMark Trust / Cenfri, "How low can we go?" (Nov 2014) | Life microinsurance still beats a micro loan on value at claims ratios of 60-80% at higher wealth levels. | Snippet only. This is NOT the "MicroInsurance Centre says above 60-70%" claim from the brief. I did not find that exact claim. Treat "60-70% = good value" as unconfirmed. | https://cenfri.org/wp-content/uploads/2014/11/How-low-can-you-go-discussion-paper_FinMark-Trust_November-2014.pdf |
| MiN Africa business case | 40% of institutions had combined ratios of 0-60%. 69% had combined ratios at or below 100%. | Snippet only. Combined ratio includes costs. | https://microinsurancenetwork.org/posts/is-there-a-business-case-for-microinsurance-in-africa |
| SEWA heat insurance, India, 2023 | Zero payout. Product did not trigger although 2023 was hot. | Verified. Trigger temperatures were too high. | ILO, "SEWA's journey towards climate resilience, 2023-2025" (A. Dalal), 2026, https://researchrepository.ilo.org/view/pdfCoverPage?download=true&filePid=13156039000002676&instCode=41ILO_INST |
| SEWA heat insurance, 2024 | Insurance layer loss ratio 154%. 46,339 of 50,000 members (93%) got a payout. Payouts INR 151-1,656. Total INR 29.2 million insurance payouts plus INR 20 million donor cash (INR 400 each at 40 C). | Verified. Pilot with donor money and reinsurance. Not a profit model. | Same ILO report. Also AIDMI blog by SEWA's Dr Sahil Hebbar, 9 Apr 2025, https://aidmi.org/blog/parametric-insurance-and-extreme-heat-sewas-experience |
| SEWA Climate Welfare Facility, 2025 | Payout INR 1,141,100 (US$13,425), "loss ratio of about 11.8%". | Verified text. The denominator is not clear to me (40,000 members paid INR 600 each). Treat the 11.8% as reported, not recomputed. | Same ILO report |
| India PMFBY crop scheme | "For every INR 100 paid as premium by farmers over the last six years, INR 517 was received in claims." | Verified. This uses the farmer-paid premium only. The state and central governments pay most of the premium. It is NOT a loss ratio on gross premium. | World Bank / Financial Protection Forum, "PMFBY Fact Sheet", 23 Feb 2024, https://financialprotectionforum.org/sites/default/files/PMFBY%20Fact%20Sheet-Final%20English.pdf |
| PMFBY, critics' totals | Premium INR 126,521 crore against claims INR 87,320 crore over five years (about 69%). | Snippet only. It is a claim by critics, not verified. | whogains.org, "India PMFBY crop insurance", https://whogains.org/case/india-pmfby-crop-insurance |
| ACRE Africa | Farmers pay 50% of premium. Maize drought cover cost about US$37 per acre, "10% of harvest value". Livestock premium 3.5% of animal value. | Snippets only. I found no loss ratio. | CPI case study, 16 Sep 2021, https://climatepolicyinitiative.org/gca-africa-adaptation-finance/case_studies/agriculture-and-climate-risk-enterprise-acre-2 ; World Bank partner profile, 2014, http://documents1.worldbank.org/curated/en/858031490693709582/pdf/113740-BRI-PartnerProfiles-ACRE-PUBLIC.pdf ; ACRE FAQ, 31 May 2017, https://acreafrica.com/frequently-asked-questions-about-livestock-insurance |
| IBISA | No loss ratio found. News: Ghana pilot, all policyholders got a payout (Dec 2024). | Snippet only. | The Insurer, 17 Dec 2024, https://theinsurer.com/parametric-insurer/news/weather-insurance-launched-in-ghana-after-pilot-payouts-2024-12-17 (page blocked) |
| Blink Parametric | No loss ratio found. Company says it focuses on "high-frequency, low-value claims" (flight delay). | Snippet only. | https://blinkparametric.com/importance-of-real-time-flight-disruption-insurance-solutions-during-large-scale-air-travel-disruption-events (21 Mar 2025) |
| Lemonade, Swiss Re, GIZ, InsuResilience | Not found. I did not search these in depth. | Gap. | n/a |

What "good value" means, from this evidence:
- Below about 30-40%: regulators and MiN treat it as a warning sign.
- 45-70%: practitioner target range (one weak source).
- Above about 70-80%: hard for the insurer to cover costs and margin. (Team assumption.)
- The ILO says client value drives new sales and persistency (ILO, "Attaining and improving profitability and sustainability in inclusive insurance", technical note, Dec 2025, https://ilo.org/sites/default/files/2026-02/Profitability_Technical_Note_ENG.pdf, verified).

---

## 2. Cover multiple: maximum payout versus premium

| Product | Premium | Maximum benefit | Ratio | Source |
|---|---|---|---|---|
| SEWA heat cover 2024 (closest comparable) | INR 446.7 per year total. Member paid INR 250 (donor paid the rest). | INR 1,230 per member | Max = 2.75 x total premium. Premium = 36% of max. Member share of max = 20%. | ILO SEWA report (above). Verified. |
| SEWA 2024 cash layer | Free, donor paid | INR 400 at 40 C | n/a | Same |
| Income Stallholder Insurance (NEA hawker licence holders) | Annual S$109.00 (Plan A, non-cooked), S$152.60, S$218.00. Cooked food: S$130.80, S$183.12, S$261.60. Includes 9% GST. "From $0.30 per day". | Property sum insured S$10,000 / 20,000 / 35,000. Closure of stall S$100 / 150 / 200 per day, maximum 120 days. Personal accident S$20,000 per person. | Closure cover max S$12,000 vs S$109-262 premium. But it is a bundle and triggers only on an insured loss (I did not read the closure wording). It has a "No Claim Discount". | Income, Stallholder Insurance leaflet 2024, https://assets-au-01.kc-usercontent.com/8acbd32f-b7e0-0294-6b7d-a2bc72d6b30c/ca4620ee-b077-4c71-b055-8049ccf1cdc5/Stallholder%20Insurance_EN_2024%20web.pdf . Verified. |
| Income SmartBiz 360 | Price not shown on page | All-risk assets, daily payout on business interruption after an insured loss, IT cover, liability. 15% chain discount for multi-location. | n/a | Income, https://income.com.sg/commercial-insurance/smartbiz-360 . Verified. Not a weather-income cover. |
| Grab Partner Cover (personal accident for drivers) | 4-wheel S$9 / 15.80 / 27.70 per month. 2-wheel S$11.50 / 17.20 / 29.20 per month. | Accidental death up to S$300,000 (4-wheel) or S$200,000 (2-wheel). Hospital income up to S$200 or S$150 per day. Medical up to S$3,000 or S$2,000. | Death cover about 2,700 x annual premium (S$300,000 / S$108). Hospital daily benefit about 1.9 x the monthly premium. | Grab SG, https://grab.com/sg/driver/finance/insurance/partner-cover (undated page, fetched 15 Nov 2026). Verified. Snippet text on the page header says "up to S$100 daily"; the table says S$200. Use the table. |
| Income + Grab Critical Illness Pay Per Trip | S$0.10 / 0.30 / 0.50 per trip, taken from the in-app wallet | Fixed sum assured, accumulating per trip (up to S$200,000 in one snippet) | n/a | Income press release, 1 Aug 2019, https://income.com.sg/about-us/corporate-information/press-releases/grab-and-ntuc-income-launch-southeast-asias-first (premium range verified; S$200,000 figure from a Business Times snippet, 11 Jun 2020, https://businesstimes.com.sg/companies-markets/consumer-healthcare/ntuc-income-offers-insurance-coverage-bite-sized-premiums ) |
| Income PA Assurance | "From only $0.64 a day" | Up to S$25,000 hospitalisation, up to S$1.5 million permanent disability, ICU up to S$1,200 per day | n/a | Income, https://www.income.com.sg/personal-accident-insurance/pa-assurance . Verified. |
| Gojek RideShield | Free (Gojek is policyholder). Ended 1 Jan 2025, replaced by statutory WICA cover underwritten by Etiqa. | Death S$100,000. Disablement up to S$100,000. Medical up to S$1,000. | n/a | Gojek SG, https://gojek.com/sg/driver/goalbetter/healthcare . Verified. |
| Singlife, FWD, Chubb, MSIG, AIG SME | Not retrieved. | | | Gap. AIG SME Package and Liberty SME packages exist (search results only). |

Lesson: accident and fire covers show multiples in the thousands because payouts are rare. Weather-day cover pays often. Its multiple must be small. SEWA, the only close comparable, is 2.75x.

Useful identity (team assumption, simple algebra):
net premium / maximum payout = expected payout / (loss ratio x maximum payout)
So a higher chance of payout forces a higher premium-to-maximum ratio. Wow comes from certainty and speed, not from a 50x multiple.

---

## 3. Payout frequency and renewal

| Finding | Source | Status |
|---|---|---|
| Customers who got an insurance payout were 9-22% more likely to buy again next year (BASIX, India, rainfall index, three years of data). The author says the effect is behavioural (payout shifts the reference point), not wealth, weather or trust in the insurer. The two abstract versions differ on "percent" and "percentage points". | Stein, "Dynamics of Demand for Rainfall Index Insurance", World Bank Policy Research WP 7035, Sep 2014, https://documents1.worldbank.org/curated/en/527171468269102015/text/WPS7035.txt | Verified |
| In Mali, "the receipt of a payout had the strongest effect on the renewal"; client satisfaction and product understanding also matter. | "Client satisfaction and product understanding as drivers for insurance renewal - A case study in Mali", https://ageconsearch.umn.edu/record/321216 (year not shown) | Snippet only. Page blocked. |
| Good client value leads to new customers and persistency. Flexible premium frequency helps customers with irregular income. | ILO technical note, Dec 2025 (URL above) | Verified |
| Low claims ratios may erode trust and uptake. | MiN posts (URLs above) | Verified |
| SEWA 2023: no trigger in a hot year. Lessons: subsidise premium until members see value, bundle several hazards, add a cash layer for moderate days. SEWA now tracks renewal rates but I found no renewal number. | AIDMI blog 2025; ILO SEWA report 2026 | Verified |
| J-PAL and ILO Impact Insurance Facility specific "payout frequency vs renewal" papers | Not found | Gap |

Reading: a payout in the year is the strongest driver found. A product that pays 0 days in some years (haze is zero in about 4 of 13 years, see section 5) needs a built-in "something happens" feature.

---

## 4. Behavioural framing that sells

| Lever | Evidence | Status |
|---|---|---|
| Premium rebate in zero-payout years | UC Davis BASIS, M. Carter, Feb 2024 slides on a Burkina Faso cotton farmer experiment: "premium rebate frame" (premium returned in bad years, payout lower by the rebate) raised willingness to pay from 151% to 165% of the fair price on average. For the third of farmers who strongly prefer certainty: 135% to 176%. https://basis.ucdavis.edu/sites/g/files/dgvnsk466/files/media/documents/RiskUncertainty_Carter.pdf | Verified slides. Lab/field game, farmers, not hawkers. Transfer to Singapore is untested. The rebate in the design was cost-neutral to the insurer (payout was cut by the rebate). |
| Daily price framing | Income already uses it: Stallholder "from $0.30 per day"; PA Assurance "from only $0.64 a day". Grab/Income used per-trip pricing of 10-50 cents. | Verified (company pages). I found no experiment that proves daily framing raises uptake. |
| "Up to N times your premium" | No source found. | Gap. Team assumption only. Keep N honest and equal to the real cap (see section 6). |
| "Less than a kopi a day" | No price source for kopi collected. | Gap. Do not print a kopi price without checking. |
| No-claim cash back / discount | Income Stallholder has a "No Claim Discount". Carter rebate evidence above. SEWA's facility plans member rebates in low-payout years. | Verified |
| Bundling | SEWA lesson: bundle rainfall, cyclone and heat; add savings and loans. Income SmartBiz 360 offers a 15% chain discount; Stallholder bundles property, closure, liability, accident. ILO: mandatory or embedded products reach scale more easily. MiN warns bundled products can leave customers unaware, which lowers claims ratios and trust. | Verified |
| Subsidised first period / trial | SEWA: members paid INR 250 of INR 446.7; donors paid the rest. SEWA lists "premium subsidisation" until members understand value. No trial-week experiment found. | Verified for SEWA. Trial week: gap. |
| Automatic payout, SMS on payout | SEWA: payout came by phone message without a claim; members valued the visible link between heat and payment. | Verified (WEF, 25 Mar 2025, https://weforum.org/stories/climate-action/the-heatwave-that-sparked-a-new-era-for-women-workers-in-india ; ILO report) |

---

## 5. Singapore context

Prices and costs
- GST is 9% since 1 Jan 2024. General insurance premiums carry GST at the prevailing rate. Source: IRAS, "GST: Guide for the Insurance Industry (Fifth Edition)", https://iras.gov.sg/docs/default-source/e-tax/etaxguide_gst_guide-for-the-insurance-industry-(fifth-edition)c87f527e-f5a9-4215-9c3b-088e68261654.pdf (snippet only). Income's Stallholder leaflet shows prices including 9% GST (verified). So S$3.00 per week incl. GST is S$2.75 net (team arithmetic).
- Hawker cost (2025): median monthly cooked-food stall rent S$1,700 at Socially-conscious Enterprise Hawker Centres and S$1,450 at comparable non-SEHCs. Service and conservancy charges about S$400 vs S$200. Table cleaning about S$650 vs S$520. Source: MSE written reply to PQ, 8 Sep 2026, https://mse.gov.sg/latest-news/written-reply-to-parliamentary-question-on-heat-preparedness-by-ms-grace-fu--minister-for-sustainability-and-the-environment- . Verified.
- Median rent for non-subsidised cooked-food stalls was about S$1,250 from 2015 to 2023. Source: MSE reply, Feb 2025, https://mse.gov.sg/latest-news/written-reply-to-parliamentary-question-on-median-rent-for-hawker-stalls-feb2025 . Snippet only.
- Hawker take-home: I found no official figure. Blogs say S$2,000-4,000 per month net. Mothership (May 2026) quotes one hawker at S$2,000-2,500. Low reliability. Daily takings: not found. Source for the Mothership item: https://mothership.sg/2026/05/nasi-lemak-hawker-break-even (snippet only).
- S$3 per week is about S$13 per month (team arithmetic). That is under 1% of a S$1,450-1,700 stall rent.

Platform workers
- Median monthly earnings in 2023 were about S$1,500-2,500. About 70,000 platform workers (3% of workforce). Source: MOM, speech by SMS Koh Poh Koon on the Platform Workers Bill, 9 Sep 2024, https://mom.gov.sg/newsroom/speeches/2024/0909-speech-by-sms-koh-on-platform-workers-bill . Verified. Split (Straits Times, 9 Sep 2024): 22,200 cabbies, 33,600 private-hire drivers, 14,700 delivery workers (snippet only).
- S$13 per month is about 0.5-0.9% of that median range (team arithmetic).
- Platform Workers Act: from 1 Jan 2025 platform operators must provide work injury compensation (WICA) and CPF contributions for platform workers. CPF is mandatory for those born on or after 1 Jan 1995 and optional for older workers. Rates rise over five years toward 20% worker and 17% operator by 2029. The PCTS cash support runs 2025-2028 for lower-income workers and falls 25% each year. Sources: CPF Board, "CPF changes and government support for platform workers", Sep 2024, https://cpf.gov.sg/member/infohub/educational-resources/cpf-changes-and-government-support-for-platform-workers (verified); NTUC, 22 Aug 2024 (snippet only, https://www.ntuc.org.sg/pme/news/MOM-Lower-income-platform-workers-salaries-unaffected-by-CPF-contributions-in-2025/).
- Meaning: injury cover is now statutory. Weather income loss is NOT covered by WICA. That is the gap Payung fills. Rising CPF deductions make take-home tighter, so price sensitivity is high. This is my inference.
- Existing platform covers are priced monthly (Grab Partner Cover S$9-29.20 per month) and deducted from the in-app wallet.

Regulation
- MAS Guidelines on Fair Dealing (FSG-G04), in force from 30 May 2024, apply to all financial institutions. Five outcomes: culture, suitable products for target segments, competent representatives, clear and accurate information, complaints handling. New guidance: institutions should test that a product meets the needs of its target customers, and must not create unrealistic expectations. Sources: MAS page https://www.mas.gov.sg/regulation/guidelines/guidelines-on-fair-dealing---board-and-senior-management-responsibilities-for-delivering-fair-dealing-outcomes-to-customers (verified); Reed Smith summary, 12 Jun 2024, https://reedsmith.com/articles/mas-updates-guidelines-on-fair-dealing (verified).
- I found NO MAS loss-ratio floor or explicit "value for money" test for small-ticket insurance. The MAS PDF itself was unreachable. Do not claim one in the pitch.

Weather frequency (matters for the chance of a payout)
- Haze: NEA 24-hour PSI data summarised by CompareSG: in 2026 to 13 Oct, at least one part of Singapore had 27 days with an hour at PSI 101 or higher, 447 hours in total, highest 192 on 9 Oct. Four of the 13 years from 2014 had none. Highest year was 2015 with 856 hours. Source: https://comparesg.org/insights/haze-in-singapore-by-year-and-region (verified; third-party site using NEA data). A day-level trigger (for example 24-hour PSI above 100 for the whole day) will fire less often than this "any hour" count.
- A haze episode is running now (October 2026). Do not sell or backdate during an episode. Use a waiting period (team assumption).
- Heat: NEA Heat Stress Advisory uses WBGT. At WBGT 33 and above the public is told to minimise outdoor activity. MOM framework bands: below 31, 31 to below 33, 33 and above. Sources: NEA, https://nea.gov.sg/media/news/news/index/new-heat-stress-advisory-launched-to-guide-public-on-minimising-risk-of-heat-related-illnesses (snippet); MOM framework, https://mom.gov.sg/-/media/mom/documents/heat-stress-measures/heat-stress-framework-outdoor-workers.pdf (snippet). Number of days per year at WBGT 33 or above: NOT found.
- Heavy rain: number of qualifying days per year: NOT found. NEA/MSS annual climate report 2023 exists (https://www.weather.gov.sg/wp-content/uploads/2024/04/ACAR_2023.pdf) but I did not read it.
- Action for the team: pull 10 years of daily NEA data (PSI, rainfall by station, WBGT by station) and count trigger days. All numbers in section 6 depend on it.

---

## 6. Recommendation

All numbers below are team design targets built from the evidence. Calibrate with actuarial data and Income's real expense and reinsurance load. I do not have those.

(a) Yearly premium as a share of the maximum yearly payout
- Target: 33-45% (cover multiple of 2.2x to 3.0x).
- Anchor: SEWA 2024 at 36%.
- Do not go below about 25% unless the triggers are very rare. A low ratio with frequent triggers makes the insurer lose money.
- Do not go above about 50%. The buyer sees a cap that is too small ("I pay S$156 to get at most S$300").
- Honest headline: "Up to 2.5x what you pay" is true at the cap. The better line is the average: "In a typical year, Payung pays about 0.6 of what you paid, plus a refund if it pays nothing." (needs calibration)

(b) Expected loss ratio
- Target: 55-70% on net premium (ex GST), in an expected year. Mid-point 62%.
- Evidence: practitioner range 45-70%; MiN median 15% is called too low; above 70-80% is hard to sustain.
- Allow a stress year (a 2015-type haze) to run above 100%. Protect with a stop-loss or reinsurance. SEWA's 154% year was funded by donors and reinsurance. Income will need its own cover.
- Remaining 30-45% of net premium pays for distribution, tech, data, claims, reinsurance, capital and margin. I have no Income expense figure. Ask Income.

(c) Chance of at least one payout per customer per year
- Target: 65-80% for the main tier. Floor 50%.
- Reason: payout is the strongest renewal driver found (9-22% more repurchase in BASIX data; strongest factor in Mali). Zero-payout years (SEWA 2023; haze-free years) hurt trust.
- Not 90%+ : SEWA 2024 hit 93% but with a 154% loss ratio. High frequency costs money.
- Mix the triggers. Haze alone cannot give 65% (4 of 13 years had none). Use rain and heat as the frequent triggers, haze as the headline trigger.
- Add a zero-payout rebate: if the customer gets no payout in a policy year, return 20-30% of premium as cash or credit. Cost is cheap: with a 25% rebate and a 25% chance of zero payout, the rebate costs about 6% of premium. (team arithmetic) Paid out of the 55-70% loss budget, so the loss ratio target includes it.

(d) Number of tiers
- Target: 3. Plus a default (middle) tier marked as popular.
- Local market norm: Grab Partner Cover has 3 plans; Income Stallholder has 3 plans. Same logic gives a familiar price ladder.
- I found no study on the best number of tiers. This is judgment, not evidence.
- One trigger set across all tiers. Only the daily amount changes. This keeps MAS "clear information" simple and avoids mis-selling.

Illustrative ladder (team assumption, prices include 9% GST)

| Tier | Weekly | Yearly | Per day | Daily framing | Payout per bad day | Yearly day cap | Max per year | Premium / max | Expected bad days paid at 60% LR on net premium |
|---|---|---|---|---|---|---|---|---|---|
| Lite | S$2 | S$104 | S$0.29 | under 30 cents a day | S$20 | 12 | S$240 | 43% | about 2.9 |
| Standard (default) | S$3 | S$156 | S$0.43 | about 43 cents a day | S$30 | 15 | S$450 | 35% | about 2.9 |
| Plus | S$5 | S$260 | S$0.71 | about 71 cents a day | S$50 | 15 | S$750 | 35% | about 2.9 |

Arithmetic check: Standard net premium = 156 / 1.09 = S$143.1. At 60% loss ratio, expected payout = S$85.9. At S$30 per day that is about 2.9 days. The cap is 15 days, so the maximum is about 5 times the expected payout.

Trade-offs
- Higher daily amount or lower cap: gives a bigger "wow" per bad day. Raises the premium-to-max gap and the insurer's tail risk. A lower cap keeps the premium low but "I hit the cap in July" feels bad. Pick the cap above the 90th percentile of trigger days (needs data).
- More triggers (rain + heat + haze): higher chance of payout and stronger renewal. Costs more per customer and needs a clean, public definition. Use stations near the customer. Basis risk (payout does not match the stall's real loss) is the main source of distrust in parametric products (Carter, UC Davis 2024: basis risk discourages purchase).
- Payout speed and SMS: automatic payout by phone message was a key trust moment for SEWA. Keep the claim to zero steps.
- Rebate: lifts willingness to pay in the field experiment, costs little, but must be netted from the payout budget. Do not promise both a high loss ratio and a large rebate.
- Adverse selection: customers buy when haze starts. Use a waiting period of about 7-14 days and a no-sale rule during a live episode (team assumption).
- Weekly billing: matches irregular income (ILO note on payment flexibility) and platform-wallet deduction (Grab model). Allow a pause. Weekly premiums raise collection cost, so deduct from a wallet or PayNow auto-debit.
- MAS fair dealing: describe the product with plain examples of trigger days and the real cap. Avoid claims such as "up to 50 times".
- Bundling with Income SmartBiz 360 or Stallholder: SmartBiz pays business-interruption days only after physical loss. Payung covers the gap (no damage, but no customers). A bundle discount (SmartBiz already has a 15% chain discount) is a natural hook. MiN warns bundled covers cause low awareness, so send a first-payout message and a monthly "your cover" note.

Open items (what I could not find)
1. Income's expense ratio, commission and reinsurance cost for micro products.
2. Days per year at heavy-rain, WBGT 33 and PSI day-level triggers.
3. J-PAL or ILO studies on payout frequency and renewal in a formal table. I found Stein (BASIX) and a Mali snippet only.
4. Experiments on "up to N times", "less than a kopi", trial weeks and number of tiers.
5. Lemonade, Swiss Re, GIZ and InsuResilience benchmarks. Singlife, FWD, Chubb, MSIG and AIG SME prices.
6. Official hawker daily takings.
7. Exact MAS value-for-money rule for small-ticket insurance (none found).

Web tools: TinyFish search (24), TinyFish fetch (6 calls, 28 URLs), WebSearch (0), WebFetch (0)
