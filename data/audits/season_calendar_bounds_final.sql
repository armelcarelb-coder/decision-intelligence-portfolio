-- =========================================================
-- BORNES DEFINITIVES DES SAISONS
-- =========================================================
--
-- Source : audit_season_calendar_raw.py
--
-- Regle :
--   season_start = premier match KEEP
--   season_end   = dernier match KEEP
--
-- Les matchs EXCLUDE_NATIONAL, EXCLUDE_FRIENDLY,
-- REVIEW_PENDING et REVIEW_CONFIRMED_DATA_QUALITY
-- sont exclus des bornes.
--
-- Cet artefact est une reference de calendrier.
-- Aucun composant aval ne doit recalculer les bornes.
-- =========================================================

CREATE OR REPLACE TABLE season_calendar_bounds_final (
    season INTEGER,
    season_start DATE,
    season_end DATE,
    duration_days INTEGER,
    games INTEGER,
    competitions INTEGER,
    first_competition_code VARCHAR,
    first_competition_name VARCHAR,
    first_competition_type VARCHAR,
    first_classification_reason VARCHAR,
    last_competition_code VARCHAR,
    last_competition_name VARCHAR,
    last_competition_type VARCHAR,
    last_classification_reason VARCHAR
);

INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2012, DATE '2012-07-03', DATE '2013-06-01', 333, 5700, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'russian-cup', 'russian-cup', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2013, DATE '2013-07-02', DATE '2014-05-24', 326, 5762, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'uefa-champions-league', 'uefa-champions-league', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2014, DATE '2014-07-01', DATE '2015-06-07', 341, 5836, 41, 'uefa-europa-league-qualifying', 'uefa-europa-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'superliga', 'superliga', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2015, DATE '2015-06-30', DATE '2016-05-29', 334, 5708, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'superliga', 'superliga', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2016, DATE '2016-06-28', DATE '2017-06-03', 340, 5699, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'uefa-champions-league', 'uefa-champions-league', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2017, DATE '2017-06-27', DATE '2018-05-26', 333, 5596, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'uefa-champions-league', 'uefa-champions-league', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2018, DATE '2018-06-26', DATE '2019-06-01', 340, 5723, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'uefa-champions-league', 'uefa-champions-league', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2019, DATE '2019-06-25', DATE '2021-04-03', 648, 5469, 41, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'copa-del-rey', 'copa-del-rey', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2020, DATE '2020-08-01', DATE '2021-05-29', 301, 5513, 39, 'scottish-premiership', 'scottish-premiership', 'OFFICIAL_CLUB_COMPETITION', 'uefa-champions-league', 'uefa-champions-league', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2021, DATE '2021-06-22', DATE '2022-05-29', 341, 5875, 42, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'russian-cup', 'russian-cup', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2022, DATE '2022-06-21', DATE '2024-02-25', 614, 6008, 42, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'russian-cup', 'russian-cup', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2023, DATE '2023-06-27', DATE '2024-08-28', 428, 5900, 43, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'russian-cup', 'russian-cup', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2024, DATE '2024-07-09', DATE '2025-12-07', 516, 9985, 58, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_EUROPEAN_QUALIFICATION', 'campeonato-brasileiro-serie-a', 'campeonato-brasileiro-serie-a', 'OFFICIAL_CLUB_COMPETITION');
INSERT INTO season_calendar_bounds_final (season, season_start, season_end, duration_days, games, competitions, first_competition_code, first_competition_name, first_classification_reason, last_competition_code, last_competition_name, last_classification_reason) VALUES (2025, DATE '2025-06-15', DATE '2026-07-06', 386, 9441, 63, 'uefa-champions-league-qualifying', 'uefa-champions-league-qualifying', 'OFFICIAL_CLUB_COMPETITION', 'allsvenskan', 'allsvenskan', 'OFFICIAL_CLUB_COMPETITION');

-- Contrôle d'intégrité
ALTER TABLE season_calendar_bounds_final ADD CONSTRAINT season_calendar_bounds_unique UNIQUE (season);
