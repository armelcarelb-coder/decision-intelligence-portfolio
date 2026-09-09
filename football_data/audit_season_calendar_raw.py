from pathlib import Path

import duckdb
import pandas as pd

DATABASE_PATH = Path("data/historical/transfermarkt-datasets.duckdb")

class RawSeasonCalendarAudit:

    def __init__(self, database_path: Path):
        self.database_path = database_path

    def connect(self):
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Base DuckDB introuvable : {self.database_path}"
            )

        return duckdb.connect(
            str(self.database_path),
            read_only=True
        )

def print_header(self, title: str):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

def audit_raw_season_bounds(self, con):
    self.print_header(
        "1. BORNES DE SAISON DANS LA TABLE RAW `games`"
    )

    query = """
    SELECT
        TRY_CAST(season AS INTEGER) AS season,
        MIN(date) AS actual_start,
        MAX(date) AS actual_end,
        COUNT(*) AS game_rows,
        COUNT(DISTINCT game_id) AS games
    FROM games
    WHERE TRY_CAST(season AS INTEGER) IS NOT NULL
    GROUP BY 1
    ORDER BY 1
    """

    df = con.execute(query).df()

    print(df.to_string(index=False))

    return df

def audit_competition_bounds(
    self,
    con,
    suspicious_seasons=(2019, 2022, 2023, 2025)
):
    self.print_header(
        "2. BORNES PAR COMPÉTITION POUR LES SAISONS SUSPECTES"
    )

    placeholders = ", ".join(
        ["?"] * len(suspicious_seasons)
    )

    query = f"""
    SELECT
        TRY_CAST(g.season AS INTEGER) AS season,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        MIN(g.date) AS competition_start,
        MAX(g.date) AS competition_end,
        COUNT(*) AS game_rows,
        COUNT(DISTINCT g.game_id) AS games
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE TRY_CAST(g.season AS INTEGER) IN ({placeholders})
    GROUP BY
        1,
        2,
        3,
        4,
        5,
        6,
        7
    ORDER BY
        season,
        competition_start,
        competition_id
    """

    df = con.execute(
        query,
        list(suspicious_seasons)
    ).df()

    for season in suspicious_seasons:
        print()
        print(f"--- SAISON {season} ---")

        season_df = df[df["season"] == season]

        if season_df.empty:
            print("Aucune donnée.")
        else:
            print(
                season_df.to_string(index=False)
            )

    return df

def audit_strong_calendar_anomalies(self, con):
    self.print_header(
        "3. ANOMALIES FORTES : DATE TRÈS ÉLOIGNÉE DE L'ANNÉE DE SAISON"
    )

    query = """
    SELECT
        g.game_id,
        TRY_CAST(g.season AS INTEGER) AS season,
        g.date,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        g.round
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE
        TRY_CAST(g.season AS INTEGER) IS NOT NULL
        AND (
            g.date < MAKE_DATE(
                TRY_CAST(g.season AS INTEGER),
                1,
                1
            )
            OR
            g.date > MAKE_DATE(
                TRY_CAST(g.season AS INTEGER) + 1,
                9,
                30
            )
        )
    ORDER BY
        season,
        date
    """

    df = con.execute(query).df()

    print(
        f"Nombre de matchs fortement suspects : {len(df):,}"
    )

    if df.empty:
        print("Aucune anomalie forte détectée.")
    else:
        print(df.to_string(index=False))

    return df

def audit_2025_before_season(self, con):
    self.print_header(
        "4. CAS CRITIQUE : SAISON 2025 AVEC MATCHS AVANT LE 01/06/2025"
    )

    query = """
    SELECT
        g.game_id,
        g.date,
        TRY_CAST(g.season AS INTEGER) AS season,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        g.round
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE
        TRY_CAST(g.season AS INTEGER) = 2025
        AND g.date < DATE '2025-06-01'
    ORDER BY
        g.date
    """

    df = con.execute(query).df()

    print(
        f"Nombre de matchs concernés : {len(df):,}"
    )

    if df.empty:
        print("Aucun match trouvé.")
    else:
        print(df.to_string(index=False))

    return df

def audit_2022_after_2023(self, con):
    self.print_header(
        "5. CAS CRITIQUE : SAISON 2022 AVEC MATCHS APRÈS LE 31/07/2023"
    )

    query = """
    SELECT
        g.game_id,
        g.date,
        TRY_CAST(g.season AS INTEGER) AS season,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        g.round
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE
        TRY_CAST(g.season AS INTEGER) = 2022
        AND g.date > DATE '2023-07-31'
    ORDER BY
        g.date
    """

    df = con.execute(query).df()

    print(
        f"Nombre de matchs concernés : {len(df):,}"
    )

    if df.empty:
        print("Aucun match trouvé.")
    else:
        print(df.to_string(index=False))

    return df

