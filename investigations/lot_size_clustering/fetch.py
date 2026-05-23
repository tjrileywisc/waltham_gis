# investigations/lot_size_clustering/fetch.py
import pandas as pd
import geopandas as gpd

from sqlalchemy import text
from data.connect_db import get_db


def _bin_lot_sizes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lot_size_bin"] = (df["LOT_SIZE"] / 500).round() * 500
    return df


def fetch_residential_lot_sizes() -> pd.DataFrame:
    raise NotImplementedError


def fetch_parcel_geometry() -> gpd.GeoDataFrame:
    raise NotImplementedError
