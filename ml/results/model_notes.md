# The models: why each one, and how it responded to tuning

Each tuned model ran 40 Optuna trials per job. A trial is one set of hyperparameters,
scored by its mean over 4 time-ordered validation folds (CV). Trials that were clearly
worse than the median after the first folds were stopped early; the trials column counts
only the ones that finished. The test column is the
chosen hyperparameters refitted on all training years and scored on the held-out years.
'Chosen' marks the model of each job with the best CV score, the one ml.publish ships.
The share next to a hyperparameter is how much of the spread in CV scores it explains.
A big gap between best and worst CV means the model is sensitive to its settings.

## climatology

Baseline. Predicts the average of the same month and region in the training years. It knows the season and nothing else, so any useful model must beat it.

| job | scored on | CV | test | chosen |
|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 0.02253 | 0.1022 |  |
| haze_h1_regression | rmse, lower is better | 15.95 | 16.36 |  |
| haze_h7_classification | average_precision, higher is better | 0.02253 | 0.1022 |  |
| haze_h7_regression | rmse, lower is better | 15.95 | 16.36 |  |
| haze_season_count | poisson_deviance, lower is better | 2.897 | 1.872 |  |
| heat_h0_classification | average_precision, higher is better | 0.05386 | 0.05773 |  |
| heat_h0_regression | rmse, lower is better | 0.6725 | 0.8645 |  |
| heat_h1_classification | average_precision, higher is better | 0.05386 | 0.05773 |  |
| heat_h1_regression | rmse, lower is better | 0.6725 | 0.8645 |  |
| rain_h0_classification | average_precision, higher is better | 0.1054 | 0.0992 |  |
| rain_h0_regression | rmse, lower is better | 10 | 10 |  |
| rain_h1_classification | average_precision, higher is better | 0.1054 | 0.0992 |  |
| rain_h1_regression | rmse, lower is better | 10 | 10 |  |
| rain_season_count | poisson_deviance, lower is better | 0.8461 | 0.7229 |  |

## persistence

Baseline for forecasts. Says tomorrow (or next week) looks like the last known reading. Haze and heat come in spells, so this is a hard baseline to beat at short horizons.

| job | scored on | CV | test | chosen |
|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 0.284 | 0.6419 |  |
| haze_h1_regression | rmse, lower is better | 7.17 | 8.024 |  |
| haze_h7_classification | average_precision, higher is better | 0.03374 | 0.3488 |  |
| haze_h7_regression | rmse, lower is better | 12.09 | 13.82 |  |
| haze_season_count | poisson_deviance, lower is better | 3.591 | 7.02 |  |
| heat_h1_classification | average_precision, higher is better | 0.09286 | 0.1733 |  |
| heat_h1_regression | rmse, lower is better | 0.7236 | 0.8569 |  |
| rain_h1_classification | average_precision, higher is better | 0.08881 | 0.08518 |  |
| rain_h1_regression | rmse, lower is better | 13.54 | 13.6 |  |
| rain_season_count | poisson_deviance, lower is better | 1.982 | 2.092 |  |

## linear

Ridge regression, logistic regression or Poisson regression on scaled features. Fast, hard to overfit, and its coefficients can be read. It shows how much of the signal is a straight-line effect of the weather features.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 16 | 0.369 | 0.3541 | 0.05612 | 0.8401 |  | C 66%, no clear direction; class_weight 34%, best balanced |
| haze_h1_regression | rmse, lower is better | 18 | 7.253 | 7.286 | 14.77 | 7.803 |  | alpha 100%, higher helped |
| haze_h7_classification | average_precision, higher is better | 19 | 0.2586 | 0.2151 | 0.03059 | 0.2428 | yes | C 58%, no clear direction; class_weight 42%, best balanced |
| haze_h7_regression | rmse, lower is better | 19 | 11.87 | 12.65 | 41.84 | 12.83 |  | alpha 100%, higher helped |
| haze_season_count | poisson_deviance, lower is better | 16 | 1.366 | 1.54 | 8.766 | 4.485 |  | alpha 100%, no clear direction |
| heat_h0_classification | average_precision, higher is better | 22 | 0.2029 | 0.2016 | 0.1237 | 0.1472 |  | C 94%, lower helped; class_weight 6%, best balanced |
| heat_h0_regression | rmse, lower is better | 19 | 0.648 | 0.6482 | 0.7126 | 0.7978 |  | alpha 100%, higher helped |
| heat_h1_classification | average_precision, higher is better | 26 | 0.2865 | 0.2824 | 0.145 | 0.3967 |  | C 86%, lower helped; class_weight 14%, best balanced |
| heat_h1_regression | rmse, lower is better | 19 | 0.6022 | 0.6041 | 0.7228 | 0.6863 |  | alpha 100%, higher helped |
| rain_h0_classification | average_precision, higher is better | 23 | 0.9158 | 0.9152 | 0.9067 | 0.907 |  | C 65%, lower helped; class_weight 35%, best balanced |
| rain_h0_regression | rmse, lower is better | 19 | 3.564 | 3.572 | 3.614 | 4.393 |  | alpha 100%, higher helped |
| rain_h1_classification | average_precision, higher is better | 27 | 0.1216 | 0.1208 | 0.111 | 0.1197 |  | C 89%, lower helped; class_weight 11%, best balanced |
| rain_h1_regression | rmse, lower is better | 19 | 9.944 | 9.957 | 10.09 | 9.865 |  | alpha 100%, higher helped |
| rain_season_count | poisson_deviance, lower is better | 24 | 0.6608 | 0.6818 | 469.8 | 0.7803 |  | alpha 100%, lower helped |

