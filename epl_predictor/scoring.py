"""plshowet points, bet picking, and probability metrics.

plshowet rules: +3 for the right outcome (home win / draw / away win), +1 more
for the right goal difference, +5 more for the exact score. So an exact score
is 9 points, right outcome and margin 4, right outcome only 3, otherwise 0.
"""
import numpy as np

MAX_PICK_GOALS = 5


def points(pick, actual):
    pick_diff = pick[0] - pick[1]
    actual_diff = actual[0] - actual[1]
    if np.sign(pick_diff) != np.sign(actual_diff):
        return 0
    if pick_diff != actual_diff:
        return 3
    if tuple(pick) != tuple(actual):
        return 4
    return 9


_PICKS = [(h, a) for h in range(MAX_PICK_GOALS + 1) for a in range(MAX_PICK_GOALS + 1)]
_points_tables = {}


def _points_table(size):
    """Points for every (pick, actual score) pair; rows follow _PICKS, columns a flattened size x size matrix."""
    if size not in _points_tables:
        _points_tables[size] = np.array(
            [[points(p, (h, a)) for h in range(size) for a in range(size)] for p in _PICKS]
        )
    return _points_tables[size]


def summarize(matrix):
    """Turn a score-probability matrix (rows = home goals, cols = away goals) into a prediction.

    The bet (`pick`) is the score with the highest expected plshowet points,
    which is not always the likeliest score (`top`): in a close match 1-0 often
    beats 1-1, because a home win also collects the outcome points from 2-0, 2-1, ...
    """
    expected = _points_table(matrix.shape[0]) @ matrix.ravel()
    best = int(np.argmax(expected))
    top = np.unravel_index(int(np.argmax(matrix)), matrix.shape)
    goals = np.arange(matrix.shape[0])
    return {
        "p_home": float(np.tril(matrix, -1).sum()),
        "p_draw": float(np.trace(matrix)),
        "p_away": float(np.triu(matrix, 1).sum()),
        "xg_home": float(matrix.sum(axis=1) @ goals),
        "xg_away": float(matrix.sum(axis=0) @ goals),
        "pick": _PICKS[best],
        "pick_points": float(expected[best]),
        "top": (int(top[0]), int(top[1])),
    }


def rps(p_home, p_draw, p_away, home_goals, away_goals):
    """Ranked probability score for the ordered outcomes home/draw/away. Lower is better."""
    outcome = (
        (1, 0, 0) if home_goals > away_goals
        else (0, 1, 0) if home_goals == away_goals
        else (0, 0, 1)
    )
    cum_p = np.cumsum([p_home, p_draw, p_away])[:2]
    cum_o = np.cumsum(outcome)[:2]
    return float(0.5 * np.sum((cum_p - cum_o) ** 2))


def leaderboard(rows, pick="pick"):
    """Score stored predictions against results, best model first.

    rows: prediction rows joined with the actual result (see db.get_scored_predictions).
    pick: "pick" (max expected points) or "top" (likeliest score).
    Only matches that every model predicted are counted, so all models face the same games.
    """
    by_model = {}
    for r in rows:
        by_model.setdefault(r["model"], {})[(r["season"], r["home_team"], r["away_team"])] = r
    if not by_model:
        return [], 0
    common = sorted(set.intersection(*(set(preds) for preds in by_model.values())))

    stats = []
    for model, preds in by_model.items():
        pts, exact, outcome, margin, rps_vals = [], 0, 0, 0, []
        for key in common:
            r = preds[key]
            actual = (r["home_goals"], r["away_goals"])
            p = points((r[f"{pick}_home"], r[f"{pick}_away"]), actual)
            pts.append(p)
            exact += p == 9
            outcome += p >= 3
            margin += p >= 4
            rps_vals.append(rps(r["p_home"], r["p_draw"], r["p_away"], *actual))
        n = len(common)
        stats.append({
            "model": model,
            "points": np.array(pts, dtype=float),
            "pts_per_match": float(np.mean(pts)) if n else 0.0,
            "exact_pct": 100 * exact / n if n else 0.0,
            "outcome_pct": 100 * outcome / n if n else 0.0,
            "margin_pct": 100 * margin / n if n else 0.0,
            "rps": float(np.mean(rps_vals)) if n else 0.0,
        })
    stats.sort(key=lambda s: s["pts_per_match"], reverse=True)

    # Paired difference to the leader: both models played the same matches, so
    # this is far less noisy than comparing two separate averages.
    best = stats[0]["points"]
    for s in stats:
        diff = s["points"] - best
        s["diff_to_best"] = float(diff.mean()) if len(diff) else 0.0
        s["diff_ci95"] = float(1.96 * diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 else 0.0
    return stats, len(common)
