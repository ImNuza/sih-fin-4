"""The models to compare, their hyperparameter search spaces, and baselines to beat.

Every model is built for one kind of target:
    regression       the reading itself (PSI, mm of rain, hours of heat)
    classification   whether the reading reaches the first payout band
    count            trigger days in a month (Poisson loss)

Libraries with native GPU support use it when the device is "cuda": XGBoost, CatBoost and the
PyTorch network. LightGBM and scikit-learn run on the CPU.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import optuna
import pandas as pd
from scipy.special import expit
from sklearn.base import BaseEstimator
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.config import SEED

KINDS = ("regression", "classification", "count")
MLP_EARLY_STOP_SHARE = 0.1
MLP_PATIENCE_EPOCHS = 5


@dataclass(frozen=True)
class Context:
    """What a model needs to know about the task it is built for."""

    kind: str
    device: str
    features: list[str]
    month_column: str
    persistence_column: str | None
    trigger: float


@dataclass(frozen=True)
class ModelSpec:
    name: str
    suggest: Callable[[optuna.Trial, str], dict] | None
    build: Callable[[dict, Context], BaseEstimator]
    available: Callable[[Context], bool] = lambda context: True


def imputed(estimator: BaseEstimator, scale: bool = False) -> BaseEstimator:
    steps = [SimpleImputer(strategy="median", keep_empty_features=True)]
    if scale:
        steps.append(StandardScaler())
    return make_pipeline(*steps, estimator)


class Climatology(BaseEstimator):
    """Mean of the target for the same calendar month and region in the training years."""

    def __init__(self, kind: str = "regression", month_column: str = "month") -> None:
        self.kind = kind
        self.month_column = month_column

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> Climatology:
        keys = [X[self.month_column], X["region_code"]]
        self.means_ = pd.Series(np.asarray(y, dtype=float), index=X.index).groupby(keys).mean()
        self.overall_ = float(np.mean(y))
        return self

    def _values(self, X: pd.DataFrame) -> np.ndarray:
        index = pd.MultiIndex.from_arrays([X[self.month_column], X["region_code"]])
        return self.means_.reindex(index).fillna(self.overall_).to_numpy()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._values(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        share = self._values(X)
        return np.column_stack([1 - share, share])


class Persistence(BaseEstimator):
    """Tomorrow looks like the last known day (or month)."""

    def __init__(
        self, kind: str = "regression", column: str = "", trigger: float = 0.0
    ) -> None:
        self.kind = kind
        self.column = column
        self.trigger = trigger

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> Persistence:
        self.fallback_ = float(np.nanmean(y))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X[self.column].fillna(self.fallback_).to_numpy(dtype=float)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        last = X[self.column].to_numpy(dtype=float)
        share = np.where(np.isnan(last), self.fallback_, last >= self.trigger).astype(float)
        return np.column_stack([1 - share, share])


class TorchMLP(BaseEstimator):
    """A feed-forward network on standardised features, trained with early stopping."""

    def __init__(
        self,
        kind: str = "regression",
        hidden: int = 256,
        layers: int = 2,
        dropout: float = 0.1,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        batch_size: int = 1024,
        epochs: int = 30,
        pos_weight: float = 1.0,
        device: str = "cpu",
    ) -> None:
        self.kind = kind
        self.hidden = hidden
        self.layers = layers
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.epochs = epochs
        self.pos_weight = pos_weight
        self.device = device

    def _network(self, inputs: int):
        import torch.nn as nn

        blocks: list[nn.Module] = []
        width = inputs
        for _ in range(self.layers):
            blocks += [nn.Linear(width, self.hidden), nn.ReLU(), nn.Dropout(self.dropout)]
            width = self.hidden
        blocks.append(nn.Linear(width, 1))
        return nn.Sequential(*blocks)

    def _loss(self):
        import torch
        import torch.nn as nn

        if self.kind == "classification":
            weight = torch.tensor([self.pos_weight], device=self.device)
            return nn.BCEWithLogitsLoss(pos_weight=weight)
        if self.kind == "count":
            return nn.PoissonNLLLoss(log_input=True)
        return nn.MSELoss()

    def fit(self, X: np.ndarray, y: np.ndarray) -> TorchMLP:
        import torch

        torch.manual_seed(SEED)
        features = torch.tensor(np.asarray(X, dtype=np.float32))
        target = np.asarray(y, dtype=np.float32)
        self.target_mean_, self.target_std_ = 0.0, 1.0
        if self.kind == "regression":
            self.target_mean_, self.target_std_ = float(target.mean()), float(target.std() or 1)
        target = torch.tensor((target - self.target_mean_) / self.target_std_)

        order = np.random.default_rng(SEED).permutation(len(features))
        cut = int(len(order) * (1 - MLP_EARLY_STOP_SHARE))
        train_rows, check_rows = order[:cut], order[cut:]
        network = self._network(features.shape[1]).to(self.device)
        optimiser = torch.optim.AdamW(
            network.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )
        loss_function = self._loss()
        check_x = features[check_rows].to(self.device)
        check_y = target[check_rows].to(self.device)
        best_loss, best_state, stale_epochs = float("inf"), None, 0
        for epoch in range(self.epochs):
            network.train()
            shuffled = np.random.default_rng(SEED + epoch).permutation(train_rows)
            for start in range(0, len(shuffled), self.batch_size):
                rows = shuffled[start : start + self.batch_size]
                optimiser.zero_grad()
                output = network(features[rows].to(self.device)).squeeze(1)
                loss_function(output, target[rows].to(self.device)).backward()
                optimiser.step()
            network.eval()
            with torch.no_grad():
                check_loss = loss_function(network(check_x).squeeze(1), check_y).item()
            if check_loss < best_loss:
                best_loss, stale_epochs = check_loss, 0
                best_state = {k: v.detach().cpu().clone() for k, v in network.state_dict().items()}
            else:
                stale_epochs += 1
                if stale_epochs >= MLP_PATIENCE_EPOCHS:
                    break
        self.inputs_ = features.shape[1]
        self.state_ = best_state
        return self

    def _raw(self, X: np.ndarray) -> np.ndarray:
        import torch

        network = self._network(self.inputs_)
        network.load_state_dict(self.state_)
        network.to(self.device).eval()
        with torch.no_grad():
            features = torch.tensor(np.asarray(X, dtype=np.float32), device=self.device)
            return network(features).squeeze(1).cpu().numpy()

    def predict(self, X: np.ndarray) -> np.ndarray:
        raw = self._raw(X)
        if self.kind == "count":
            return np.exp(raw)
        return raw * self.target_std_ + self.target_mean_

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        share = expit(self._raw(X))
        return np.column_stack([1 - share, share])


def suggest_linear(trial: optuna.Trial, kind: str) -> dict:
    if kind == "classification":
        return {
            "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
            "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
        }
    return {"alpha": trial.suggest_float("alpha", 1e-4, 1e3, log=True)}


def build_linear(params: dict, context: Context) -> BaseEstimator:
    if context.kind == "classification":
        return imputed(LogisticRegression(max_iter=2000, **params), scale=True)
    if context.kind == "count":
        return imputed(PoissonRegressor(max_iter=2000, **params), scale=True)
    return imputed(Ridge(**params), scale=True)


def suggest_random_forest(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
        "max_depth": trial.suggest_int("max_depth", 4, 30),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 100, log=True),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.3, 0.6, 1.0]),
        "max_samples": trial.suggest_float("max_samples", 0.2, 1.0),
    }
    if kind == "classification":
        params["class_weight"] = trial.suggest_categorical(
            "class_weight", [None, "balanced_subsample"]
        )
    return params


def build_random_forest(params: dict, context: Context) -> BaseEstimator:
    shared = {"n_jobs": -1, "random_state": SEED, **params}
    if context.kind == "classification":
        return imputed(RandomForestClassifier(**shared))
    criterion = "poisson" if context.kind == "count" else "squared_error"
    return imputed(RandomForestRegressor(criterion=criterion, **shared))


def suggest_hist_gbm(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "max_iter": trial.suggest_int("max_iter", 100, 1000, step=50),
        "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 255, log=True),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 200, log=True),
        "l2_regularization": trial.suggest_float("l2_regularization", 1e-6, 10, log=True),
    }
    if kind == "classification":
        params["class_weight"] = trial.suggest_categorical("class_weight", [None, "balanced"])
    return params


def build_hist_gbm(params: dict, context: Context) -> BaseEstimator:
    if context.kind == "classification":
        return HistGradientBoostingClassifier(random_state=SEED, **params)
    loss = "poisson" if context.kind == "count" else "squared_error"
    return HistGradientBoostingRegressor(loss=loss, random_state=SEED, **params)


def suggest_xgboost(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 2000, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "min_child_weight": trial.suggest_float("min_child_weight", 1, 50, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10, log=True),
        "gamma": trial.suggest_float("gamma", 0, 5),
    }
    if kind == "classification":
        params["scale_pos_weight"] = trial.suggest_float("scale_pos_weight", 1, 50, log=True)
    return params


def build_xgboost(params: dict, context: Context) -> BaseEstimator:
    import xgboost

    shared = {"tree_method": "hist", "device": context.device, "random_state": SEED, **params}
    if context.kind == "classification":
        return xgboost.XGBClassifier(objective="binary:logistic", **shared)
    objective = "count:poisson" if context.kind == "count" else "reg:squarederror"
    return xgboost.XGBRegressor(objective=objective, **shared)


def suggest_lightgbm(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 2000, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 200, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10, log=True),
    }
    if kind == "classification":
        params["scale_pos_weight"] = trial.suggest_float("scale_pos_weight", 1, 50, log=True)
    return params


def build_lightgbm(params: dict, context: Context) -> BaseEstimator:
    import lightgbm

    shared = {"subsample_freq": 1, "random_state": SEED, "verbose": -1, "n_jobs": -1, **params}
    if context.kind == "classification":
        return lightgbm.LGBMClassifier(**shared)
    objective = "poisson" if context.kind == "count" else "regression"
    return lightgbm.LGBMRegressor(objective=objective, **shared)


def suggest_catboost(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "iterations": trial.suggest_int("iterations", 300, 3000, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "depth": trial.suggest_int("depth", 4, 10),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 30, log=True),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0, 1),
        "border_count": trial.suggest_int("border_count", 32, 254),
    }
    if kind == "classification":
        params["scale_pos_weight"] = trial.suggest_float("scale_pos_weight", 1, 50, log=True)
    return params


def build_catboost(params: dict, context: Context) -> BaseEstimator:
    import catboost

    # Monthly count tables have a few hundred rows: the GPU only adds start-up time there.
    on_gpu = context.device == "cuda" and context.kind != "count"
    shared = {
        "task_type": "GPU" if on_gpu else "CPU",
        "random_seed": SEED,
        "verbose": 0,
        "allow_writing_files": False,
        **params,
    }
    if context.kind == "classification":
        return catboost.CatBoostClassifier(loss_function="Logloss", **shared)
    loss = "Poisson" if context.kind == "count" else "RMSE"
    return catboost.CatBoostRegressor(loss_function=loss, **shared)


def suggest_mlp(trial: optuna.Trial, kind: str) -> dict:
    params = {
        "hidden": trial.suggest_int("hidden", 64, 1024, log=True),
        "layers": trial.suggest_int("layers", 1, 4),
        "dropout": trial.suggest_float("dropout", 0.0, 0.5),
        "learning_rate": trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-7, 1e-2, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [256, 512, 1024, 2048]),
        "epochs": trial.suggest_int("epochs", 10, 60, step=10),
    }
    if kind == "classification":
        params["pos_weight"] = trial.suggest_float("pos_weight", 1, 50, log=True)
    return params


def build_mlp(params: dict, context: Context) -> BaseEstimator:
    return imputed(TorchMLP(kind=context.kind, device=context.device, **params), scale=True)


MODELS = {
    spec.name: spec
    for spec in (
        ModelSpec(
            "climatology",
            None,
            lambda params, context: Climatology(context.kind, context.month_column),
        ),
        ModelSpec(
            "persistence",
            None,
            lambda params, context: Persistence(
                context.kind, context.persistence_column or "", context.trigger
            ),
            available=lambda context: context.persistence_column is not None,
        ),
        ModelSpec("linear", suggest_linear, build_linear),
        ModelSpec("random_forest", suggest_random_forest, build_random_forest),
        ModelSpec("hist_gbm", suggest_hist_gbm, build_hist_gbm),
        ModelSpec("xgboost", suggest_xgboost, build_xgboost),
        ModelSpec("lightgbm", suggest_lightgbm, build_lightgbm),
        ModelSpec("catboost", suggest_catboost, build_catboost),
        ModelSpec("mlp", suggest_mlp, build_mlp),
    )
}


def predict(model: BaseEstimator, X: pd.DataFrame, kind: str) -> np.ndarray:
    """Probability of a trigger for classification, the expected value otherwise."""
    if kind == "classification":
        return model.predict_proba(X)[:, 1]
    return np.clip(model.predict(X), 0, None)
