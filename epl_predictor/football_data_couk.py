"""football-data.co.uk Premier League results and bookmaker odds (free CSVs, no key).

One CSV per season, updated a few times a week. Column notes:
https://www.football-data.co.uk/notes.txt
"""
import csv
import io
from datetime import datetime

import requests

from . import config

# Pre-match market averages first: those are what you'd see when placing a bet
# ahead of the round. The other columns cover seasons that lack them.
_ODDS_1X2 = [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA"), ("AvgCH", "AvgCD", "AvgCA")]
_ODDS_OVER_UNDER = [("Avg>2.5", "Avg<2.5"), ("BbAv>2.5", "BbAv<2.5"), ("AvgC>2.5", "AvgC<2.5")]


def _season_code(year):
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_odds(row, column_sets):
    for columns in column_sets:
        values = [_float(row.get(c)) for c in columns]
        if all(values):
            return values
    return [None] * len(column_sets[0])


def _kickoff(row):
    date_fmt = "%d/%m/%Y" if len(row["Date"]) == 10 else "%d/%m/%y"
    day = datetime.strptime(row["Date"], date_fmt)
    # Times are UK local time; labelling them UTC is off by at most an hour,
    # which doesn't matter for match ordering.
    time = row.get("Time") or "15:00"
    return f"{day:%Y-%m-%d}T{time}:00Z"


def _normalize(row, season):
    odds_home, odds_draw, odds_away = _first_odds(row, _ODDS_1X2)
    odds_over25, odds_under25 = _first_odds(row, _ODDS_OVER_UNDER)
    home, away = row["HomeTeam"], row["AwayTeam"]
    return {
        "fixture_id": f"couk-{season}-{home}-{away}",
        "season": season,
        "round": None,
        "kickoff": _kickoff(row),
        "status": "FT",
        "home_team": home,
        "away_team": away,
        "home_goals": int(row["FTHG"]),
        "away_goals": int(row["FTAG"]),
        "odds_home": odds_home,
        "odds_draw": odds_draw,
        "odds_away": odds_away,
        "odds_over25": odds_over25,
        "odds_under25": odds_under25,
    }


def get_season_results(season):
    """Finished matches for one season; empty if the season's file doesn't exist yet."""
    url = f"{config.FOOTBALL_DATA_COUK_BASE_URL}/{_season_code(season)}/E0.csv"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    try:
        text = resp.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = resp.content.decode("latin-1")
    rows = csv.DictReader(io.StringIO(text))
    return [_normalize(r, season) for r in rows if r.get("HomeTeam") and r.get("FTHG")]
