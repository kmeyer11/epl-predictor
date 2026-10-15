import numpy as np

from .base import Model, poisson_matrix


class Baseline(Model):
    """Ignores who is playing: every match gets the league's average home and away goals.

    Any model that can't beat this has learned nothing about the teams.
    """

    name = "baseline"
    description = "Ignores the teams: every match gets the league-average goals. The floor to beat."
    benchmark = True

    def fit(self, matches):
        matches = list(matches)
        self.lam = float(np.mean([m["home_goals"] for m in matches]))
        self.mu = float(np.mean([m["away_goals"] for m in matches]))
        return self

    def score_matrix(self, fixture):
        return poisson_matrix(self.lam, self.mu)
