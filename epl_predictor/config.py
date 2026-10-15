import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "epl_predictor.db"

FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

FOOTBALL_DATA_COUK_BASE_URL = "https://www.football-data.co.uk/mmz4281"

# football-data.co.uk has odds for every season from here on.
FIRST_SEASON = 2014

# Models train on the current season plus this many previous ones.
PREVIOUS_SEASONS = 2
MIN_TRAINING_MATCHES = 20
