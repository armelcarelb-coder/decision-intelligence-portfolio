from __future__ import annotations

from pathlib import Path
import argparse

import numpy as np
import pandas as pd


GAME_PLAYER_DEFAULT = Path(
    "data/enrichment/xg_xa_game_player.csv"
)

PERFORMANCE_DEFAULT = Path(
    "data/performances/"
    "player_competition_season_performance_xgxa.csv"
)

AUDIT_DIR_DEFAULT = Path(
    "data/audits"
)


def check(
    name: str,
    passed: bool,
    actual: str = "",
) -> dict:

    return {
        "check": name,
        "status": "PASS" if passed else "FAIL",
        "actual": actual,
    }


def run_audit(
    game_player_path: Path,
    performance_path: Path,
    audit_dir: Path,
) -> None:

    if not game_player_path.exists():
        raise FileNotFoundError(
            f"Fichier game/player absent : "
            f"{game_player_path}"
        )

    if not performance_path.exists():
        raise FileNotFoundError(
            f"Fichier performance absent : "
            f"{performance_path}"
        )

    audit_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    gp = pd.read_csv(
        game_player_path
    )

    perf = pd.read_csv(
        performance_path
    )

    checks = []

    # ======================================================================
    # GAME PLAYER
    # ======================================================================

    duplicated = gp.duplicated(
        subset=[
            "game_id",
            "player_id",
        ],
        keep=False,
    )

    checks.append(
        check(
            "UNIQUE_GAME_PLAYER",
            not duplicated.any(),
            f"duplicates={int(duplicated.sum())}",
        )
    )

    for column in [
        "xg",
        "xa",
    ]:

        values = pd.to_numeric(
            gp[column],
            errors="coerce",
        )

        invalid_negative = (
            values.notna()
            & (values < 0)
        )

        checks.append(
            check(
                f"NON_NEGATIVE_{column.upper()}",
                not invalid_negative.any(),
                (
                    f"negative_rows="
                    f"{int(invalid_negative.sum())}"
                ),
            )
        )

    # ----------------------------------------------------------------------
    # SOURCE / STATUS
    # ----------------------------------------------------------------------

    confirmed_without_source = (
        (
            gp[
                "source_metric_status"
            ]
            == "SOURCE_CONFIRMED"
        )
        &
        (
            gp[
                "understat_game_id"
            ].isna()
        )
    )

    checks.append(
        check(
            "CONFIRMED_HAS_SOURCE_MATCH",
            not confirmed_without_source.any(),
            (
                "rows="
                f"{int(confirmed_without_source.sum())}"
            ),
        )
    )

    confirmed_without_xg = (
        (
            gp[
                "source_metric_status"
            ]
            == "SOURCE_CONFIRMED"
        )
        &
        (
            gp["xg"].isna()
            |
            gp["xa"].isna()
        )
    )

    checks.append(
        check(
            "CONFIRMED_HAS_XG_XA",
            not confirmed_without_xg.any(),
            (
                "rows="
                f"{int(confirmed_without_xg.sum())}"
            ),
        )
    )

    # ======================================================================
    # PERFORMANCE
    # ======================================================================

    duplicates_perf = perf.duplicated(
        subset=[
            "player_id",
            "season",
            "competition_id",
        ],
        keep=False,
    )

    checks.append(
        check(
            "UNIQUE_PLAYER_COMPETITION_SEASON",
            not duplicates_perf.any(),
            (
                "duplicates="
                f"{int(duplicates_perf.sum())}"
            ),
        )
    )

    complete = (
        perf[
            "xg_xa_enrichment_status"
        ]
        == "COMPLETE"
    )

    complete_with_missing = (
        complete
        &
        (
            perf["xg"].isna()
            |
            perf["xa"].isna()
            |
            perf["xg_per90"].isna()
            |
            perf["xa_per90"].isna()
        )
    )

    checks.append(
        check(
            "COMPLETE_HAS_ALL_XG_XA_METRICS",
            not complete_with_missing.any(),
            (
                "rows="
                f"{int(complete_with_missing.sum())}"
            ),
        )
    )

    # ----------------------------------------------------------------------
    # MINUTES
    # ----------------------------------------------------------------------

    minutes_review = perf[
        "xg_xa_enrichment_status"
    ].eq(
        "MINUTES_MISMATCH_REVIEW"
    )

    checks.append(
        check(
            "NO_MINUTES_MISMATCH",
            not minutes_review.any(),
            (
                "rows="
                f"{int(minutes_review.sum())}"
            ),
        )
    )

    # ----------------------------------------------------------------------
    # PER90
    # ----------------------------------------------------------------------

    negative_rates = (
        (
            pd.to_numeric(
                perf["xg_per90"],
                errors="coerce",
            )
            < 0
        )
        |
        (
            pd.to_numeric(
                perf["xa_per90"],
                errors="coerce",
            )
            < 0
        )
    )

    checks.append(
        check(
            "NON_NEGATIVE_PER90",
            not negative_rates.fillna(
                False
            ).any(),
            (
                "invalid_rows="
                f"{int(negative_rates.fillna(False).sum())}"
            ),
        )
    )

    # ======================================================================
    # OUTPUTS
    # ======================================================================

    validation = pd.DataFrame(
        checks
    )

    validation_path = (
        audit_dir
        / "xg_xa_game_player_validation.csv"
    )

    validation.to_csv(
        validation_path,
        index=False,
        encoding="utf-8",
    )

    summary_rows = [
        {
            "metric": "game_player_rows",
            "value": len(gp),
        },
        {
            "metric": "unique_games",
            "value": gp[
                "game_id"
            ].nunique(),
        },
        {
            "metric": "unique_players",
            "value": gp[
                "player_id"
            ].nunique(),
        },
        {
            "metric": "xg_non_null",
            "value": gp[
                "xg"
            ].notna().sum(),
        },
        {
            "metric": "xa_non_null",
            "value": gp[
                "xa"
            ].notna().sum(),
        },
        {
            "metric": "player_confirmed",
            "value": (
                gp[
                    "player_mapping_status"
                ]
                == "PLAYER_CONFIRMED"
            ).sum(),
        },
        {
            "metric": "match_confirmed",
            "value": (
                gp[
                    "mapping_status"
                ]
                == "MATCH_CONFIRMED"
            ).sum(),
        },
        {
            "metric": "performance_rows",
            "value": len(perf),
        },
        {
            "metric": "performance_complete",
            "value": complete.sum(),
        },
        {
            "metric": "performance_partial",
            "value": (
                perf[
                    "xg_xa_enrichment_status"
                ]
                == "PARTIAL"
            ).sum(),
        },
        {
            "metric": "performance_out_of_scope",
            "value": (
                perf[
                    "xg_xa_enrichment_status"
                ]
                == "OUT_OF_SCOPE"
            ).sum(),
        },
    ]

    summary = pd.DataFrame(
        summary_rows
    )

    summary_path = (
        audit_dir
        / "xg_xa_enrichment_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
        encoding="utf-8",
    )

    # ======================================================================
    # REPORT
    # ======================================================================

    failed = (
        validation[
            "status"
        ]
        == "FAIL"
    ).sum()

    report_lines = [
        "XG/XA ENRICHMENT V1 — AUDIT",
        "",
        f"Game/player rows : {len(gp):,}",
        f"Performance rows : {len(perf):,}",
        "",
        "VALIDATION",
        "----------",
        validation.to_string(
            index=False
        ),
        "",
        f"FAILURES : {int(failed)}",
    ]

    report_path = (
        audit_dir
        / "xg_xa_enrichment_report.txt"
    )

    report_path.write_text(
        "\n".join(report_lines)
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "============================================================"
    )

    if failed == 0:

        print(
            "XG/XA ENRICHMENT AUDIT : PASS"
        )

    else:

        print(
            "XG/XA ENRICHMENT AUDIT : FAIL"
        )

    print(
        "============================================================"
    )

    print(
        f"Validation : {validation_path}"
    )

    print(
        f"Summary    : {summary_path}"
    )

    print(
        f"Report     : {report_path}"
    )

    if failed > 0:

        raise SystemExit(
            2
        )


def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Audit de l'enrichissement "
            "xG/xA V1"
        )
    )

    parser.add_argument(
        "--game-player-path",
        default=str(
            GAME_PLAYER_DEFAULT
        ),
    )

    parser.add_argument(
        "--performance-path",
        default=str(
            PERFORMANCE_DEFAULT
        ),
    )

    parser.add_argument(
        "--audit-dir",
        default=str(
            AUDIT_DIR_DEFAULT
        ),
    )

    return parser.parse_args()


def main():

    args = parse_args()

    run_audit(
        game_player_path=Path(
            args.game_player_path
        ),
        performance_path=Path(
            args.performance_path
        ),
        audit_dir=Path(
            args.audit_dir
        ),
    )


if __name__ == "__main__":
    main()