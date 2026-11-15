# SafeDay distribution proposal: sold through the customer's agent or an association

Date: 15 Nov 2026, revised the same evening after Income's private mentoring session [S27]. This is problem-statement deliverable 7. It recommends only. It changes no number in the product.

**What changed in the revision.** Income's product lead said SmartBiz 360 is sold through intermediaries (agents). A direct sale to those customers goes around the agent. She called that "an absolute no-no" [S27]. So SafeDay has no direct sale. Every sale goes through one of two routes:
1. **The customer's own Income agent** adds SafeDay to the customer's SmartBiz 360 or Stallholder policy. For a cheap product that does good, Income could pay about 5% commission instead of the usual 15%. She quoted a range of 5% to 20% [S27].
2. **An association** offers SafeDay to its members as a group scheme. Each member still pays the member's own premium [S23].

The prototype buy flow (`/buy/`) now shows this. The adviser or the association fills in the form with the customer. The form saves who did it (the adviser code, or the association name), and the insurer desk shows it.
Brief: `/Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md`, section 1.
Team draft checked: "SafeDay doc section 13" in `/Users/dewa/Documents/Projects/SIH/whatsapp/2026-11-15 SIH FIN-4/00003068-SafeDay-Hackathon-Plan.pdf`.

Source tags like [S3] point to the list at the end. A claim with no tag is our own reasoning. "No source found" means we searched and found nothing.

## 1. Recommendation

| Customer group | Launch channel (who sells) | Second channel | Later |
|---|---|---|---|
| Hawker stallholders (pilot) | The stallholder's Income agent adds SafeDay to Stallholder Insurance or SmartBiz 360 | Group scheme through the centre's hawkers' association, or through FMAS | NEA-appointed social-enterprise operators |
| Neighbourhood shops | The shop's Income agent adds SafeDay to SmartBiz 360 | Group scheme through the precinct's merchants' association (FMAS members) | HDB or town council partners |
| Platform workers (next phase, not in the pilot) | NTUC associations NDCA and NPHVA as group scheme | One platform's in-app deduction (Grab has an Income pay-per-trip precedent) | Employers |

**Assumption we record (P1 "SmartBiz 360 add-on vs standalone"):** SafeDay is an add-on to SmartBiz 360, sold through the customer's existing Income agent or an association. Not a standalone direct product.

Three reasons drive this choice.
1. It respects Income's agents. The agent keeps the customer and earns the commission. A direct tick-box would go around the agent [S27].
2. Each launch channel already has a licence or account check. A licence or a UEN gives insurable interest at the point of sale.
3. Each channel fits the locked payer rule. SMEs pay 100% as an add-on, also inside a group scheme. The association enrols members and does not pay [S23].

The platform channel is not in the pilot. It needs a signed partner. Section 5 lists the fallback.

## 2. What we checked in the team draft (section 13)

| Draft claim | Result |
|---|---|
| "Zero extra sales cost" for the add-on | Not checked here. Deval owns cost. |
| "Already-insured SMEs are the easiest first buyers" | Partly supported. About two-thirds of cooked-food stallholders hold some insurance [S4]. SmartBiz 360 is new (Oct 2026 per the brief [S22]). No source found for its policy count. |
| Hawker association group "commits a budget" | Conflicts with the locked rule. SMEs pay 100% [S23]. An association can enrol and collect. It does not pay. Ask the team to reword. |
| "Income and Grab already do pay-per-trip cover" | Supported for 2019. Income and Grab launched critical illness cover paid per trip [S9]. No source found that it is still on sale. Droplet (2018) covered passengers, not drivers [S26]. Income says Droplet died off for weak demand [S21]. |
| "Platforms are recognised partners of NTA, NPHVA and NDCA" | Partly supported. Grab recognised NDCA and NPHVA on 7 Mar 2025 [S16]. No source found for NTA. No source found for other platforms. NTUC only "encourages" operators to partner [S8]. |
| NTUC associations "could co-fund the start-up subsidy" | No source found. NTUC pays the premium for NTUC GIFT [S14]. That shows NTUC funds group cover. It does not show NTUC will fund SafeDay. |
| "Union membership benefit (like NTUC GIFT)" | The name is right. NTUC calls it NTUC GIFT [S13]. The page does not spell out the letters. |
| Employers of cleaners and construction workers | Outside the three groups in this note. See channel F. |

## 3. Channel sheets

Each sheet answers the seven questions. The last row of each sheet is the cost column that joins Deval's work.

