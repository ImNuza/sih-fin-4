# Confusion matrices on the test years

Each row is one model scored on the held-out test years, counting station-days (heat, rain)
or region-days (haze). A trigger day is a day whose reading reaches the first payout band, so
it is a day the policy pays.

- **TP** (true positive): a payout day the model called. **FN** (false negative): a payout
  day it missed. **FP** (false positive): a day it called that paid nothing. **TN** (true
  negative): a quiet day it left alone.
- **Accuracy** is the share of all days called right. Trigger days are rare (the base rate
  column), so a model that always says "no trigger" already scores 1 minus the base rate.
  The "always-no accuracy" column shows that bar. Accuracy alone cannot rank these models.
- **Precision** is TP / (TP + FP): of the days the model flags, how many really pay. Low
  precision means false alarms: payouts or warnings for days that never triggered.
- **Recall** is TP / (TP + FN): of the days that really pay, how many the model caught.
  Low recall means missed payout days.
- **F1** balances the two. Average precision (in report.md) ranks the models over every
  cut-off, not only 0.5, and is what the tuning maximised.

Why it matters for the insurance product:

- Horizon 0 models rebuild past days from weather data to fill in history. That history
  sets the premium. Missed trigger days (low recall) make the history look calmer than it
  was and under-price the cover. False alarms (low precision) over-price it.
- Horizon 1 and 7 models forecast the next day or week. A miss means a payout day arrives
  without warning, so reserves and customer alerts are late. A false alarm means a warning,
  or cash set aside, for a day that pays nothing.
- Payouts are made from the measured readings, never from the model, so these errors cost
  pricing accuracy and warning quality, not customers' claims.
- The 0.5 cut-off is not tuned. A lower cut-off trades precision for recall, and the right
  trade depends on whether a missed payout day or a false alarm costs more.


## haze_h1_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 7035 | 0.0205 | 115 | 29 | 29 | 6862 | 0.9918 | 0.9795 | 0.7986 | 0.7986 | 0.7986 | 0.6419 |
| lightgbm | 7035 | 0.0205 | 120 | 24 | 49 | 6842 | 0.9896 | 0.9795 | 0.7101 | 0.8333 | 0.7668 | 0.7286 |
| xgboost | 7035 | 0.0205 | 111 | 33 | 41 | 6850 | 0.9895 | 0.9795 | 0.7303 | 0.7708 | 0.75 | 0.764 |
| mlp | 7035 | 0.0205 | 135 | 9 | 105 | 6786 | 0.9838 | 0.9795 | 0.5625 | 0.9375 | 0.7031 | 0.8557 |
| random_forest | 7035 | 0.0205 | 138 | 6 | 122 | 6769 | 0.9818 | 0.9795 | 0.5308 | 0.9583 | 0.6832 | 0.6505 |
| linear | 7035 | 0.0205 | 51 | 93 | 0 | 6891 | 0.9868 | 0.9795 | 1.0 | 0.3542 | 0.5231 | 0.8401 |
| hist_gbm | 7035 | 0.0205 | 20 | 124 | 8 | 6883 | 0.9812 | 0.9795 | 0.7143 | 0.1389 | 0.2326 | 0.6142 |
| climatology | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 | 0.1022 |

