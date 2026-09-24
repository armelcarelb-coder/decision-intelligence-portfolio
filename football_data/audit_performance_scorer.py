from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import duckdb


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path(
    "data/performances/player_competition_season_performance.csv"
)

DUCKDB_FILE = Path(
    "data/historical/transfermarkt-datasets.duckdb"
)

AUDIT_DIR = Path("data/audits")

EXPECTED_ROWS = 191_355
EXPECTED_PLAYERS = 29_330
EXPECTED_SEASONS = 14
EXPECTED_COMPETITIONS = 46

MIN_MINUTES = 900

METRICS = [
    "goals_per90",
    "assists_per90",
    "xg_per90",
    "xa_per90",
]

REQUIRED_COLUMNS = [
    "player_id",
    "player",
    "position",
    "sub_position",
    "season",
    "competition_id",
    "competition_name",
    "competition_level",
    "minutes",
    "goals",
    "assists",
    "goals_per90",
    "assists_per90",
    "xg",
    "xa",
    "xg_per90",
    "xa_per90",
]

PLAYER_REFERENCE_COLUMNS = [
    "player_id",
    "player",
    "position",
    "sub_position",
    "season",
    "competition_id",
    "competition_name",
    "competition_level",
    "minutes",
]


# ============================================================
# UTILITAIRES
# ============================================================

def pct(value: int | float, total: int | float) -> float:
    if total == 0:
        return 0.0

    return round(
        100.0 * value / total,
        2,
    )


def save_csv(
    df: pd.DataFrame,
    filename: str,
) -> Path:
    path = AUDIT_DIR / filename

    df.to_csv(
        path,
        index=False,
    )

    return path


def require_columns(
    df: pd.DataFrame,
) -> None:
    missing = sorted(
        set(REQUIRED_COLUMNS)
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Colonnes obligatoires manquantes : "
            + ", ".join(missing)
        )


# ============================================================
# AUDIT DATASET
# ============================================================

def audit_dataset_structure(
    df: pd.DataFrame,
) -> list[dict]:
    rows = []

    actual_rows = len(df)

    actual_players = (
        df["player_id"]
        .nunique(dropna=True)
    )

    actual_seasons = (
        df["season"]
        .nunique(dropna=True)
    )

    actual_competitions = (
        df["competition_id"]
        .nunique(dropna=True)
    )

    checks = [
        (
            "ROWS",
            actual_rows,
            EXPECTED_ROWS,
        ),
        (
            "PLAYERS",
            actual_players,
            EXPECTED_PLAYERS,
        ),
        (
            "SEASONS",
            actual_seasons,
            EXPECTED_SEASONS,
        ),
        (
            "COMPETITIONS",
            actual_competitions,
            EXPECTED_COMPETITIONS,
        ),
    ]

    for check, actual, expected in checks:
        passed = actual == expected

        rows.append(
            {
                "audit": "DATASET_STRUCTURE",
                "metric": check,
                "actual": actual,
                "expected": expected,
                "status": (
                    "PASS"
                    if passed
                    else "STRUCTURAL_REVIEW"
                ),
            }
        )

    return rows


# ============================================================
# AUDIT METRICS
# ============================================================

def audit_metric_coverage(
    df: pd.DataFrame,
) -> list[dict]:
    rows = []

    total = len(df)

    for metric in METRICS:
        non_null = int(
            df[metric]
            .notna()
            .sum()
        )

        null = int(
            df[metric]
            .isna()
            .sum()
        )

        rows.append(
            {
                "audit": "METRIC_COVERAGE",
                "metric": metric,
                "total_rows": total,
                "non_null": non_null,
                "null": null,
                "coverage_pct": pct(
                    non_null,
                    total,
                ),
                "status": (
                    "PASS"
                    if null == 0
                    else "INFO"
                ),
            }
        )

    all_four = (
        df[METRICS]
        .notna()
        .all(axis=1)
    )

    four_available = int(
        all_four.sum()
    )

    four_missing = int(
        (~all_four).sum()
    )

    rows.append(
        {
            "audit": "METRIC_COVERAGE",
            "metric": "ALL_FOUR_METRICS",
            "total_rows": total,
            "non_null": four_available,
            "null": four_missing,
            "coverage_pct": pct(
                four_available,
                total,
            ),
            "status": (
                "PASS"
                if four_available == total
                else "INFO"
            ),
        }
    )

    return rows