### A. SmartBiz 360 add-on

| Field | Answer |
|---|---|
| Group | Neighbourhood shops first. Hawkers second. |
| Who it reaches | SmartBiz 360 sectors include Retail (mini-marts and retailers), Food and Beverage (coffee shops, canteen stalls) and Micro SMEs (F&B) such as push-carts and kiosks [S1]. The page does not name NEA-licensed hawker stalls. Those buy Stallholder Insurance [S2]. |
| How many (cited) | 356,600 SMEs in Singapore in 2024 [S19]. About 15,200 HDB shops in 2022 [S18]. SmartBiz 360 policies in force: No source found. |
| Who sells it | The customer's Income agent. SmartBiz 360 is sold through intermediaries [S27]. The page names a "BIX intermediary journey" [S1]. |
| How the premium is collected | With the SmartBiz 360 premium. The page says premiums include distribution costs "if any" [S1]. Payment method: No source found. |
| What Income already has | Online application, a customer journey and an intermediary journey called BIX, UEN and SSIC retrieval, a 15% chain discount, a Micro SME segment, and a daily business-interruption payout that needs physical loss [S1]. Our prototype uses the same SSIC and postcode inputs for shops. |
| What must be built | Income decides: endorsement on SmartBiz 360 or separate policy. This is on the team question list [S24]. Then a trigger schedule, a postcode-to-region table, a 30-day waiting rule, a payout rail and an SMS template. |
| Main risk | SmartBiz 360 sectors are mostly indoor (office, education, healthcare, beauty) [S1]. Only retail and F&B fit weather loss. The buyer base may be small because the product is new. |
| Priority | First for neighbourhood shops. Second for hawkers. |
| Cost per channel | See Deval's distribution-cost row |

### B. Income's Stallholder Insurance add-on

| Field | Answer |
|---|---|
| Group | Hawker stallholders |
| Who it reaches | Registered NEA hawker licence holders only. Food Shop, Mobile Food Wagon, vending and private canteen licences are excluded [S3]. |
| How many (cited) | NEA manages 123 markets and hawker centres [S6]. More than 14,000 hawker stalls in 119 centres at 31 Mar 2024 [S5]. About two-thirds of cooked-food stallholders hold some insurance [S4]. Stallholder Insurance policies in force: No source found. |
| Who sells it | The stallholder's Income agent. Income's page shows "Buy now" and "Speak with an advisor" for it [S2]. The Jan 2024 application form has a field for the intermediary's name and code [S28]. So agents sell it too. Whether the "no direct sale" rule also covers Stallholder Insurance: ask Income (section 7). Until then we treat it as SmartBiz 360. |
| How the premium is collected | Annual premium of S$109.00 to S$261.60 with 9% GST, not guaranteed [S3]. The Jan 2024 application form also allows a posted cheque [S28]. |
| What Income already has | A live product, a licence-based eligibility rule, a closure-of-stall benefit of S$100 to S$200 a day up to 120 days [S3], a no-claim discount at renewal [S3], and online sale [S2]. The brochure text we read states no weather trigger. NEA may require stallholders to hold insurance in future [S4]. |
| What must be built | An add-on option on the Stallholder quote and renewal screens. Alignment of the annual renewal with the SafeDay 12 or 24 month term. Licence check against NEA. SMS and PayNow payout. Income must confirm that the current wording allows an add-on [S24]. |
| Main risk | Unknown base size. If the base is under 300 policies, the 300-stall pilot needs channel E. Annual renewals do not match a 24-month term. |
| Priority | First for hawkers |
| Cost per channel | See Deval's distribution-cost row |

### C. Per-trip deduction through Grab or other platforms

| Field | Answer |
|---|---|
| Group | Platform workers |
| Who it reaches | Drivers and riders on one platform at a time. |
| How many (cited) | 71,600 resident regular platform workers in 2025. That is 36,000 private-hire drivers, 20,900 taxi drivers and 14,700 delivery workers [S7]. Grab's share: No source found. |
| How the premium is collected | In the Income and Grab 2019 plan, drivers chose S$0.10, S$0.30 or S$0.50 a trip. Grab deducted it from the in-app cash wallet and paid Income [S9]. Grab Partner Cover also deducts from the driver wallet [S10]. Gojek, Tada and ComfortDelGro drivers have income-loss cover from Etiqa [S11]. |
| What Income already has | The 2019 pay-per-trip plan with Grab [S9]. Income is one of six insurers in the 2023 work injury network with platforms [S12]. Which platform Income insures: No source found. Grab Partner Cover uses Chubb, not Income [S10]. |
| What must be built | A platform data agreement for proof of activity. A wallet deduction that turns variable trips into a flat weekly amount. A split where the platform pays half. A partner portal. A consent flow under PDPA. |
| Main risk | The platform must agree to pay half. The Platform Workers Act obliges platforms to fund work injury cover and CPF [S20]. It does not oblige them to fund weather cover. Delhi gig workers would not pre-pay for heat cover [S22]. A per-trip price conflicts with the locked flat weekly rate and 12 or 24 month term [S23]. |
| Priority | First for platform workers, with a fallback (section 5) |
| Cost per channel | See Deval's distribution-cost row |

