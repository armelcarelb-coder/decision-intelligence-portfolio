import os
os.environ["PYTENSOR_FLAGS"] = "device=cpu, floatX=float64, cxx="

from dataclasses import dataclass
from typing import Dict, Optional
from interfaces.player_engine import PlayerEngine

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm


# ---------------------------------------------------------------------------
# Ability registry
# ---------------------------------------------------------------------------

ABILITY_REGISTRY = {
    "finishing": {
        "description": "Ability to convert expected-goal opportunities into goals.",
        "likelihood": "poisson_offset",
        "outcome": "goals",
        "exposure": "xg_total",
        "positions": [
            "STRIKER", "WINGER", "ATTACKING_MIDFIELDER",
            "CENTRAL_MIDFIELDER"
        ],
    },
    "chance_creation": {
        "description": "Ability to generate dangerous actions through key passes and assists.",
        "likelihood": "poisson_per90",
        "outcome": "key_passes",
        "positions": [
            "STRIKER", "WINGER", "ATTACKING_MIDFIELDER",
            "CENTRAL_MIDFIELDER", "FULL_BACK"
        ],
    },
    "ball_progression": {
        "description": "Ability to progress the ball through progressive passes.",
        "likelihood": "poisson_per90",
        "outcome": "progressive_passes",
        "positions": [
            "WINGER", "ATTACKING_MIDFIELDER", "CENTRAL_MIDFIELDER",
            "DEFENSIVE_MIDFIELDER", "FULL_BACK", "CENTRE_BACK"
        ],
    },
    "defensive_impact": {
        "description": "Ability to interrupt opponent actions through tackles and interceptions.",
        "likelihood": "poisson_per90",
        "outcome": "defensive_actions",
        "positions": [
            "FULL_BACK", "CENTRE_BACK", "DEFENSIVE_MIDFIELDER",
            "CENTRAL_MIDFIELDER"
        ],
    },
    "pressing_impact": {
        "description": "Ability to apply pressure and disrupt opponent build-up.",
        "likelihood": "poisson_per90",
        "outcome": "pressures",
        "positions": [
            "STRIKER", "WINGER", "ATTACKING_MIDFIELDER",
            "CENTRAL_MIDFIELDER", "DEFENSIVE_MIDFIELDER", "FULL_BACK"
        ],
    },
}


@dataclass
class PlayerSeasonRecord:
    player: str
    position: str
    minutes: float
    metrics: Dict[str, float]