# ============================================================
# AUDIT MINUTES
# ============================================================

def audit_minutes(
    df: pd.DataFrame,
) -> list[dict]:
    rows = []

    minutes = pd.to_numeric(
        df["minutes"],
        errors="coerce",
    )

    null_minutes = int(
        minutes.isna().sum()
    )

    negative_minutes = int(
        (minutes < 0).sum()
    )

    zero_minutes = int(
        (minutes == 0).sum()
    )

    below_900 = int(
        (minutes < MIN_MINUTES).sum()
    )

    at_least_900 = int(
        (minutes >= MIN_MINUTES).sum()
    )

    rows.extend(
        [
            {
                "audit": "MINUTES",
                "metric": "NULL_MINUTES",
                "value": null_minutes,
                "status": (
                    "PASS"
                    if null_minutes == 0
                    else "STRUCTURAL_REVIEW"
                ),
            },
            {
                "audit": "MINUTES",
                "metric": "NEGATIVE_MINUTES",
                "value": negative_minutes,
                "status": (
                    "PASS"
                    if negative_minutes == 0
                    else "STRUCTURAL_REVIEW"
                ),
            },
            {
                "audit": "MINUTES",
                "metric": "ZERO_MINUTES",
                "value": zero_minutes,
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MINUTES_LT_900",
                "value": below_900,
                "pct_rows": pct(
                    below_900,
                    len(df),
                ),
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MINUTES_GE_900",
                "value": at_least_900,
                "pct_rows": pct(
                    at_least_900,
                    len(df),
                ),
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MIN_MINUTES",
                "value": minutes.min(),
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MAX_MINUTES",
                "value": minutes.max(),
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MEAN_MINUTES",
                "value": round(
                    minutes.mean(),
                    2,
                ),
                "status": "INFO",
            },
            {
                "audit": "MINUTES",
                "metric": "MEDIAN_MINUTES",
                "value": round(
                    minutes.median(),
                    2,
                ),
                "status": "INFO",
            },
        ]
    )

    return rows


# ============================================================
# STATUT THÉORIQUE DU SCORER
# ============================================================