## haze_h1_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 7035 | 0.0205 | 115 | 29 | 29 | 6862 | 0.9918 | 0.9795 | 0.7986 | 0.7986 | 0.7986 |  |
| random_forest | 7035 | 0.0205 | 118 | 26 | 35 | 6856 | 0.9913 | 0.9795 | 0.7712 | 0.8194 | 0.7946 |  |
| hist_gbm | 7035 | 0.0205 | 106 | 38 | 17 | 6874 | 0.9922 | 0.9795 | 0.8618 | 0.7361 | 0.794 |  |
| linear | 7035 | 0.0205 | 97 | 47 | 12 | 6879 | 0.9916 | 0.9795 | 0.8899 | 0.6736 | 0.7668 |  |
| mlp | 7035 | 0.0205 | 94 | 50 | 9 | 6882 | 0.9916 | 0.9795 | 0.9126 | 0.6528 | 0.7611 |  |
| xgboost | 7035 | 0.0205 | 90 | 54 | 14 | 6877 | 0.9903 | 0.9795 | 0.8654 | 0.625 | 0.7258 |  |
| lightgbm | 7035 | 0.0205 | 81 | 63 | 13 | 6878 | 0.9892 | 0.9795 | 0.8617 | 0.5625 | 0.6807 |  |
| climatology | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 |  |

## haze_h7_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 7035 | 0.0205 | 84 | 60 | 60 | 6831 | 0.9829 | 0.9795 | 0.5833 | 0.5833 | 0.5833 | 0.3488 |
| xgboost | 7035 | 0.0205 | 87 | 57 | 91 | 6800 | 0.979 | 0.9795 | 0.4888 | 0.6042 | 0.5404 | 0.4672 |
| hist_gbm | 7035 | 0.0205 | 72 | 72 | 111 | 6780 | 0.974 | 0.9795 | 0.3934 | 0.5 | 0.4404 | 0.3311 |
| mlp | 7035 | 0.0205 | 4 | 140 | 23 | 6868 | 0.9768 | 0.9795 | 0.1481 | 0.0278 | 0.0468 | 0.1637 |
| climatology | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 | 0.1022 |
| linear | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 | 0.2428 |
| random_forest | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 | 0.4394 |
| lightgbm | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 | 0.4021 |

## haze_h7_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 7035 | 0.0205 | 84 | 60 | 60 | 6831 | 0.9829 | 0.9795 | 0.5833 | 0.5833 | 0.5833 |  |
| random_forest | 7035 | 0.0205 | 46 | 98 | 32 | 6859 | 0.9815 | 0.9795 | 0.5897 | 0.3194 | 0.4144 |  |
| lightgbm | 7035 | 0.0205 | 40 | 104 | 29 | 6862 | 0.9811 | 0.9795 | 0.5797 | 0.2778 | 0.3756 |  |
| linear | 7035 | 0.0205 | 25 | 119 | 19 | 6872 | 0.9804 | 0.9795 | 0.5682 | 0.1736 | 0.266 |  |
| hist_gbm | 7035 | 0.0205 | 23 | 121 | 18 | 6873 | 0.9802 | 0.9795 | 0.561 | 0.1597 | 0.2486 |  |
| xgboost | 7035 | 0.0205 | 3 | 141 | 2 | 6889 | 0.9797 | 0.9795 | 0.6 | 0.0208 | 0.0403 |  |
| climatology | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 |  |
| mlp | 7035 | 0.0205 | 0 | 144 | 0 | 6891 | 0.9795 | 0.9795 |  | 0.0 | 0.0 |  |

## heat_h0_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| xgboost | 4883 | 0.0561 | 112 | 162 | 446 | 4163 | 0.8755 | 0.9439 | 0.2007 | 0.4088 | 0.2692 | 0.2278 |
| hist_gbm | 4883 | 0.0561 | 181 | 93 | 921 | 3688 | 0.7923 | 0.9439 | 0.1642 | 0.6606 | 0.2631 | 0.242 |
| catboost | 4883 | 0.0561 | 83 | 191 | 277 | 4332 | 0.9042 | 0.9439 | 0.2306 | 0.3029 | 0.2618 | 0.2091 |
| random_forest | 4883 | 0.0561 | 45 | 229 | 141 | 4468 | 0.9242 | 0.9439 | 0.2419 | 0.1642 | 0.1957 | 0.1694 |
| linear | 4883 | 0.0561 | 272 | 2 | 4028 | 581 | 0.1747 | 0.9439 | 0.0633 | 0.9927 | 0.1189 | 0.1472 |
| lightgbm | 4883 | 0.0561 | 18 | 256 | 19 | 4590 | 0.9437 | 0.9439 | 0.4865 | 0.0657 | 0.1158 | 0.2282 |
| climatology | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 | 0.0577 |
| mlp | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 | 0.1468 |

