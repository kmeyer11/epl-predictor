"""Elo ratings turned into goal expectations.

Ratings update after every match (bigger wins move them more). Expected goals
come from two Poisson regressions of home and away goals on the rating gap,
fitted on the same matches, so the model can produce a full score matrix.
"""
import numpy as np
from scipy.optimize import minimize

from .base import Model, poisson_matrix, weakest_mean

START_RATING = 1500
LEAGUE_SIZE = 20
WARMUP_GAMES = 10


def _margin_multiplier(margin):
    # World Football Elo: a 3-0 says more about the teams than a 1-0.
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11 + margin) / 8


def _fit_log_linear(gap, goals):
    """Poisson regression goals ~ exp(a + b * gap); returns (a, b)."""

    def neg_log_lik(params):
        a, b = params
        log_rate = a + b * gap
        rate = np.exp(log_rate)
        nll = np.sum(rate - goals * log_rate)
        grad = np.array([np.sum(rate - goals), np.sum((rate - goals) * gap)])
        return nll, grad

    return minimize(neg_log_lik, np.zeros(2), jac=True, method="L-BFGS-B").x


class Elo(Model):
    name = "elo"
    description = "Elo ratings, turned into expected goals by a Poisson regression."

    def __init__(self, k=20, home_advantage=60):
        self.k = k
        self.home_advantage = home_advantage
        self.ratings = {}

    def _gap(self, home_rating, away_rating):
        return (home_rating + self.home_advantage - away_rating) / 400

    def _rating(self, team):
        if team in self.ratings:
            return self.ratings[team]
        # Teams with no history are almost always promoted.
        if len(self.ratings) < LEAGUE_SIZE:
            return START_RATING
        return weakest_mean(self.ratings.values())

    def fit(self, matches):
        self.ratings = {}
        games = {}
        gaps, home_goals, away_goals = [], [], []
        for m in sorted(matches, key=lambda m: m["kickoff"]):
            home, away = m["home_team"], m["away_team"]
            for team in (home, away):
                self.ratings[team] = self._rating(team)
            gap = self._gap(self.ratings[home], self.ratings[away])

            # Ratings start out flat, so skip the warm-up games when learning
            # how a rating gap translates into goals.
            if games.get(home, 0) >= WARMUP_GAMES and games.get(away, 0) >= WARMUP_GAMES:
                gaps.append(gap)
                home_goals.append(m["home_goals"])
                away_goals.append(m["away_goals"])

            expected = 1 / (1 + 10 ** -gap)
            hg, ag = m["home_goals"], m["away_goals"]
            result = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
            delta = self.k * _margin_multiplier(abs(hg - ag)) * (result - expected)
            self.ratings[home] += delta
            self.ratings[away] -= delta
            games[home] = games.get(home, 0) + 1
            games[away] = games.get(away, 0) + 1

        if len(gaps) < 20:
            raise ValueError("Need more matches to relate Elo ratings to goals.")
        gaps = np.array(gaps)
        self.home_coef = _fit_log_linear(gaps, np.array(home_goals))
        self.away_coef = _fit_log_linear(gaps, np.array(away_goals))
        return self

    def score_matrix(self, fixture):
        gap = self._gap(self._rating(fixture["home_team"]), self._rating(fixture["away_team"]))
        lam = np.exp(self.home_coef[0] + self.home_coef[1] * gap)
        mu = np.exp(self.away_coef[0] + self.away_coef[1] * gap)
        return poisson_matrix(lam, mu)
