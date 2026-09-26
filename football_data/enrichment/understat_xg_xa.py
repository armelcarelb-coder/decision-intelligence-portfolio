from __future__ import annotations

import importlib.metadata
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import soccerdata as sd

from .xg_xa_source import XgXaSource


class UnderstatXgXaSource(XgXaSource):
    """
    Source xG/xA V1 : Understat via soccerdata.

    Les données sont conservées au niveau :

        Understat game_id × Understat player_id

    Un cache local est utilisé afin d'éviter de télécharger
    plusieurs fois les mêmes matchs.
    """

    source_name = "Understat"
    source_library = "soccerdata"

    COUNTRY_TO_LEAGUE = {
        "england": "ENG-Premier League",
        "spain": "ESP-La Liga",
        "italy": "ITA-Serie A",
        "germany": "GER-Bundesliga",
        "france": "FRA-Ligue 1",
    }

    def __init__(
        self,
        cache_dir: str = "data/enrichment/understat_cache",
        no_cache: bool = False,
        request_pause_seconds: float = 0.25,
        batch_size: int = 50,
    ) -> None:

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.soccerdata_cache_dir = (
            self.cache_dir / "soccerdata"
        )

        self.soccerdata_cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.no_cache = no_cache
        self.request_pause_seconds = max(
            float(request_pause_seconds),
            0.0,
        )

        self.batch_size = max(
            int(batch_size),
            1,
        )

        try:
            self.source_version = (
                importlib.metadata.version(
                    "soccerdata"
                )
            )
        except importlib.metadata.PackageNotFoundError:
            self.source_version = "UNKNOWN"

    # ======================================================================
    # PUBLIC
    # ======================================================================

    @classmethod
    def league_for_country(
        cls,
        country_name: str,
    ) -> str | None:

        if country_name is None:
            return None

        normalized = (
            str(country_name)
            .strip()
            .lower()
        )

        return cls.COUNTRY_TO_LEAGUE.get(
            normalized
        )

    # ======================================================================
    # READER
    # ======================================================================

    def _build_reader(
        self,
        league: str,
        season: int,
    ) -> sd.Understat:
        """
        Construit le lecteur Understat avec un code de saison
        explicite.

        Exemple :
            2024 -> "2425"
            2025 -> "2526"

        Cela évite l'ambiguïté de certains codes comme "2021".
        """

        season_start = int(season)

        season_code = (
            f"{season_start % 100:02d}"
            f"{(season_start + 1) % 100:02d}"
        )

        return sd.Understat(
            leagues=[league],
            seasons=[season_code],
            no_cache=self.no_cache,
            data_dir=self.soccerdata_cache_dir,
        )
    # ======================================================================
    # CACHE PATH
    # ======================================================================

    @staticmethod
    def _safe_name(value: str) -> str:

        return (
            str(value)
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

    def _schedule_cache_path(
        self,
        league: str,
        season: int,
    ) -> Path:

        return (
            self.cache_dir
            / (
                f"schedule_"
                f"{self._safe_name(league)}_"
                f"{season}.parquet"
            )
        )

    def _player_match_cache_path(
        self,
        league: str,
        season: int,
    ) -> Path:

        return (
            self.cache_dir
            / (
                f"player_match_"
                f"{self._safe_name(league)}_"
                f"{season}.parquet"
            )
        )

    # ======================================================================
    # SCHEDULE
    # ======================================================================

    def load_schedule(
        self,
        league: str,
        season: int,
    ) -> pd.DataFrame:

        cache_path = self._schedule_cache_path(
            league,
            season,
        )

        if (
            cache_path.exists()
            and not self.no_cache
        ):

            df = pd.read_parquet(
                cache_path
            )

            return self._normalize_schedule(
                df
            )

        print(
            "[Understat] "
            f"Chargement calendrier : "
            f"{league} / {season}"
        )

        reader = self._build_reader(
            league,
            season,
        )

        try:

            df = reader.read_schedule(
                include_matches_without_data=True
            )

        except Exception as exc:

            print(
                "[Understat] "
                f"Échec calendrier {league}/{season}: "
                f"{type(exc).__name__}: {exc}"
            )

            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df = (
            df.reset_index(
                drop=False
            )
            .copy()
        )

        df = self._normalize_schedule(
            df
        )

        if not df.empty:
            df.to_parquet(
                cache_path,
                index=False,
            )

        return df

    # ======================================================================
    # PLAYER MATCH
    # ======================================================================

    def load_player_match_stats(
        self,
        league: str,
        season: int,
        match_ids: Iterable[int],
    ) -> pd.DataFrame:

        requested_ids = sorted(
            {
                int(match_id)
                for match_id in match_ids
                if pd.notna(match_id)
            }
        )

        if not requested_ids:
            return pd.DataFrame()

        cache_path = (
            self._player_match_cache_path(
                league,
                season,
            )
        )

        if (
            cache_path.exists()
            and not self.no_cache
        ):

            cached = pd.read_parquet(
                cache_path
            )

            cached = (
                self._normalize_player_match(
                    cached
                )
            )

        else:

            cached = pd.DataFrame()

        cached_ids = set()

        if (
            not cached.empty
            and "game_id" in cached.columns
        ):

            cached_ids = set(
                cached["game_id"]
                .dropna()
                .astype(int)
                .unique()
            )

        missing_ids = [
            match_id
            for match_id in requested_ids
            if match_id not in cached_ids
        ]

        newly_loaded = []

        if missing_ids:

            reader = self._build_reader(
                league,
                season,
            )

            for start in range(
                0,
                len(missing_ids),
                self.batch_size,
            ):

                batch = missing_ids[
                    start:
                    start + self.batch_size
                ]

                print(
                    "[Understat] "
                    f"Joueurs/match : "
                    f"{league} / {season} "
                    f"({len(batch)} matchs)"
                )

                try:

                    df = (
                        reader.read_player_match_stats(
                            match_id=batch
                        )
                    )

                    if (
                        df is not None
                        and not df.empty
                    ):

                        df = (
                            df.reset_index(
                                drop=False
                            )
                        )

                        df = (
                            self._normalize_player_match(
                                df
                            )
                        )

                        newly_loaded.append(
                            df
                        )

                except Exception as exc:

                    print(
                        "[Understat] "
                        f"Batch en échec "
                        f"{league}/{season} "
                        f"{batch[:3]}... : "
                        f"{type(exc).__name__}: {exc}"
                    )

                    # Fallback match par match.
                    for match_id in batch:

                        try:

                            df_single = (
                                reader.read_player_match_stats(
                                    match_id=int(
                                        match_id
                                    )
                                )
                            )

                            if (
                                df_single is not None
                                and not df_single.empty
                            ):

                                df_single = (
                                    df_single.reset_index(
                                        drop=False
                                    )
                                )

                                df_single = (
                                    self._normalize_player_match(
                                        df_single
                                    )
                                )

                                newly_loaded.append(
                                    df_single
                                )

                        except Exception as single_exc:

                            print(
                                "[Understat] "
                                f"Match {match_id} "
                                f"non récupéré : "
                                f"{type(single_exc).__name__}: "
                                f"{single_exc}"
                            )

                        if (
                            self.request_pause_seconds
                            > 0
                        ):

                            time.sleep(
                                self.request_pause_seconds
                            )

                if (
                    self.request_pause_seconds
                    > 0
                ):

                    time.sleep(
                        self.request_pause_seconds
                    )

        frames = []

        if not cached.empty:
            frames.append(cached)

        frames.extend(
            newly_loaded
        )

        if not frames:
            return pd.DataFrame()

        result = pd.concat(
            frames,
            ignore_index=True,
        )

        result = (
            self._normalize_player_match(
                result
            )
        )

        result = (
            result
            .drop_duplicates(
                subset=[
                    "game_id",
                    "player_id",
                ],
                keep="last",
            )
        )

        result.to_parquet(
            cache_path,
            index=False,
        )

        return result[
            result["game_id"]
            .isin(requested_ids)
        ].copy()

    # ======================================================================
    # NORMALIZATION
    # ======================================================================

    def _normalize_schedule(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df is None or df.empty:
            return pd.DataFrame(
                columns=[
                    "league",
                    "season",
                    "game_id",
                    "date",
                    "home_team",
                    "away_team",
                    "home_goals",
                    "away_goals",
                    "home_xg",
                    "away_xg",
                    "has_data",
                    "source_name",
                    "source_library",
                    "source_version",
                ]
            )

        df = df.copy()

        rename_map = {
            "game": "game",
            "game_id": "game_id",
            "date": "date",
            "home_team": "home_team",
            "away_team": "away_team",
            "home_goals": "home_goals",
            "away_goals": "away_goals",
            "home_xg": "home_xg",
            "away_xg": "away_xg",
            "has_data": "has_data",
        }

        df = df.rename(
            columns=rename_map
        )

        required_defaults = {
            "league": pd.NA,
            "season": pd.NA,
            "game_id": pd.NA,
            "date": pd.NaT,
            "home_team": pd.NA,
            "away_team": pd.NA,
            "home_goals": pd.NA,
            "away_goals": pd.NA,
            "home_xg": pd.NA,
            "away_xg": pd.NA,
            "has_data": pd.NA,
        }

        for column, default in required_defaults.items():

            if column not in df.columns:
                df[column] = default

        df["game_id"] = pd.to_numeric(
            df["game_id"],
            errors="coerce",
        )

        df["season"] = pd.to_numeric(
            df["season"],
            errors="coerce",
        )

        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce",
        )

        for column in [
            "home_goals",
            "away_goals",
            "home_xg",
            "away_xg",
        ]:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df["has_data"] = (
            df["has_data"]
            .fillna(False)
            .astype(bool)
        )

        df["source_name"] = self.source_name
        df["source_library"] = self.source_library
        df["source_version"] = self.source_version
        df["source_url"] = (
            "https://understat.com/match/"
            + df["game_id"]
            .astype("Int64")
            .astype("string")
        )

        return df[
            [
                "league",
                "season",
                "game_id",
                "date",
                "home_team",
                "away_team",
                "home_goals",
                "away_goals",
                "home_xg",
                "away_xg",
                "has_data",
                "source_name",
                "source_library",
                "source_version",
                "source_url",
            ]
        ].copy()

    def _normalize_player_match(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        required_columns = [
            "league",
            "season",
            "game_id",
            "team",
            "team_id",
            "player",
            "player_id",
            "minutes",
            "goals",
            "assists",
            "xg",
            "xa",
            "source_name",
            "source_library",
            "source_version",
            "source_url",
            "source_retrieved_at",
        ]

        # ------------------------------------------------------------------
        # DATAFRAME ABSENT OU VIDE
        # ------------------------------------------------------------------

        if df is None or df.empty:

            return pd.DataFrame(
                columns=required_columns
            )

        df = df.copy()

        # ------------------------------------------------------------------
        # COLONNES OBLIGATOIRES
        # ------------------------------------------------------------------

        required_defaults = {
            "league": pd.NA,
            "season": pd.NA,
            "game_id": pd.NA,
            "team": pd.NA,
            "team_id": pd.NA,
            "player": pd.NA,
            "player_id": pd.NA,
            "minutes": pd.NA,
            "goals": pd.NA,
            "assists": pd.NA,
            "xg": pd.NA,
            "xa": pd.NA,
        }

        for column, default in required_defaults.items():

            if column not in df.columns:
                df[column] = default

        # ------------------------------------------------------------------
        # TYPES
        # ------------------------------------------------------------------

        for column in [
            "season",
            "game_id",
            "team_id",
            "player_id",
            "minutes",
            "goals",
            "assists",
        ]:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        for column in [
            "xg",
            "xa",
        ]:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        # ------------------------------------------------------------------
        # METADATA SOURCE
        # ------------------------------------------------------------------

        df["source_name"] = self.source_name
        df["source_library"] = self.source_library
        df["source_version"] = self.source_version

        df["source_url"] = (
            "https://understat.com/match/"
            + df["game_id"]
            .astype("Int64")
            .astype("string")
        )

        df["source_retrieved_at"] = (
            pd.Timestamp.now(
                tz="UTC"
            )
        )

        # ------------------------------------------------------------------
        # OUTPUT
        # ------------------------------------------------------------------

        return df[
            required_columns
        ].copy()