import sqlite3
from contextlib import contextmanager

from . import config

FIXTURE_COLUMNS = [
    "fixture_id", "season", "round", "kickoff", "status",
    "home_team", "away_team", "home_goals", "away_goals",
    "odds_home", "odds_draw", "odds_away", "odds_over25", "odds_under25",
]

PREDICTION_COLUMNS = [
    "kind", "model", "model_version", "season", "home_team", "away_team", "kickoff", "created_at",
    "p_home", "p_draw", "p_away", "xg_home", "xg_away",
    "pick_home", "pick_away", "top_home", "top_away",
]
PREDICTION_KEY = ["kind", "model", "model_version", "season", "home_team", "away_team"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id   TEXT PRIMARY KEY,
    season       INTEGER NOT NULL,
    round        TEXT,
    kickoff      TEXT NOT NULL,
    status       TEXT NOT NULL,
    home_team    TEXT NOT NULL,
    away_team    TEXT NOT NULL,
    home_goals   INTEGER,
    away_goals   INTEGER,
    odds_home    REAL,
    odds_draw    REAL,
    odds_away    REAL,
    odds_over25  REAL,
    odds_under25 REAL
);

-- One row per model version per match. kind is 'backtest' (replayed history)
-- or 'live' (saved by `predict` before kickoff). pick_* is the bet with the
-- most expected plshowet points, top_* the likeliest score.
CREATE TABLE IF NOT EXISTS predictions (
    kind          TEXT NOT NULL,
    model         TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    season        INTEGER NOT NULL,
    home_team  TEXT NOT NULL,
    away_team  TEXT NOT NULL,
    kickoff    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    p_home     REAL NOT NULL,
    p_draw     REAL NOT NULL,
    p_away     REAL NOT NULL,
    xg_home    REAL NOT NULL,
    xg_away    REAL NOT NULL,
    pick_home  INTEGER NOT NULL,
    pick_away  INTEGER NOT NULL,
    top_home   INTEGER NOT NULL,
    top_away   INTEGER NOT NULL,
    PRIMARY KEY (kind, model, model_version, season, home_team, away_team)
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
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(fixtures)")}
        if columns and "odds_home" not in columns:
            # Old cache filled from football-data.org, with different team
            # names. It's only a cache: drop it and let `fetch` refill it.
            conn.execute("DROP TABLE fixtures")
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(predictions)")}
        if columns and "model_version" not in columns:
            # Predictions from before models had versions; the key changed.
            conn.execute("DROP TABLE predictions")
        conn.executescript(SCHEMA)


def _upsert(conn, table, columns, key, rows):
    updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in key)
    conn.executemany(
        f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        ON CONFLICT({", ".join(key)}) DO UPDATE SET {updates}
        """,
        [tuple(r[c] for c in columns) for r in rows],
    )


def upsert_fixtures(fixtures):
    """fixtures: list of normalized dicts (see football_data_couk.py `_normalize`)."""
    with connect() as conn:
        _upsert(conn, "fixtures", FIXTURE_COLUMNS, ["fixture_id"], fixtures)
    return len(fixtures)


def get_finished_fixtures(seasons):
    placeholders = ",".join("?" for _ in seasons)
    with connect() as conn:
        cur = conn.execute(
            f"""
            SELECT * FROM fixtures
            WHERE season IN ({placeholders}) AND status = 'FT'
            ORDER BY kickoff
            """,
            tuple(seasons),
        )
        return [dict(r) for r in cur.fetchall()]


def get_seasons():
    with connect() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT season FROM fixtures ORDER BY season")]


def replace_backtest_predictions(models, seasons, rows):
    """Swap out earlier backtest rows for these (name, version) models and seasons,
    so stale rows don't linger. Rows from other versions are kept."""
    with connect() as conn:
        for name, version in models:
            conn.execute(
                f"""
                DELETE FROM predictions WHERE kind = 'backtest'
                AND model = ? AND model_version = ?
                AND season IN ({",".join("?" for _ in seasons)})
                """,
                (name, version, *seasons),
            )
        _upsert(conn, "predictions", PREDICTION_COLUMNS, PREDICTION_KEY, rows)


def upsert_predictions(rows):
    with connect() as conn:
        _upsert(conn, "predictions", PREDICTION_COLUMNS, PREDICTION_KEY, rows)


def get_scored_predictions(kind, models=None, seasons=None):
    """Predictions joined with the final score, for matches that have been played.

    models: (name, version) pairs to include; None for every stored version.
    """
    sql = """
        SELECT p.*, f.home_goals, f.away_goals
        FROM predictions p
        JOIN fixtures f
          ON f.season = p.season AND f.home_team = p.home_team AND f.away_team = p.away_team
        WHERE p.kind = ? AND f.status = 'FT'
    """
    params = [kind]
    if models:
        sql += " AND (" + " OR ".join("(p.model = ? AND p.model_version = ?)" for _ in models) + ")"
        params += [v for pair in models for v in pair]
    if seasons:
        sql += f" AND p.season IN ({','.join('?' for _ in seasons)})"
        params += list(seasons)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def prediction_row(kind, model, fixture, prediction, created_at):
    """Flatten a model prediction (scoring.summarize output) into a predictions row."""
    return {
        "kind": kind,
        "model": model.name,
        "model_version": model.version,
        "season": fixture["season"],
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "kickoff": fixture["kickoff"],
        "created_at": created_at,
        **{k: prediction[k] for k in ("p_home", "p_draw", "p_away", "xg_home", "xg_away")},
        "pick_home": prediction["pick"][0],
        "pick_away": prediction["pick"][1],
        "top_home": prediction["top"][0],
        "top_away": prediction["top"][1],
    }


def get_unplayed_live_predictions(models):
    """Live bets for matches that have no final score stored yet."""
    sql = """
        SELECT p.* FROM predictions p
        LEFT JOIN fixtures f
          ON f.season = p.season AND f.home_team = p.home_team AND f.away_team = p.away_team
          AND f.status = 'FT'
        WHERE p.kind = 'live' AND f.fixture_id IS NULL
    """
    sql += " AND (" + " OR ".join("(p.model = ? AND p.model_version = ?)" for _ in models) + ")"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, [v for pair in models for v in pair])]