def audit_2019_after_2020(self, con):
    self.print_header(
        "6. CAS CRITIQUE : SAISON 2019 AVEC MATCHS APRÈS LE 31/07/2020"
    )

    query = """
    SELECT
        g.game_id,
        g.date,
        TRY_CAST(g.season AS INTEGER) AS season,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        g.round
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE
        TRY_CAST(g.season AS INTEGER) = 2019
        AND g.date > DATE '2020-07-31'
    ORDER BY
        g.date
    """

    df = con.execute(query).df()

    print(
        f"Nombre de matchs concernés : {len(df):,}"
    )

    if df.empty:
        print("Aucun match trouvé.")
    else:
        print(df.to_string(index=False))

    return df

def audit_2023_after_2024(self, con):
    self.print_header(
        "7. CAS CRITIQUE : SAISON 2023 AVEC MATCHS APRÈS LE 31/07/2024"
    )

    query = """
    SELECT
        g.game_id,
        g.date,
        TRY_CAST(g.season AS INTEGER) AS season,
        g.competition_id,
        c.competition_code,
        c.name AS competition_name,
        c.sub_type,
        c.type,
        g.competition_type,
        g.round
    FROM games g
    LEFT JOIN competitions c
        ON g.competition_id = c.competition_id
    WHERE
        TRY_CAST(g.season AS INTEGER) = 2023
        AND g.date > DATE '2024-07-31'
    ORDER BY
        g.date
    """

    df = con.execute(query).df()

    print(
        f"Nombre de matchs concernés : {len(df):,}"
    )

    if df.empty:
        print("Aucun match trouvé.")
    else:
        print(df.to_string(index=False))

    return df

def audit_suspicious_games_with_appearances(
    self,
    con,
    suspicious_seasons=(2019, 2022, 2023, 2025)
):
    self.print_header(
        "8. MATCHS SUSPECTS + NOMBRE D'APPARITIONS ASSOCIÉES"
    )

    placeholders = ", ".join(
        ["?"] * len(suspicious_seasons)
    )

    query = f"""
    WITH suspicious_games AS (
        SELECT
            g.game_id,
            TRY_CAST(g.season AS INTEGER) AS season,
            g.date,
            g.competition_id,
            c.competition_code,
            c.name AS competition_name,
            c.sub_type,
            c.type,
            g.competition_type,
            g.round
        FROM games g
        LEFT JOIN competitions c
            ON g.competition_id = c.competition_id
        WHERE
            TRY_CAST(g.season AS INTEGER)
            IN ({placeholders})
            AND (
                g.date < MAKE_DATE(
                    TRY_CAST(g.season AS INTEGER),
                    1,
                    1
                )
                OR
                g.date > MAKE_DATE(
                    TRY_CAST(g.season AS INTEGER) + 1,
                    9,
                    30
                )
            )
    ),

    appearance_stats AS (
        SELECT
            game_id,
            COUNT(*) AS appearance_rows,
            COUNT(DISTINCT player_id) AS distinct_players
        FROM appearances
        GROUP BY game_id
    )

    SELECT
        s.game_id,
        s.season,
        s.date,
        s.competition_id,
        s.competition_code,
        s.competition_name,
        s.sub_type,
        s.type,
        s.competition_type,
        s.round,
        COALESCE(a.appearance_rows, 0)
            AS appearance_rows,
        COALESCE(a.distinct_players, 0)
            AS distinct_players
    FROM suspicious_games s
    LEFT JOIN appearance_stats a
        ON s.game_id = a.game_id
    ORDER BY
        s.season,
        s.date
    """

    df = con.execute(
        query,
        list(suspicious_seasons)
    ).df()

    print(
        f"Nombre de matchs suspects : {len(df):,}"
    )

    if df.empty:
        print("Aucun match suspect.")
    else:
        print(df.to_string(index=False))

    return df

def audit_season_value_distribution(self, con):
    self.print_header(
        "9. DISTRIBUTION DES SAISONS DANS `games`"
    )

    query = """
    SELECT
        TRY_CAST(season AS INTEGER) AS season,
        COUNT(*) AS game_rows,
        COUNT(DISTINCT game_id) AS games,
        MIN(date) AS min_date,
        MAX(date) AS max_date
    FROM games
    GROUP BY 1
    ORDER BY 1
    """

    df = con.execute(query).df()

    print(df.to_string(index=False))

    return df

def run(self):
    con = self.connect()

    try:
        results = {}

        results["season_bounds"] = (
            self.audit_raw_season_bounds(con)
        )

        results["competition_bounds"] = (
            self.audit_competition_bounds(con)
        )

        results["strong_anomalies"] = (
            self.audit_strong_calendar_anomalies(con)
        )

        results["season_2025_before"] = (
            self.audit_2025_before_season(con)
        )

        results["season_2022_after"] = (
            self.audit_2022_after_2023(con)
        )

        results["season_2019_after"] = (
            self.audit_2019_after_2020(con)
        )

        results["season_2023_after"] = (
            self.audit_2023_after_2024(con)
        )

        results["suspicious_games_appearances"] = (
            self.audit_suspicious_games_with_appearances(con)
        )

        results["season_distribution"] = (
            self.audit_season_value_distribution(con)
        )

        return results

    finally:
        con.close()


def main():
    audit = RawSeasonCalendarAudit(
    DATABASE_PATH
    )
    audit.run()


if __name__ == "__main__":
    main()