## heat_h0_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hist_gbm | 4883 | 0.0561 | 45 | 229 | 46 | 4563 | 0.9437 | 0.9439 | 0.4945 | 0.1642 | 0.2466 |  |
| lightgbm | 4883 | 0.0561 | 37 | 237 | 22 | 4587 | 0.947 | 0.9439 | 0.6271 | 0.135 | 0.2222 |  |
| xgboost | 4883 | 0.0561 | 37 | 237 | 49 | 4560 | 0.9414 | 0.9439 | 0.4302 | 0.135 | 0.2056 |  |
| catboost | 4883 | 0.0561 | 32 | 242 | 64 | 4545 | 0.9373 | 0.9439 | 0.3333 | 0.1168 | 0.173 |  |
| random_forest | 4883 | 0.0561 | 16 | 258 | 15 | 4594 | 0.9441 | 0.9439 | 0.5161 | 0.0584 | 0.1049 |  |
| climatology | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 |  |
| linear | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 |  |
| mlp | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 |  |

## heat_h1_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hist_gbm | 4883 | 0.0561 | 133 | 141 | 278 | 4331 | 0.9142 | 0.9439 | 0.3236 | 0.4854 | 0.3883 | 0.3056 |
| persistence | 4883 | 0.0561 | 93 | 181 | 162 | 4447 | 0.9298 | 0.9439 | 0.3647 | 0.3394 | 0.3516 | 0.1733 |
| linear | 4883 | 0.0561 | 62 | 212 | 42 | 4567 | 0.948 | 0.9439 | 0.5962 | 0.2263 | 0.328 | 0.3967 |
| mlp | 4883 | 0.0561 | 197 | 77 | 862 | 3747 | 0.8077 | 0.9439 | 0.186 | 0.719 | 0.2956 | 0.3759 |
| xgboost | 4883 | 0.0561 | 43 | 231 | 34 | 4575 | 0.9457 | 0.9439 | 0.5584 | 0.1569 | 0.245 | 0.3805 |
| lightgbm | 4883 | 0.0561 | 7 | 267 | 3 | 4606 | 0.9447 | 0.9439 | 0.7 | 0.0255 | 0.0493 | 0.3795 |
| climatology | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 | 0.0577 |
| random_forest | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 | 0.4058 |

## heat_h1_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 4883 | 0.0561 | 93 | 181 | 162 | 4447 | 0.9298 | 0.9439 | 0.3647 | 0.3394 | 0.3516 |  |
| mlp | 4883 | 0.0561 | 64 | 210 | 49 | 4560 | 0.947 | 0.9439 | 0.5664 | 0.2336 | 0.3307 |  |
| linear | 4883 | 0.0561 | 55 | 219 | 40 | 4569 | 0.947 | 0.9439 | 0.5789 | 0.2007 | 0.2981 |  |
| xgboost | 4883 | 0.0561 | 43 | 231 | 35 | 4574 | 0.9455 | 0.9439 | 0.5513 | 0.1569 | 0.2443 |  |
| random_forest | 4883 | 0.0561 | 42 | 232 | 36 | 4573 | 0.9451 | 0.9439 | 0.5385 | 0.1533 | 0.2386 |  |
| lightgbm | 4883 | 0.0561 | 34 | 240 | 26 | 4583 | 0.9455 | 0.9439 | 0.5667 | 0.1241 | 0.2036 |  |
| catboost | 4883 | 0.0561 | 25 | 249 | 21 | 4588 | 0.9447 | 0.9439 | 0.5435 | 0.0912 | 0.1562 |  |
| hist_gbm | 4883 | 0.0561 | 19 | 255 | 4 | 4605 | 0.947 | 0.9439 | 0.8261 | 0.0693 | 0.1279 |  |
| climatology | 4883 | 0.0561 | 0 | 274 | 0 | 4609 | 0.9439 | 0.9439 |  | 0.0 | 0.0 |  |

