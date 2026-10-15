"""Walk-forward backtest: replay past seasons as if betting on each match before it was played.

Matches are taken in blocks of up to REFIT_DAYS days (roughly one round).
Before each block every model is refitted on the matches played on earlier
days only, from the same season window that `predict` uses. So a model never
sees the result it is predicting.
"""
from datetime import date, timedelta

from . import config, db
from .models import MODELS

REFIT_DAYS = 3


def _blocks(matches):
    blocks = []
    for m in sorted(matches, key=lambda m: m["kickoff"]):
        day = date.fromisoformat(m["kickoff"][:10])
        if not blocks or day >= blocks[-1][0] + timedelta(days=REFIT_DAYS):
            blocks.append((day, []))
        blocks[-1][1].append(m)
    return blocks


def run_season(model_names, season, history):
    """Prediction rows for every finished match of `season`.

    history: finished fixtures covering at least `season` and the
    config.PREVIOUS_SEASONS before it.
    """
    window = [
        m for m in history if season - config.PREVIOUS_SEASONS <= m["season"] <= season
    ]
    models = [MODELS[name]() for name in model_names]
    rows = []
    for start, block in _blocks(m for m in window if m["season"] == season):
        train = [m for m in window if m["kickoff"][:10] < start.isoformat()]
        if len(train) < config.MIN_TRAINING_MATCHES:
            continue
        for model in models:
            model.fit(train)
            for fixture in block:
                try:
                    prediction = model.predict(fixture)
                except ValueError:
                    continue
                rows.append(db.prediction_row("backtest", model, fixture, prediction, start.isoformat()))
    return rows
