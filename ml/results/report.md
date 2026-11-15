# Hazard model results

Device cuda, budget standard. Test years are held out from training and tuning.
Baselines: climatology (same month and region in the training years) and persistence
(the last known reading). A model is only useful if it beats both.

## heat_h0_regression

Best: **lightgbm** (test rmse 0.7653).
Best baseline: climatology (0.8645).
Top features: latitude, era5_work_wetbulb_mean, longitude, era5_work_temp_mean, era5_temp_mean, era5_dew_mean, era5_wind_mean, era5_temp_max_mean_3d, era5_wetbulb_max, era5_work_wind_mean, era5_temp_max, day_of_year_sin, era5_temp_max_mean_30d, era5_rh_mean_30d, day_of_year_cos.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| lightgbm | 0.7653 | 0.5114 | 0.1466 | 0.2222 | 0.9437 | 0.3339 | -83.3647 | 54.9 |
| xgboost | 0.7768 | 0.4748 | 0.1208 | 0.2056 | 0.939 | 0.3604 | -75.7519 | 65.8 |
| random_forest | 0.784 | 0.5528 | 0.1042 | 0.1049 | 0.9427 | 0.3477 | -91.2594 | 50.2 |
| hist_gbm | 0.7905 | 0.5136 | 0.0895 | 0.2466 | 0.9396 | 0.3496 | -74.3421 | 70.1 |
| linear | 0.7978 | 0.4833 | 0.0724 | 0.0 | 0.9439 | 0.3486 | -100.0 | 8.8 |
| mlp | 0.8038 | 0.4076 | 0.0585 | 0.0 | 0.9439 | 0.3486 | -100.0 | 29.2 |
| catboost | 0.805 | 0.4749 | 0.0556 | 0.173 | 0.9351 | 0.3811 | -72.6504 | 783.3 |
| climatology | 0.8645 | 0.4866 | -0.089 | 0.0 | 0.9439 | 0.3486 | -100.0 | 0.0 |

## heat_h0_classification

Best: **hist_gbm** (test average_precision 0.242).
Best baseline: climatology (0.05773).

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| hist_gbm | 0.242 | 0.7956 | 0.1416 | 0.2631 | 0.0561 | 258.6 |
| lightgbm | 0.2282 | 0.7856 | 0.0487 | 0.1158 | 0.0561 | 26.0 |
| xgboost | 0.2278 | 0.7813 | 0.088 | 0.2692 | 0.0561 | 62.7 |
| catboost | 0.2091 | 0.79 | 0.0711 | 0.2618 | 0.0561 | 3807.9 |
| random_forest | 0.1694 | 0.7613 | 0.076 | 0.1957 | 0.0561 | 39.6 |
| linear | 0.1472 | 0.7263 | 0.5337 | 0.1189 | 0.0561 | 9.4 |
| mlp | 0.1468 | 0.6741 | 0.0523 | 0.0 | 0.0561 | 19.8 |
| climatology | 0.0577 | 0.4747 | 0.0555 | 0.0 | 0.0561 | 0.0 |

## heat_h1_regression

Best: **linear** (test rmse 0.6863).
Best baseline: persistence (0.8569).
Top features: hours_ge_32_lag1, hours_ge_32_mean30d, trigger_days_30d, hours_ge_32_mean7d, hours_ge_32_max7d, dmi_lag2m, hours_ge_32_lag2, oni_lag4m, era5_wind_mean, era5_rain_sum_30d, era5_temp_max, year, era5_temp_mean, era5_dew_mean, dmi_lag3m.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| linear | 0.6863 | 0.4058 | 0.3136 | 0.2981 | 0.9414 | 0.3339 | -73.2143 | 13.0 |
| mlp | 0.6895 | 0.3594 | 0.3073 | 0.3307 | 0.9408 | 0.3339 | -68.1391 | 21.7 |
| catboost | 0.693 | 0.4184 | 0.3002 | 0.1562 | 0.9418 | 0.3447 | -87.0301 | 866.2 |
| hist_gbm | 0.6944 | 0.4016 | 0.2974 | 0.1279 | 0.9451 | 0.3339 | -93.515 | 80.3 |
| xgboost | 0.6964 | 0.4162 | 0.2933 | 0.2443 | 0.941 | 0.3408 | -78.0075 | 64.2 |
| lightgbm | 0.702 | 0.4248 | 0.2818 | 0.2036 | 0.9416 | 0.3408 | -83.0827 | 44.0 |
| random_forest | 0.7305 | 0.493 | 0.2224 | 0.2386 | 0.941 | 0.3427 | -78.0075 | 65.2 |
| persistence | 0.8569 | 0.3842 | -0.07 | 0.3516 | 0.9226 | 0.4492 | -7.0489 | 0.0 |
| climatology | 0.8645 | 0.4866 | -0.089 | 0.0 | 0.9439 | 0.3486 | -100.0 | 0.0 |

## heat_h1_classification

Best: **random_forest** (test average_precision 0.4058).
Best baseline: persistence (0.1733).
Top features: hours_ge_32_mean7d, hours_ge_32_mean30d, hours_ge_32_max7d, trigger_days_30d, hours_ge_32_lag1, hours_ge_32_max30d, hours_ge_32_lag2, latitude, era5_dew_mean, era5_work_temp_mean, hours_ge_32_lag3, era5_work_wetbulb_mean, era5_temp_mean, day_of_year_sin, era5_temp_max_mean_30d.

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| random_forest | 0.4058 | 0.8994 | 0.0433 | 0.0 | 0.0561 | 40.9 |
| linear | 0.3967 | 0.9032 | 0.0416 | 0.328 | 0.0561 | 9.5 |
| xgboost | 0.3805 | 0.8883 | 0.0474 | 0.245 | 0.0561 | 47.7 |
| lightgbm | 0.3795 | 0.8908 | 0.0424 | 0.0493 | 0.0561 | 25.3 |
| mlp | 0.3759 | 0.8349 | 0.1346 | 0.2956 | 0.0561 | 23.1 |
| hist_gbm | 0.3056 | 0.8708 | 0.0608 | 0.3883 | 0.0561 | 240.5 |
| persistence | 0.1733 | 0.6724 | 0.07 | 0.3516 | 0.0561 | 0.0 |
| climatology | 0.0577 | 0.4747 | 0.0555 | 0.0 | 0.0561 | 0.0 |

## rain_h0_regression

Best: **lightgbm** (test rmse 2.748).
Best baseline: climatology (10).
Top features: rain_daily_mm, era5_rain_sum, era5_work_temp_mean, era5_work_wind_mean, era5_temp_mean, era5_work_sun_wh, era5_wind_mean, era5_work_rain_max_hour, era5_temp_max, era5_rain_max_hour, era5_rh_mean, day_of_year_sin, era5_work_rh_mean, era5_work_wetbulb_mean, era5_rain_sum_3d.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| lightgbm | 2.748 | 1.0725 | 0.925 | 0.8584 | 0.9567 | 0.2815 | -2.8971 | 204.5 |
| hist_gbm | 2.8014 | 1.0043 | 0.922 | 0.8616 | 0.9572 | 0.2824 | -0.3478 | 224.2 |
| xgboost | 2.8439 | 1.1232 | 0.9196 | 0.8579 | 0.956 | 0.2903 | -1.7784 | 266.4 |
| mlp | 3.0008 | 1.2305 | 0.9105 | 0.8551 | 0.9554 | 0.2977 | -3.7469 | 256.4 |
| linear | 4.3934 | 1.7038 | 0.8082 | 0.8093 | 0.9447 | 0.379 | -9.2112 | 32.6 |
| climatology | 10.0031 | 6.333 | 0.0057 | 0.0 | 0.9206 | 0.7722 | -100.0 | 0.2 |

## rain_h0_classification