## rain_h0_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random_forest | 72239 | 0.0794 | 5322 | 413 | 1098 | 65406 | 0.9791 | 0.9206 | 0.829 | 0.928 | 0.8757 | 0.928 |
| lightgbm | 72239 | 0.0794 | 5362 | 373 | 1200 | 65304 | 0.9782 | 0.9206 | 0.8171 | 0.935 | 0.8721 | 0.931 |
| xgboost | 72239 | 0.0794 | 5602 | 133 | 1658 | 64846 | 0.9752 | 0.9206 | 0.7716 | 0.9768 | 0.8622 | 0.931 |
| linear | 72239 | 0.0794 | 4732 | 1003 | 756 | 65748 | 0.9757 | 0.9206 | 0.8622 | 0.8251 | 0.8433 | 0.907 |
| mlp | 72239 | 0.0794 | 5658 | 77 | 2560 | 63944 | 0.9635 | 0.9206 | 0.6885 | 0.9866 | 0.811 | 0.9269 |
| climatology | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 | 0.0992 |

## rain_h0_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hist_gbm | 72239 | 0.0794 | 5023 | 712 | 902 | 65602 | 0.9777 | 0.9206 | 0.8478 | 0.8759 | 0.8616 |  |
| lightgbm | 72239 | 0.0794 | 4975 | 760 | 882 | 65622 | 0.9773 | 0.9206 | 0.8494 | 0.8675 | 0.8584 |  |
| xgboost | 72239 | 0.0794 | 4988 | 747 | 905 | 65599 | 0.9771 | 0.9206 | 0.8464 | 0.8697 | 0.8579 |  |
| mlp | 72239 | 0.0794 | 4923 | 812 | 857 | 65647 | 0.9769 | 0.9206 | 0.8517 | 0.8584 | 0.8551 |  |
| linear | 72239 | 0.0794 | 4403 | 1332 | 743 | 65761 | 0.9713 | 0.9206 | 0.8556 | 0.7677 | 0.8093 |  |
| climatology | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |

## rain_h1_classification

Trigger called when probability >= 0.5.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mlp | 72239 | 0.0794 | 1994 | 3741 | 13225 | 53279 | 0.7651 | 0.9206 | 0.131 | 0.3477 | 0.1903 | 0.1215 |
| persistence | 72239 | 0.0794 | 711 | 5024 | 5001 | 61503 | 0.8612 | 0.9206 | 0.1245 | 0.124 | 0.1242 | 0.0852 |
| random_forest | 72239 | 0.0794 | 18 | 5717 | 38 | 66466 | 0.9203 | 0.9206 | 0.3214 | 0.0031 | 0.0062 | 0.1285 |
| climatology | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 | 0.0992 |
| linear | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 | 0.1197 |
| xgboost | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 | 0.1251 |
| lightgbm | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 | 0.1281 |

## rain_h1_regression

Trigger called when predicted reading in the first payout band.

| model | test_days | base_rate | TP | FN | FP | TN | accuracy | always_no_accuracy | precision | recall | f1 | average_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| persistence | 72239 | 0.0794 | 711 | 5024 | 5001 | 61503 | 0.8612 | 0.9206 | 0.1245 | 0.124 | 0.1242 |  |
| climatology | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| linear | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| random_forest | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| hist_gbm | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| xgboost | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| lightgbm | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| catboost | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
| mlp | 72239 | 0.0794 | 0 | 5735 | 0 | 66504 | 0.9206 | 0.9206 |  | 0.0 | 0.0 |  |
