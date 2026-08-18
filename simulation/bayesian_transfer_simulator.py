import math
from typing import Dict, List, Optional

import pandas as pd

from interfaces.player_engine import PlayerEngine


class BayesianTransferSimulator(PlayerEngine):

    """
    Bayesian Transfer Simulator

    ---------------------------------------------------------------
    Modèle :
        Bayesian Naive Bayes

    Objectif :
        Estimer P(transfer_success | player_features)

    Le modèle utilise :

        P(Success | Features)

    ∝

        P(Success)
        ×
        Π P(Feature_i | Success)

    Les probabilités conditionnelles sont estimées avec
    des distributions Beta.

    ---------------------------------------------------------------
    Important :

    Ce moteur NE prend PAS de décision de recrutement.

    Il produit uniquement :

        - success_probability
        - probability_interval
        - risk_level
        - simulation_reasons

    La décision SIGN / MONITOR / AVOID appartient
    au RecruitmentEngine.
    """

    # =============================================================
    # INITIALISATION
    # =============================================================

    def __init__(
        self,
        prior_alpha: float = 2.0,
        prior_beta: float = 2.0
    ):

        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

        self.is_fitted = False

        self.feature_models = {}

        self.success_count = 0
        self.failure_count = 0

        self.total_count = 0

    # =============================================================
    # FEATURES
    # =============================================================

    @staticmethod
    def _extract_features(player: dict) -> dict:

        age = player.get("age")

        salary = player.get("salary")

        if age is None:
            age_bucket = "unknown"

        elif age <= 22:
            age_bucket = "young"

        elif age <= 27:
            age_bucket = "prime"

        elif age <= 30:
            age_bucket = "experienced"

        else:
            age_bucket = "veteran"

        if salary is None:
            salary_bucket = "unknown"

        elif salary <= 8:
            salary_bucket = "low"

        elif salary <= 15:
            salary_bucket = "medium"

        else:
            salary_bucket = "high"

        return {

            "fit_level":
                player.get(
                    "fit_level",
                    "LOW"
                ),

            "market_level":
                player.get(
                    "market_level",
                    "RISKY"
                ),

            "age_bucket":
                age_bucket,

            "injury_risk":
                player.get(
                    "injury_risk",
                    "medium"
                ),

            "salary_bucket":
                salary_bucket
        }

    # =============================================================
    # FIT MODEL
    # =============================================================

    def fit(
        self,
        historical_data: pd.DataFrame,
        target_column: str = "transfer_success"
    ):

        if historical_data is None:

            raise ValueError(
                "historical_data ne peut pas être None."
            )

        if historical_data.empty:

            raise ValueError(
                "historical_data est vide."
            )

        if target_column not in historical_data.columns:

            raise ValueError(
                f"La colonne '{target_column}' "
                f"est obligatoire."
            )

        data = historical_data.copy()

        # ---------------------------------------------------------
        # Vérification target
        # ---------------------------------------------------------

        data = data[
            data[target_column].isin([0, 1])
        ].copy()

        if data.empty:

            raise ValueError(
                "Aucune observation valide "
                "pour transfer_success."
            )

        self.total_count = len(data)

        self.success_count = int(
            data[target_column].sum()
        )

        self.failure_count = (
            self.total_count
            - self.success_count
        )

        if self.success_count == 0:

            raise ValueError(
                "Le dataset ne contient aucun "
                "transfert réussi."
            )

        if self.failure_count == 0:

            raise ValueError(
                "Le dataset ne contient aucun "
                "transfert échoué."
            )

        # ---------------------------------------------------------
        # Prior Bayesian
        # ---------------------------------------------------------

        self.prior_success_probability = (

            (
                self.prior_alpha
                + self.success_count
            )
            /
            (
                self.prior_alpha
                + self.prior_beta
                + self.total_count
            )

        )

        # ---------------------------------------------------------
        # Feature models
        # ---------------------------------------------------------

        feature_columns = [

            "fit_level",
            "market_level",
            "age_bucket",
            "injury_risk",
            "salary_bucket"

        ]

        self.feature_models = {}

        # ---------------------------------------------------------
        # Construction des distributions Beta
        # ---------------------------------------------------------

        for feature in feature_columns:

            feature_data = {}

            temp = data.copy()

            # Créer les catégories dérivées
            if feature == "age_bucket":

                temp["age_bucket"] = temp["age"].apply(
                    self._age_bucket
                )

            elif feature == "salary_bucket":

                temp["salary_bucket"] = temp["salary"].apply(
                    self._salary_bucket
                )

            # Valeurs manquantes
            temp[feature] = (
                temp[feature]
                .fillna("unknown")
                .astype(str)
                .str.lower()
            )

            categories = temp[feature].unique()

            for category in categories:

                category_data = temp[
                    temp[feature] == category
                ]

                success = int(
                    category_data[
                        target_column
                    ].sum()
                )

                observations = len(
                    category_data
                )

                failure = (
                    observations
                    - success
                )

                # -------------------------------------------------
                # Beta posterior
                #
                # alpha_post = alpha_prior + successes
                # beta_post  = beta_prior + failures
                # -------------------------------------------------

                alpha_success = (
                    self.prior_alpha
                    + success
                )

                beta_success = (
                    self.prior_beta
                    + failure
                )

                # -------------------------------------------------
                # P(feature=value | success)
                #
                # Ici nous utilisons une estimation bayésienne
                # lissée par le prior.
                # -------------------------------------------------

                p_feature_given_success = (

                    alpha_success
                    /
                    (
                        alpha_success
                        + beta_success
                    )

                )

                # -------------------------------------------------
                # Distribution Beta pour la classe failure
                # -------------------------------------------------

                failure_success = failure

                failure_failure = (
                    observations
                    - failure_success
                )

                alpha_failure = (
                    self.prior_alpha
                    + failure_success
                )

                beta_failure = (
                    self.prior_beta
                    + failure_failure
                )

                p_feature_given_failure = (

                    alpha_failure
                    /
                    (
                        alpha_failure
                        + beta_failure
                    )

                )

                feature_data[
                    category
                ] = {

                    "success":
                        p_feature_given_success,

                    "failure":
                        p_feature_given_failure,

                    "observations":
                        observations,

                    "success_count":
                        success,

                    "failure_count":
                        failure
                }

            self.feature_models[
                feature
            ] = feature_data

        self.is_fitted = True

        return self

    # =============================================================
    # AGE BUCKET
    # =============================================================

    @staticmethod
    def _age_bucket(age):

        if pd.isna(age):

            return "unknown"

        if age <= 22:

            return "young"

        if age <= 27:

            return "prime"

        if age <= 30:

            return "experienced"

        return "veteran"

    # =============================================================
    # SALARY BUCKET
    # =============================================================

    @staticmethod
    def _salary_bucket(salary):

        if pd.isna(salary):

            return "unknown"

        if salary <= 8:

            return "low"

        if salary <= 15:

            return "medium"

        return "high"

    # =============================================================
    # BETA INTERVAL
    # =============================================================

    def _estimate_interval(
        self,
        probability: float,
        confidence: float = 0.90
    ):

        """
        Approximation bayésienne de l'incertitude.

        Nous utilisons une approximation normale autour
        de la probabilité prédictive.

        Ce n'est pas utilisé pour le calcul principal.
        Il sert à communiquer l'incertitude.
        """

        n = max(
            self.total_count,
            1
        )

        variance = (

            probability
            *
            (1 - probability)
            /
            n

        )

        std = math.sqrt(
            max(variance, 0)
        )

        z = 1.645

        lower = max(
            0.0,
            probability - z * std
        )

        upper = min(
            1.0,
            probability + z * std
        )

        return (
            round(lower, 2),
            round(upper, 2)
        )

    # =============================================================
    # BAYESIAN PREDICTION
    # =============================================================

    def predict_probability(
        self,
        player: dict
    ):

        if not self.is_fitted:

            raise RuntimeError(
                "Le modèle BayesianTransferSimulator "
                "doit être entraîné avec .fit() "
                "avant d'appeler .process()."
            )

        features = self._extract_features(
            player
        )

        # ---------------------------------------------------------
        # Prior
        # ---------------------------------------------------------

        prior_success = (

            (
                self.prior_alpha
                + self.success_count
            )
            /
            (
                self.prior_alpha
                + self.prior_beta
                + self.total_count
            )

        )

        prior_failure = 1 - prior_success

        # ---------------------------------------------------------
        # Log probabilities
        #
        # Nous travaillons en log pour éviter
        # les problèmes numériques.
        # ---------------------------------------------------------

        log_success = math.log(
            prior_success
        )

        log_failure = math.log(
            prior_failure
        )

        reasons = []

        # ---------------------------------------------------------
        # Evidence
        # ---------------------------------------------------------

        for feature, value in features.items():

            model = self.feature_models.get(
                feature,
                {}
            )

            category = str(
                value
            ).lower()

            statistics = model.get(
                category
            )

            if statistics is None:

                continue

            p_success = max(
                statistics["success"],
                1e-9
            )

            p_failure = max(
                statistics["failure"],
                1e-9
            )

            log_success += math.log(
                p_success
            )

            log_failure += math.log(
                p_failure
            )

            # -----------------------------------------------------
            # Explication
            # -----------------------------------------------------

            if (
                p_success
                >
                p_failure
            ):

                reasons.append(
                    f"{feature}={value} "
                    "constitue une evidence "
                    "favorable"
                )

            elif (
                p_success
                <
                p_failure
            ):

                reasons.append(
                    f"{feature}={value} "
                    "constitue une evidence "
                    "défavorable"
                )

        # ---------------------------------------------------------
        # Normalisation Bayésienne
        #
        # P(S|X) =
        #
        # P(X|S)P(S)
        # -------------------------
        # P(X|S)P(S) + P(X|F)P(F)
        # ---------------------------------------------------------

        max_log = max(
            log_success,
            log_failure
        )

        success_exp = math.exp(
            log_success - max_log
        )

        failure_exp = math.exp(
            log_failure - max_log
        )

        probability = (

            success_exp
            /
            (
                success_exp
                + failure_exp
            )

        )

        return (
            probability,
            reasons
        )

    # =============================================================
    # PROCESS
    # =============================================================

    def process(self, player):

        probability, reasons = (
            self.predict_probability(
                player
            )
        )

        # ---------------------------------------------------------
        # Risk classification
        # ---------------------------------------------------------

        if probability >= 0.75:

            risk = "LOW"

        elif probability >= 0.55:

            risk = "MEDIUM"

        else:

            risk = "HIGH"

        # ---------------------------------------------------------
        # Uncertainty interval
        # ---------------------------------------------------------

        interval = self._estimate_interval(
            probability
        )

        # ---------------------------------------------------------
        # Update player
        # ---------------------------------------------------------

        player.update({

            "success_probability":
                round(
                    probability,
                    3
                ),

            "probability_interval":
                interval,

            "risk_level":
                risk,

            "simulation_reasons":
                reasons
        })

        return player


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