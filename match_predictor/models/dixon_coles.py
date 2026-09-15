"""Dixon-Coles goal-based model for football match outcomes.

Reference: Dixon, M.J. and Coles, S.G. (1997), "Modelling Association Football
Scores and Inefficiencies in the Football Betting Market".

Each team gets an attack strength and a defence strength. Expected goals for a
fixture come from the two teams' strengths plus a home-advantage term, and a
low-score correlation correction (rho) fixes the standard bivariate-Poisson
model's tendency to underestimate 0-0/1-0/0-1/1-1 draws.
"""
from datetime import datetime, timezone

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from ..teamnames import normalize_team

MAX_GOALS = 9


def _tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


class DixonColes:
    def __init__(self, xi=0.0018, l2=1e-3):
        """xi: daily time-decay rate (higher = older results matter less).
        l2: ridge penalty on attack/defence params, keeps the fit stable
        with limited data and pins down the alpha/beta scale."""
        self.xi = xi
        self.l2 = l2
        self.teams = []
        self.alpha = {}
        self.beta = {}
        self.gamma = 0.0
        self.rho = 0.0
        self._fitted = False

    def fit(self, matches):
        """matches: iterable of dicts with home_team, away_team, home_goals,
        away_goals, kickoff (ISO date string)."""
        matches = list(matches)
        if len(matches) < 20:
            raise ValueError("Need at least ~20 finished matches to fit a model.")

        teams = sorted(
            {normalize_team(m["home_team"]) for m in matches}
            | {normalize_team(m["away_team"]) for m in matches}
        )
        self.teams = teams
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        most_recent = max(_parse_date(m["kickoff"]) for m in matches)
        weights = np.array(
            [np.exp(-self.xi * (most_recent - _parse_date(m["kickoff"])).days) for m in matches]
        )
        home_idx = np.array([idx[normalize_team(m["home_team"])] for m in matches])
        away_idx = np.array([idx[normalize_team(m["away_team"])] for m in matches])
        home_goals = np.array([m["home_goals"] for m in matches])
        away_goals = np.array([m["away_goals"] for m in matches])

        def unpack(params):
            alpha = params[:n]
            beta = params[n : 2 * n]
            gamma = params[2 * n]
            rho = params[2 * n + 1]
            return alpha, beta, gamma, rho

        def neg_log_lik(params):
            alpha, beta, gamma, rho = unpack(params)
            lam = np.exp(alpha[home_idx] + beta[away_idx] + gamma)
            mu = np.exp(alpha[away_idx] + beta[home_idx])

            ll = (
                home_goals * np.log(lam)
                - lam
                + away_goals * np.log(mu)
                - mu
            )
            tau_vals = np.array(
                [
                    _tau(hg, ag, lm, m, rho)
                    for hg, ag, lm, m in zip(home_goals, away_goals, lam, mu)
                ]
            )
            tau_vals = np.clip(tau_vals, 1e-10, None)
            ll = ll + np.log(tau_vals)

            penalty = self.l2 * (np.sum(alpha**2) + np.sum(beta**2))
            return -np.sum(weights * ll) + penalty

        x0 = np.zeros(2 * n + 2)
        bounds = [(-3, 3)] * n + [(-3, 3)] * n + [(-2, 2), (-0.9, 0.9)]
        result = minimize(neg_log_lik, x0, method="L-BFGS-B", bounds=bounds)
        alpha, beta, gamma, rho = unpack(result.x)

        self.alpha = dict(zip(teams, alpha))
        self.beta = dict(zip(teams, beta))
        self.gamma = float(gamma)
        self.rho = float(rho)
        self._fitted = True
        return self

    def expected_goals(self, home_team, away_team):
        if not self._fitted:
            raise RuntimeError("Call fit() before predicting.")
        home_key, away_key = normalize_team(home_team), normalize_team(away_team)
        if home_key not in self.alpha or away_key not in self.alpha:
            missing = home_team if home_key not in self.alpha else away_team
            raise ValueError(f"'{missing}' has no fitted data (not enough recent matches).")
        lam = np.exp(self.alpha[home_key] + self.beta[away_key] + self.gamma)
        mu = np.exp(self.alpha[away_key] + self.beta[home_key])
        return float(lam), float(mu)

    def score_matrix(self, home_team, away_team):
        lam, mu = self.expected_goals(home_team, away_team)
        goals = np.arange(0, MAX_GOALS + 1)
        home_probs = poisson.pmf(goals, lam)
        away_probs = poisson.pmf(goals, mu)
        matrix = np.outer(home_probs, away_probs)
        for x in range(2):
            for y in range(2):
                matrix[x, y] *= _tau(x, y, lam, mu, self.rho)
        matrix /= matrix.sum()
        return matrix

    def predict_match(self, home_team, away_team, top_n=3):
        matrix = self.score_matrix(home_team, away_team)
        lam, mu = self.expected_goals(home_team, away_team)
        home_win = float(np.tril(matrix, -1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, 1).sum())

        flat_idx = np.argsort(matrix, axis=None)[::-1][:top_n]
        top_scores = [
            {
                "score": f"{i}-{j}",
                "probability": float(matrix[i, j]),
            }
            for i, j in (np.unravel_index(k, matrix.shape) for k in flat_idx)
        ]

        return {
            "home_team": home_team,
            "away_team": away_team,
            "expected_home_goals": round(lam, 2),
            "expected_away_goals": round(mu, 2),
            "home_win_pct": round(home_win * 100, 1),
            "draw_pct": round(draw * 100, 1),
            "away_win_pct": round(away_win * 100, 1),
            "top_scores": top_scores,
        }


def _parse_date(iso_string):
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00")).astimezone(timezone.utc)
