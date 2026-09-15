import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "match_predictor.db"

FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

# "3" is TheSportsDB's shared public test key (works, but rate-shared with
# everyone using it). Register a free key at thesportsdb.com/api.php and set
# THESPORTSDB_KEY in .env for more reliable access.
THESPORTSDB_KEY = os.environ.get("THESPORTSDB_KEY", "123")
THESPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"

_FD = "football_data"
_TSDB = "thesportsdb"
_FDCOUK = "football_data_couk"

# Each league lists which provider serves its *upcoming round* (live
# fixtures) and which serves its *historical results* (training data) -
# usually the same provider, but the Danish Superliga needs two: it isn't in
# football-data.org's free tier, and TheSportsDB's free tier caps historical
# season lookups too low to train on, so results come from football-data.co.uk
# instead while fixtures still come from TheSportsDB.
LEAGUES = {
    "premier-league": {
        "round": (_FD, {"code": "PL"}),
        "history": (_FD, {"code": "PL"}),
    },
    "la-liga": {
        "round": (_FD, {"code": "PD"}),
        "history": (_FD, {"code": "PD"}),
    },
    "bundesliga": {
        "round": (_FD, {"code": "BL1"}),
        "history": (_FD, {"code": "BL1"}),
    },
    "champions-league": {
        "round": (_FD, {"code": "CL"}),
        "history": (_FD, {"code": "CL"}),
    },
    "world-cup": {
        "round": (_FD, {"code": "WC"}),
        "history": (_FD, {"code": "WC"}),
    },
    "danish-superliga": {
        "round": (_TSDB, {"league_id": "4340"}),
        "history": (_FDCOUK, {"country_code": "DNK"}),
    },
}
