"""football-data.org v4 client for the Premier League (free tier: 10 requests/minute).

Docs: https://www.football-data.org/documentation/api
"""
import time

import click
import requests

from . import config

COMPETITION = "PL"

_STATUS_MAP = {"FINISHED": "FT"}


class ProviderError(click.ClickException):
    pass


def _headers():
    if not config.FOOTBALL_DATA_KEY:
        raise ProviderError(
            "FOOTBALL_DATA_KEY is not set. Copy .env.example to .env and add your free "
            "key from https://www.football-data.org/client/register"
        )
    return {"X-Auth-Token": config.FOOTBALL_DATA_KEY}


def _get(path, params=None, retries=2):
    url = f"{config.FOOTBALL_DATA_BASE_URL}{path}"
    for attempt in range(retries + 1):
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=15)
        if resp.status_code == 429 and attempt < retries:
            time.sleep(int(resp.headers.get("Retry-After", "6")))
            continue
        if resp.status_code in (400, 401):
            raise ProviderError(
                f"football-data.org rejected the request ({resp.status_code}): "
                f"{resp.text[:200]}. Check that FOOTBALL_DATA_KEY in .env is a real key "
                "from https://www.football-data.org/client/register (not a placeholder)."
            )
        if resp.status_code == 403:
            raise ProviderError(
                "football-data.org returned 403 - this season isn't included in the free tier."
            )
        resp.raise_for_status()
        return resp.json()
    raise ProviderError("Rate limited by football-data.org, try again shortly.")


def _normalize(match):
    status = _STATUS_MAP.get(match["status"], "NS")
    score = match.get("score", {}).get("fullTime", {})
    return {
        "fixture_id": f"fd-{match['id']}",
        "season": int(match["season"]["startDate"][:4]),
        "round": f"Matchday {match['matchday']}" if match.get("matchday") else "N/A",
        "kickoff": match["utcDate"],
        "status": status,
        "home_team": match["homeTeam"]["name"],
        "away_team": match["awayTeam"]["name"],
        "home_goals": score.get("home"),
        "away_goals": score.get("away"),
    }


def get_current_round():
    """Returns (round_label, season_year).

    football-data.org's `currentSeason.currentMatchday` field lags behind
    reality (it can stay pointed at a matchday for a day or two after every
    game in it has finished), so instead this finds the earliest matchday
    that still has an unplayed fixture.
    """
    data = _get(f"/competitions/{COMPETITION}/matches", {"status": "SCHEDULED"})
    matches = [m for m in data.get("matches", []) if m.get("matchday")]
    if not matches:
        raise ProviderError(
            "No upcoming Premier League fixtures found - the season may be over, "
            "or fixtures for the next round aren't published yet."
        )
    next_match = min(matches, key=lambda m: (m["matchday"], m["utcDate"]))
    season_year = int(next_match["season"]["startDate"][:4])
    return f"Matchday {next_match['matchday']}", season_year


def get_round_fixtures(round_label):
    matchday = round_label.replace("Matchday ", "")
    data = _get(f"/competitions/{COMPETITION}/matches", {"matchday": matchday})
    return [_normalize(m) for m in data.get("matches", [])]

