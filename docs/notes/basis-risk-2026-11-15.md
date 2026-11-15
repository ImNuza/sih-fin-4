# Basis risk: missed losses and false alarms per trigger option (15 Nov 2026)

The brief asks us to "show, from past NEA and PUB data, how often target customers would have
lost income or property with no payout". The burn analysis shows what SafeDay pays. This note
shows the other half: how often a payout misses a bad day at the stall, and how often it pays a
day that was fine at the stall. Ashutosh (14 Nov) asked for it as a confusion matrix per
trigger option.

All numbers come from `uv run scripts/basis_risk.py`, which writes
`data/processed/basis_risk.csv`. The band levels come from `api/default_tariff.json`.

## Method

We have no daily sales records, so the weather at the stall stands in for a lost day.

1. Each NEA rain gauge and WBGT station takes a turn as "the stall". Its own reading is the
   truth for that day.
2. Each trigger option reads only the other stations, as a payout would for a stall with no
   station of its own (leave one out):
   - **nearest station**: the rule the product uses today;
   - **worst of 2 nearest**: the higher of the 2 nearest stations;
   - **median of 3 nearest**: the middle of the 3 nearest stations.
3. A day is bad at a band level: the first band (the day pays part of a day) or the top band
   (the day pays in full).
4. For every day a station reported, the day is one of: **hit** (bad at the stall, paid),
   **missed loss** (bad at the stall, not paid), **false alarm** (fine at the stall, paid) or
   quiet. Days a station did not report are left out (see the fallback rule in
   `docs/notes/payout-flow-design-2026-11-15.md`).

Data: rain gauges, Dec 2016 to Nov 2026 (3,582 days, 590 stall-years). WBGT stations, Jan 2025
to Nov 2026 (660 days, 31 stall-years).

## Results

| Hazard and band | Option | Hit | Missed loss | False alarm | Missed share of bad days | False share of paid days |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Rain, 20 mm work hour (first band) | nearest station (today) | 6,986 | 4,222 | 4,368 | 37.7% | 38.5% |
| | worst of 2 nearest | 8,591 | 2,617 | 8,047 | 23.3% | 48.4% |
| | median of 3 nearest | 6,389 | 4,819 | 3,208 | 43.0% | 33.4% |
| Rain, 50 mm work hour (top band) | nearest station (today) | 371 | 498 | 503 | 57.3% | 57.6% |
| | worst of 2 nearest | 508 | 361 | 1,021 | 41.5% | 66.8% |
| | median of 3 nearest | 261 | 608 | 248 | 70.0% | 48.7% |
| Heat, 2 h at WBGT 32 °C (first band) | nearest station (today) | 69 | 411 | 349 | 85.6% | 83.5% |
| | worst of 2 nearest | 102 | 378 | 543 | 78.7% | 84.2% |
| | median of 3 nearest | 35 | 445 | 73 | 92.7% | 67.6% |
| Heat, 6 h at WBGT 32 °C (top band) | all three options | 0 | 9 | 0 to 1 | 100% | n/a |

Per stall per year (same file, columns `*_per_stall_year`):

| Hazard and band | Bad days at the stall | Option | Missed losses | False alarms |
| --- | ---: | --- | ---: | ---: |
| Rain, 20 mm | 18.99 | nearest station (today) | 7.15 | 7.40 |
| | | worst of 2 nearest | 4.43 | 13.63 |
| | | median of 3 nearest | 8.16 | 5.44 |
| Rain, 50 mm | 1.47 | nearest station (today) | 0.84 | 0.85 |
| Heat, 2 h | 15.42 | nearest station (today) | 13.20 | 11.21 |

## What this means

1. **Rain, today's rule.** A stall has about 19 days a year with a 20 mm work hour. The
   nearest-station rule misses about 7 of them and pays about 7 other days. So it pays about the
   right number of days, but often not on the stall's own bad days. On average the cover is fair.
   On a given day it can be wrong.
2. **Rain, worst of 2.** It cuts missed losses by 38% (7.15 to 4.43 a year) and almost doubles
   false alarms (7.40 to 13.63 a year). That raises the payout cost and the premium.
3. **Rain, median of 3.** It cuts false alarms but misses more storms. It is the wrong choice if
   the aim is fewer missed losses, which is the brief's question.
4. **Heat.** Stations rarely agree on hours at WBGT 32 °C or more. The nearest station misses 86%
   of the stall's heat days and 84% of its heat payouts fall on days the stall was below the
   line. A WBGT reading near 32 °C changes by station, so 2 hours at one station says little about
   a stall 2 km away. Only 9 stall-days reached 6 hours in 31 stall-years, which is too few to
   judge the top band.
5. **Haze** is not in the table. The index is one PSI reading per region, so the stall and its
   payout read the same number. Within a region the basis risk cannot be measured with this data.
6. **Flood** is not in the table. There is no PUB flood history in the repo yet.

## Limits

- **An upper bound.** Leaving a station out puts the payout station farther from "the stall"
  than in real life. The median distance to the payout station is 1.79 km left out against
  0.92 km from a hawker centre (rain), and 2.82 km against 1.59 km (WBGT). Real stalls are about
  half as far from their station, so their basis risk is lower than this table.
- **Weather, not sales.** A missed loss here is a bad-weather day at the stall with no payout. It
  is not a measured loss of sales.
- **Heat history is short:** 660 days from 31 stations.

## Recommendations (no change made to the product)

1. Say in the proposal that today's rule pays about the right number of rain days a year, and
   show the missed-loss share (38% at 20 mm, an upper bound) next to it. The brief asks for it.
2. For rain, "worst of 2 nearest" is the option that cuts missed losses most. It costs about 6
   more false-alarm days a stall a year at 20 mm. Deval's pricing page would need to price that
   before any change.
3. For heat, the one-station rule has high basis risk at 32 °C. This note did not test 31 °C or
   33 °C. Bring these numbers to the heat-band decision (a P2 row, waiting on the mentors).