## random_forest

Averages many deep decision trees fitted on random samples. Handles thresholds and interactions (hot and still air together) with little tuning, and is robust to outliers. Saved models can be large.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 17 | 0.4714 | 0.4193 | 0.3089 | 0.6505 | yes | class_weight 25%, best balanced_subsample; max_depth 24%, lower helped |
| haze_h1_regression | rmse, lower is better | 32 | 6.827 | 6.914 | 8.028 | 7.989 | yes | max_features 49%, best 0.6; max_samples 27%, lower helped |
| haze_h7_classification | average_precision, higher is better | 8 | 0.1113 | 0.0984 | 0.08915 | 0.4394 |  | max_samples 33%, no clear direction; max_features 29%, best 0.3 |
| haze_h7_regression | rmse, lower is better | 27 | 10.64 | 10.8 | 13.97 | 12.2 |  | max_features 76%, best sqrt; min_samples_leaf 18%, higher helped |
| haze_season_count | poisson_deviance, lower is better | 25 | 1.901 | 2.15 | 2.71 | 2.458 |  | min_samples_leaf 68%, no clear direction; max_samples 16%, higher helped |
| heat_h0_classification | average_precision, higher is better | 11 | 0.248 | 0.2269 | 0.2054 | 0.1694 | yes | max_depth 34%, higher helped; class_weight 24%, best balanced_subsample |
| heat_h0_regression | rmse, lower is better | 11 | 0.6224 | 0.6259 | 0.6564 | 0.784 | yes | max_samples 29%, higher helped; n_estimators 27%, lower helped |
| heat_h1_classification | average_precision, higher is better | 17 | 0.2933 | 0.2788 | 0.2271 | 0.4058 | yes | min_samples_leaf 48%, higher helped; max_samples 18%, higher helped |
| heat_h1_regression | rmse, lower is better | 9 | 0.6129 | 0.6191 | 0.6504 | 0.7305 |  | max_features 51%, best 0.3; n_estimators 23%, higher helped |
| rain_h0_classification | average_precision, higher is better | 31 | 0.926 | 0.9254 | 0.8267 | 0.928 |  | max_samples 60%, no clear direction; max_features 20%, best 1.0 |
| rain_h1_classification | average_precision, higher is better | 25 | 0.1256 | 0.123 | 0.1123 | 0.1285 |  | class_weight 43%, best balanced_subsample; max_features 24%, best sqrt |
| rain_h1_regression | rmse, lower is better | 28 | 9.797 | 9.805 | 10.45 | 9.814 | yes | min_samples_leaf 56%, higher helped; max_features 43%, best sqrt |
| rain_season_count | poisson_deviance, lower is better | 29 | 0.6357 | 0.647 | 0.8191 | 0.7219 | yes | min_samples_leaf 48%, lower helped; n_estimators 18%, higher helped |

## hist_gbm

