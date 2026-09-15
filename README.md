# match-predictor

This is a command-line football match predictor. It uses a Dixon-Coles
Poisson goal model. No single free API supplies current fixture data for
every league, so the tool gets data from two sources, split by league:

- football-data.org (free, 10 requests per minute) supplies data for
  Premier League, La Liga, Bundesliga, Champions League, and World Cup. It
  supplies both fixtures and historical results.
- football-data.org's free tier does not include Danish Superliga. For this
  league, the tool uses two other sources:
  - TheSportsDB (free, 30 requests per minute, community-maintained data)
    supplies upcoming fixtures.
  - football-data.co.uk (free, no key required) supplies historical results
    as CSV files.

  The two sources spell some team names differently. For example,
  TheSportsDB uses "Silkeborg IF", but football-data.co.uk uses
  "Silkeborg". The file `match_predictor/teamnames.py` normalizes team
  names before it matches them.

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
- `THESPORTSDB_KEY`: The default value is the shared public test key
  `123`. This key works, but all free users share its rate limit. To get a
  private rate limit for Danish Superliga data, register your own free key
  at https://www.thesportsdb.com/api.php.

The tool caches fixture data locally in a SQLite database
(`data/match_predictor.db`). This avoids repeated downloads on every run.

## Usage

```bash
# Download recent results to train the model.
# Repeat this command occasionally to refresh the data.
python -m match_predictor.cli fetch --league premier-league

# Show predictions for every match in the next round.
python -m match_predictor.cli predict --league premier-league

# List the data provider for each league.
python -m match_predictor.cli leagues
```

Supported league slugs: `premier-league`, `la-liga`, `bundesliga`,
`champions-league`, `world-cup`, `danish-superliga`.

## How it works

1. `fetch` downloads finished results for the last two seasons of a league.
   It stores the results in the local SQLite database.
2. `predict` finds the next round of fixtures from the provider. It fits a
   [Dixon-Coles](https://en.wikipedia.org/wiki/Score-based_ranking_(statistics))
   model on the stored results. The model gives each team an attack
   strength and a defence strength, and weights recent results more
   heavily than older results. For each fixture, the model simulates the
   range of possible scorelines. From this simulation, `predict` reports
   the win, draw, and loss percentages, and the most likely scores.
3. If a team has too little recent data, for example a newly promoted or
   relegated team, `predict` skips that fixture and prints a note. It does
   not guess the result.

## Notes

- Champions League and World Cup combine group stages with knockout
  stages. The model treats every fixture the same way, using goal-based
  team strengths. This method works reasonably well for group-stage
  matches. It does not account for the context of a two-legged knockout
  tie.
- football-data.org's free tier delays scores and schedules. It does not
  provide real-time data. This delay does not affect pre-match
  predictions. Do not use this tool for live scores.
- This tool is a baseline statistical model. It is not a betting tool.
  Treat the probabilities as a rough guide, not as a guarantee.
