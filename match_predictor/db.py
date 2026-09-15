import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id TEXT PRIMARY KEY,
    league     TEXT NOT NULL,
    season     INTEGER NOT NULL,
    round      TEXT,
    kickoff    TEXT NOT NULL,
    status     TEXT NOT NULL,
    home_team  TEXT NOT NULL,
    away_team  TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA)


def upsert_fixtures(fixtures):
    """fixtures: list of normalized dicts (see providers/*.py `_normalize`)."""
    rows = [
        (
            f["fixture_id"],
            f["league"],
            f["season"],
            f["round"],
            f["kickoff"],
            f["status"],
            f["home_team"],
            f["away_team"],
            f["home_goals"],
            f["away_goals"],
        )
        for f in fixtures
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO fixtures (
                fixture_id, league, season, round, kickoff, status,
                home_team, away_team, home_goals, away_goals
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                round=excluded.round,
                kickoff=excluded.kickoff,
                status=excluded.status,
                home_goals=excluded.home_goals,
                away_goals=excluded.away_goals
            """,
            rows,
        )
    return len(rows)


def get_finished_fixtures(league_slug, seasons):
    placeholders = ",".join("?" for _ in seasons)
    with connect() as conn:
        cur = conn.execute(
            f"""
            SELECT * FROM fixtures
            WHERE league = ? AND season IN ({placeholders}) AND status = 'FT'
            ORDER BY kickoff
            """,
            (league_slug, *seasons),
        )
        return [dict(r) for r in cur.fetchall()]
