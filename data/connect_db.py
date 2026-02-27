from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
import json

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"

def get_db() -> Engine:

    config = json.load(open(CONFIG))

    username = config["username"]
    password = config["password"]

    url = f"postgresql+psycopg://{username}:{password}@127.0.0.1:5432/walthamdata"

    con = create_engine(url)

    return con
