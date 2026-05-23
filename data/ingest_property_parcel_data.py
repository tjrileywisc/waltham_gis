"""
MassGIS doesn't make historic tax parcel data available through their API,
they only have a really big zip that they put out, which contains ALL of the
data for the whole state that they have.

This script is useful for uploading data from that folder into the PostGIS db.

This script is really simple at the moment, it assumes you are passing the path
to the unzipped data as an argument. The user is responsible for deleting the folders
for community data they don't want.
"""

import argparse
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon
from sqlalchemy import text
from sqlalchemy.sql import quoted_name

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.connect_db import get_db

DIR_RE = re.compile(r"^L3_SHP_(M\d+)_\w+_(CY\d+_FY\d+)$")


def existing_tables(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).fetchall()
    return {r[0] for r in rows}


def promote_to_multi(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Promote any Polygon geometries to MultiPolygon for consistent column typing."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: MultiPolygon([g]) if g is not None and g.geom_type == "Polygon" else g
    )
    return gdf


def load_assess(src: Path, table: str, engine) -> None:
    gdf = gpd.read_file(src)
    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
    df.to_sql(quoted_name(table, quote=True), engine, if_exists="replace", index=False)


def load_taxpar(src: Path, table: str, engine) -> None:
    gdf = gpd.read_file(src)
    gdf = promote_to_multi(gdf)
    gdf = gdf.rename_geometry("geom")
    gdf.to_postgis(quoted_name(table, quote=True), engine, if_exists="replace", index=False)


def main(source_dir):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would be loaded without doing it")
    parser.add_argument("--skip-existing", action="store_true", help="Skip tables already in the DB")
    args = parser.parse_args()

    engine = get_db()

    dirs = sorted(d for d in source_dir.iterdir() if d.is_dir() and DIR_RE.match(d.name))
    print(f"Found {len(dirs)} directories to process")

    already_loaded = existing_tables(engine) if args.skip_existing else set()

    ok = errors = skipped = 0

    for d in dirs:
        m = DIR_RE.match(d.name)
        mcode, yearcode = m.group(1), m.group(2)

        targets = [
            (next(d.glob(f"*Assess*.dbf"), None), f"{mcode}Assess_{yearcode}", load_assess),
            (next(d.glob(f"*TaxPar*.shp"), None), f"{mcode}TaxPar_{yearcode}", load_taxpar),
        ]

        for src, table, loader in targets:
            if src is None:
                continue
            if args.skip_existing and table in already_loaded:
                print(f"  skip  {table} (already exists)")
                skipped += 1
                continue
            print(f"  load  {table} <- {src.name}")
            if args.dry_run:
                ok += 1
                continue
            try:
                loader(src, table, engine)
                ok += 1
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                errors += 1

    print(f"\nDone: {ok} loaded, {skipped} skipped, {errors} errors")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
