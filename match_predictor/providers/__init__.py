import click


class ProviderError(click.ClickException):
    pass


def _module(provider_name):
    if provider_name == "football_data":
        from . import football_data

        return football_data
    if provider_name == "thesportsdb":
        from . import thesportsdb

        return thesportsdb
    if provider_name == "football_data_couk":
        from . import football_data_couk

        return football_data_couk
    raise ProviderError(f"Unknown provider: {provider_name}")


def round_provider(league_cfg):
    """Returns (module, provider_cfg) for the league's live-fixtures source."""
    name, provider_cfg = league_cfg["round"]
    return _module(name), provider_cfg


def history_provider(league_cfg):
    """Returns (module, provider_cfg) for the league's historical-results source."""
    name, provider_cfg = league_cfg["history"]
    return _module(name), provider_cfg
