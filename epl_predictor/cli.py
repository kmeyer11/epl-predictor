import time
from datetime import date, datetime, timezone

import click

from . import config, db, export, football_data, football_data_couk, scoring
from .backtest import run_season
from .models import MODELS
from .teams import canonical

MODEL_OPTION = click.option(
    "--model",
    "model_names",
    multiple=True,
    type=click.Choice(list(MODELS)),
    help="Only these models (repeatable). Default: all.",
)
SEASONS_HELP = "Season start years: 2024,2025 or 2021-2025."


def _parse_seasons(value):
    seasons = []
    for part in value.split(","):
        if "-" in part:
            first, last = part.split("-")
            seasons.extend(range(int(first), int(last) + 1))
        else:
            seasons.append(int(part))
    return seasons


def _current_season():
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def _season_label(season):
    return f"{season % 100:02d}/{(season + 1) % 100:02d}"


@click.group()
def cli():
    """Free, ML(ish)-powered Premier League match predictor."""


@cli.command()
@click.option(
    "--seasons",
    default=None,
    help=f"{SEASONS_HELP} Defaults to {config.FIRST_SEASON} up to the current season.",
)
def fetch(seasons):
    """Download finished Premier League results and odds from football-data.co.uk."""
    db.init_db()
    if seasons:
        season_list = _parse_seasons(seasons)
    else:
        season_list = range(config.FIRST_SEASON, _current_season() + 1)

    total = 0
    for season in season_list:
        fixtures = football_data_couk.get_season_results(season)
        if fixtures:
            db.upsert_fixtures(fixtures)
        click.echo(f"  {_season_label(season)}: {len(fixtures)} matches")
        total += len(fixtures)
    click.echo(f"Stored/updated {total} finished matches.")


@cli.command()
@MODEL_OPTION
def predict(model_names):
    """Show each model's bet for the upcoming round.

    Bets for matches that haven't kicked off are saved, so `compare --live`
    can score them once the results are in. Run `fetch` first.
    """
    db.init_db()

    round_label, season = football_data.get_current_round()
    click.echo(f"Upcoming round: {round_label} ({season}/{season + 1} season)\n")

    round_fixtures = football_data.get_round_fixtures(round_label)
    if not round_fixtures:
        click.echo("No fixtures found for that round yet - try again closer to matchday.")
        return

    history = db.get_finished_fixtures(range(season - config.PREVIOUS_SEASONS, season + 1))
    if len(history) < config.MIN_TRAINING_MATCHES:
        click.echo(
            f"Only {len(history)} finished matches found locally. "
            "Run: python -m epl_predictor.cli fetch"
        )
        return

    models = {name: cls().fit(history) for name, cls in MODELS.items()}
    shown = model_names or list(MODELS)
    known_teams = {m["home_team"] for m in history} | {m["away_team"] for m in history}
    now = datetime.now(timezone.utc)
    rows, skipped = [], {}

    for f in round_fixtures:
        f = {**f, "home_team": canonical(f["home_team"]), "away_team": canonical(f["away_team"])}
        kickoff = datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
        click.echo(f"{f['home_team']} vs {f['away_team']}  ({kickoff:%a %d %b %H:%M} UTC)")
        if kickoff <= now:
            click.echo("  already kicked off\n")
            continue
        for team in (f["home_team"], f["away_team"]):
            if team not in known_teams:
                click.echo(f"  note: no stored results for {team}, rated like a promoted team")

        for name, model in models.items():
            try:
                pred = model.predict(f)
            except ValueError as e:
                skipped.setdefault(name, str(e))
                continue
            rows.append(db.prediction_row("live", model, f, pred, now.isoformat()))
            if name in shown:
                click.echo(
                    f"  {name:<12} xG {pred['xg_home']:.1f}-{pred['xg_away']:.1f}  "
                    f"H {pred['p_home']*100:3.0f}%  D {pred['p_draw']*100:3.0f}%  "
                    f"A {pred['p_away']*100:3.0f}%   "
                    f"bet {pred['pick'][0]}-{pred['pick'][1]} ({pred['pick_points']:.2f} exp. pts)"
                )
        click.echo()

    db.upsert_predictions(rows)
    for name, reason in skipped.items():
        if name in shown:
            click.echo(f"{name}: skipped ({reason}).")
    click.echo(f"Saved {len(rows)} bets for live tracking (see: compare --live).")


@cli.command()
@click.option(
    "--seasons",
    default=None,
    help=f"{SEASONS_HELP} Default: every stored season with "
    f"{config.PREVIOUS_SEASONS} earlier seasons to train on.",
)
@MODEL_OPTION
def backtest(seasons, model_names):
    """Replay past seasons: each model bets on every match using only earlier results."""
    db.init_db()
    stored = db.get_seasons()
    if not stored:
        click.echo("No results stored. Run: python -m epl_predictor.cli fetch")
        return
    season_list = _parse_seasons(seasons) if seasons else stored[config.PREVIOUS_SEASONS:]
    model_names = list(model_names or MODELS)
    history = db.get_finished_fixtures(stored)

    for season in season_list:
        started = time.monotonic()
        rows = run_season(model_names, season, history)
        db.replace_backtest_predictions(_current_versions(model_names), [season], rows)
        matches = len({(r["home_team"], r["away_team"]) for r in rows})
        click.echo(
            f"  {_season_label(season)}: {matches} matches "
            f"({time.monotonic() - started:.0f}s)"
        )
    click.echo()
    _print_leaderboard("backtest", model_names, season_list, "pick", False, False)


