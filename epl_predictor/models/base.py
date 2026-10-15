import numpy as np
from scipy.stats import poisson

from .. import scoring

MAX_GOALS = 9


def dc_tau(x, y, lam, mu, rho):
    """Dixon-Coles low-score correction factor; works on scalars or numpy arrays."""
    return np.select(
        [(x == 0) & (y == 0), (x == 0) & (y == 1), (x == 1) & (y == 0), (x == 1) & (y == 1)],
        [1 - lam * mu * rho, 1 + lam * rho, 1 + mu * rho, np.full_like(lam * 1.0, 1 - rho)],
        default=1.0,
    )


def poisson_matrix(lam, mu, rho=0.0):
    """Score-probability matrix for independent Poisson goals, with optional Dixon-Coles rho."""
    goals = np.arange(MAX_GOALS + 1)
    matrix = np.outer(poisson.pmf(goals, lam), poisson.pmf(goals, mu))
    if rho:
        x, y = np.meshgrid([0, 1], [0, 1], indexing="ij")
        matrix[:2, :2] *= dc_tau(x, y, lam, mu, rho)
    return matrix / matrix.sum()


class Model:
    """A model learns from finished matches and gives a score-probability matrix per fixture.

    Subclasses set `name`, `version` and `description`, implement `score_matrix`,
    and usually `fit`. Fixtures and matches are the dicts stored in db.fixtures.

    Saved predictions are keyed by name and version. Bump `version` whenever a
    change alters the model's predictions, so its live record isn't mixed with
    bets the old code made. A variant with other settings is a new subclass with
    its own name, not a changed default.
    """

    name = None
    version = 1
    description = ""
    # Yardsticks (no-skill floor, bookmakers) rather than real attempts at predicting.
    benchmark = False

    def fit(self, matches):
        return self

    def score_matrix(self, fixture):
        """Rows = home goals, columns = away goals, sums to 1.
        Raise ValueError when the model can't predict this fixture."""
        raise NotImplementedError

    def predict(self, fixture):
        return scoring.summarize(self.score_matrix(fixture))


def weakest_mean(values, n=3):
    """Mean of the n lowest values: the starting strength for a team with no history.

    Teams without history are almost always newly promoted, and promoted teams
    usually play like the clubs at the bottom of the table.
    """
    return float(np.mean(sorted(values)[:n]))