def build_theoretical_status(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    minutes = pd.to_numeric(
        df["minutes"],
        errors="coerce",
    )

    all_four = (
        df[METRICS]
        .notna()
        .all(axis=1)
    )

    status = np.select(
        [
            minutes < MIN_MINUTES,
            (
                (minutes >= MIN_MINUTES)
                & (~all_four)
            ),
            (
                (minutes >= MIN_MINUTES)
                & all_four
            ),
        ],
        [
            "INSUFFICIENT_MINUTES",
            "INSUFFICIENT_METRICS",
            "ELIGIBLE",
        ],
        default="INVALID",
    )

    result = df[
        [
            "player_id",
            "player",
            "position",
            "sub_position",
            "season",
            "competition_id",
            "competition_name",
            "competition_level",
            "minutes",
        ]
    ].copy()

    result["all_four_metrics_available"] = (
        all_four
    )

    result["theoretical_scorer_status"] = (
        status
    )

    counts = (
        result[
            "theoretical_scorer_status"
        ]
        .value_counts()
        .rename_axis("status")
        .reset_index(
            name="rows"
        )
    )

    counts["pct_rows"] = (
        counts["rows"]
        .div(len(result))
        .mul(100)
        .round(2)
    )

    counts.insert(
        0,
        "audit",
        "THEORETICAL_SCORER_STATUS",
    )

    return (
        result,
        counts.to_dict("records"),
    )


# ============================================================
# AUDIT GROUPES PERCENTILE
# ============================================================

def audit_percentile_groups(
    df: pd.DataFrame,
    theoretical_status: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    group_columns = [
        "position",
        "competition_level",
        "season",
    ]

    base = df[
        group_columns
    ].copy()

    base["minutes"] = pd.to_numeric(
        df["minutes"],
        errors="coerce",
    )

    base["candidate_900"] = (
        base["minutes"] >= MIN_MINUTES
    )

    base["theoretical_status"] = (
        theoretical_status[
            "theoretical_scorer_status"
        ]
        .values
    )

    group_audit = (
        base.groupby(
            group_columns,
            dropna=False,
        )
        .agg(
            rows=(
                "candidate_900",
                "size",
            ),
            candidate_900=(
                "candidate_900",
                "sum",
            ),
            eligible=(
                "theoretical_status",
                lambda x: (
                    x == "ELIGIBLE"
                ).sum(),
            ),
        )
        .reset_index()
    )

    group_audit[
        "has_candidate_900"
    ] = (
        group_audit["candidate_900"]
        > 0
    )

    group_audit[
        "has_eligible"
    ] = (
        group_audit["eligible"]
        > 0
    )

    total_groups = len(
        group_audit
    )

    candidate_groups = int(
        (
            group_audit[
                "candidate_900"
            ]
            > 0
        ).sum()
    )

    groups_zero_eligible = int(
        (
            group_audit[
                "eligible"
            ]
            == 0
        ).sum()
    )

    groups_one_eligible = int(
        (
            group_audit[
                "eligible"
            ]
            == 1
        ).sum()
    )

    groups_two_plus_eligible = int(
        (
            group_audit[
                "eligible"
            ]
            >= 2
        ).sum()
    )

    eligible_groups = int(
        (
            group_audit[
                "eligible"
            ]
            > 0
        ).sum()
    )

    summary = [
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": "TOTAL_GROUPS",
            "value": total_groups,
            "status": "INFO",
        },
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": (
                "GROUPS_WITH_CANDIDATE_900"
            ),
            "value": candidate_groups,
            "status": "INFO",
        },
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": (
                "GROUPS_WITH_ZERO_ELIGIBLE"
            ),
            "value": groups_zero_eligible,
            "status": "INFO",
        },
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": (
                "GROUPS_WITH_ONE_ELIGIBLE"
            ),
            "value": groups_one_eligible,
            "status": "INFO",
        },
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": (
                "GROUPS_WITH_GE_2_ELIGIBLE"
            ),
            "value": groups_two_plus_eligible,
            "status": "INFO",
        },
        {
            "audit": "PERCENTILE_GROUPS",
            "metric": (
                "GROUPS_WITH_ELIGIBLE"
            ),
            "value": eligible_groups,
            "status": "INFO",
        },
    ]

    return (
        group_audit,
        summary,
    )


# ============================================================
# AUDIT POSITION
# ============================================================

def audit_position(
    df: pd.DataFrame,
) -> list[dict]:
    position = df["position"]

    null_count = int(
        position.isna().sum()
    )

    unknown_count = int(
        position.astype("string")
        .str.upper()
        .eq("UNKNOWN")
        .sum()
    )

    distinct = int(
        position.nunique(
            dropna=True
        )
    )

    return [
        {
            "audit": "POSITION",
            "metric": "DISTINCT_POSITIONS",
            "value": distinct,
            "status": "INFO",
        },
        {
            "audit": "POSITION",
            "metric": "NULL_POSITION",
            "value": null_count,
            "pct_rows": pct(
                null_count,
                len(df),
            ),
            "status": (
                "INFO"
                if null_count == 0
                else "DATA_QUALITY_REVIEW"
            ),
        },
        {
            "audit": "POSITION",
            "metric": "UNKNOWN_POSITION",
            "value": unknown_count,
            "pct_rows": pct(
                unknown_count,
                len(df),
            ),
            "status": "INFO",
        },
    ]


# ============================================================
# AUDIT COMPETITION LEVEL
# ============================================================