scikit-learn's gradient boosting on binned features. Builds trees one after another, each fixing the last one's errors, and handles missing readings natively. A strong boosted model with no extra library.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 19 | 0.3571 | 0.2643 | 0.1868 | 0.6142 |  | max_iter 35%, higher helped; learning_rate 20%, higher helped |
| haze_h1_regression | rmse, lower is better | 20 | 7.073 | 7.157 | 7.677 | 8.175 |  | min_samples_leaf 58%, higher helped; max_iter 15%, no clear direction |
| haze_h7_classification | average_precision, higher is better | 15 | 0.2124 | 0.1272 | 0.07564 | 0.3311 |  | max_iter 36%, lower helped; min_samples_leaf 27%, lower helped |
| haze_h7_regression | rmse, lower is better | 24 | 12.61 | 13.64 | 16.02 | 12.47 |  | min_samples_leaf 79%, higher helped; max_iter 16%, lower helped |
| haze_season_count | poisson_deviance, lower is better | 13 | 1.117 | 1.41 | 2.674 | 4.213 |  | learning_rate 40%, lower helped; min_samples_leaf 19%, higher helped |
| heat_h0_classification | average_precision, higher is better | 13 | 0.2127 | 0.1791 | 0.1406 | 0.242 |  | min_samples_leaf 35%, higher helped; l2_regularization 22%, higher helped |
| heat_h0_regression | rmse, lower is better | 12 | 0.6343 | 0.6421 | 0.6655 | 0.7905 |  | min_samples_leaf 38%, higher helped; max_leaf_nodes 37%, higher helped |
| heat_h1_classification | average_precision, higher is better | 10 | 0.2088 | 0.1802 | 0.1294 | 0.3056 |  | max_leaf_nodes 49%, lower helped; min_samples_leaf 18%, no clear direction |
| heat_h1_regression | rmse, lower is better | 12 | 0.6282 | 0.6387 | 0.7006 | 0.6944 |  | min_samples_leaf 67%, higher helped; max_iter 17%, no clear direction |
| rain_h0_regression | rmse, lower is better | 28 | 2.814 | 2.835 | 2.916 | 2.801 |  | min_samples_leaf 90%, higher helped; learning_rate 6%, lower helped |
| rain_h1_regression | rmse, lower is better | 32 | 9.837 | 9.871 | 10.2 | 9.86 |  | min_samples_leaf 42%, no clear direction; max_leaf_nodes 22%, lower helped |
| rain_season_count | poisson_deviance, lower is better | 27 | 0.6593 | 0.7095 | 0.8944 | 0.8154 |  | min_samples_leaf 60%, lower helped; max_iter 17%, no clear direction |

## xgboost

Regularised gradient boosting, trained on the GPU here. Usually among the best models on tabular data like daily weather tables.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 24 | 0.4297 | 0.3891 | 0.2149 | 0.764 |  | subsample 18%, no clear direction; reg_lambda 15%, higher helped |
| haze_h1_regression | rmse, lower is better | 25 | 6.968 | 7.115 | 7.987 | 8.195 |  | min_child_weight 49%, higher helped; learning_rate 39%, no clear direction |
| haze_h7_classification | average_precision, higher is better | 21 | 0.1772 | 0.1195 | 0.09599 | 0.4672 |  | gamma 31%, lower helped; subsample 21%, lower helped |
| haze_h7_regression | rmse, lower is better | 35 | 11.1 | 11.7 | 13.63 | 13.25 |  | subsample 39%, higher helped; reg_lambda 31%, higher helped |
| haze_season_count | poisson_deviance, lower is better | 20 | 0.9939 | 1.1 | 1.353 | 2.257 | yes | reg_alpha 35%, lower helped; colsample_bytree 17%, no clear direction |
| heat_h0_classification | average_precision, higher is better | 10 | 0.2201 | 0.2032 | 0.14 | 0.2278 |  | subsample 42%, higher helped; learning_rate 15%, lower helped |
| heat_h0_regression | rmse, lower is better | 28 | 0.6324 | 0.638 | 0.6691 | 0.7768 |  | min_child_weight 28%, lower helped; learning_rate 27%, no clear direction |
| heat_h1_classification | average_precision, higher is better | 18 | 0.2267 | 0.1996 | 0.114 | 0.3805 |  | min_child_weight 21%, no clear direction; n_estimators 19%, lower helped |
| heat_h1_regression | rmse, lower is better | 21 | 0.6221 | 0.6267 | 0.6589 | 0.6964 |  | learning_rate 32%, no clear direction; colsample_bytree 25%, lower helped |
| rain_h0_classification | average_precision, higher is better | 22 | 0.9295 | 0.9268 | 0.9048 | 0.931 | yes | colsample_bytree 24%, higher helped; subsample 18%, no clear direction |
| rain_h0_regression | rmse, lower is better | 26 | 2.789 | 2.854 | 3.379 | 2.844 |  | learning_rate 48%, lower helped; max_depth 31%, lower helped |
| rain_h1_classification | average_precision, higher is better | 16 | 0.1229 | 0.1201 | 0.1025 | 0.1251 |  | colsample_bytree 21%, higher helped; learning_rate 20%, lower helped |
| rain_h1_regression | rmse, lower is better | 28 | 9.831 | 9.952 | 11.6 | 9.857 |  | learning_rate 32%, lower helped; n_estimators 16%, lower helped |
| rain_season_count | poisson_deviance, lower is better | 29 | 0.651 | 0.6737 | 0.7533 | 0.7272 |  | gamma 40%, lower helped; reg_alpha 30%, lower helped |

