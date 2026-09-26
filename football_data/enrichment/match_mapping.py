from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd


TEAM_ALIASES = {
    # England
    "man utd": "manchester united",
    "man united": "manchester united",
    "manchester utd": "manchester united",
    "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur",
    "newcastle": "newcastle united",
    "brighton": "brighton hove albion",
    "brighton and hove albion": "brighton hove albion",
    "brighton & hove albion": "brighton hove albion",
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "west ham": "west ham united",
    "nottingham": "nottingham forest",
    "nottm forest": "nottingham forest",
    "leicester": "leicester city",
    "leeds": "leeds united",

    # Spain
    "atletico": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "athletic bilbao": "athletic club",

    # Germany
    "bayern munich": "bayern munich",
    "fc bayern munchen": "bayern munich",
    "borussia m gladbach": "borussia monchengladbach",
    "borussia m.gladbach": "borussia monchengladbach",
    "gladbach": "borussia monchengladbach",
    "mainz": "mainz 05",
    "fsv mainz 05": "mainz 05",

    # Italy
    "inter": "inter",
    "internazionale": "inter",
    "inter milan": "inter",
    "ac milan": "milan",
    "as roma": "roma",
    "ss lazio": "lazio",

    # France
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "paris saint germain": "paris saint germain",
    "olympique lyon": "lyon",
    "olympique lyonnais": "lyon",
    "olympique marseille": "marseille",
    "as monaco": "monaco",
    "monaco": "monaco",
    "lille osc": "lille",
    "ogc nice": "nice",
    "stade rennais": "rennes",
    "fc nantes": "nantes",
    "rc lens": "lens",
    "montpellier hsc": "montpellier",
    "as saint etienne": "saint etienne",
    "girondins bordeaux": "bordeaux",
}


