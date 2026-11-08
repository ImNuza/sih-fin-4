# Singapore-India Hackathon (SIH) 2026: what we know

Last updated: 2026-11-07. Track: FinTech / InsurTech. Problem statement document: received (see section 5.0).

Sources:
- Problem statements (Markdown, all 4 tracks): /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md
- Problem statements (original PDF): /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/[Ext] SIH 2026 Industry Track Problem Statements - Google Docs.pdf
- Infopack: /Users/dewa/Documents/Projects/SIH/SIH 2026 SG Participant Infopack_CAA 15 Oct.pptx
- Recording of Online Session 1 (29 Oct 2026): /Users/dewa/Documents/Projects/SIH/2026-10-29 20-13-50.mov
- Full transcript: /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/notes/transcript-2026-10-29-industry-track-sharing.md
- Official page: https://iie.smu.edu.sg/singapore-india-hackathon-2026

## 1. The event

- 4th edition of a bilateral hackathon. The Prime Ministers of Singapore and India proposed it in 2018. Past hosts: NTU, IIT Madras, IIT Gandhinagar.
- Organisers: SMU Institute of Innovation and Entrepreneurship (IIE), AICTE and the MoE Innovation Cell (India), and TiE Singapore.
- 120 students: 60 from Singapore, 60 from India. Cross-border teams. Ours: 6 people (3 SG, 3 IN).
- Venue: SMU Connexion (L4, L5) and School of Law (SOL B1 Hall 1-3).
- The official page says "36 hours" and says organisers give teams "a suite of AI tools". Which tools is not known yet (someone asked in the Slido; no answer was given).
- Communication: WhatsApp groups (SG Delegates and All Delegates). Email is for official items only.
- Date note: the infopack cover says 14-19 Nov, but the agenda runs 14-17 Nov. The web page says 15-17 Nov. Day 1 (14 Nov) is the evening kickoff.

## 2. Agenda

| Day | Dress | Key items |
|---|---|---|
| 29 Oct (online) | - | Industry Track Sharing. Track preference form. (Done) |
| 5 Nov (online) | - | Intro and team formation. Teams start ideation on their own after this. (Done) |
| Fri 14 Nov | Smart casual | 5:30 PM registration at Connexion L5, meet teammates. 6 PM speeches, admin brief, rules. 7 PM icebreakers and dinner. 8 PM hacking starts. Connexion open until 2 AM. |
| Sat 15 Nov | Smart casual | 8 AM breakfast. 10:30 AM official opening (SOL B1). 12:30 PM consultations with industry track reps (mass and per team). 4 PM mentoring slots. Connexion open until 2 AM. Online mentoring also available. |
| Sun 16 Nov | Business casual | 10 AM mentoring. 5 PM **Semi-Finals Demo Day**. 7 PM networking dinner. |
| Mon 17 Nov | Business / business formal | 10 AM **finalist announcement: top 8 teams, 2 per track**. 12 PM **Grand Finals Demo Day** (SOL B1). 2 PM talent exchange. 6 PM TiECon Gala Dinner. |

Packing: laptop and chargers, extension cord, clicker, water bottle, jacket and blazer, medication.

## 3. Prizes

Four tracks. Each track has the same prizes. Total pool S$88,000.

| Award (per track) | Prize |
|---|---|
| Industry Track Winner | S$13,750 |
| Merit Award | S$8,520 |

## 4. The four tracks (from the 29 Oct session)

| Track | Set by | Problem in one line |
|---|---|---|
| **FinTech / InsurTech (ours)** | Income Insurance | Climate-risk insurance that is affordable, accessible and actionable for vulnerable households and SMEs in Singapore |
| Sustainability / Climate Action | Ministry of Energy, Trade and Industry (speaker: Vivek) | Indian smallholder produce exported to Singapore: quality, consistency, post-harvest loss |
| Emerging Technologies | Singtel (Michelle Lim, Senior Director, AI Transformation) | AI to help enterprise (B2B) sales teams understand customers and pick the next best action |
| Social Innovation | raiSE (Dr Erwin Chan, Lead, Startup Development) | Holistic, affordable, motivating ageing for seniors in Singapore and India |