## lightgbm

Gradient boosting that grows the most useful leaf first. The fastest boosted model on the CPU, which matters on the 212,000-row rain table.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 28 | 0.4631 | 0.397 | 0.1626 | 0.7286 |  | min_child_samples 51%, higher helped; n_estimators 21%, lower helped |
| haze_h1_regression | rmse, lower is better | 32 | 6.99 | 7.116 | 8.58 | 8.74 |  | learning_rate 73%, lower helped; num_leaves 11%, lower helped |
| haze_h7_classification | average_precision, higher is better | 25 | 0.176 | 0.1121 | 0.01898 | 0.4021 |  | learning_rate 67%, lower helped; n_estimators 8%, lower helped |
| haze_h7_regression | rmse, lower is better | 22 | 11.8 | 12.2 | 13.6 | 12.48 |  | min_child_samples 43%, lower helped; learning_rate 23%, lower helped |
| haze_season_count | poisson_deviance, lower is better | 20 | 1.148 | 1.2 | 2.225 | 3.584 |  | min_child_samples 39%, lower helped; learning_rate 23%, lower helped |
| heat_h0_classification | average_precision, higher is better | 11 | 0.2333 | 0.2151 | 0.1 | 0.2282 |  | colsample_bytree 27%, higher helped; learning_rate 24%, no clear direction |
| heat_h0_regression | rmse, lower is better | 25 | 0.6311 | 0.6388 | 0.677 | 0.7653 |  | colsample_bytree 60%, higher helped; learning_rate 29%, lower helped |
| heat_h1_classification | average_precision, higher is better | 28 | 0.2191 | 0.1978 | 0.1018 | 0.3795 |  | min_child_samples 59%, higher helped; n_estimators 9%, lower helped |
| heat_h1_regression | rmse, lower is better | 35 | 0.6209 | 0.6312 | 0.6921 | 0.702 |  | learning_rate 57%, lower helped; min_child_samples 23%, no clear direction |
| rain_h0_classification | average_precision, higher is better | 27 | 0.9267 | 0.9255 | 0.9119 | 0.931 |  | learning_rate 33%, no clear direction; scale_pos_weight 20%, lower helped |
| rain_h0_regression | rmse, lower is better | 29 | 2.775 | 2.812 | 3.266 | 2.748 | yes | learning_rate 83%, lower helped; subsample 5%, lower helped |
| rain_h1_classification | average_precision, higher is better | 26 | 0.1259 | 0.1229 | 0.1026 | 0.1281 | yes | learning_rate 40%, lower helped; num_leaves 16%, lower helped |
| rain_h1_regression | rmse, lower is better | 38 | 9.821 | 9.876 | 11.04 | 9.847 |  | learning_rate 69%, lower helped; num_leaves 9%, no clear direction |
| rain_season_count | poisson_deviance, lower is better | 34 | 0.6456 | 0.6696 | 0.8076 | 0.7007 |  | min_child_samples 67%, lower helped; learning_rate 21%, lower helped |

## catboost

Gradient boosting with ordered boosting, which overfits less on small tables such as heat (from January 2025 only). Trained on the GPU here and the slowest per trial.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_season_count | poisson_deviance, lower is better | 19 | 1.209 | 1.293 | 2.056 | 3.834 |  | iterations 48%, lower helped; depth 20%, higher helped |
| heat_h0_classification | average_precision, higher is better | 23 | 0.2438 | 0.2129 | 0.1289 | 0.2091 |  | bagging_temperature 59%, lower helped; scale_pos_weight 20%, higher helped |
| heat_h0_regression | rmse, lower is better | 17 | 0.6237 | 0.6321 | 0.6465 | 0.805 |  | l2_leaf_reg 44%, lower helped; learning_rate 29%, no clear direction |
| heat_h1_regression | rmse, lower is better | 30 | 0.6224 | 0.6308 | 0.6689 | 0.693 |  | bagging_temperature 33%, higher helped; border_count 32%, higher helped |
| rain_h1_regression | rmse, lower is better | 27 | 9.807 | 9.824 | 10.77 | 9.833 |  | border_count 46%, higher helped; learning_rate 26%, lower helped |
| rain_season_count | poisson_deviance, lower is better | 27 | 0.7895 | 0.84 | 1.394 | 0.7841 |  | learning_rate 62%, lower helped; border_count 13%, higher helped |

