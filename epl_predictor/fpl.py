"""Team news from the Fantasy Premier League API (no key).

Every player's availability ('Hamstring injury - 75% chance of playing') and
their season so far. Current season only: there is no archive of past news.
"""
from datetime import datetime
from functools import cache

import click
import requests

from . import config
from .teams import canonical

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _parse_time(iso_string):
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


@cache
def _bootstrap():
    try:
        resp = requests.get(f"{config.FPL_BASE_URL}/bootstrap-static/", timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise click.ClickException(f"Could not fetch team news from the FPL API: {e}")
    return resp.json()


def _chance(player, field):
    """Chance of playing, 0-1. FPL leaves it empty when there is no news."""
    chance = player[field]
    if chance is None:
        return 1.0 if player["status"] == "a" else 0.0
    return chance / 100


def get_team_news(kickoff):
    """Players per team (canonical names) with their chance of playing a match at `kickoff`.

    Only players who have played this season: the rest don't count towards
    the team's output, so their absence changes nothing.
    """
    data = _bootstrap()
    # FPL gives one chance for the gameweek in progress and one for the next.
    upcoming = [_parse_time(e["deadline_time"]) for e in data["events"] if not e["finished"]]
    in_progress = any(e["is_current"] and not e["finished"] for e in data["events"])
    field = (
        "chance_of_playing_this_round"
        if in_progress and upcoming and _parse_time(kickoff) < min(upcoming)
        else "chance_of_playing_next_round"
    )
    team_names = {t["id"]: canonical(t["name"]) for t in data["teams"]}
    news = {}
    for p in data["elements"]:
        if not p["minutes"]:
            continue
        news.setdefault(team_names[p["team"]], []).append({
            "name": p["web_name"],
            "position": POSITIONS[p["element_type"]],
            "minutes": p["minutes"],
            "xgi": float(p["expected_goal_involvements"]),
            "chance": _chance(p, field),
            "news": p["news"],
        })
    return news