## 5. Our track in detail: FinTech / InsurTech (Income Insurance)

### 5.0 What the written brief adds (beyond the slides and the talk)

Full text: /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md, section 1.

**Prior art (what failed and why).** The brief lists about 15 schemes. The lessons repeat:

| Lesson | Evidence in the brief |
|---|---|
| A first season with no payout kills the product | SEWA 2023 (thresholds set at record heat), ZhongAn 37°C (cool summer), Caribbean (demand faded in years with no payout) |
| Someone other than the worker must carry the premium | Delhi gig workers would not pre-pay. KB Insurance stallholder cover had zero subscribers after 10 months. Meituan works because the platform pays. |
| The index must feel like *my* risk | Jakarta flood card used one city gauge; residents did not trust it. BlockBima used the trader's own market. |
| Payout speed matters | SEWA took 6 to 8 weeks. BlockBima settled in one day. FloodFlash paid within hours. |
| Single thresholds are crude | ZhongAn ignored humidity, and the regulator called it gambling-like. |
| Cheap embedded cover can sell | Igloo x DANA: IDR 500 at checkout. PayPay: from ¥100 a day, 400,000+ policies. |
| Droplet (Income, 2018) | Parametric rain cover for ride-hailing surge, up to 60% of fare, max $50/day, premium up to $9.60/day. Weak demand. |
| Only existing SG parametric products | Singlife rain travel cover, Swiss Re PSI haze cover for businesses, flight delay. "None reaches households, workers or small traders." |

**Hard design rules (new, stricter than the slides):**
- Insurable interest: sell only to people who would actually lose. Show it at point of sale. A payout to someone with nothing to lose is a bet.
- One sentence at point of sale that says it can fail to pay. Use several trigger levels.
- **Back-test the trigger** on past NEA and PUB data. Show how often target users lost income with no payout (basis risk).
- Use indices people already act on: NEA WBGT heat-stress levels, 24-hour PSI bands, PUB flood sensors, MSS rain gauges. Need decades of history and a fallback feed. Explain the gap between station and worksite temperature.
- Decide who pays first: member, platform, employer, union, or a time-limited subsidy with an end date. No permanent subsidy.
- Cap payable days per season. Bundle heat, rain and haze. Budget for reinsurance.
- Price: a few dollars a week or month. Expenses at or below about 20% of premium. Benchmarks: Philippines cap 7.5% of daily minimum wage; Malaysia Perlindungan Tenang RM50-75/year; Asia-Pacific microinsurance average about US$13/year.
- Trigger, payout and exclusions must fit in **one SMS**, in the customer's language.
- PDPA consent. AI pricing must be explainable and must not price out the people who most need cover (MAS FEAT).
- Do not duplicate work-injury cover (platform workers have it from 1 Jan 2025). Cover lost income.

**Case study: SmartBiz 360** (verified name). Income's all-risk SME package, launched Oct 2026. It covers property, business assets and malware damage. Business interruption is covered up to 100 days a year, **but only when caused by property loss or damage**. The open question: *how might we extend a simple, low-cost package like this to cover climate-related income loss (heat, haze, flash floods) for SMEs, using public data and AI to price cover and trigger payouts, while keeping premiums affordable?*

**Scope.**
- In: lower-income households, renters and seniors (including union members) in flood-prone or heat-exposed homes. Outdoor and platform workers. SMEs (hawkers, neighbourhood shops, home-based businesses). Parametric or hybrid products on public data. AI to cut underwriting, pricing or claims cost. Bundles with risk reduction (cooling, flood barriers) or rewards for safer behaviour. Plain-language, multilingual sales.
- Out: large corporates and industrial risks. Reinsurance, cat bonds, capital-market structures. National infrastructure. Climate ideas with no insurance element. New hardware or sensors as the core. Crypto or token models. Ideas that need a law change.