## mlp

A feed-forward neural network on standardised features, with early stopping. Tests whether a neural network adds anything over trees on tables of this size.

| job | tuned on | trials | best CV | median CV | worst CV | test | chosen | most influential hyperparameters |
|---|---|---|---|---|---|---|---|---|
| haze_h1_classification | average_precision, higher is better | 17 | 0.3401 | 0.3076 | 0.2391 | 0.8557 |  | pos_weight 46%, higher helped; hidden 34%, higher helped |
| haze_h1_regression | rmse, lower is better | 21 | 7.176 | 7.449 | 10.1 | 8.233 |  | hidden 26%, higher helped; learning_rate 23%, lower helped |
| haze_h7_classification | average_precision, higher is better | 21 | 0.2553 | 0.1754 | 0.1202 | 0.1637 |  | dropout 46%, lower helped; hidden 18%, no clear direction |
| haze_h7_regression | rmse, lower is better | 32 | 10.19 | 10.38 | 13.51 | 15.49 | yes | batch_size 67%, no clear direction; learning_rate 14%, lower helped |
| haze_season_count | poisson_deviance, lower is better | 19 | 1.013 | 1.458 | 2.822 | 7.987 |  | dropout 39%, lower helped; layers 20%, lower helped |
| heat_h0_classification | average_precision, higher is better | 13 | 0.173 | 0.1586 | 0.1359 | 0.1468 |  | hidden 76%, no clear direction; learning_rate 6%, higher helped |
| heat_h0_regression | rmse, lower is better | 21 | 0.6345 | 0.6389 | 0.6641 | 0.8038 |  | learning_rate 39%, lower helped; hidden 17%, lower helped |
| heat_h1_classification | average_precision, higher is better | 14 | 0.2265 | 0.2149 | 0.1211 | 0.3759 |  | batch_size 45%, lower helped; pos_weight 17%, higher helped |
| heat_h1_regression | rmse, lower is better | 26 | 0.591 | 0.6063 | 0.6681 | 0.6895 | yes | learning_rate 36%, lower helped; batch_size 25%, higher helped |
| rain_h0_classification | average_precision, higher is better | 22 | 0.9171 | 0.9147 | 0.9052 | 0.9269 |  | dropout 27%, higher helped; learning_rate 21%, lower helped |
| rain_h0_regression | rmse, lower is better | 15 | 3.006 | 3.07 | 3.279 | 3.001 |  | learning_rate 33%, no clear direction; weight_decay 24%, higher helped |
| rain_h1_classification | average_precision, higher is better | 22 | 0.1216 | 0.1169 | 0.09689 | 0.1215 |  | epochs 40%, lower helped; learning_rate 17%, lower helped |
| rain_h1_regression | rmse, lower is better | 26 | 9.84 | 9.943 | 11.62 | 9.851 |  | dropout 47%, higher helped; layers 21%, higher helped |
| rain_season_count | poisson_deviance, lower is better | 20 | 0.704 | 0.7736 | 2.425e+35 | 0.9644 |  | hidden 43%, higher helped; layers 28%, lower helped |

## Still tuning

These searches had not finished when this file was written, so the tables
above leave them out. One whose best CV so far beats a job's chosen model may
replace that model once it finishes and is published.

| job | model | finished trials so far | best CV so far |
|---|---|---|---|
| haze_h1_classification | catboost | 2 | 0.3722 |
| haze_h1_regression | catboost | 10 | 7.066 |
| haze_h7_classification | catboost | 2 | 0.1312 |
| haze_h7_regression | catboost | 10 | 11.05 |
| heat_h1_classification | catboost | 5 | 0.2347 |
| rain_h0_classification | catboost | 11 | 0.9306 |
| rain_h0_classification | hist_gbm | 25 | 0.9274 |
| rain_h0_regression | catboost | 27 | 2.708 |
| rain_h0_regression | random_forest | 33 | 2.746 |
| rain_h1_classification | catboost | 7 | 0.1226 |
| rain_h1_classification | hist_gbm | 11 | 0.1211 |