### D. NTUC associations and Income's group schemes (NTUC GIFT)

| Field | Answer |
|---|---|
| Group | Platform workers, next phase only. Not hawkers or shops. |
| Who it reaches | NTA (taxi), NPHVA (private hire) and NDCA (delivery) became recognised Platform Work Associations on 7 Jan 2025 [S8]. foodpanda recognised NDCA on 11 Sep 2026 [S35]. |
| How many (cited) | NTUC GIFT covers 800,000 union members [S14]. NPHVA: 3,240 members in Oct 2017 (NTUC, snippet only) [S36]. NDCA and NTA: No source found. Hawker or shop owners as union members: No source found. |
| How the premium is collected | NTUC GIFT premium is paid fully by NTUC with co-payment from affiliated unions [S14]. NTUC keeps the master policy [S13]. How a union would collect a member-paid premium: No source found. |
| What Income already has | NTUC GIFT: group cover for death and disability up to S$40,000 for union members under 65 [S13]. A claim form endorsed by the union [S13]. NDCA already takes proof of delivery activity (app screenshot or weekly statement) for its relief fund [S15]. |
| What must be built | A new group master policy or a rider. NTUC must agree to the terms. A weather trigger does not fit GIFT's claim-form flow. |
| Main risk | If NTUC pays, this becomes a standing subsidy. The brief allows only a time-limited subsidy with an end date [S22]. The locked rule says no permanent subsidy [S23]. |
| Priority | Second for platform workers. Later for others. |
| Cost per channel | See Deval's distribution-cost row |

### E. Hawker and merchants' associations (group scheme)

| Field | Answer |
|---|---|
| Group | Hawkers first. Shops through heartland merchants' associations. |
| Who it reaches | FMAS: 75 merchants' and hawkers' associations in five zones [S29]. Centre associations we would approach first (members: No source found for each): Tiong Bahru Market Hawkers' Association [S30], Chinatown Complex Hawkers' Association [S31], Old Airport Road Food Centre Merchants' Association [S32], Ghim Moh Market & Shops Merchants' Association [S33], Bedok North Blk 216 Food Centre and Market Hawkers' Association [S34]. |
| How many (cited) | FMAS says it works with about 16,000 hawkers and stallholders in NEA centres and about 20,000 retailers in HDB centres (27 Aug 2026) [S29]. These are the people its associations serve, not paid members. Older figure: 16,000 hawkers and 17,000 retailers (Straits Times, 23 Oct 2020) [S17]. |
| How the premium is collected | No source found for any Income group scheme with a hawker association. The locked rule says each stallholder pays 100% [S23]. The association would enrol members and pass on payment. |
| What Income already has | The group master-policy pattern (NTUC GIFT) [S13]. Income does not need a new licence for this. No source found for hawker-association deals. NEA-appointed operators may already require stallholders to buy insurance [S4]. |
| What must be built | An agreement with one association or one NEA-appointed operator. A member list under PDPA consent. A collection method (No source found for GIRO or PayNow bulk collection by associations). A rule that blocks sign-up during a haze advisory. |
| Main risk | Hawker centre associations are run by volunteers (SMU research, 2023, read as a snippet only) [S17]. Korea's KB stallholder cover had no subscribers because nobody carried the premium [S22]. |
| Other route | NEA-appointed operators of socially-conscious enterprise hawker centres (Koufu, Fei Siong, NTUC Foodfare, Timbre+, Kopitiam) run 12 centres with close to 500 stalls (31 Mar 2024) [S5]. That is about 3.5% of the more than 14,000 stalls (our arithmetic). A small channel. |
| Priority | Second for hawkers. First for a pilot that needs 300 stalls fast. |
| Cost per channel | See Deval's distribution-cost row |

### F. Employers