**Data and links given:** NEA V3 climate study, NEA WBGT API, NEA real-time rainfall and air temperature APIs (data.gov.sg), PUB flood hotspots, Income Stallholder and Enhanced Home brochures, MSE parliamentary reply on hawker insurance (4 Aug 2026), NTUC platform worker article, MAS sustainable finance guidance, MOM Labour Force 2025, MOM heat-stress measures. Frameworks: MAS Environmental Risk Management for Insurers, MAS FEAT, MAS Fair Dealing, PDPA, V3 climate scenarios. All links are in the Markdown file.

**About Income.** Formerly NTUC Income, set up by NTUC in 1970 as its first social enterprise. Part of NTUC Enterprise. Protects union members through group schemes such as NTUC GIFT. NTUC unions and associations represent many platform workers. This makes unions and platform associations a natural distribution and "who pays" channel.

### 5.0.1 Speaker

Speaker: Xin Yi Chua, Senior Manager, Corporate Sustainability, Income Insurance. (The transcript hears her name as "Sini".) She said this is a real business problem for Income, and she is not a product specialist.

### 5.1 Problem statement (slide)

> How might we reimagine insurance, powered by data and AI, so that climate risk protection becomes affordable, accessible and actionable for every vulnerable household and SME in Singapore?

Scope is Singapore only, because Income operates only in Singapore.

### 5.2 Why now (slide)

- Singapore is getting hotter and wetter, and drier and hazier in El Nino years.
- Days above 35 C: about 21 a year now. Could reach 41 to 351 a year by 2100, by emissions scenario.
- Extreme rainfall is rising in every season.
- This year's haze is the longest since 2015. Its cost estimate is already above the 2015 episode.
- From 1 Dec 2026, four more heat-stress measures become mandatory for outdoor work.
- Open real-time weather and air-quality data plus AI make it cheaper to price these risks, pay out automatically, and reach customers that were too costly to serve.

### 5.3 Current gaps (slide plus talk)

| Group | What exists | Gap |
|---|---|---|
| Households | Comprehensive home insurance can cover flood damage to contents and renovation | It is voluntary. Only fire insurance is compulsory (set by the home loan provider). |
| Outdoor workers | Work injury compensation covers injury | No cover for **income lost** when haze, heat or heavy rain stops work. About 71,600 residents were regular platform workers (taxi, private-hire, delivery) in 2025. Construction workers are also exposed. |
| SMEs | Property / asset insurance covers weather damage | **Business interruption without physical damage** is usually not covered. Business-interruption loss is also hard to assess. |
| Insurer (Income) | Traditional indemnity cover: high coverage, high premium, payout after a loss assessment | One event (haze, flood) hits the whole country at once. This strains capital and operations. Loss assessment is slow and costly. Payouts can take months, when people need cash fast. |

### 5.4 What a strong 36-hour outcome looks like (slide)

A **product proposal**, with justification for each item:
1. Concept / design
2. Target group or groups
3. Simple pricing logic and unit economics
4. Clear claim parameters (trigger event, payout basis) and exclusions
5. Expected impact: how much of the protection gap it closes, and why it is affordable. (Size who is affected today, how much is uninsured, and how much the product covers.)
6. Market competitiveness. A new-to-market product gives first-mover advantage, but its payout, operations and distribution are untested. We must address that risk for the judges.
7. Distribution proposal: online, agents, or intermediaries at point of sale (example: Income sells motor insurance through car dealers).
8. How AI and data fit into the proposal.

Note: Singtel asked for a working prototype. Income asked for a product proposal. A clickable demo will still help on demo day, but the business case is the core deliverable.

### 5.5 Must-haves and constraints (slide plus talk)

- Must be designed for Income to offer, as the licensed insurer (alone or with partners).
- Payout triggers and pricing inputs must use **independent and verifiable data**. A person must not be able to fake the trigger event (fraud prevention).
- The product must **not give a person an incentive to harm themselves** (said in the talk, not on the slide).
- The target user must understand what they pay for, and when they get paid, **in under a minute**.
- Collect only the personal data that is needed. Any AI decision must be explainable.
- No new hardware for the core product.

