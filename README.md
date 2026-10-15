# epl-predictor

This is a command-line Premier League match predictor. It runs several
models side by side and ranks them by the points they would score in the
plshowet prediction game.

- football-data.co.uk supplies past results and bookmaker odds. It is free
  and needs no key.
- football-data.org supplies the upcoming fixtures. It is free and allows
  10 requests per minute.
- The Fantasy Premier League API supplies team news (injuries,
  suspensions, doubts) for the `gossip` model. It is free and needs no key.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

- `FOOTBALL_DATA_KEY`: Register for a free key at
  https://www.football-data.org/client/register. Registration is immediate
  and needs only an email address.
- `SITE_DIR` (optional): the folder `export` writes the website's
  `data.js` to. Defaults to `site/`.
- `EPL_DATA_DIR` (optional): the folder for the database. Defaults to
  `data/`.

The tool caches results and predictions locally in a SQLite database
(`data/epl_predictor.db`).

## Usage

```bash
# Download results and odds from 2014/15 to today. Rerun after each round.
python -m epl_predictor.cli fetch

# Show every model's bet for the next round, and save the bets.
python -m epl_predictor.cli predict

# Replay past seasons and rank the models (takes about 40 seconds).
python -m epl_predictor.cli backtest

# List the models.
python -m epl_predictor.cli models

# Update the comparison website and open it.
python -m epl_predictor.cli export --open

# Run fetch, predict, backtest and export in turn (for a daily schedule).
python -m epl_predictor.cli daily

# Show the leaderboard again, with options.
python -m epl_predictor.cli compare --by-season
python -m epl_predictor.cli compare --seasons 2023-2025 --model elo --model dixon-coles
python -m epl_predictor.cli compare --pick likeliest
python -m epl_predictor.cli compare --live
python -m epl_predictor.cli compare --live --all-versions
```

## Scoring

The leaderboard uses the plshowet rules:

| Bet vs. result | Points |
|---|---|
| Exact score | 9 (5 + 3 + 1) |
| Right outcome and goal difference, e.g. 3-1 vs 2-0, or 1-1 vs 2-2 | 4 (3 + 1) |
| Right outcome only, e.g. 3-1 vs 3-0 | 3 |
| Wrong outcome | 0 |

Every model gives a probability for each possible score. The bet is the
score with the highest expected points. This is not always the likeliest
score: in a close match, 1-0 often beats 1-1, because a home win also
collects the outcome points from 2-0, 2-1, and so on. Use
`compare --pick likeliest` to see the difference.

## Models

| Name | Idea |
|---|---|
| `baseline` | Ignores the teams. Every match gets the league-average goals. A model must beat this one. |
| `dixon-coles` | Attack and defence strength per team, with recent results weighted more. |
| `elo` | Elo ratings, converted to expected goals by a Poisson regression. |
| `market` | The bookmakers' average pre-match odds, converted to a score matrix. This is a benchmark. It works in the backtest only, because upcoming matches have no odds yet. |
| `gossip` | `dixon-coles`, adjusted for the latest team news. It works live only, because there is no archive of past team news. |

Every model trains on the current season and the two before it. A team
with no results in that window, usually a promoted team, starts with the
average strength of the three weakest teams.

`gossip` reads each player's chance of playing from the FPL API. A team
without players who make a big share of its expected goals and assists
scores less. A team without its keeper or regular defenders concedes more.
`predict` prints the absences behind each `gossip` bet. How much an
absence costs is a guess (`ATTACK_LOSS`, `DEFENCE_LOSS` in
`models/gossip.py`), because there is no past news to fit it on. Compare it
with `compare --live` after a few rounds.

`baseline` and `market` are marked as benchmarks: they are yardsticks,
not real attempts at predicting.

To add a model:

1. Create a module in `epl_predictor/models/` with a `Model` subclass
   (see `base.py`). Set `name`, `description`, and `version = 1`.
   Implement `fit` and `score_matrix`.
2. Append the class to `_ALL` in `epl_predictor/models/__init__.py`.
3. Run `backtest --model <name>`, then `compare`.

Each model's predictions are saved under its name and version. If you
change a model in a way that changes its predictions, bump its
`version`. Its new live bets are then tracked apart from the old ones,
and `compare --all-versions` shows both. To try different settings,
make a subclass with a new name instead of changing the defaults.

## How the comparison works

- `backtest` replays each past season in blocks of a few days. Before each
  block, every model is refitted on earlier results only. It then bets on
  the matches in that block. No model sees the result it is predicting.
- `predict` saves each model's bet before kickoff. After `fetch` loads the
  results, `compare --live` scores those bets.
- The leaderboard compares every model on the same matches.
- The `vs #1` column shows each model's gap to the leader, with a 95%
  interval. If the interval includes 0, the gap could be luck. Even 10
  seasons of results cannot separate models that are close.

## Website

`site/` is a static dashboard that compares the models: the leaderboard
(backtest and live), each season's race against the bookmakers, points
per season, and every model's bet for the next matches. It is plain HTML
and JavaScript, with no build step or server.

`export` writes the data it shows to `site/data.js`. Rerun it after
`fetch`, `backtest`, or `predict`, then reload the page.

```bash
python -m epl_predictor.cli export --open   # or open site/index.html
```

## Docker

The image runs `daily` on start and then every day at 06:00 UTC, and
serves `site/` on port 8010. The database lives in the `/data` volume.

```bash
docker build -t epl-predictor .
docker run -d --env-file .env -p 127.0.0.1:8010:8010 -v epl-data:/data epl-predictor
```

Set `REFRESH_AT` (UTC, `HH:MM`) to change the refresh time. The homelab
deploys it from `homelab/services/epl-predictor/`.

## Notes

- football-data.org's free tier delays scores and schedules. It does not
  provide real-time data. This delay does not affect pre-match
  predictions. Do not use this tool for live scores.
- This tool is not a betting tool. Treat the probabilities as a rough
  guide, not as a guarantee.