class RoleAwareBayesianTalentEngine (PlayerEngine):
    """
    Role-aware Bayesian engine for player-ability estimation.

    The engine estimates separate ability dimensions and applies partial
    pooling by position group. It does not produce a universal talent score.

    Supported likelihoods
    ---------------------
    - poisson_offset: count outcome relative to an opportunity exposure.
    - poisson_per90: count outcome normalised by minutes played.
    - binomial: successful events relative to attempted events.
    - normal_per90: continuous per-90 output.

    Physical-output dimensions such as distance covered require a tracking or
    GPS source. They are not enabled unless that source is integrated.
    """

    def process(self, player: dict) -> dict:
        if self.idata is None:
            raise RuntimeError(
                "RoleAwareBayesianTalentEngine must be trained "
                "before calling process()."
            )

        player_name = player.get("player")

        if player_name not in self.player_index:
            raise ValueError(f"Unknown player: {player_name}")

        profile = self.player_profile(player_name)

        player.update(
            {
                "ability_profile": profile["abilities"],
                "ability_uncertainty": {
                    ability: {
                        "hdi_low": values["hdi_low"],
                        "hdi_high": values["hdi_high"],
                    }
                    for ability, values in profile["abilities"].items()
                },
            }
        )

        return player


    def __init__(
        self,
        abilities: list[str],
        random_seed: int = 42,
        draws: int = 2000,
        tune: int = 1000,
        chains: int = 4,
        target_accept: float = 0.9,
    ):
        unknown = [a for a in abilities if a not in ABILITY_REGISTRY]
        if unknown:
            raise ValueError(f"Unknown abilities: {unknown}")

        self.abilities = abilities
        self.random_seed = random_seed
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.target_accept = target_accept

        self.model = None
        self.idata: Optional[az.InferenceData] = None
        self.player_index: Optional[dict] = None
        self.position_index: Optional[dict] = None
        self.ability_index: Optional[dict] = None

    def _validate_records(self, records: list[PlayerSeasonRecord]):
        if not records:
            raise ValueError("At least one player record is required.")

        for record in records:
            if record.position not in self.position_index:
                continue

            for ability in self.abilities:
                spec = ABILITY_REGISTRY[ability]

                if record.position not in spec["positions"]:
                    continue

                required = [
                    spec[key]
                    for key in ("outcome", "exposure", "trials")
                    if key in spec
                ]

                missing = [
                    column for column in required
                    if column not in record.metrics
                ]

                if missing:
                    raise ValueError(
                        f"Player '{record.player}' is missing metrics "
                        f"{missing} required for '{ability}'."
                    )

    def _prepare_data(self, records: list[PlayerSeasonRecord]):
        players = sorted({r.player for r in records})
        positions = sorted({r.position for r in records})

        self.player_index = {p: i for i, p in enumerate(players)}
        self.position_index = {p: i for i, p in enumerate(positions)}
        self.ability_index = {a: i for i, a in enumerate(self.abilities)}

        self._validate_records(records)

        player_codes = np.array(
            [self.player_index[r.player] for r in records], dtype="int32"
        )
        position_codes = np.array(
            [self.position_index[r.position] for r in records], dtype="int32"
        )
        minutes = np.array([r.minutes for r in records], dtype="float64")

        return player_codes, position_codes, minutes, records

    def build_model(self, records: list[PlayerSeasonRecord]):
        (
            player_codes,
            position_codes,
            minutes,
            records,
        ) = self._prepare_data(records)

        defensive_actions = np.array(
            [
                record.metrics.get("tackles", 0)
                + record.metrics.get("interceptions", 0)
                for record in records
            ],
            dtype="float64",
        )

        n_players = len(self.player_index)
        n_positions = len(self.position_index)
        n_abilities = len(self.abilities)

        with pm.Model() as self.model:
            pm.Data("player_codes", player_codes)
            pm.Data("position_codes", position_codes)
            pm.Data("minutes", minutes)

            # Population-level ability distribution.
            population_mu = pm.Normal(
                "population_mu",
                mu=0.0,
                sigma=0.35,
                dims="ability",
            )

            population_sigma = pm.HalfNormal(
                "population_sigma",
                sigma=0.35,
                dims="ability",
            )

            # Position-level opportunity and role adjustment.
            position_offset = pm.Normal(
                "position_offset",
                mu=0.0,
                sigma=0.25,
                dims=("position", "ability"),
            )

            # Player ability, partially pooled by position.
            ability_log = pm.Normal(
                "player_ability_log",
                mu=population_mu
                + position_offset[position_codes],
                sigma=population_sigma,
                dims=("player", "ability"),
            )

            player_ability = pm.Deterministic(
                "player_ability",
                pm.math.exp(ability_log),
                dims=("player", "ability"),
            )

            for ability in self.abilities:
                spec = ABILITY_REGISTRY[ability]
                ability_code = self.ability_index[ability]

                relevant_rows = [
                    i for i, record in enumerate(records)
                    if record.position in spec["positions"]
                ]

                if not relevant_rows:
                    continue

                rows = np.array(relevant_rows, dtype="int32")
                ability_code = self.ability_index[ability]

                player_for_rows = player_codes[rows]
                ability_for_rows = player_ability[player_for_rows, ability_code]

                outcome = np.array(
                    [record.metrics[spec["outcome"]] for record in records],
                    dtype="float64",
                )[rows]

                if spec["likelihood"] == "poisson_offset":
                    exposure = np.array(
                        [record.metrics[spec["exposure"]] for record in records],
                        dtype="float64",
                    )[rows]

                    pm.Poisson(
                        f"{ability}_obs",
                        mu=ability_for_rows * exposure,
                        observed=outcome,
                    )

                elif spec["likelihood"] == "poisson_per90":
                    per90 = (
                        outcome
                        / minutes[rows]
                        * 90
                    )

                    pm.Poisson(
                        f"{ability}_obs",
                        mu=ability_for_rows * np.maximum(per90, 1e-6),
                        observed=outcome,
                    )

                elif spec["likelihood"] == "binomial":
                    trials = np.array(
                        [record.metrics[spec["trials"]] for record in records],
                        dtype="float64",
                    )[rows]

                    if np.any(trials <= 0):
                        raise ValueError(
                            f"'{ability}' requires positive trial counts."
                        )

                    pm.Binomial(
                        f"{ability}_obs",
                        n=trials,
                        p=pm.math.clip(
                            ability_for_rows / 2.0,
                            1e-6,
                            1 - 1e-6,
                        ),
                        observed=outcome,
                    )

                elif spec["likelihood"] == "normal_per90":
                    per90 = (
                        outcome
                        / minutes[rows]
                        * 90
                    )

                    sigma = pm.HalfNormal(
                        f"{ability}_sigma",
                        sigma=1.0,
                    )

                    pm.Normal(
                        f"{ability}_obs",
                        mu=ability_for_rows,
                        sigma=sigma,
                        observed=per90,
                    )
                    
                elif spec["likelihood"] == "poisson_per90":
                    if spec["outcome"] == "defensive_actions":
                        outcome = defensive_actions[rows]
                    else:
                        outcome = np.array(
                            [
                                record.metrics[spec["outcome"]]
                                for record in records
                            ],
                            dtype="float64",
                        )[rows]

                    per90 = outcome / minutes[rows] * 90

                    pm.Poisson(
                        f"{ability}_obs",
                        mu=ability_for_rows * np.maximum(per90, 1e-6),
                        observed=outcome,
                    )

        return self.model

    def train(self):
        if self.model is None:
            raise ValueError("Model must be built before training.")

        with self.model:
            self.idata = pm.sample(
                draws=self.draws,
                tune=self.tune,
                chains=self.chains,
                target_accept=self.target_accept,
                random_seed=self.random_seed,
                return_inferencedata=True,
            )

        return self.idata

    def diagnostics(
        self,
        rhat_threshold: float = 1.01,
        min_ess: int = 400,
    ):
        if self.idata is None:
            raise ValueError("Model must be trained before diagnostics.")

        summary = az.summary(
            self.idata,
            var_names=["player_ability"],
            kind="diagnostics",
        )

        rhat_max = float(summary["r_hat"].max())
        ess_bulk_min = float(summary["ess_bulk"].min())
        ess_tail_min = float(summary["ess_tail"].min())

        checks = {
            "r_hat_pass": rhat_max < rhat_threshold,
            "ess_bulk_pass": ess_bulk_min >= min_ess,
            "ess_tail_pass": ess_tail_min >= min_ess,
        }

        return {
            "r_hat_max": rhat_max,
            "ess_bulk_min": ess_bulk_min,
            "ess_tail_min": ess_tail_min,
            "thresholds": {
                "r_hat_max": rhat_threshold,
                "min_ess": min_ess,
            },
            "checks": checks,
            "all_checks_passed": all(checks.values()),
            "summary": summary,
        }

    def player_profile(
        self,
        player_name: str,
        hdi_probability: float = 0.94,
    ):
        if self.idata is None:
            raise ValueError("Model must be trained before profiling.")

        if player_name not in self.player_index:
            raise ValueError(f"Unknown player: {player_name}")

        code = self.player_index[player_name]
        samples = self.idata.posterior["player_ability"].isel(player=code)

        profile = {}

        for ability in self.abilities:
            ability_code = self.ability_index[ability]
            values = samples.isel(ability=ability_code).values.flatten()

            hdi = az.hdi(values, hdi_prob=hdi_probability)

            profile[ability] = {
                "posterior_mean": float(values.mean()),
                "hdi_low": float(hdi[0]),
                "hdi_high": float(hdi[1]),
                "probability_above_1": float((values > 1).mean()),
            }

        return {
            "player": player_name,
            "hdi_probability": hdi_probability,
            "abilities": profile,
        }

    def plot_diagnostics(self, output_path="models/role_aware_diagnostics.png"):
        if self.idata is None:
            raise ValueError("Model must be trained before plotting.")

        axes = az.plot_trace(
            self.idata,
            var_names=["player_ability"],
            compact=True,
        )

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        return output_path