### 5.6 Q&A answers from Income

- **Most critical metric?** Financial viability first. In the simplest form, premiums collected must cover payouts.
- **Can we target one specific loss or group** (for example workers, solar, SMEs)? Yes. A narrow product is fine if the rationale is strong.
- **What has Income tried?** Nothing beyond traditional property-linked weather cover. One past product, "Droplet", paid the Grab surge-price difference during heavy rain. It ended because demand was weak.
- **What would take an idea to a pilot?** Prove the business case first: real demand and willingness to pay. Then financial viability.
- **Must it be climate-related?** Yes.
- **Add-on to Income's SME product (SmartBiz 360, confirmed by the written brief) or standalone?** Our choice. A standalone product must be viable on its own and attractive enough to buy alone. Open question she raised: will people buy a standalone cover for one peril (for example haze only, or heat only)?
- **Which problem to pick?** Our choice: pick where we see the biggest business potential or social impact.

### 5.7 First reading (my notes, not from the organisers)

- The brief points strongly at **parametric insurance**: pay a fixed amount when an independent index crosses a threshold (for example PSI, WBGT heat index, or rainfall at a weather station), with no loss assessment. This fixes the speed, cost and fraud issues the speaker listed.
- The clearest uncovered gaps she named: income loss for outdoor and platform workers, and SME business interruption without property damage.
- Droplet is a warning: weak demand killed a narrow rain product. Our pitch needs demand evidence (survey, interviews, or proxy data) and a distribution channel that reaches users at low cost (for example through platforms or SME channels).
- Basis risk (the index triggers but the person had no loss, or the reverse) and correlated, country-wide events (capital strain) are the two risks the judges will likely probe.
- The written brief confirms this reading: it names "parametric or hybrid products using public weather and air-quality data" as an encouraged direction, and it asks for a back-test of the trigger on NEA and PUB history.
- The brief's case study points at one concrete product: a climate income-loss add-on to SmartBiz 360 for SMEs (hawkers, small shops). Workers through unions or platforms is the other strong option, because "who pays" has a natural answer there.

## 6. Other tracks: short notes

**Sustainability (agri supply chain, India to Singapore).** Smallholder farms under 1 ha. Inconsistent quality and spoilage make Singapore buyers (supermarkets, re-export traders) switch source countries. Advice: target cooperatives / FPOs or aggregators, not single farmers. Pick one crop and one Indian state (rice and tomatoes have very different supply chains). Buyers on the Singapore side. Solve a small part of the chain well. Must be cheap for farmers and able to scale.

**Emerging Tech (Singtel).** Customer data is split across Salesforce, market reports and other tools. Research is manual and depends on the person. Overseas markets are hard. Do not build a new CRM. Mock data is fine. Show business impact (percentages are fine), pilot and scale plan. Must respect data privacy, security, and integration with existing systems. Must turn insights into concrete sales actions. Hunting (new customers) or farming (existing accounts), either is fine. Burning problem: grow revenue.

**Social Innovation (raiSE).** Singapore became super-aged in 2026 (21.4% of citizens 65 and above). The aim is healthspan, not only lifespan. Active Ageing Centres exist, but participation is uneven. Men are as low as 20% at some centres. Wants novel ideas ("don't ask AI for solutions"), a sustainable business model, and outcome measures (quality of life), not only engagement numbers. Design with seniors, not for them.

## 7. Open items

- [x] Get the detailed problem statement document. Done: /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md
- [ ] Check that the NEA WBGT, rainfall and air temperature APIs on data.gov.sg work, and how far back their history goes (needed for the back-test).
- [ ] Confirm which AI tools and credits the organisers provide.
- [ ] Confirm judging criteria and pitch length for semi-finals and finals.
- [ ] Prepare questions for the Income consultation on Sat 15 Nov, 12:30 PM.
- [ ] Repo: /Users/dewa/Documents/Projects/SIH/sih-fin-4 (git repo, no commits yet).
