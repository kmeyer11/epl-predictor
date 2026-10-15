import click

from . import db, football_data
from .models.dixon_coles import DixonColes


@click.group()
def cli():
    """Free, ML(ish)-powered Premier League match predictor."""


@cli.command()
@click.option(
    "--seasons",
    default=None,
    help="Comma-separated season start years, e.g. 2024,2025. Defaults to current + previous.",
)
def fetch(seasons):
    """Download finished Premier League fixtures and store them locally."""
    db.init_db()

    if seasons:
        season_list = [int(s) for s in seasons.split(",")]
    else:
        _, current_season = football_data.get_current_round()
        season_list = [current_season - 1, current_season]

    fixtures = football_data.get_historical_fixtures(season_list)
    if not fixtures:
        click.echo(f"No finished fixtures returned for seasons {season_list}.")
        return
    count = db.upsert_fixtures(fixtures)
    click.echo(f"Stored/updated {count} finished fixtures (seasons {season_list}).")


@cli.command()
def predict():
    """Predict every fixture in the upcoming Premier League round.

    Run `fetch` first so there's historical data to train on.
    """
    db.init_db()

    round_label, season = football_data.get_current_round()
    click.echo(f"Upcoming round: {round_label} ({season}/{season + 1} season)\n")

    round_fixtures = football_data.get_round_fixtures(round_label)
    if not round_fixtures:
        click.echo("No fixtures found for that round yet - try again closer to matchday.")
        return

    history = db.get_finished_fixtures([season - 1, season])
    if len(history) < 20:
        click.echo(
            f"Only {len(history)} finished matches found locally. "
            "Run: python -m epl_predictor.cli fetch"
        )
        return

    model = DixonColes().fit(history)

    for f in round_fixtures:
        home, away = f["home_team"], f["away_team"]
        try:
            pred = model.predict_match(home, away)
        except ValueError as e:
            click.echo(f"{home} vs {away}: skipped ({e})")
            continue

        top = ", ".join(f"{s['score']} ({s['probability']*100:.0f}%)" for s in pred["top_scores"])
        click.echo(
            f"{home} vs {away}\n"
            f"  xG: {pred['expected_home_goals']} - {pred['expected_away_goals']}\n"
            f"  Home {pred['home_win_pct']}% | Draw {pred['draw_pct']}% | Away {pred['away_win_pct']}%\n"
            f"  Likeliest scores: {top}\n"
        )


if __name__ == "__main__":
    cli()