@cli.command()
@click.option("--live", is_flag=True, help="Score the bets saved by `predict` instead of the backtest.")
@click.option("--seasons", default=None, help=SEASONS_HELP)
@MODEL_OPTION
@click.option(
    "--pick",
    type=click.Choice(["best", "likeliest"]),
    default="best",
    help="Score the bet with the most expected points (default) or the likeliest score.",
)
@click.option("--by-season", is_flag=True, help="Also show points per match for each season.")
@click.option(
    "--all-versions",
    is_flag=True,
    help="Include saved predictions from older model versions and removed models.",
)
def compare(live, seasons, model_names, pick, by_season, all_versions):
    """Leaderboard of models by average plshowet points per match."""
    db.init_db()
    kind = "live" if live else "backtest"
    season_list = _parse_seasons(seasons) if seasons else None
    column = "pick" if pick == "best" else "top"
    _print_leaderboard(kind, model_names, season_list, column, by_season, all_versions)


@cli.command()
def models():
    """List the registered models."""
    for cls in MODELS.values():
        click.echo(f"{cls.name:<12} v{cls.version}  {cls.description}")


@cli.command("export")
def export_site():
    """Write data.js for the comparison website (to SITE_DIR from .env)."""
    db.init_db()
    path = config.SITE_DIR / "data.js"
    data = export.write(path)
    click.echo(
        f"Wrote {path}: {data['backtest']['matches']} backtest matches, "
        f"{data['live']['matches']} scored live bets, {len(data['upcoming'])} upcoming matches."
    )


def _current_versions(model_names=None):
    return [(name, MODELS[name].version) for name in (model_names or MODELS)]


def _print_leaderboard(kind, model_names, seasons, pick, by_season, all_versions):
    if all_versions:
        rows = db.get_scored_predictions(kind, None, seasons)
        if model_names:
            rows = [r for r in rows if r["model"] in model_names]
        for r in rows:
            r["model"] = f"{r['model']} v{r['model_version']}"
    else:
        rows = db.get_scored_predictions(kind, _current_versions(model_names), seasons)
    stats, n = scoring.leaderboard(rows, pick)
    if not n:
        hint = "predict" if kind == "live" else "backtest"
        click.echo(f"No scored {kind} predictions yet. Run: python -m epl_predictor.cli {hint}")
        return

    played = sorted({r["season"] for r in rows})
    span = (
        f"seasons {_season_label(played[0])} to {_season_label(played[-1])}"
        if len(played) > 1
        else f"season {_season_label(played[0])}"
    )
    click.echo(f"{kind.capitalize()}: {n} matches, {span}. Every model is scored on the same matches.\n")
    w = max(12, *(len(s["model"]) for s in stats))
    click.echo(
        f"  #  {'model':<{w}} {'pts/match':>9}  {'vs #1':>15}  {'pts/season':>10}  "
        f"{'exact':>6}  {'outcome':>7}  {'margin':>6}  {'RPS':>6}"
    )
    for i, s in enumerate(stats, 1):
        vs_best = "-" if i == 1 else f"{s['diff_to_best']:+.3f} ± {s['diff_ci95']:.3f}"
        click.echo(
            f"  {i}  {s['model']:<{w}} {s['pts_per_match']:>9.3f}  {vs_best:>15}  "
            f"{s['pts_per_match'] * 380:>10.0f}  {s['exact_pct']:>5.1f}%  "
            f"{s['outcome_pct']:>6.1f}%  {s['margin_pct']:>5.1f}%  {s['rps']:>6.4f}"
        )
    click.echo(
        "\n  pts/season = pts/match x 380. exact/outcome/margin = % of bets with that right.\n"
        "  vs #1 = gap to the leader in pts/match, with a 95% interval: if it includes 0,\n"
        "  the gap could be luck. RPS rates the win/draw/loss probabilities (lower is better)."
    )

    if by_season:
        order = [s["model"] for s in stats]
        click.echo(f"\n  {'pts/match':<{w}} " + " ".join(f"{_season_label(y):>6}" for y in played))
        per_season = {
            y: {s["model"]: s["pts_per_match"] for s in scoring.leaderboard(
                [r for r in rows if r["season"] == y], pick)[0]}
            for y in played
        }
        for model in order:
            cells = (per_season[y].get(model) for y in played)
            click.echo(
                f"  {model:<{w}} "
                + " ".join(f"{c:>6.2f}" if c is not None else f"{'-':>6}" for c in cells)
            )


if __name__ == "__main__":
    cli()