Best: **lightgbm** (test average_precision 0.931).
Best baseline: climatology (0.0992).
Top features: rain_daily_mm, era5_work_wind_mean, era5_work_sun_wh, era5_wind_mean, era5_rain_sum, day_of_year_cos, era5_work_direct_sun_wh, era5_work_rh_mean, era5_work_temp_mean, era5_rain_sum_30d, day_of_year_sin, era5_temp_max, era5_rh_mean, oni_lag6m, era5_temp_max_mean_3d.

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| lightgbm | 0.931 | 0.9935 | 0.0154 | 0.8721 | 0.0794 | 208.8 |
| xgboost | 0.931 | 0.9935 | 0.0182 | 0.8622 | 0.0794 | 131.1 |
| random_forest | 0.928 | 0.9915 | 0.0154 | 0.8757 | 0.0794 | 531.5 |
| mlp | 0.9269 | 0.9936 | 0.0282 | 0.811 | 0.0794 | 409.3 |
| linear | 0.907 | 0.9924 | 0.0175 | 0.8433 | 0.0794 | 87.1 |
| climatology | 0.0992 | 0.5622 | 0.073 | 0.0 | 0.0794 | 0.2 |

## rain_h1_regression

Best: **random_forest** (test rmse 9.814).
Best baseline: climatology (10).
Top features: era5_rain_sum, era5_wind_mean, era5_work_wind_mean, era5_rain_sum_3d, era5_rain_max_hour, era5_rain_sum_7d, era5_work_rain_max_hour, era5_rh_mean_7d, day_of_year_cos, era5_rain_sum_30d, era5_rh_mean_3d, era5_work_direct_sun_wh, era5_rh_mean, era5_dry_days_in_a_row, day_of_year_sin.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| random_forest | 9.8141 | 6.1543 | 0.0429 | 0.0 | 0.9206 | 0.7722 | -100.0 | 410.8 |
| catboost | 9.8335 | 6.2127 | 0.0391 | 0.0 | 0.9206 | 0.7722 | -100.0 | 857.0 |
| lightgbm | 9.8466 | 6.2241 | 0.0366 | 0.0 | 0.9206 | 0.7722 | -100.0 | 279.1 |
| mlp | 9.8514 | 6.4209 | 0.0356 | 0.0 | 0.9206 | 0.7722 | -100.0 | 497.2 |
| xgboost | 9.857 | 6.3416 | 0.0345 | 0.0 | 0.9206 | 0.7722 | -100.0 | 475.4 |
| hist_gbm | 9.8599 | 6.2501 | 0.034 | 0.0 | 0.9206 | 0.7722 | -100.0 | 239.7 |
| linear | 9.8649 | 6.459 | 0.033 | 0.0 | 0.9206 | 0.7722 | -100.0 | 41.1 |
| climatology | 10.0031 | 6.333 | 0.0057 | 0.0 | 0.9206 | 0.7722 | -100.0 | 0.2 |
| persistence | 13.5973 | 7.1878 | -0.8372 | 0.1242 | 0.856 | 1.3901 | -0.4123 | 0.1 |

## rain_h1_classification

Best: **random_forest** (test average_precision 0.1285).
Best baseline: climatology (0.0992).
Top features: era5_rain_sum, era5_wind_mean, era5_work_wind_mean, era5_rain_sum_7d, era5_rain_sum_3d, era5_rain_max_hour, era5_work_rain_max_hour, era5_work_direct_sun_wh, era5_work_sun_wh, era5_rh_mean_7d, era5_rh_mean_3d, era5_rain_sum_30d, era5_rh_mean, day_of_year_cos, era5_rh_mean_30d.

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| random_forest | 0.1285 | 0.632 | 0.1069 | 0.0062 | 0.0794 | 696.2 |
| lightgbm | 0.1281 | 0.6297 | 0.0721 | 0.0 | 0.0794 | 293.6 |
| xgboost | 0.1251 | 0.6339 | 0.0737 | 0.0 | 0.0794 | 212.2 |
| mlp | 0.1215 | 0.63 | 0.1677 | 0.1903 | 0.0794 | 202.2 |
| linear | 0.1197 | 0.6251 | 0.0722 | 0.0 | 0.0794 | 161.9 |
| climatology | 0.0992 | 0.5622 | 0.073 | 0.0 | 0.0794 | 0.2 |
| persistence | 0.0852 | 0.5248 | 0.1387 | 0.1242 | 0.0794 | 0.2 |

## haze_season_count

Best: **climatology** (test poisson_deviance 1.872).
Best baseline: climatology (1.872).

