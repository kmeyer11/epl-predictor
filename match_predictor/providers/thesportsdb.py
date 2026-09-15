"""TheSportsDB provider (free tier: 30 requests/minute).

Used only as the *live/upcoming fixtures* source for the Danish Superliga,
which football-data.org's free tier doesn't include. Its free tier caps
historical season lookups too low to be useful for training (see
providers/football_data_couk.py for that instead). Data here is
community-maintained rather than professionally verified, so treat it as
best-effort. Docs: https://www.thesportsdb.com/api.php
"""
import requests

from .. import config
from . import ProviderError


def _season_str(year):
    return f"{year}-{year + 1}"


def _get(path, params=None):
    url = f"{config.THESPORTSDB_BASE_URL}/{config.THESPORTSDB_KEY}{path}"
    resp = requests.get(url, params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _normalize(event, league_slug):
    status = "FT" if event.get("strStatus") in ("FT", "Match Finished") else "NS"
    time_part = event.get("strTime") or "00:00:00"
    home_goals, away_goals = event.get("intHomeScore"), event.get("intAwayScore")
    return {
        "fixture_id": f"tsdb-{event['idEvent']}",
        "league": league_slug,
        "season": int(event["strSeason"].split("-")[0]),
        "round": f"Round {event['intRound']}",
        "kickoff": f"{event['dateEvent']}T{time_part}Z",
        "status": status,
        "home_team": event["strHomeTeam"],
        "away_team": event["strAwayTeam"],
        "home_goals": int(home_goals) if home_goals not in (None, "") else None,
        "away_goals": int(away_goals) if away_goals not in (None, "") else None,
    }


def get_current_round(league_slug, league_cfg):
    """Returns (round_label, season_year)."""
    data = _get("/eventsnextleague.php", {"id": league_cfg["league_id"]})
    events = data.get("events") or []
    if not events:
        raise ProviderError(f"No upcoming fixtures found for {league_slug} on TheSportsDB.")
    soonest = sorted(events, key=lambda e: (e["dateEvent"], e.get("strTime") or ""))[0]
    return f"Round {soonest['intRound']}", int(soonest["strSeason"].split("-")[0])


def get_round_fixtures(league_slug, league_cfg, season_year, round_label):
    round_num = round_label.replace("Round ", "")
    data = _get(
        "/eventsround.php",
        {"id": league_cfg["league_id"], "r": round_num, "s": _season_str(season_year)},
    )
    return [_normalize(e, league_slug) for e in (data.get("events") or [])]
