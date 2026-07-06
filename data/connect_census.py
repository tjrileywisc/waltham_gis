
import json
from pathlib import Path

def get_census_key() -> str:
    ROOT = Path(__file__).resolve().parent.parent
    CONFIG = ROOT / "config.json"
    
    config = json.load(open(CONFIG))
    key = config["census"]["api_key"]
    
    return key