| model | test_poisson_deviance | test_mae | test_total_bias_pct | seconds |
|---|---|---|---|---|
| climatology | 1.8719 | 0.8546 | -13.4645 | 0.0 |
| xgboost | 2.2569 | 0.6257 | -81.1973 | 34.5 |
| random_forest | 2.4575 | 1.0964 | 14.8171 | 61.8 |
| lightgbm | 3.584 | 0.631 | -90.8871 | 19.3 |
| catboost | 3.8343 | 0.6219 | -94.3486 | 192.7 |
| hist_gbm | 4.2127 | 0.636 | -92.9706 | 26.7 |
| linear | 4.4853 | 0.6437 | -91.1136 | 51.1 |
| persistence | 7.02 | 0.8851 | 0.0 | 0.0 |
| mlp | 7.9868 | 0.6292 | -96.9503 | 14.5 |

## rain_season_count

Best: **lightgbm** (test poisson_deviance 0.7007).
Best baseline: climatology (0.7229).
Top features: era5_month_temp_max_lag1m, trigger_days_lag12m, era5_month_rain_sum_lag1m, dmi_lag4m, dmi_lag2m, month_of_year, trigger_days_lag1m, dmi_lag6m, trigger_days_lag3m, era5_month_rh_mean_lag1m, trigger_days_lag2m, oni_lag6m, dmi_lag3m, oni_lag2m, oni_lag4m.

| model | test_poisson_deviance | test_mae | test_total_bias_pct | seconds |
|---|---|---|---|---|
| lightgbm | 0.7007 | 1.0489 | -7.3941 | 91.9 |
| random_forest | 0.7219 | 1.0598 | -5.2586 | 80.5 |
| climatology | 0.7229 | 1.007 | -5.7601 | 0.0 |
| xgboost | 0.7272 | 1.0615 | -9.8497 | 74.2 |
| linear | 0.7803 | 1.1222 | 5.3683 | 18.3 |
| catboost | 0.7841 | 1.0912 | -9.0035 | 118.9 |
| hist_gbm | 0.8154 | 1.1214 | -10.0334 | 33.7 |
| mlp | 0.9644 | 1.2909 | 19.7814 | 18.2 |
| persistence | 2.0918 | 1.4821 | 1.1162 | 0.0 |

## haze_h1_regression

Best: **linear** (test rmse 7.803).
Best baseline: persistence (8.024).
Top features: psi_max_lag1, psi_max_lag2, psi_max_mean7d, psi_max_max7d, psi_max_mean30d, psi_max_lag3, era5_work_sun_wh, psi_max_lag7, era5_temp_max_mean_3d, era5_wind_mean, psi_max_max30d, era5_temp_max, era5_rain_sum, trigger_days_30d, era5_work_wind_mean.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| linear | 7.8029 | 5.3001 | 0.8054 | 0.7668 | 0.9905 | 0.0914 | -28.2895 | 10.3 |
| random_forest | 7.9886 | 5.2048 | 0.7961 | 0.7946 | 0.9902 | 0.0942 | 0.6579 | 140.7 |
| persistence | 8.0237 | 5.3522 | 0.7943 | 0.7986 | 0.9909 | 0.0873 | 0.0 | 0.0 |
| hist_gbm | 8.1751 | 5.2623 | 0.7864 | 0.794 | 0.991 | 0.086 | -19.0789 | 145.6 |
| xgboost | 8.1955 | 5.2804 | 0.7854 | 0.7258 | 0.9892 | 0.1037 | -31.5789 | 477.8 |
| mlp | 8.2333 | 5.4134 | 0.7834 | 0.7611 | 0.9905 | 0.0914 | -32.2368 | 73.6 |
| lightgbm | 8.74 | 5.3734 | 0.7559 | 0.6807 | 0.9881 | 0.1146 | -38.1579 | 105.2 |
| climatology | 16.3613 | 10.6376 | 0.1445 | 0.0 | 0.9795 | 0.2074 | -100.0 | 0.0 |

## haze_h1_classification