def audit_competition_level(
    df: pd.DataFrame,
) -> list[dict]:
    level = df[
        "competition_level"
    ]

    null_count = int(
        level.isna().sum()
    )

    unknown_count = int(
        level.astype("string")
        .str.upper()
        .eq("UNKNOWN")
        .sum()
    )

    distinct = int(
        level.nunique(
            dropna=True
        )
    )

    return [
        {
            "audit": "COMPETITION_LEVEL",
            "metric": "DISTINCT_LEVELS",
            "value": distinct,
            "status": "INFO",
        },
        {
            "audit": "COMPETITION_LEVEL",
            "metric": "NULL_LEVEL",
            "value": null_count,
            "pct_rows": pct(
                null_count,
                len(df),
            ),
            "status": (
                "PASS"
                if null_count == 0
                else "STRUCTURAL_REVIEW"
            ),
        },
        {
            "audit": "COMPETITION_LEVEL",
            "metric": "UNKNOWN_LEVEL",
            "value": unknown_count,
            "pct_rows": pct(
                unknown_count,
                len(df),
            ),
            "status": "INFO",
        },
    ]


# ============================================================
# AUDIT DOUBLONS
# ============================================================

def audit_duplicates(
    df: pd.DataFrame,
) -> list[dict]:
    grain = [
        "player_id",
        "season",
        "competition_id",
    ]

    duplicate_mask = df.duplicated(
        subset=grain,
        keep=False,
    )

    duplicate_rows = int(
        duplicate_mask.sum()
    )

    duplicate_groups = int(
        df.loc[
            duplicate_mask,
            grain,
        ]
        .drop_duplicates()
        .shape[0]
    )

    return [
        {
            "audit": "DUPLICATES",
            "metric": "DUPLICATE_ROWS",
            "value": duplicate_rows,
            "status": (
                "PASS"
                if duplicate_rows == 0
                else "STRUCTURAL_REVIEW"
            ),
        },
        {
            "audit": "DUPLICATES",
            "metric": "DUPLICATE_GROUPS",
            "value": duplicate_groups,
            "status": (
                "PASS"
                if duplicate_groups == 0
                else "STRUCTURAL_REVIEW"
            ),
        },
    ]


# ============================================================
# AUDIT XG / XA BASELINE
# ============================================================

def audit_xg_xa_raw(
    df: pd.DataFrame,
) -> list[dict]:
    rows = []

    for column in [
        "xg",
        "xa",
        "xg_per90",
        "xa_per90",
    ]:
        null_count = int(
            df[column]
            .isna()
            .sum()
        )

        non_null = int(
            df[column]
            .notna()
            .sum()
        )

        rows.append(
            {
                "audit": "XG_XA_BASELINE",
                "metric": column,
                "null": null_count,
                "non_null": non_null,
                "coverage_pct": pct(
                    non_null,
                    len(df),
                ),
                "status": "INFO",
            }
        )

    return rows


# ============================================================
# RÉFÉRENTIEL JOUEURS DU DATASET
# ============================================================

def audit_player_ids_in_dataset(
    df: pd.DataFrame,
) -> list[dict]:
    null_player_ids = int(
        df["player_id"]
        .isna()
        .sum()
    )

    return [
        {
            "audit": "PLAYER_REFERENCE",
            "metric": "NULL_PLAYER_ID",
            "value": null_player_ids,
            "pct_rows": pct(
                null_player_ids,
                len(df),
            ),
            "status": (
                "PASS"
                if null_player_ids == 0
                else "STRUCTURAL_REVIEW"
            ),
        }
    ]


# ============================================================
# VÉRIFICATION PLAYERS DUCKDB
# ============================================================