| Field | Answer |
|---|---|
| Group | None of the three. |
| Who it reaches | Platform workers have no employer. They are own-account workers [S7]. Hawker assistants and shop staff work for the stallholder or shop owner. SafeDay insures the owner's takings, not staff wages. |
| How many (cited) | Not sized, because the channel does not fit. |
| How the premium is collected | No source found for any Income weather cover paid by an employer. |
| What Income already has | Employer products such as Work Injury Compensation [S2]. |
| What must be built | A wage-loss cover and a new trigger design. This is outside the current product. |
| Main risk | Scope creep. The brief lists construction and cleaners as users [S22]. The team product covers hawkers, shops and platform workers. |
| Priority | Later |
| Cost per channel | See Deval's distribution-cost row |

## 4. Join table for Deval

| Channel | Group | Who sells | Reach (cited) | Collection | Priority | Commission (from Income [S27]) | Cost per channel: see Deval's distribution-cost row |
|---|---|---|---|---|---|---|---|
| A. SmartBiz 360 add-on | Shops, hawkers | Customer's Income agent | 356,600 SMEs, 15,200 HDB shops | With the SmartBiz 360 premium | First (shops) | About 5% (usual 15%, range 5% to 20%) | see Deval's distribution-cost row |
| B. Stallholder add-on | Hawkers | Customer's Income agent | More than 14,000 stalls | Annual premium | First (hawkers) | About 5% (same as A, to confirm) | see Deval's distribution-cost row |
| C. Platform per-trip | Platform workers | Platform | 71,600 workers | Wallet deduction | Next phase | No source found | see Deval's distribution-cost row |
| D. NTUC associations and GIFT | Platform workers | Association | 800,000 union members | Master policy | Next phase | No source found | see Deval's distribution-cost row |
| E. Hawker and merchants' associations | Hawkers, shops | Association | 75 associations; about 16,000 hawkers and 20,000 retailers served (2026) | Enrol members; each member pays | Second | No source found. Income called this route cheaper [S27] | see Deval's distribution-cost row |
| F. Employers | None | Employer | Not sized | Employer pays | Later | No source found | see Deval's distribution-cost row |

**For Deval:** the agent commission of about 5% feeds the 25% expense ratio. Income quoted 5% for a cheap do-good product, against a usual 15% and a range of 5% to 20% [S27].

## 5. Fallback if the platform deal fails

Use NDCA or NPHVA as the enrolment route. Members pay by PayNow. Proof of activity comes from an app screenshot or weekly statement, the same proof NDCA already accepts [S15]. The platform half of the premium has no payer in this case. The team must then decide whether to price the worker share alone or drop the 50/50 rule. That is a locked-rule change. Do not make it without the team.

## 6. Conflicts to settle inside the team

1. The draft says an association "commits a budget". The locked rule says SMEs pay 100%. Pick one.
2. The draft says "per-trip micro-deduction". The locked rule says a flat weekly rate on 12 or 24 month terms. A per-trip deduction can only be a collection method. It cannot be the price.
3. The team uses 71,600 platform workers. The NTUC article uses 67,600, which is the 2024 figure [S8]. MOM's 2025 report gives 71,600 and 67,200 for 2024 [S7]. Cite MOM 2025 and drop the NTUC figure.
4. The 2020 FMAS count is old. Do not put it on a slide without the year.

## 7. Open questions for Income

1. Can SafeDay be an endorsement on SmartBiz 360 and on Stallholder Insurance, or must it be a separate policy?
2. How many SmartBiz 360 and Stallholder Insurance policies are in force, and how many renew each year? The answer sizes channels A and B.
3. Can a licensed hawker hold SmartBiz 360 as well as Stallholder Insurance, or does one exclude the other?
4. Is the 2019 pay-per-trip plan with Grab still on sale? Which platforms integrate with Income today?
5. Why did Droplet lose demand? Was the cause the product, the price or the Grab channel?
6. Can Income take premium by platform wallet deduction? Can it turn variable trip deductions into a flat weekly premium?
7. Would Income write a group policy with a hawker association or an NEA-appointed operator? What PDPA terms apply to member lists?
8. Would NTUC carry part of the premium for a fixed period with an end date? Or must members pay in full?
9. Who owns the customer record and consent in each channel?
10. Partly answered [S27]: about 5% to the agent for SafeDay, against a usual 15%. Still open: does the 5% hold for Stallholder Insurance, and what does an association scheme cost?
12. Does the "no direct sale" rule cover Stallholder Insurance too, which Income's site sells with "Buy now" [S2]?
11. Which sign-up channel does Income prefer: My Income app, WhatsApp, Telegram or SMS? (Question 10 in the team list [S24].)

## 8. Sources

All web pages were read on 15 Nov 2026 unless the entry says otherwise.

- [S1] Income Insurance, SmartBiz 360 page, "Information is correct as at 05 November 2026": https://income.com.sg/commercial-insurance/smartbiz-360
- [S2] Income Insurance, Customise your Commercial Insurance (Stallholder Insurance with "Buy now", Work Injury Compensation): https://income.com.sg/commercial-insurance/customise-your-commercial-insurance
- [S3] Income Insurance, Stallholder Insurance brochure 2024, archived copy of 25 Sep 2025: https://web.archive.org/web/20250925221020/https://www.income.com.sg/kcassets/ca4620ee-b077-4c71-b055-8049ccf1cdc5/Stallholder%20Insurance_EN_2024%20web.pdf
- [S4] Ministry of Sustainability and the Environment, Written reply to PQ on insurance for hawkers, 4 Aug 2026: https://www.mse.gov.sg/latest-news/written-reply-to-parliamentary-question-on-insurance-for-hawkers/
- [S5] MSE, Written reply to PQ on evaluation of stall tender bids (119 centres, more than 14,000 stalls, 12 socially-conscious enterprise hawker centres with close to 500 stalls, at 31 Mar 2024): https://mse.gov.sg/latest-news/written-reply-to-pq-on-evaluation-of-stall-tender-bids (read in full on 15 Nov 2026). Operator names from Straits Times, "13 new social-enterprise hawker centres by 2027" (search snippet only): https://straitstimes.com/singapore/13-new-social-enterprise-hawker-centres-by-2027
- [S6] NEA, Hawker management overview (123 markets and hawker centres): https://nea.gov.sg/our-services/hawker-management/overview
- [S7] MOM, Labour Force in Singapore 2025, paragraph 2.36: https://stats.mom.gov.sg/iMAS_PdfLibrary/mrsd_2025Labourforce.pdf
- [S8] NTUC, "NTA, NPHVA, and NDCA Secure Stronger Protection for Platform Workers with Legal Recognition", 15 Jan 2025: https://www.ntuc.org.sg/uportal/news/NTA-NPHVA-NDCA-Secure-Stronger-Protection-Platform-Workers/
- [S9] Income Insurance press release, "Grab and NTUC Income Launch Southeast Asia's First Micro-insurance for Critical Illness Protection", 1 Aug 2019: https://income.com.sg/about-us/corporate-information/press-releases/grab-and-ntuc-income-launch-southeast-asias-first
- [S10] Grab Singapore, Partner Cover page: https://grab.com/sg/driver/finance/insurance/partner-cover
- [S11] Straits Times, "Platform workers law: Drivers, riders welcome work injury insurance, but mixed on CPF contributions", 12 Sep 2024: https://straitstimes.com/singapore/platform-workers-law-drivers-riders-welcome-work-injury-insurance-but-mixed-on-cpf-contributions
- [S12] Straits Times, "New network to develop work injury compensation policies for platform workers", 3 Feb 2023: https://straitstimes.com/singapore/new-network-to-develop-work-injury-compensation-policies-for-platform-workers (search snippet only)
- [S13] NTUC, NTUC GIFT page: https://www.ntuc.org.sg/uportal/programmes/ntuc-gift
- [S14] Business Times, "Income Insurance needs adequate capital in order to stay financially sustainable: NTUC", 5 Aug 2024: https://businesstimes.com.sg/companies-markets/income-insurance-needs-adequate-capital-order-stay-financially-sustainable-ntuc
- [S15] NDCA, Financial Assistance Schemes: https://ndca.org.sg/membership/financial-assistance-schemes
- [S16] NTUC, "Grab officially recognises NPHVA and NDCA", 7 Mar 2025: https://spaces.ntuc.org.sg/news/Grab-officially-recognises-NPHVA-and-NDCA (search snippet only)
- [S17] Straits Times, "Heartland businesses key part of Singapore's social network", 23 Oct 2020 (16,000 hawkers, 17,000 retailers): https://straitstimes.com/business/heartland-businesses-key-part-of-singapores-social-network-president-halimah-yacob. FMAS YouTube channel text (75 association members): https://www.youtube.com/@FMASsg. FMAS About page: https://fmas.glueup.com/org/fmas/about. SMU research (L Kong, 2023): https://ink.library.smu.edu.sg/cgi/viewcontent.cgi?article=1152&context=cis_research (snippet only)
- [S18] HDB press release, 19 Nov 2022, "Supporting Heartland Shops" (about 15,200 shops): https://hdb.gov.sg/cs/infoweb/about-us/news-and-publications/press-releases/19112022-Supporting-Heartland-Shops-to-Enhan (search snippet only)
- [S19] MOM, Written answer to PQ on distribution of SMEs, 3 Mar 2026 (356,600 SMEs in 2024): https://mom.gov.sg/newsroom/parliament-questions-and-replies/2026/0303-written-answer-to-pq-on-distribution-of-smes (search snippet only)
- [S20] MOM, Platform Workers Act, what it covers: https://mom.gov.sg/employment-practices/platform-workers-act/what-it-covers
- [S21] Income speaker, industry track Q&A, 29 Oct 2026: `/Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/notes/transcript-2026-10-29-industry-track-sharing.md`, timestamps 0:54:02 to 0:54:27
- [S22] Problem statements, section 1: `/Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md`
- [S23] Notion, Singapore Hackathon Global Doc (REAL), LOCKED callout of 15 Nov 2026 09:28 (read only). Also "Pitch, Features & Proposal — Master List" and the TODO "[FROM INCOME Q&A] Put a cost on distribution" (assigned to Deval, 15 Nov 2026).
- [S24] SafeDay Hackathon Plan PDF, section 13 (distribution) and section 20 (questions for Income mentors), in `/Users/dewa/Documents/Projects/SIH/whatsapp/2026-11-15 SIH FIN-4/00003068-SafeDay-Hackathon-Plan.pdf`
- [S27] Income product lead, private mentoring session, 15 Nov 2026, as recorded in Notion: TODO "[FROM INCOME Q&A] Rework distribution" and "Pitch, Features & Proposal — Master List", section "Income private session 15 Nov".
- [S28] Income Insurance, Application for Stallholder Insurance (Jan 2024), fields "Intermediary's name" and "Intermediary's code": https://assets-au-01.kc-usercontent.com/8acbd32f-b7e0-0294-6b7d-a2bc72d6b30c/5e970ee5-6cac-41b0-a4f2-127d120b9f81/Application%20for%20Stallholder%20Insurance%20%28Jan%202024%29.pdf
- [S29] FMAS, Instagram post of 27 Aug 2026 (75 associations, about 20,000 retailers, 16,000 hawkers and stallholders): https://instagram.com/p/Dcid3SPGmCA. Same figures on https://www.youtube.com/@FMASsg (undated).
- [S30] Mothership, Tiong Bahru Market upgrade, Feb 2025: https://mothership.sg/2025/02/tiong-bahru-market-upgrades-apr-14-to-jul-13 (search snippet only)
- [S31] NLB Infopedia, Chinatown Complex: https://nlb.gov.sg/main/article-detail?cmsuuid=ed1f5021-0acb-47b1-b1f7-b6350d29c155 (search snippet only)
- [S32] The New Paper, Old Airport Road Food Centre reopens, Oct 2024: https://tnp.sg/news/singapore/old-airport-road-food-centre-reopens (search snippet only)
- [S33] Must Share News, Ghim Moh Market and Food Centre reopens, May 2024: https://mustsharenews.com/ghim-moh-market-food-centre-reopens (search snippet only)
- [S34] CNA, Bedok food centre business slow, 20 May 2026: https://channelnewsasia.com/singapore/bedok-food-centre-market-business-slow-tuberculosis-6131566 (search snippet only)
- [S35] NTUC, NDCA formally recognised by foodpanda: https://ntuc.org.sg/uportal/news/NDCA-formally-recognised-by-foodpanda-to-represent-its-delivery-partners
- [S36] NTUC, "Making Good Progress", Oct 2017 (NPHVA 3,240 members): https://ntuc.org.sg/uportal/news/Making-Good-Progress (search snippet only)
- [S26] Straits Times, "NTUC Income launches Droplet", 24 Oct 2018: https://www.straitstimes.com/business/banking/ntuc-income-launches-droplet-insurance-plan-to-shield-grab-customers-from-surge (search snippet only)

Notion page "SIH2026 Singapore Market Basics" (14 Nov 2026) gives PayNow reach (over 90% of adults) and smartphone ownership of 88.9% for ages 60 and above (IMDA and SingStat, 2024). It supports the choice of SMS and PayNow for older hawkers.
