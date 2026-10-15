# epl-predictor

This is a command-line Premier League match predictor. It uses a
Dixon-Coles Poisson goal model. football-data.org (free, 10 requests per
minute) supplies both the upcoming fixtures and the historical results.

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

The tool caches fixture data locally in a SQLite database
(`data/epl_predictor.db`). This avoids repeated downloads on every run.

## Usage

```bash
# Download recent results to train the model.
# Repeat this command occasionally to refresh the data.
python -m epl_predictor.cli fetch

# Show predictions for every match in the next round.
python -m epl_predictor.cli predict
```

## How it works

1. `fetch` downloads finished Premier League results for the last two
   seasons. It stores the results in the local SQLite database.
2. `predict` finds the next round of fixtures from football-data.org. It fits a
   [Dixon-Coles](https://en.wikipedia.org/wiki/Score-based_ranking_(statistics))
   model on the stored results. The model gives each team an attack
   strength and a defence strength, and weights recent results more
   heavily than older results. For each fixture, the model simulates the
   range of possible scorelines. From this simulation, `predict` reports
   the win, draw, and loss percentages, and the most likely scores.
3. If a team has too little recent data, for example a newly promoted
   team, `predict` skips that fixture and prints a note. It does not guess
   the result.

## Notes

- football-data.org's free tier delays scores and schedules. It does not
  provide real-time data. This delay does not affect pre-match
  predictions. Do not use this tool for live scores.
- This tool is a baseline statistical model. It is not a betting tool.
  Treat the probabilities as a rough guide, not as a guarantee.