def audit_player_reference_duckdb(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Vérifie que les player_id présents dans le dataset
    existent dans la table players du DuckDB source.

    Cette vérification ne modifie aucune donnée.
    """

    if not DUCKDB_FILE.exists():
        print(
            f"[AUDIT] DuckDB introuvable : {DUCKDB_FILE}"
        )

        return pd.DataFrame(
            columns=(
                PLAYER_REFERENCE_COLUMNS
                + [
                    "reason",
                    "impact_on_scoring",
                    "decision",
                ]
            )
        )

    player_ids = (
        pd.to_numeric(
            df["player_id"],
            errors="coerce",
        )
        .dropna()
        .astype("int64")
        .drop_duplicates()
    )

    if player_ids.empty:
        return pd.DataFrame()

    con = duckdb.connect(
        str(DUCKDB_FILE),
        read_only=True,
    )

    try:
        source_players = con.execute(
            """
            SELECT
                player_id
            FROM players
            """
        ).fetchdf()

    finally:
        con.close()

    source_players["player_id"] = (
        pd.to_numeric(
            source_players["player_id"],
            errors="coerce",
        )
    )

    source_player_ids = set(
        source_players[
            "player_id"
        ]
        .dropna()
        .astype("int64")
        .tolist()
    )

    missing_player_ids = set(
        player_ids.tolist()
    ) - source_player_ids

    if not missing_player_ids:
        return pd.DataFrame(
            columns=(
                PLAYER_REFERENCE_COLUMNS
                + [
                    "reason",
                    "impact_on_scoring",
                    "decision",
                ]
            )
        )

    review = df[
        df["player_id"].isin(
            missing_player_ids
        )
    ][
        PLAYER_REFERENCE_COLUMNS
    ].copy()

    review["reason"] = (
        "MISSING_PLAYER_REFERENCE_IN_SOURCE"
    )

    review["impact_on_scoring"] = (
        np.where(
            pd.to_numeric(
                review["minutes"],
                errors="coerce",
            )
            >= MIN_MINUTES,
            "POTENTIAL_IMPACT",
            "NONE",
        )
    )

    review["decision"] = (
        np.where(
            review["impact_on_scoring"]
            == "NONE",
            "KEEP_RAW_EXCLUDE_FROM_SCORING",
            "REVIEW_BEFORE_PRODUCTION_SCORING",
        )
    )

    return review


# ============================================================
# AUDIT IMPACT RÉFÉRENTIEL
# ============================================================

def build_player_reference_summary(
    review: pd.DataFrame,
    df: pd.DataFrame,
) -> list[dict]:
    if review.empty:
        return [
            {
                "audit": "PLAYER_REFERENCE",
                "metric": (
                    "PLAYER_IDS_MISSING_FROM_PLAYERS"
                ),
                "value": 0,
                "status": "PASS",
            },
            {
                "audit": "PLAYER_REFERENCE",
                "metric": (
                    "ROWS_WITH_MISSING_PLAYER_REFERENCE"
                ),
                "value": 0,
                "status": "PASS",
            },
        ]

    missing_ids = int(
        review["player_id"]
        .nunique()
    )

    missing_rows = len(
        review
    )

    potential_impact = int(
        (
            review[
                "impact_on_scoring"
            ]
            == "POTENTIAL_IMPACT"
        ).sum()
    )

    return [
        {
            "audit": "PLAYER_REFERENCE",
            "metric": (
                "PLAYER_IDS_MISSING_FROM_PLAYERS"
            ),
            "value": missing_ids,
            "status": (
                "DATA_QUALITY_REVIEW"
            ),
        },
        {
            "audit": "PLAYER_REFERENCE",
            "metric": (
                "ROWS_WITH_MISSING_PLAYER_REFERENCE"
            ),
            "value": missing_rows,
            "status": (
                "DATA_QUALITY_REVIEW"
            ),
        },
        {
            "audit": "PLAYER_REFERENCE",
            "metric": (
                "ROWS_WITH_POTENTIAL_SCORING_IMPACT"
            ),
            "value": potential_impact,
            "status": (
                "DATA_QUALITY_REVIEW"
                if potential_impact > 0
                else "INFO"
            ),
        },
    ]


# ============================================================
# RAPPORT TEXTUEL
# ============================================================

def build_text_report(
    df: pd.DataFrame,
    theoretical_status: pd.DataFrame,
    percentile_groups: pd.DataFrame,
    player_reference_review: pd.DataFrame,
) -> str:
    lines = []

    lines.append("=" * 80)
    lines.append(
        "PERFORMANCE SCORER — REAL DATA AUDIT"
    )
    lines.append("=" * 80)

    lines.append("")
    lines.append("DATASET")
    lines.append("-" * 80)

    lines.append(
        f"Rows              : {len(df):,}"
    )

    lines.append(
        f"Players           : "
        f"{df['player_id'].nunique():,}"
    )

    lines.append(
        f"Seasons           : "
        f"{df['season'].nunique():,}"
    )

    lines.append(
        f"Competitions      : "
        f"{df['competition_id'].nunique():,}"
    )

    lines.append("")
    lines.append("METRICS COVERAGE")
    lines.append("-" * 80)

    for metric in METRICS:
        non_null = int(
            df[metric]
            .notna()
            .sum()
        )

        null = int(
            df[metric]
            .isna()
            .sum()
        )

        lines.append(
            f"{metric:<20} "
            f"non-null={non_null:,} "
            f"null={null:,} "
            f"coverage="
            f"{pct(non_null, len(df)):.2f}%"
        )

    all_four = (
        df[METRICS]
        .notna()
        .all(axis=1)
    )

    lines.append(
        f"{'ALL FOUR AVAILABLE':<20} "
        f"{int(all_four.sum()):,} / "
        f"{len(df):,} "
        f"({pct(all_four.sum(), len(df)):.2f}%)"
    )

    lines.append("")
    lines.append("MINUTES")
    lines.append("-" * 80)

    minutes = pd.to_numeric(
        df["minutes"],
        errors="coerce",
    )

    lines.append(
        f"< 900 minutes       : "
        f"{int((minutes < MIN_MINUTES).sum()):,}"
    )

    lines.append(
        f">= 900 minutes      : "
        f"{int((minutes >= MIN_MINUTES).sum()):,}"
    )

    lines.append(
        f"Min minutes         : "
        f"{minutes.min()}"
    )

    lines.append(
        f"Max minutes         : "
        f"{minutes.max()}"
    )

    lines.append(
        f"Mean minutes        : "
        f"{minutes.mean():.2f}"
    )

    lines.append(
        f"Median minutes      : "
        f"{minutes.median():.2f}"
    )

    lines.append("")
    lines.append(
        "THEORETICAL SCORER STATUS"
    )
    lines.append("-" * 80)

    counts = (
        theoretical_status[
            "theoretical_scorer_status"
        ]
        .value_counts()
    )

    for status in [
        "INSUFFICIENT_MINUTES",
        "INSUFFICIENT_METRICS",
        "ELIGIBLE",
        "INVALID",
    ]:
        count = int(
            counts.get(
                status,
                0,
            )
        )

        lines.append(
            f"{status:<25} "
            f"{count:,} "
            f"({pct(count, len(df)):.2f}%)"
        )

    lines.append("")
    lines.append(
        "PERCENTILE GROUPS"
    )
    lines.append("-" * 80)

    lines.append(
        f"Total groups                   : "
        f"{len(percentile_groups):,}"
    )

    lines.append(
        f"Groups with candidate >=900    : "
        f"{int(percentile_groups['candidate_900'].gt(0).sum()):,}"
    )

    lines.append(
        f"Groups with zero eligible      : "
        f"{int(percentile_groups['eligible'].eq(0).sum()):,}"
    )

    lines.append(
        f"Groups with one eligible       : "
        f"{int(percentile_groups['eligible'].eq(1).sum()):,}"
    )

    lines.append(
        f"Groups with >=2 eligible       : "
        f"{int(percentile_groups['eligible'].ge(2).sum()):,}"
    )

    lines.append("")
    lines.append(
        "PLAYER REFERENCE"
    )
    lines.append("-" * 80)

    if player_reference_review.empty:
        lines.append(
            "Missing player references    : 0"
        )
        lines.append(
            "Reference status             : PASS"
        )
    else:
        missing_ids = (
            player_reference_review[
                "player_id"
            ]
            .nunique()
        )

        missing_rows = len(
            player_reference_review
        )

        potential_impact = int(
            (
                player_reference_review[
                    "impact_on_scoring"
                ]
                == "POTENTIAL_IMPACT"
            ).sum()
        )

        lines.append(
            f"Missing player IDs           : "
            f"{missing_ids}"
        )

        lines.append(
            f"Rows affected               : "
            f"{missing_rows}"
        )

        lines.append(
            f"Potential scoring impact    : "
            f"{potential_impact}"
        )

        lines.append(
            "Status                      : "
            "DATA_QUALITY_REVIEW"
        )

    lines.append("")
    lines.append(
        "XG / XA CONCLUSION"
    )
    lines.append("-" * 80)

    if all_four.sum() == 0:
        lines.append(
            "Production scoring possible : NO"
        )

        lines.append(
            "Reason : xG/xA enrichment required "
            "before production scoring."
        )

        lines.append(
            "No partial scoring and no "
            "weight renormalization."
        )

    else:
        lines.append(
            "Production scoring coverage exists "
            "for a subset of rows."
        )

        lines.append(
            "Strict four-metric eligibility "
            "must be applied."
        )

    lines.append("")
    lines.append(
        "METHODOLOGICAL RULE"
    )
    lines.append("-" * 80)

    lines.append(
        "ELIGIBLE = minutes >= 900 "
        "AND all four metrics available."
    )

    lines.append(
        "Missing metrics => "
        "INSUFFICIENT_METRICS."
    )

    lines.append(
        "No missing metric is replaced by zero."
    )

    lines.append(
        "No partial score and no weight "
        "renormalization."
    )

    lines.append(
        "Production score and percentile "
        "are NOT calculated by this audit."
    )

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 80)
    print(
        "PERFORMANCE SCORER — REAL DATA AUDIT"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        print(
            f"[ERROR] Fichier introuvable : "
            f"{INPUT_FILE}",
            file=sys.stderr,
        )

        return 1

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"[AUDIT] Source : {INPUT_FILE}"
    )

    df = pd.read_csv(
        INPUT_FILE,
        low_memory=False,
    )

    print(
        f"[AUDIT] Lignes chargées : "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    require_columns(df)

    print(
        "[AUDIT] Colonnes obligatoires : OK"
    )

    audit_rows = []

    audit_rows.extend(
        audit_dataset_structure(df)
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    audit_rows.extend(
        audit_metric_coverage(df)
    )

    # --------------------------------------------------------
    # MINUTES
    # --------------------------------------------------------

    audit_rows.extend(
        audit_minutes(df)
    )

    # --------------------------------------------------------
    # THEORETICAL STATUS
    # --------------------------------------------------------

    (
        theoretical_status,
        theoretical_rows,
    ) = build_theoretical_status(df)

    audit_rows.extend(
        theoretical_rows
    )

    # --------------------------------------------------------
    # PERCENTILE GROUPS
    # --------------------------------------------------------

    (
        percentile_groups,
        percentile_summary,
    ) = audit_percentile_groups(
        df,
        theoretical_status,
    )

    audit_rows.extend(
        percentile_summary
    )

    # --------------------------------------------------------
    # POSITION
    # --------------------------------------------------------

    audit_rows.extend(
        audit_position(df)
    )

    # --------------------------------------------------------
    # COMPETITION LEVEL
    # --------------------------------------------------------

    audit_rows.extend(
        audit_competition_level(df)
    )

    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    audit_rows.extend(
        audit_duplicates(df)
    )

    # --------------------------------------------------------
    # PLAYER ID
    # --------------------------------------------------------

    audit_rows.extend(
        audit_player_ids_in_dataset(df)
    )

    # --------------------------------------------------------
    # XG / XA
    # --------------------------------------------------------

    audit_rows.extend(
        audit_xg_xa_raw(df)
    )

    # --------------------------------------------------------
    # PLAYER REFERENCE DUCKDB
    # --------------------------------------------------------

    print(
        "[AUDIT] Vérification référentiel "
        "players DuckDB..."
    )

    player_reference_review = (
        audit_player_reference_duckdb(df)
    )

    audit_rows.extend(
        build_player_reference_summary(
            player_reference_review,
            df,
        )
    )

    # --------------------------------------------------------
    # SAVE SUMMARY
    # --------------------------------------------------------

    summary_df = pd.DataFrame(
        audit_rows
    )

    summary_path = save_csv(
        summary_df,
        "performance_scorer_audit_summary.csv",
    )

    # --------------------------------------------------------
    # SAVE ELIGIBILITY
    # --------------------------------------------------------

    eligibility_path = save_csv(
        theoretical_status,
        "performance_scorer_eligibility.csv",
    )

    # --------------------------------------------------------
    # SAVE GROUPS
    # --------------------------------------------------------

    percentile_path = save_csv(
        percentile_groups,
        "performance_scorer_percentile_groups.csv",
    )

    # --------------------------------------------------------
    # SAVE PLAYER REFERENCES
    # --------------------------------------------------------

    player_reference_path = save_csv(
        player_reference_review,
        "performance_scorer_player_reference_review.csv",
    )

    # --------------------------------------------------------
    # VALIDATIONS
    # --------------------------------------------------------

    structural_reviews = summary_df[
        summary_df["status"]
        == "STRUCTURAL_REVIEW"
    ]

    data_quality_reviews = summary_df[
        summary_df["status"]
        == "DATA_QUALITY_REVIEW"
    ]

    validation_rows = [
        {
            "validation": "EXPECTED_ROW_COUNT",
            "expected": EXPECTED_ROWS,
            "actual": len(df),
            "status": (
                "PASS"
                if len(df) == EXPECTED_ROWS
                else "STRUCTURAL_REVIEW"
            ),
        },
        {
            "validation": "NO_DUPLICATES",
            "expected": 0,
            "actual": int(
                df.duplicated(
                    [
                        "player_id",
                        "season",
                        "competition_id",
                    ]
                ).sum()
            ),
            "status": (
                "PASS"
                if not df.duplicated(
                    [
                        "player_id",
                        "season",
                        "competition_id",
                    ]
                ).any()
                else "STRUCTURAL_REVIEW"
            ),
        },
        {
            "validation": "STRICT_ELIGIBILITY_RULE",
            "expected": (
                "minutes >= 900 AND "
                "all four metrics available"
            ),
            "actual": (
                "Implemented in audit"
            ),
            "status": "PASS",
        },
        {
            "validation": "NO_PRODUCTION_SCORING",
            "expected": (
                "No raw score / percentile computed"
            ),
            "actual": "Audit only",
            "status": "PASS",
        },
        {
            "validation": "STRUCTURAL_REVIEW_COUNT",
            "expected": 0,
            "actual": len(
                structural_reviews
            ),
            "status": (
                "PASS"
                if len(structural_reviews) == 0
                else "STRUCTURAL_REVIEW"
            ),
        },
        {
            "validation": "DATA_QUALITY_REVIEW_COUNT",
            "expected": 0,
            "actual": len(
                data_quality_reviews
            ),
            "status": (
                "PASS"
                if len(data_quality_reviews) == 0
                else "INFO"
            ),
        },
    ]

    validation_df = pd.DataFrame(
        validation_rows
    )

    validation_path = save_csv(
        validation_df,
        "performance_scorer_audit_validation.csv",
    )

    # --------------------------------------------------------
    # TEXT REPORT
    # --------------------------------------------------------

    report = build_text_report(
        df,
        theoretical_status,
        percentile_groups,
        player_reference_review,
    )

    report_path = (
        AUDIT_DIR
        / "performance_scorer_audit_report.txt"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # CONSOLE
    # --------------------------------------------------------

    print()
    print(report)

    print()
    print("=" * 80)
    print("AUDIT ARTIFACTS")
    print("=" * 80)

    print(
        f"Summary       : {summary_path}"
    )

    print(
        f"Eligibility   : {eligibility_path}"
    )

    print(
        f"Groups        : {percentile_path}"
    )

    print(
        f"Player refs   : {player_reference_path}"
    )

    print(
        f"Validation    : {validation_path}"
    )

    print(
        f"Report        : {report_path}"
    )

    print("=" * 80)

    # --------------------------------------------------------
    # EXIT CODE
    # --------------------------------------------------------

    if len(structural_reviews) > 0:
        print(
            "[AUDIT] STRUCTURAL_REVIEW — "
            "anomalies structurelles bloquantes détectées."
        )

        return 2

    if len(data_quality_reviews) > 0:
        print(
            "[AUDIT] PASS AVEC DATA_QUALITY_REVIEW — "
            "anomalies source non bloquantes détectées."
        )

        return 0

    print(
        "[AUDIT] PASS — "
        "aucune anomalie structurelle ou qualité."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )