"""Map football-data.org and Fantasy Premier League team names to football-data.co.uk's spelling.

Results come from football-data.co.uk, upcoming fixtures from football-data.org
and team news from FPL, so names must match. co.uk's short names are canonical.
"""

_ALIASES = {
    "Brighton & Hove Albion": "Brighton",
    "Cardiff City": "Cardiff",
    "Coventry City": "Coventry",
    "Huddersfield Town": "Huddersfield",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Manchester City": "Man City",
    "Man Utd": "Man United",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Norwich City": "Norwich",
    "Nottingham Forest": "Nott'm Forest",
    "Queens Park Rangers": "QPR",
    "Stoke City": "Stoke",
    "Spurs": "Tottenham",
    "Swansea City": "Swansea",
    "Tottenham Hotspur": "Tottenham",
    "West Bromwich Albion": "West Brom",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}


def canonical(name):
    """'Manchester United FC' -> 'Man United', 'AFC Bournemouth' -> 'Bournemouth'."""
    name = name.strip()
    for suffix in (" AFC", " FC"):
        name = name.removesuffix(suffix)
    name = name.removeprefix("AFC ")
    return _ALIASES.get(name, name)
