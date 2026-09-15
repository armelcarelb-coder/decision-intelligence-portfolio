from pathlib import Path

import duckdb
import pandas as pd


DB_PATH = Path(
    "data/historical/transfermarkt-datasets.duckdb"
)

GAME_ID = 3606208


def main() -> None:
    connection = duckdb.connect(
        database=str(DB_PATH),
        read_only=True,
    )

    try:
        print("=" * 100)
        print("1. MATCH REVIEW — game_id 3606208")
        print("=" * 100)

        game = connection.execute(
            """
            SELECT
                g.game_id,
                g.competition_id,
                g.season,
                g.round,
                g.date,
                g.home_club_id,
                g.away_club_id,
                g.home_club_goals,
                g.away_club_goals,
                g.competition_type,

                c.competition_code,
                c.name AS competition_name,
                c.sub_type AS competition_sub_type,
                c.type AS competition_metadata_type,
                c.country_name,
                c.confederation

            FROM games AS g

            LEFT JOIN competitions AS c
                ON g.competition_id = c.competition_id

            WHERE g.game_id = ?
            """,
            [GAME_ID],
        ).fetchdf()

        print(game.to_string(index=False))

        print()
        print("=" * 100)
        print("2. CLUBS CONCERNÉS")
        print("=" * 100)

        clubs = connection.execute(
            """
            SELECT
                club_id,
                name,
                domestic_competition_id
            FROM clubs
            WHERE club_id IN (
                SELECT CAST(home_club_id AS VARCHAR)
                FROM games
                WHERE game_id = ?

                UNION

                SELECT CAST(away_club_id AS VARCHAR)
                FROM games
                WHERE game_id = ?
            )
            ORDER BY club_id
            """,
            [GAME_ID, GAME_ID],
        ).fetchdf()

        print(clubs.to_string(index=False))

        print()
        print("=" * 100)
        print("3. MATCHS DES DEUX CLUBS AUTOUR DU 22/09/2021")
        print("=" * 100)

        nearby = connection.execute(
            """
            WITH review_game AS (
                SELECT
                    home_club_id,
                    away_club_id,
                    date
                FROM games
                WHERE game_id = ?
            )

            SELECT
                g.game_id,
                g.season,
                g.date,
                g.round,
                g.competition_id,
                c.competition_code,
                c.name AS competition_name,
                g.competition_type,
                g.home_club_id,
                g.away_club_id,
                g.home_club_goals,
                g.away_club_goals

            FROM games AS g

            LEFT JOIN competitions AS c
                ON g.competition_id = c.competition_id

            CROSS JOIN review_game AS r

            WHERE
                (
                    g.home_club_id = r.home_club_id
                    OR g.home_club_id = r.away_club_id
                    OR g.away_club_id = r.home_club_id
                    OR g.away_club_id = r.away_club_id
                )

                AND g.date BETWEEN
                    r.date - INTERVAL 90 DAY
                    AND
                    r.date + INTERVAL 90 DAY

            ORDER BY
                g.date,
                g.game_id
            """,
            [GAME_ID],
        ).fetchdf()

        print(nearby.to_string(index=False))

        print()
        print("=" * 100)
        print("4. TOUS LES MATCHS DU CLUBS EN 2021 ET 2025")
        print("=" * 100)

        chronology = connection.execute(
            """
            WITH review_game AS (
                SELECT
                    home_club_id,
                    away_club_id
                FROM games
                WHERE game_id = ?
            ),

            review_clubs AS (
                SELECT home_club_id AS club_id
                FROM review_game

                UNION

                SELECT away_club_id AS club_id
                FROM review_game
            )

            SELECT
                g.game_id,
                g.season,
                g.date,
                g.round,
                g.competition_id,
                c.competition_code,
                c.name AS competition_name,
                g.competition_type,
                g.home_club_id,
                g.away_club_id

            FROM games AS g

            LEFT JOIN competitions AS c
                ON g.competition_id = c.competition_id

            WHERE
                (
                    g.home_club_id IN (
                        SELECT club_id
                        FROM review_clubs
                    )
                    OR
                    g.away_club_id IN (
                        SELECT club_id
                        FROM review_clubs
                    )
                )

                AND (
                    g.date BETWEEN
                        DATE '2021-01-01'
                        AND DATE '2021-12-31'

                    OR

                    g.date BETWEEN
                        DATE '2025-01-01'
                        AND DATE '2025-12-31'
                )

            ORDER BY
                g.date,
                g.game_id
            """,
            [GAME_ID],
        ).fetchdf()

        print(chronology.to_string(index=False))

    finally:
        connection.close()


if __name__ == "__main__":
    main()