Best: **mlp** (test average_precision 0.8557).
Best baseline: persistence (0.6419).

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| mlp | 0.8557 | 0.9897 | 0.0132 | 0.7031 | 0.0205 | 51.8 |
| linear | 0.8401 | 0.9923 | 0.0102 | 0.5231 | 0.0205 | 29.1 |
| xgboost | 0.764 | 0.987 | 0.0073 | 0.75 | 0.0205 | 82.2 |
| lightgbm | 0.7286 | 0.9928 | 0.0076 | 0.7668 | 0.0205 | 38.5 |
| random_forest | 0.6505 | 0.9917 | 0.0168 | 0.6832 | 0.0205 | 132.0 |
| persistence | 0.6419 | 0.8972 | 0.0082 | 0.7986 | 0.0205 | 0.0 |
| hist_gbm | 0.6142 | 0.9883 | 0.0177 | 0.2326 | 0.0205 | 153.2 |
| climatology | 0.1022 | 0.9095 | 0.0183 | 0.0 | 0.0205 | 0.0 |

## haze_h7_regression

Best: **random_forest** (test rmse 12.2).
Best baseline: persistence (13.82).
Top features: psi_max_mean7d, psi_max_lag8, psi_max_mean30d, psi_max_max7d, psi_max_lag7, psi_max_lag9, psi_max_max30d, psi_max_lag13, day_of_year_sin, year, day_of_year_cos, oni_lag2m, era5_rain_sum_30d, era5_temp_max_mean_30d, oni_lag3m.

| model | test_rmse | test_mae | test_r2 | test_trigger_f1 | test_band_accuracy | test_payout_mae_sgd | test_payout_bias_pct | seconds |
|---|---|---|---|---|---|---|---|---|
| random_forest | 12.1953 | 8.3598 | 0.5247 | 0.4144 | 0.9805 | 0.1883 | -48.6842 | 50.4 |
| hist_gbm | 12.474 | 8.6048 | 0.5027 | 0.2486 | 0.9797 | 0.2006 | -73.0263 | 132.0 |
| lightgbm | 12.4779 | 8.6798 | 0.5024 | 0.3756 | 0.9808 | 0.1924 | -54.6053 | 87.9 |
| linear | 12.8281 | 8.5931 | 0.4741 | 0.266 | 0.9797 | 0.1992 | -71.0526 | 12.0 |
| xgboost | 13.2542 | 8.843 | 0.4386 | 0.0403 | 0.9797 | 0.2061 | -96.7105 | 332.6 |
| persistence | 13.8182 | 9.5957 | 0.3898 | 0.5833 | 0.9808 | 0.1856 | 0.0 | 0.0 |
| mlp | 15.4885 | 9.8358 | 0.2334 | 0.0 | 0.9795 | 0.2074 | -100.0 | 71.0 |
| climatology | 16.3613 | 10.6376 | 0.1445 | 0.0 | 0.9795 | 0.2074 | -100.0 | 0.0 |

## haze_h7_classification

Best: **xgboost** (test average_precision 0.4672).
Best baseline: persistence (0.3488).
Top features: psi_max_mean7d, psi_max_lag8, psi_max_lag9, psi_max_lag7, psi_max_mean30d, day_of_year_sin, month, dmi_lag2m, psi_max_lag13, era5_rain_sum_30d, year, oni_lag3m, oni_lag4m, oni_lag2m, psi_max_max30d.

| model | test_average_precision | test_roc_auc | test_brier | test_f1_at_half | test_base_rate | seconds |
|---|---|---|---|---|---|---|
| xgboost | 0.4672 | 0.9854 | 0.0131 | 0.5404 | 0.0205 | 73.8 |
| random_forest | 0.4394 | 0.9809 | 0.0151 | 0.0 | 0.0205 | 63.6 |
| lightgbm | 0.4021 | 0.9833 | 0.0151 | 0.0 | 0.0205 | 56.2 |
| persistence | 0.3488 | 0.7873 | 0.0171 | 0.5833 | 0.0205 | 0.0 |
| hist_gbm | 0.3311 | 0.9683 | 0.0177 | 0.4404 | 0.0205 | 329.2 |
| linear | 0.2428 | 0.9331 | 0.0201 | 0.0 | 0.0205 | 45.4 |
| mlp | 0.1637 | 0.9341 | 0.0202 | 0.0468 | 0.0205 | 44.4 |
| climatology | 0.1022 | 0.9095 | 0.0183 | 0.0 | 0.0205 | 0.0 |
