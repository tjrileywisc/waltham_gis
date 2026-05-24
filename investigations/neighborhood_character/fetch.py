# investigations/lot_size_clustering/fetch.py
import pandas as pd
import geopandas as gpd

from sqlalchemy import text
from data.connect_db import get_db
from waltham.constants import SQ_FT_PER_ACRE

_RESIDENTIAL_FILTER = (
    '"USE_CODE"::integer < 200'
    ' AND ("USE_CODE"::integer < 130 OR "USE_CODE"::integer > 140)'
)


def _bin_lot_sizes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lot_size_bin"] = (df["LOT_SIZE_SQFT"] / 500).round() * 500
    return df


def fetch_residential_lot_sizes() -> pd.DataFrame:
    """Return residential parcels with lot sizes from the 2025 assessment snapshot.

    Filters to USE_CODE < 200 (excl. 130-140) and LOT_SIZE > 0.
    LOT_SIZE_SQFT is the lot size converted from acres to square feet.
    Adds a `lot_size_bin` column: lot size rounded to the nearest 500 sq ft.
    """
    engine = get_db()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                f'SELECT "LOC_ID", "LOT_SIZE", "USE_CODE", "UNITS", "SITE_ADDR"'
                f' FROM "M308Assess_CY25_FY25"'
                f' WHERE {_RESIDENTIAL_FILTER}'
                f'   AND "LOT_SIZE" > 0'
            ),
            conn,
        )
    df = df.rename(columns={"LOT_SIZE": "LOT_SIZE_SQFT"})
    df["LOT_SIZE_SQFT"] = df["LOT_SIZE_SQFT"] * SQ_FT_PER_ACRE
    return _bin_lot_sizes(df)


def fetch_parcel_geometry() -> gpd.GeoDataFrame:
    """Return all parcel geometries from the 2025 snapshot."""
    engine = get_db()
    return gpd.read_postgis(
        'SELECT "LOC_ID", "geom" FROM "M308TaxPar_CY25_FY25"',
        engine,
        geom_col="geom",
    )


def fetch_waltham_zoning() -> gpd.GeoDataFrame:
    """Return Waltham zoning district polygons."""
    engine = get_db()
    return gpd.read_postgis(
        'SELECT "id", "NAME", "geom" FROM "WalthamZoning"',
        engine,
        geom_col="geom",
    )


def fetch_building_footprints() -> gpd.GeoDataFrame:
    """Return all building footprints from the 2025 structures snapshot."""
    engine = get_db()
    return gpd.read_postgis(
        'SELECT "geom", "SHAPE_AREA" FROM "structures_poly_308"',
        engine,
        geom_col="geom",
    )
