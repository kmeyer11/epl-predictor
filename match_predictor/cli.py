import click

from . import config, db
from .models.dixon_coles import DixonColes
from .providers import history_provider, round_provider


@click.group()
def cli():
    """Free, ML(ish)-powered football match predictor."""


@cli.command()
def leagues():
    """List the configured leagues and which free provider serves each one."""
    for slug, cfg in sorted(config.LEAGUES.items()):
        round_name, round_cfg = cfg["round"]
        hist_name, hist_cfg = cfg["history"]
        click.echo(f"{slug:<18} fixtures={round_name} {round_cfg}  history={hist_name} {hist_cfg}")


@cli.command()
@click.option("--league", "league_slug", required=True, type=click.Choice(sorted(config.LEAGUES)))
@click.option(
    "--seasons",
    default=None,
    help="Comma-separated season start years, e.g. 2024,2025. Defaults to current + previous.",
)
def fetch(league_slug, seasons):
    """Download finished fixtures for a league and store them locally."""
    db.init_db()
    league_cfg = config.LEAGUES[league_slug]
    round_mod, round_cfg = round_provider(league_cfg)
    hist_mod, hist_cfg = history_provider(league_cfg)

    if seasons:
        season_list = [int(s) for s in seasons.split(",")]
    else:
        _, current_season = round_mod.get_current_round(league_slug, round_cfg)
        season_list = [current_season - 1, current_season]

    fixtures = hist_mod.get_historical_fixtures(league_slug, hist_cfg, season_list)
    if not fixtures:
        click.echo(f"No finished fixtures returned for {league_slug} / seasons {season_list}.")
        return
    count = db.upsert_fixtures(fixtures)
    click.echo(f"Stored/updated {count} finished fixtures for {league_slug} (seasons {season_list}).")


@cli.command()
@click.option("--league", "league_slug", required=True, type=click.Choice(sorted(config.LEAGUES)))
def predict(league_slug):
    """Predict every fixture in the upcoming round for a league.

    Run `fetch --league <slug>` first so there's historical data to train on.
    """
    db.init_db()
    league_cfg = config.LEAGUES[league_slug]
    round_mod, round_cfg = round_provider(league_cfg)

    round_label, season = round_mod.get_current_round(league_slug, round_cfg)
    click.echo(f"Upcoming round: {round_label} ({season}/{season + 1} season)\n")

    round_fixtures = round_mod.get_round_fixtures(league_slug, round_cfg, season, round_label)
    if not round_fixtures:
        click.echo("No fixtures found for that round yet - try again closer to matchday.")
        return

    history = db.get_finished_fixtures(league_slug, [season - 1, season])
    if len(history) < 20:
        click.echo(
            f"Only {len(history)} finished matches found locally for {league_slug}. "
            f"Run: python -m match_predictor.cli fetch --league {league_slug}"
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
