
import csv
from pathlib import Path

from .zone import Zone

def read_zoning_csv():
    out = []
    
    csv_path = Path(__file__).parent.parent / Path("data/zoning_rules_table.csv")

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(row)

    return out

def make_zones(zone_features):
    zoning = dict()
    for zone_rules in zone_features:

        far = zone_rules["FAR by right"]
        if far != "":
            far = float(far)
        else:
            far = None

        max_lot_coverage = zone_rules["max lot coverage"]
        if max_lot_coverage != "":
            max_lot_coverage = float(max_lot_coverage)
        else:
            max_lot_coverage = None
        
        min_open_space = zone_rules["min open space"]
        if min_open_space != "":
            min_open_space = float(min_open_space)
        else:
            min_open_space = None
            
        lot_area = zone_rules["lot area"]
        if lot_area != "":
            lot_area = int(lot_area)
        else:
            lot_area = None
        
        max_dua = zone_rules["max DUA"]
        if max_dua != "":
            max_dua = int(max_dua)
        else:
            max_dua = None
        
        z = Zone(
            zone_rules["District"],
            int(zone_rules["front setback"]),
            int(zone_rules["side setback"]),
            int(zone_rules["rear setback"]),
            int(zone_rules["height"]),
            float(zone_rules["stories"]),
            far,
            max_lot_coverage,
            min_open_space,
            lot_area,
            max_dua,
            int(zone_rules["lot frontage"])
        )

        zoning[zone_rules["District"]] = z

    return zoning