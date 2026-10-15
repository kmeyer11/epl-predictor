"""The bookmakers' view, as a benchmark.

Converts the average pre-match odds (home/draw/away and over/under 2.5 goals)
into implied probabilities, then finds the Dixon-Coles score matrix that
matches them. Beating this over a season is hard; getting close is good.
"""
import numpy as np
from scipy.optimize import least_squares

from .base import MAX_GOALS, Model, poisson_matrix

_GOALS = np.arange(MAX_GOALS + 1)
_OVER_25 = np.add.outer(_GOALS, _GOALS) > 2


def _implied(odds):
    """Bookmaker odds -> probabilities, with the bookmaker's margin removed proportionally."""
    p = 1 / np.array(odds, dtype=float)
    return p / p.sum()


class Market(Model):
    name = "market"
    description = "The bookmakers' average pre-match odds. A benchmark; backtest only."
    benchmark = True

    def score_matrix(self, fixture):
        odds_1x2 = [fixture.get("odds_home"), fixture.get("odds_draw"), fixture.get("odds_away")]
        if not all(odds_1x2):
            raise ValueError("no bookmaker odds for this match")
        p_home, _, p_away = _implied(odds_1x2)
        over_under = [fixture.get("odds_over25"), fixture.get("odds_under25")]
        p_over = _implied(over_under)[0] if all(over_under) else None

        def residuals(params):
            lam, mu, rho = params
            m = poisson_matrix(lam, mu, rho)
            res = [np.tril(m, -1).sum() - p_home, np.triu(m, 1).sum() - p_away]
            if p_over is not None:
                res.append(m[_OVER_25].sum() - p_over)
            else:
                res.append(rho)  # no totals market: keep rho at 0
            return res

        fit = least_squares(
            residuals, x0=[1.5, 1.2, 0.0], bounds=([0.05, 0.05, -0.3], [6, 6, 0.3])
        )
        return poisson_matrix(*fit.x)
