# Basis risk: missed losses and false alarms per trigger option (15 Nov 2026)

The brief asks us to "show, from past NEA and PUB data, how often target customers would have
lost income or property with no payout". The burn analysis shows what SafeDay pays. This note
shows the other half: how often a payout misses a bad day at the stall, and how often it pays a
day that was fine at the stall. Ashutosh (14 Nov) asked for it as a confusion matrix per
trigger option.

All numbers come from `uv run scripts/basis_risk.py`, which writes
`data/processed/basis_risk.csv`. The band levels and the number of stations a payout reads come
from `api/default_tariff.json`. Updated after Deval's commit `16ec056`, which made the payout
read the same stations as the price (`api/readings.py`).

## Method

We have no daily sales records, so the weather at the stall stands in for a lost day.

1. Each rain gauge and WBGT station of the pricing network (`site_hazard_readings.csv`: 116
   gauges, 31 WBGT stations) takes a turn as "the stall". Its own reading is the truth for that
   day.
2. Each trigger option reads only the other stations, as a payout would for a stall with no
   station of its own (leave one out):
   - **today's payout rule**: the code in `api/readings.py` itself. Rain takes the median of the
     first 3 gauges that reported, among the nearest gauge and every other gauge within 5 km.
     Heat takes the first WBGT station that reported, on the same terms. If no gauge reported,
     rain takes the MSS daily record. Like a payout, it never reads a station the tariff has on
     hold (WBGT stations S142 and S128 in `api/default_tariff.json`); the other options read
     every other station.
   - **nearest station**: the nearest station that reported, at any distance.
   - **worst of 2 nearest**: the higher of the 2 nearest stations that reported.
   - **median of 3 nearest**: the middle of the 3 nearest stations that reported, at any
     distance.
3. A day is bad at a band level: the first band (the day pays part of a day) or the top band
   (the day pays in full).
4. For every day a station reported, the day is one of: **hit** (bad at the stall, paid),
   **missed loss** (bad at the stall, not paid), **false alarm** (fine at the stall, paid) or
   quiet. A day counts only when at least 3 other stations reported and today's rule gives a
   reading, so every option is judged on the same days.

Data: rain gauges, 3,628 days (579 stall-years). WBGT stations, 660 days (22 stall-years).

## Results

| Hazard and band | Option | Hit | Missed loss | False alarm | Missed share of bad days | False share of paid days |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Rain, 20 mm work hour (first band) | **today's payout rule** | 6,528 | 4,523 | 3,236 | **40.9%** | 33.1% |
| | nearest station | 6,997 | 4,054 | 4,141 | 36.7% | 37.2% |
| | worst of 2 nearest | 8,565 | 2,486 | 7,707 | 22.5% | 47.4% |
| | median of 3 nearest | 6,401 | 4,650 | 3,077 | 42.1% | 32.5% |
| Rain, 50 mm work hour (top band) | **today's payout rule** | 276 | 592 | 274 | **68.2%** | 49.8% |
| | nearest station | 385 | 483 | 487 | 55.6% | 55.8% |
| | worst of 2 nearest | 523 | 345 | 977 | 39.7% | 65.1% |
| | median of 3 nearest | 270 | 598 | 247 | 68.9% | 47.8% |
| Heat, 2 h at WBGT 32 °C (first band) | **today's payout rule** | 58 | 338 | 194 | **85.4%** | 77.0% |
| | nearest station | 64 | 332 | 269 | 83.8% | 80.8% |
| | worst of 2 nearest | 94 | 302 | 409 | 76.3% | 81.3% |
| | median of 3 nearest | 35 | 361 | 57 | 91.2% | 62.0% |
| Heat, 6 h at WBGT 32 °C (top band) | all four options | 0 | 9 | 0 to 1 | 100% | n/a |

Per stall per year (same file, columns `*_per_stall_year`):

| Hazard and band | Bad days at the stall | Option | Missed losses | False alarms |
| --- | ---: | --- | ---: | ---: |
| Rain, 20 mm | 19.07 | today's payout rule | 7.81 | 5.59 |
| | | nearest station | 7.00 | 7.15 |
| | | worst of 2 nearest | 4.29 | 13.30 |
| | | median of 3 nearest | 8.03 | 5.31 |
| Rain, 50 mm | 1.50 | today's payout rule | 1.02 | 0.47 |
| Heat, 2 h | 17.90 | today's payout rule | 15.28 | 8.77 |

## What this means

1. **Rain, today's rule.** A stall has about 19 days a year with a 20 mm work hour. Today's rule
   misses about 8 of them and pays about 6 other days. It pays fewer false alarms than the
   nearest gauge would, but it misses more of the stall's own storms (40.9% against 36.7%).
   Taking the middle of 3 gauges smooths out a storm that hits only one place.
2. **Rain, worst of 2.** It cuts missed losses to 22.5% (4.29 a year) but almost doubles false
   alarms (13.30 a year). That raises the payout cost and the premium.
3. **Rain, full days.** At 50 mm, today's rule misses 68.2% of the stall's full-loss storm days.
   A one-place cloudburst seldom reaches 50 mm at the middle of 3 gauges.
4. **Heat.** Stations rarely agree on hours at WBGT 32 °C or more. Today's rule (the nearest
   station not on hold) misses 85.4% of the stall's heat days, and 77.0% of its heat payouts fall
   on days the stall was below the line. Putting S142 and S128 on hold cut false alarms from 12.2
   to 8.8 a stall-year against reading the nearest station, and missed slightly more heat days
   (85.4% against 83.8%). A WBGT reading near 32 °C changes by station, so 2 hours at one
   station says little about a stall 2 km away. Only 9 stall-days reached 6 hours, which is too
   few to judge the top band.
5. **Haze** is not in the table. The index is one PSI reading per region, so the stall and its
   payout read the same number. Within a region the basis risk cannot be measured with this data.
6. **Flood** is not in the table. There is no PUB flood history in the repo yet.

## Limits

- **An upper bound.** Leaving a station out puts the payout station farther from "the stall"
  than in real life. The median distance to the payout station is 1.64 km left out against
  0.80 km from a hawker centre (rain), and 2.82 km against 1.59 km (WBGT). Real stalls are about
  half as far from their station, so their basis risk is lower than this table.
- **Weather, not sales.** A missed loss here is a bad-weather day at the stall with no payout. It
  is not a measured loss of sales.
- **Heat history is short:** 660 days from 31 stations.

## Recommendations (no change made to the product)

1. Say in the proposal that today's rule misses up to 41% of a stall's 20 mm storm days (an
   upper bound), and that it pays fewer false alarms in exchange. The brief asks for this number.
2. If the team wants fewer missed losses, "worst of 2 nearest" cuts them to 22.5%. It costs about
   8 more false-alarm days a stall a year at 20 mm. Deval's pricing page would need to price that
   before any change.
3. For heat, the one-station rule has high basis risk at 32 °C. This note did not test 31 °C or
   33 °C. Bring these numbers to the heat-band decision (a P2 row, waiting on the mentors).