def normalize_text(
    value: object,
) -> str:

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    text = str(value).strip().lower()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = (
        text.replace("’", "'")
        .replace("&", " and ")
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return TEAM_ALIASES.get(
        text,
        text,
    )


def normalize_player_name(
    value: object,
) -> str:

    return normalize_text(value)


def _score_compatible(
    tm_home_goals: object,
    tm_away_goals: object,
    us_home_goals: object,
    us_away_goals: object,
) -> bool:

    values = [
        tm_home_goals,
        tm_away_goals,
        us_home_goals,
        us_away_goals,
    ]

    if any(
        pd.isna(value)
        for value in values
    ):
        return True

    return (
        int(tm_home_goals)
        == int(us_home_goals)
        and
        int(tm_away_goals)
        == int(us_away_goals)
    )


def build_match_mapping(
    transfermarkt_matches: pd.DataFrame,
    understat_schedule: pd.DataFrame,
) -> pd.DataFrame:
    """
    Mappe les matchs Transfermarkt vers Understat.

    Une correspondance n'est CONFIRMED que si :
        date exacte
        + équipe domicile
        + équipe extérieure
        + score compatible
    """
    MATCH_MAPPING_COLUMNS = [
        "tm_game_id",
        "understat_game_id",
        "tm_match_date",
        "understat_match_date",
        "tm_home_team",
        "tm_away_team",
        "understat_home_team",
        "understat_away_team",
        "candidate_count",
        "candidate_ids",
        "mapping_status",
        "mapping_method",
        "mapping_reason",
    ]
    required_tm = {
        "game_id",
        "match_date",
        "home_team",
        "away_team",
    }

    required_us = {
        "game_id",
        "date",
        "home_team",
        "away_team",
    }

    missing_tm = (
        required_tm
        - set(transfermarkt_matches.columns)
    )

    missing_us = (
        required_us
        - set(understat_schedule.columns)
    )

    if missing_tm:
        raise ValueError(
            "Colonnes Transfermarkt manquantes : "
            + ", ".join(sorted(missing_tm))
        )

    if missing_us:
        raise ValueError(
            "Colonnes Understat manquantes : "
            + ", ".join(sorted(missing_us))
        )

    tm = transfermarkt_matches.copy()
    us = understat_schedule.copy()

    tm["match_date"] = pd.to_datetime(
        tm["match_date"],
        errors="coerce",
    ).dt.date

    us["date"] = pd.to_datetime(
        us["date"],
        errors="coerce",
    ).dt.date

    tm["home_norm"] = tm[
        "home_team"
    ].map(normalize_text)

    tm["away_norm"] = tm[
        "away_team"
    ].map(normalize_text)

    us["home_norm"] = us[
        "home_team"
    ].map(normalize_text)

    us["away_norm"] = us[
        "away_team"
    ].map(normalize_text)

    rows = []

    for _, tm_row in tm.iterrows():

        tm_game_id = tm_row["game_id"]

        exact = us[
            (us["date"] == tm_row["match_date"])
            &
            (us["home_norm"] == tm_row["home_norm"])
            &
            (us["away_norm"] == tm_row["away_norm"])
        ].copy()

        if len(exact) == 1:

            candidate = exact.iloc[0]

            score_ok = _score_compatible(
                tm_row.get("home_goals"),
                tm_row.get("away_goals"),
                candidate.get("home_goals"),
                candidate.get("away_goals"),
            )

            if score_ok:

                status = "MATCH_CONFIRMED"
                reason = "EXACT_DATE_TEAMS_SCORE_COMPATIBLE"

            else:

                status = "MATCH_REVIEW"
                reason = "SCORE_MISMATCH"

            rows.append(
                {
                    "tm_game_id": tm_game_id,
                    "understat_game_id": candidate[
                        "game_id"
                    ],
                    "tm_match_date": tm_row[
                        "match_date"
                    ],
                    "understat_match_date": candidate[
                        "date"
                    ],
                    "tm_home_team": tm_row[
                        "home_team"
                    ],
                    "tm_away_team": tm_row[
                        "away_team"
                    ],
                    "understat_home_team": candidate[
                        "home_team"
                    ],
                    "understat_away_team": candidate[
                        "away_team"
                    ],
                    "candidate_count": 1,
                    "candidate_ids": str(
                        int(candidate["game_id"])
                    ),
                    "mapping_status": status,
                    "mapping_method": (
                        "EXACT_DATE_TEAMS"
                    ),
                    "mapping_reason": reason,
                }
            )

            continue

        if len(exact) > 1:

            rows.append(
                {
                    "tm_game_id": tm_game_id,
                    "understat_game_id": pd.NA,
                    "tm_match_date": tm_row[
                        "match_date"
                    ],
                    "understat_match_date": pd.NaT,
                    "tm_home_team": tm_row[
                        "home_team"
                    ],
                    "tm_away_team": tm_row[
                        "away_team"
                    ],
                    "understat_home_team": pd.NA,
                    "understat_away_team": pd.NA,
                    "candidate_count": len(exact),
                    "candidate_ids": ",".join(
                        exact["game_id"]
                        .astype(int)
                        .astype(str)
                        .tolist()
                    ),
                    "mapping_status": "MATCH_REVIEW",
                    "mapping_method": (
                        "EXACT_DATE_TEAMS_MULTIPLE"
                    ),
                    "mapping_reason": (
                        "MULTIPLE_EXACT_CANDIDATES"
                    ),
                }
            )

            continue

        # --------------------------------------------------------------
        # REVIEW ±1 JOUR
        # --------------------------------------------------------------

        tm_date = pd.Timestamp(
            tm_row["match_date"]
        )

        near = us[
            (
                (
                    us["date"].apply(
                        lambda x: (
                            abs(
                                (
                                    pd.Timestamp(x)
                                    - tm_date
                                ).days
                            )
                            <= 1
                        )
                    )
                )
            )
            &
            (us["home_norm"] == tm_row[
                "home_norm"
            ])
            &
            (us["away_norm"] == tm_row[
                "away_norm"
            ])
        ]

        if len(near) > 0:

            rows.append(
                {
                    "tm_game_id": tm_game_id,
                    "understat_game_id": pd.NA,
                    "tm_match_date": tm_row[
                        "match_date"
                    ],
                    "understat_match_date": (
                        near.iloc[0]["date"]
                    ),
                    "tm_home_team": tm_row[
                        "home_team"
                    ],
                    "tm_away_team": tm_row[
                        "away_team"
                    ],
                    "understat_home_team": (
                        near.iloc[0]["home_team"]
                    ),
                    "understat_away_team": (
                        near.iloc[0]["away_team"]
                    ),
                    "candidate_count": len(near),
                    "candidate_ids": ",".join(
                        near["game_id"]
                        .astype(int)
                        .astype(str)
                        .tolist()
                    ),
                    "mapping_status": "MATCH_REVIEW",
                    "mapping_method": (
                        "TEAM_MATCH_DATE_OFFSET"
                    ),
                    "mapping_reason": (
                        "DATE_OFFSET_LE_1_DAY"
                    ),
                }
            )

            continue

        # --------------------------------------------------------------
        # UNMATCHED
        # --------------------------------------------------------------

        rows.append(
            {
                "tm_game_id": tm_game_id,
                "understat_game_id": pd.NA,
                "tm_match_date": tm_row[
                    "match_date"
                ],
                "understat_match_date": pd.NaT,
                "tm_home_team": tm_row[
                    "home_team"
                ],
                "tm_away_team": tm_row[
                    "away_team"
                ],
                "understat_home_team": pd.NA,
                "understat_away_team": pd.NA,
                "candidate_count": 0,
                "candidate_ids": "",
                "mapping_status": "MATCH_UNMATCHED",
                "mapping_method": "NO_EXACT_CANDIDATE",
                "mapping_reason": (
                    "NO_CONFIRMED_MATCH_CANDIDATE"
                ),
            }
        )

    if not rows:

        return pd.DataFrame(
            columns=MATCH_MAPPING_COLUMNS
        )

    result = pd.DataFrame(rows)

    for column in MATCH_MAPPING_COLUMNS:

        if column not in result.columns:

            result[column] = pd.NA

    return result[
        MATCH_MAPPING_COLUMNS
    ].copy()


def build_player_mapping(
    transfermarkt_player_games: pd.DataFrame,
    understat_player_stats: pd.DataFrame,
    match_mapping: pd.DataFrame,
) -> pd.DataFrame:

    tm = transfermarkt_player_games.copy()

    us = understat_player_stats.copy()

    mm = match_mapping.copy()

    # ------------------------------------------------------------------
    # SCHEMA UNDERSTAT VIDE
    # ------------------------------------------------------------------

    understat_columns = [
        "game_id",
        "team",
        "team_id",
        "player",
        "player_id",
        "xg",
        "xa",
        "source_name",
        "source_library",
        "source_version",
        "source_url",
        "source_retrieved_at",
    ]

    for column in understat_columns:

        if column not in us.columns:

            us[column] = pd.NA

    # ------------------------------------------------------------------
    # SCHEMA MATCH MAPPING
    # ------------------------------------------------------------------

    for column in [
        "tm_game_id",
        "understat_game_id",
        "mapping_method",
    ]:

        if column not in mm.columns:

            mm[column] = pd.NA

    # ------------------------------------------------------------------
    # NORMALISATION
    # ------------------------------------------------------------------

    tm["player_norm"] = (
        tm["player"]
        .map(normalize_player_name)
    )

    tm["team_norm"] = (
        tm["team"]
        .map(normalize_text)
    )

    us["player_norm"] = (
        us["player"]
        .map(normalize_player_name)
    )

    us["team_norm"] = (
        us["team"]
        .map(normalize_text)
    )

    # ------------------------------------------------------------------
    # MATCHES CONFIRMES UNIQUEMENT
    # ------------------------------------------------------------------

    confirmed_matches = mm[
        mm["mapping_status"]
        == "MATCH_CONFIRMED"
    ].copy()

    # --------------------------------------------------------------
    # Aucun match confirmé
    # --------------------------------------------------------------

    if confirmed_matches.empty:

        result = tm.copy()

        result[
            "understat_game_id"
        ] = pd.NA

        result[
            "understat_player_id"
        ] = pd.NA

        result[
            "mapping_status"
        ] = "MATCH_UNMATCHED"

        result[
            "player_mapping_status"
        ] = "PLAYER_UNMATCHED"

        result[
            "player_mapping_method"
        ] = "NO_CONFIRMED_MATCH"

        result["xg"] = np.nan
        result["xa"] = np.nan

        return result

    tm = tm.merge(
        confirmed_matches[
            [
                "tm_game_id",
                "understat_game_id",
                "mapping_method",
            ]
        ].drop_duplicates(
            subset=[
                "tm_game_id"
            ]
        ),
        left_on="game_id",
        right_on="tm_game_id",
        how="left",
    )

    rows = []

    for _, tm_row in tm.iterrows():

        if pd.isna(
            tm_row["understat_game_id"]
        ):

            rows.append(
                {
                    **tm_row.to_dict(),
                    "understat_player_id": pd.NA,
                    "player_mapping_status": (
                        "PLAYER_UNMATCHED"
                    ),
                    "player_mapping_method": (
                        "MATCH_NOT_CONFIRMED"
                    ),
                    "xg": pd.NA,
                    "xa": pd.NA,
                }
            )

            continue

        source_candidates = us[
            (
                us["game_id"]
                == int(
                    tm_row["understat_game_id"]
                )
            )
            &
            (
                us["team_norm"]
                == tm_row["team_norm"]
            )
            &
            (
                us["player_norm"]
                == tm_row["player_norm"]
            )
        ]

        if len(source_candidates) == 1:

            source = (
                source_candidates.iloc[0]
            )

            rows.append(
                {
                    **tm_row.to_dict(),
                    "understat_player_id": (
                        source["player_id"]
                    ),
                    "player_mapping_status": (
                        "PLAYER_CONFIRMED"
                    ),
                    "player_mapping_method": (
                        "EXACT_MATCH_TEAM_PLAYER"
                    ),
                    "xg": source["xg"],
                    "xa": source["xa"],
                    "source_name": (
                        source["source_name"]
                    ),
                    "source_library": (
                        source["source_library"]
                    ),
                    "source_version": (
                        source["source_version"]
                    ),
                    "source_url": (
                        source["source_url"]
                    ),
                    "source_retrieved_at": (
                        source[
                            "source_retrieved_at"
                        ]
                    ),
                }
            )

            continue

        # Nom identique mais équipe différente
        same_name = us[
            (
                us["game_id"]
                == int(
                    tm_row["understat_game_id"]
                )
            )
            &
            (
                us["player_norm"]
                == tm_row["player_norm"]
            )
        ]

        if len(same_name) > 0:

            status = (
                "PLAYER_REVIEW_TEAM_MISMATCH"
            )

        else:

            status = "PLAYER_UNMATCHED"

        rows.append(
            {
                **tm_row.to_dict(),
                "understat_player_id": pd.NA,
                "player_mapping_status": status,
                "player_mapping_method": (
                    "NO_CONFIRMED_PLAYER_MATCH"
                ),
                "xg": pd.NA,
                "xa": pd.NA,
            }
        )

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    if "xg" not in result.columns:
        result["xg"] = pd.NA

    if "xa" not in result.columns:
        result["xa"] = pd.NA

    result["xg"] = pd.to_numeric(
        result["xg"],
        errors="coerce",
    )

    result["xa"] = pd.to_numeric(
        result["xa"],
        errors="coerce",
    )

    return result