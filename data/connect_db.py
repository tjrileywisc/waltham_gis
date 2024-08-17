from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
import json


def get_db() -> Engine:

    config = json.load(open("config.json"))

    username = config["username"]
    password = config["password"]

    url = f"postgresql://{username}:{password}@127.0.0.1:5432/walthamdata"

    con = create_engine(url)

    return con
