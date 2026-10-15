"""Model registry.

To add a model: create a module here with a `Model` subclass (see base.py),
then append it to `_ALL`. Order is display order and the website gives each
model a colour by position, so append rather than insert.
"""
from .baseline import Baseline
from .dixon_coles import DixonColes
from .elo import Elo
from .gossip import Gossip
from .market import Market

_ALL = (Baseline, DixonColes, Elo, Market, Gossip)

MODELS = {cls.name: cls for cls in _ALL}
