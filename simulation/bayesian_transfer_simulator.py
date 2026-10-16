import math
from typing import Dict, List, Optional

from interfaces.player_engine import PlayerEngine


import numpy as np
import pandas as pd
import pymc as pm
import arviz as az


class BayesianTransferSimulator:
    """
    Hierarchical Bayesian logistic-regression transfer simulator.

    Estimates:

        P(transfer_success | fit, market, age, injury risk, salary)

    rather than assuming feature independence.

    The model produces:
    - posterior coefficients
    - posterior predictive success probabilities
    - credible intervals for predicted probabilities
    - calibration-oriented diagnostics
    """

    def __init__(
        self,
        random_seed: int = 42,
        draws: int = 2000,
        tune: int = 1000,
        chains: int = 4,
        target_accept: float = 0.9,
    ):
        self.random_seed = random_seed
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.target_accept = target_accept

        self.model = None
        self.idata = None
        self.feature_columns = None

    @staticmethod
    def _prepare_features(data: pd.DataFrame):
        data = data.copy()

        required = [
            "fit_level", "market_level", "age",
            "injury_risk", "salary", "transfer_success"
        ]

        missing = [c for c in required if c not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        data = data[data["transfer_success"].isin([0, 1])].copy()

        if data.empty:
            raise ValueError("No valid transfer observations.")

        # Ordered / categorical feature encoding.
        fit_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        market_map = {"RISKY": 0, "GOOD": 1, "EXCELLENT": 2}
        injury_map = {"low": 0, "medium": 1, "high": 2}

        data["fit_score"] = data["fit_level"].map(fit_map)
        data["market_score"] = data["market_level"].map(market_map)
        data["injury_score"] = data["injury_risk"].map(injury_map)

        if data[["fit_score", "market_score", "injury_score"]].isna().any().any():
            raise ValueError("Unknown category in fit, market or injury risk.")

        # Standardise continuous variables.
        for column in ["age", "salary"]:
            mean = data[column].mean()
            std = data[column].std()

            if std == 0 or np.isnan(std):
                raise ValueError(f"'{column}' has no variation.")

            data[f"{column}_z"] = (data[column] - mean) / std

        feature_columns = [
            "fit_score",
            "market_score",
            "age_z",
            "injury_score",
            "salary_z",
        ]

        X = data[feature_columns].to_numpy(dtype="float64")
        y = data["transfer_success"].to_numpy(dtype="int32")

        return data, X, y, feature_columns

    def fit(self, historical_data: pd.DataFrame):
        data, X, y, feature_columns = self._prepare_features(historical_data)

        self.feature_columns = feature_columns

        n_features = X.shape[1]

        with pm.Model() as self.model:
            X_data = pm.Data("X", X)
            y_data = pm.Data("y", y)

            # Weakly informative priors.
            intercept = pm.Normal("intercept", mu=0.0, sigma=1.5)

            # Hierarchical structure: feature effects share a common scale.
            global_scale = pm.HalfNormal("global_scale", sigma=1.0)

            coefficients = pm.Normal(
                "coefficients",
                mu=0.0,
                sigma=global_scale,
                shape=n_features,
            )

            logits = intercept + pm.math.dot(X_data, coefficients)

            pm.Bernoulli(
                "transfer_success",
                logit_p=logits,
                observed=y_data,
            )

            # Posterior predictive success probability for observed records.
            pm.Deterministic(
                "success_probability",
                pm.math.sigmoid(logits),
            )

            self.idata = pm.sample(
                draws=self.draws,
                tune=self.tune,
                chains=self.chains,
                target_accept=self.target_accept,
                random_seed=self.random_seed,
                return_inferencedata=True,
            )

        return self

    def predict_probability(
        self,
        player: dict,
        hdi_probability: float = 0.94,
    ):
        if self.idata is None:
            raise RuntimeError("Model must be fitted before prediction.")

        fit_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        market_map = {"RISKY": 0, "GOOD": 1, "EXCELLENT": 2}
        injury_map = {"low": 0, "medium": 1, "high": 2}

        try:
            fit_score = fit_map[player["fit_level"]]
            market_score = market_map[player["market_level"]]
            injury_score = injury_map[player["injury_risk"]]
        except KeyError as error:
            raise ValueError(f"Unknown category: {error}")

        # In production, store training means and standard deviations.
        age_z = (player["age"] - self._training_mean["age"]) / self._training_std["age"]
        salary_z = (
            (player["salary"] - self._training_mean["salary"])
            / self._training_std["salary"]
        )

        x = np.array(
            [fit_score, market_score, age_z, injury_score, salary_z],
            dtype="float64",
        )

        intercept_samples = self.idata.posterior["intercept"].values.flatten()
        coefficient_samples = (
            self.idata.posterior["coefficients"]
            .values.reshape(-1, len(self.feature_columns))
        )

        logits = intercept_samples + coefficient_samples @ x
        probabilities = 1 / (1 + np.exp(-logits))

        hdi = az.hdi(probabilities, hdi_prob=hdi_probability)

        return {
            "success_probability": float(probabilities.mean()),
            "probability_hdi": [float(hdi[0]), float(hdi[1])],
            "hdi_probability": hdi_probability,
        }

    def diagnostics(self):
        if self.idata is None:
            raise ValueError("Model must be fitted before diagnostics.")

        summary = az.summary(
            self.idata,
            var_names=["intercept", "coefficients"],
            kind="diagnostics",
        )

        return {
            "r_hat_max": float(summary["r_hat"].max()),
            "ess_bulk_min": float(summary["ess_bulk"].min()),
            "ess_tail_min": float(summary["ess_tail"].min()),
            "summary": summary,
        }


# =================================================================
# TEST DU MODULE
# =================================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(
        "BAYESIAN TRANSFER SIMULATION"
    )
    print("=" * 60)

    # =============================================================
    # HISTORICAL DATASET
    # =============================================================

    historical_data = pd.DataFrame({

        "fit_level": [

            "HIGH",
            "HIGH",
            "MEDIUM",
            "LOW",
            "HIGH",
            "MEDIUM",
            "LOW",
            "HIGH",
            "HIGH",
            "LOW",
            "MEDIUM",
            "HIGH"

        ],

        "market_level": [

            "GOOD",
            "GOOD",
            "GOOD",
            "RISKY",
            "EXCELLENT",
            "RISKY",
            "RISKY",
            "GOOD",
            "EXCELLENT",
            "RISKY",
            "GOOD",
            "GOOD"

        ],

        "age": [

            24,
            25,
            27,
            31,
            23,
            30,
            32,
            26,
            24,
            33,
            28,
            25

        ],

        "injury_risk": [

            "low",
            "low",
            "medium",
            "high",
            "low",
            "medium",
            "high",
            "low",
            "low",
            "high",
            "medium",
            "low"

        ],

        "salary": [

            7,
            8,
            12,
            22,
            6,
            18,
            25,
            9,
            7,
            24,
            14,
            8

        ],

        "transfer_success": [

            1,
            1,
            1,
            0,
            1,
            0,
            0,
            1,
            1,
            0,
            1,
            1

        ]

    })

    # =============================================================
    # TRAIN MODEL
    # =============================================================

    engine = (
        BayesianTransferSimulator()
    )

    engine.fit(
        historical_data
    )

    print()
    print(
        "MODEL TRAINED"
    )

    print(
        f"Historical transfers : "
        f"{engine.total_count}"
    )

    print(
        f"Successful transfers : "
        f"{engine.success_count}"
    )

    print(
        f"Failed transfers : "
        f"{engine.failure_count}"
    )

    print(
        f"Bayesian prior success : "
        f"{engine.prior_success_probability:.3f}"
    )

    # =============================================================
    # TEST 1
    # =============================================================

    print()
    print("-" * 60)
    print("TEST 1 — PROFIL FAVORABLE")
    print("-" * 60)

    player_1 = {

        "player":
            "Elite Candidate",

        "fit_level":
            "HIGH",

        "market_level":
            "GOOD",

        "age":
            25,

        "injury_risk":
            "low",

        "salary":
            8
    }

    result_1 = (
        engine.process(
            player_1
        )
    )

    print(result_1)

    assert (
        "success_probability"
        in result_1
    )

    assert (
        "risk_level"
        in result_1
    )

    assert (
        "probability_interval"
        in result_1
    )

    assert (
        "transfer_decision"
        not in result_1
    )

    assert (
        result_1[
            "success_probability"
        ] > 0.50
    )

    print(
        "TEST 1 PASSED"
    )

    # =============================================================
    # TEST 2
    # =============================================================

    print()
    print("-" * 60)
    print("TEST 2 — PROFIL RISQUÉ")
    print("-" * 60)

    player_2 = {

        "player":
            "Risky Candidate",

        "fit_level":
            "LOW",

        "market_level":
            "RISKY",

        "age":
            33,

        "injury_risk":
            "high",

        "salary":
            25
    }

    result_2 = (
        engine.process(
            player_2
        )
    )

    print(result_2)

    assert (
        result_2[
            "success_probability"
        ] < 0.50
    )

    assert (
        result_2[
            "risk_level"
        ] == "HIGH"
    )

    assert (
        "transfer_decision"
        not in result_2
    )

    print(
        "TEST 2 PASSED"
    )

    # =============================================================
    # TEST 3
    # =============================================================

    print()
    print("-" * 60)
    print("TEST 3 — API process()")
    print("-" * 60)

    player_3 = {

        "player":
            "API Test",

        "fit_level":
            "MEDIUM",

        "market_level":
            "GOOD",

        "age":
            27,

        "injury_risk":
            "medium",

        "salary":
            12
    }

    original_id = id(
        player_3
    )

    result_3 = (
        engine.process(
            player_3
        )
    )

    assert (
        id(result_3)
        ==
        original_id
    )

    assert (
        result_3[
            "success_probability"
        ]
        >= 0
    )

    assert (
        result_3[
            "success_probability"
        ]
        <= 1
    )

    print(
        "TEST 3 PASSED"
    )

    print()
    print("=" * 60)
    print(
        "ALL BAYESIAN TESTS PASSED"
    )
    print("=" * 60)