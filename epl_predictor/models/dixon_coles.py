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

from .base import Model, dc_tau, poisson_matrix


class DixonColes(Model):
    name = "dixon-coles"
    description = "Attack and defence strength per team, recent results weighted more."

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
            {m["home_team"] for m in matches} | {m["away_team"] for m in matches}
        )
        self.teams = teams
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        most_recent = max(_parse_date(m["kickoff"]) for m in matches)
        weights = np.array(
            [np.exp(-self.xi * (most_recent - _parse_date(m["kickoff"])).days) for m in matches]
        )
        home_idx = np.array([idx[m["home_team"]] for m in matches])
        away_idx = np.array([idx[m["away_team"]] for m in matches])
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
            tau_vals = np.clip(dc_tau(home_goals, away_goals, lam, mu, rho), 1e-10, None)
            ll = ll + np.log(tau_vals)

            penalty = self.l2 * (np.sum(alpha**2) + np.sum(beta**2))
            return -np.sum(weights * ll) + penalty

        # Start from the previous fit when there is one: the backtest refits
        # every few days on nearly the same data, so this saves most iterations.
        x0 = np.concatenate([
            [self.alpha.get(t, 0.0) for t in teams],
            [self.beta.get(t, 0.0) for t in teams],
            [self.gamma, self.rho],
        ])
        bounds = [(-3, 3)] * n + [(-3, 3)] * n + [(-2, 2), (-0.9, 0.9)]
        result = minimize(neg_log_lik, x0, method="L-BFGS-B", bounds=bounds)
        alpha, beta, gamma, rho = unpack(result.x)

        self.alpha = dict(zip(teams, alpha))
        self.beta = dict(zip(teams, beta))
        self.gamma = float(gamma)
        self.rho = float(rho)

        # Newly promoted teams have no history; give them the average attack
        # and defence of the three weakest teams in the data.
        weakest = sorted(teams, key=lambda t: self.alpha[t] - self.beta[t])[:3]
        self._newcomer = (
            float(np.mean([self.alpha[t] for t in weakest])),
            float(np.mean([self.beta[t] for t in weakest])),
        )
        self._fitted = True
        return self

    def _strength(self, team):
        if team in self.alpha:
            return self.alpha[team], self.beta[team]
        return self._newcomer

    def expected_goals(self, home_team, away_team):
        if not self._fitted:
            raise RuntimeError("Call fit() before predicting.")
        home_att, home_def = self._strength(home_team)
        away_att, away_def = self._strength(away_team)
        lam = np.exp(home_att + away_def + self.gamma)
        mu = np.exp(away_att + home_def)
        return float(lam), float(mu)

    def score_matrix(self, fixture):
        lam, mu = self.expected_goals(fixture["home_team"], fixture["away_team"])
        return poisson_matrix(lam, mu, self.rho)


def _parse_date(iso_string):
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00")).astimezone(timezone.utc)
