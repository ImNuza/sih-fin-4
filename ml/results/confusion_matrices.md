# Confusion matrices on the test years

Days per actual and predicted outcome, for the best model of each job. Rows are what
happened, columns what the model said. 'tariff band' compares the payout band of the
real and the predicted reading, so it shows payout errors directly.

## heat_h0_regression (random_forest), reading >= 2

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 4594 | 15 |
| trigger | 258 | 16 |

## heat_h0_regression (random_forest), tariff band

| actual \ predicted | none | from 2 | from 4 | from 6 |
|---|---|---|---|---|
| none | 4594 | 15 | 0 | 0 |
| from 2 | 195 | 9 | 0 | 0 |
| from 4 | 55 | 7 | 0 | 0 |
| from 6 | 8 | 0 | 0 | 0 |

## heat_h0_classification (random_forest), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 4468 | 141 |
| trigger | 229 | 45 |

## heat_h1_regression (mlp), reading >= 2

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 4560 | 49 |
| trigger | 210 | 64 |

## heat_h1_regression (mlp), tariff band

| actual \ predicted | none | from 2 | from 4 | from 6 |
|---|---|---|---|---|
| none | 4560 | 49 | 0 | 0 |
| from 2 | 170 | 34 | 0 | 0 |
| from 4 | 39 | 23 | 0 | 0 |
| from 6 | 1 | 7 | 0 | 0 |

## heat_h1_classification (random_forest), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 4609 | 0 |
| trigger | 274 | 0 |

## rain_h0_regression (lightgbm), reading >= 20

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 65622 | 882 |
| trigger | 760 | 4975 |

## rain_h0_regression (lightgbm), tariff band

| actual \ predicted | none | from 20 | from 30 | from 50 |
|---|---|---|---|---|
| none | 65622 | 794 | 88 | 0 |
| from 20 | 738 | 1760 | 466 | 8 |
| from 30 | 20 | 620 | 1445 | 79 |
| from 50 | 2 | 6 | 308 | 283 |

## rain_h0_classification (xgboost), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 64846 | 1658 |
| trigger | 133 | 5602 |

## rain_h1_regression (random_forest), reading >= 20

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 66504 | 0 |
| trigger | 5735 | 0 |

## rain_h1_regression (random_forest), tariff band

| actual \ predicted | none | from 20 | from 30 | from 50 |
|---|---|---|---|---|
| none | 66504 | 0 | 0 | 0 |
| from 20 | 2972 | 0 | 0 | 0 |
| from 30 | 2164 | 0 | 0 | 0 |
| from 50 | 599 | 0 | 0 | 0 |

## rain_h1_classification (lightgbm), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 66504 | 0 |
| trigger | 5735 | 0 |

## haze_h1_regression (random_forest), reading >= 101

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 6856 | 35 |
| trigger | 26 | 118 |

## haze_h1_regression (random_forest), tariff band

| actual \ predicted | none | from 101 | from 201 | from 301 |
|---|---|---|---|---|
| none | 6856 | 35 | 0 | 0 |
| from 101 | 26 | 110 | 0 | 0 |
| from 201 | 0 | 8 | 0 | 0 |
| from 301 | 0 | 0 | 0 | 0 |

## haze_h1_classification (random_forest), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 6769 | 122 |
| trigger | 6 | 138 |

## haze_h7_regression (mlp), reading >= 101

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 6891 | 0 |
| trigger | 144 | 0 |

## haze_h7_regression (mlp), tariff band

| actual \ predicted | none | from 101 | from 201 | from 301 |
|---|---|---|---|---|
| none | 6891 | 0 | 0 | 0 |
| from 101 | 136 | 0 | 0 | 0 |
| from 201 | 8 | 0 | 0 | 0 |
| from 301 | 0 | 0 | 0 | 0 |

## haze_h7_classification (linear), probability >= 0.5

| actual \ predicted | no trigger | trigger |
|---|---|---|
| no trigger | 6891 | 0 |
| trigger | 144 | 0 |
