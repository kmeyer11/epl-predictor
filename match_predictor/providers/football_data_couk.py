"""football-data.co.uk provider (free, no auth, no rate limit) - used only as
a *historical results* source, for leagues whose live/upcoming fixtures come
from a different provider (see providers/thesportsdb.py for the Danish
Superliga). This site does not expose upcoming fixtures, only played results.

Docs/downloads: https://www.football-data.co.uk/downloadm.php
"""
import csv
import io
from datetime import datetime

import requests

from . import ProviderError

BASE_URL = "https://football-data.co.uk/new"


def get_historical_fixtures(league_slug, league_cfg, season_years):
    url = f"{BASE_URL}/{league_cfg['country_code']}.csv"
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        raise ProviderError(f"football-data.co.uk returned {resp.status_code} for {url}")

    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))
    wanted_seasons = {f"{y}/{y + 1}" for y in season_years}

    fixtures = []
    for row in reader:
        season = (row.get("Season") or "").strip()
        if season not in wanted_seasons:
            continue
        home_goals, away_goals = row.get("HG"), row.get("AG")
        if home_goals in (None, "") or away_goals in (None, ""):
            continue  # not yet played, or missing data

        match_date = datetime.strptime(row["Date"].strip(), "%d/%m/%Y").date()
        kickoff_time = (row.get("Time") or "00:00").strip() or "00:00"
        home, away = row["Home"].strip(), row["Away"].strip()

        fixtures.append(
            {
                "fixture_id": f"fdcouk-{match_date.isoformat()}-{home}-{away}".replace(" ", "_"),
                "league": league_slug,
                "season": int(season.split("/")[0]),
                "round": "N/A",
                "kickoff": f"{match_date.isoformat()}T{kickoff_time}:00Z",
                "status": "FT",
                "home_team": home,
                "away_team": away,
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
            }
        )
    return fixtures
