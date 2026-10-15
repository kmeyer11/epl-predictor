"""Dixon-Coles adjusted for team news: injuries, suspensions and doubts.

Team news comes from the Fantasy Premier League API. A team without the
players who make a big share of its chances (expected goals + assists this
season) scores less. A team without its keeper or regular defenders concedes
more. A doubtful player counts by his chance of missing out.

News exists only for upcoming matches, so this model can't be backtested.
It competes in the live leaderboard only.
"""
from datetime import datetime, timezone

from .. import fpl
from .base import Model, poisson_matrix
from .dixon_coles import DixonColes

# Share of a missing player's output the team loses; whoever replaces him makes
# up the rest. Guesses, not fitted: there is no archive of pre-match news to fit them on.
ATTACK_LOSS = 0.4
DEFENCE_LOSS = 0.25


def _missing_share(players, weight):
    """Share of the team's `weight` (xgi or minutes) expected to be missing."""
    total = sum(weight(p) for p in players)
    if not total:
        return 0.0
    return sum((1 - p["chance"]) * weight(p) for p in players) / total


def _absences(players):
    """(attack share missing, defence share missing) for one team's news."""
    defenders = [p for p in players if p["position"] in ("GK", "DEF")]
    return (
        _missing_share(players, lambda p: p["xgi"]),
        _missing_share(defenders, lambda p: p["minutes"]),
    )


class Gossip(Model):
    name = "gossip"
    description = "Dixon-Coles adjusted for injuries and suspensions in the FPL team news. Live only."

    def __init__(self):
        self._matches = []
        self._base = None

    def fit(self, matches):
        # Dixon-Coles is fitted on first use instead: the backtest calls fit
        # before every round but never gets a prediction out of this model.
        self._matches = list(matches)
        self._base = None
        return self

    def _team_news(self, fixture):
        kickoff = datetime.fromisoformat(fixture["kickoff"].replace("Z", "+00:00"))
        if kickoff <= datetime.now(timezone.utc):
            raise ValueError("team news only exists for upcoming matches")
        news = fpl.get_team_news(fixture["kickoff"])
        for team in (fixture["home_team"], fixture["away_team"]):
            if team not in news:
                raise ValueError(f"no FPL team news for {team}")
        return news[fixture["home_team"]], news[fixture["away_team"]]

    def score_matrix(self, fixture):
        home, away = self._team_news(fixture)
        if self._base is None:
            self._base = DixonColes().fit(self._matches)
        lam, mu = self._base.expected_goals(fixture["home_team"], fixture["away_team"])
        home_att, home_def = _absences(home)
        away_att, away_def = _absences(away)
        lam *= (1 - ATTACK_LOSS * home_att) * (1 + DEFENCE_LOSS * away_def)
        mu *= (1 - ATTACK_LOSS * away_att) * (1 + DEFENCE_LOSS * home_def)
        return poisson_matrix(lam, mu, self._base.rho)

    def explain(self, fixture):
        try:
            teams = dict(zip((fixture["home_team"], fixture["away_team"]), self._team_news(fixture)))
        except ValueError:
            return None
        parts = []
        for team, players in teams.items():
            att, dfn = _absences(players)
            out = sorted(
                (p for p in players if p["chance"] < 1),
                key=lambda p: (1 - p["chance"]) * p["minutes"],
                reverse=True,
            )
            if not out:
                parts.append(f"{team}: full squad")
                continue
            names = ", ".join(
                p["name"] if p["chance"] == 0 else f"{p['name']} {p['chance']:.0%}" for p in out[:4]
            )
            more = f" +{len(out) - 4}" if len(out) > 4 else ""
            parts.append(
                f"{team}: {names}{more} "
                f"(scores {-ATTACK_LOSS * att:+.0%}, concedes {DEFENCE_LOSS * dfn:+.0%})"
            )
        return "news: " + "; ".join(parts)
