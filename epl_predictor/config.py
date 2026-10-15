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
