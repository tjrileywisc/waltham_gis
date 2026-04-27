
import pandas as pd
import geopandas as gpd

from pathlib import Path
from sqlalchemy import text
from data.connect_db import get_db

# Max by-right DUA per zoning district (NaN where no cap is defined)
_ZONE_MAX_DUA: pd.Series = (
    pd.read_csv(
        Path(__file__).resolve().parent.parent.parent / "data" / "zoning_rules_table.csv",
        skipinitialspace=True,
    )
    .set_index("District")["max DUA"]
    .apply(pd.to_numeric, errors="coerce")
)

# One entry per distinct calendar year (mirrors development_turnover/fetch.py)
ASSESSMENT_TABLES = [
    ("M308Assess_CY11_FY11", 2011),
    ("M308Assess_CY14_FY14", 2014),
    ("M308Assess_CY15_FY15", 2015),
    ("M308Assess_CY16_FY16", 2016),
    ("M308Assess_CY17_FY17", 2017),
    ("M308Assess_CY18_FY18", 2018),
    ("M308Assess_CY19_FY18", 2019),
    ("M308Assess_CY20_FY20", 2020),
    ("M308Assess_CY21_FY21", 2021),
    ("M308Assess_CY22_FY22", 2022),
    ("M308Assess_CY23_FY23", 2023),
    ("M308Assess_CY25_FY25", 2025),
    ("M308Assess_CY26_FY26", 2026),
]

# Adjacent snapshot pairs used for label construction
CONSECUTIVE_PAIRS = [
    (ASSESSMENT_TABLES[i][0], ASSESSMENT_TABLES[i + 1][0],
     ASSESSMENT_TABLES[i][1], ASSESSMENT_TABLES[i + 1][1])
    for i in range(len(ASSESSMENT_TABLES) - 1)
]

_PAR_TABLE = "M308TaxPar_CY25_FY25"

_RESIDENTIAL_FILTER = (
    'a."USE_CODE"::integer < 200'
    ' AND (a."USE_CODE"::integer < 130 OR a."USE_CODE"::integer > 140)'
)


def fetch_features_for_snapshot(table_name: str, year: int) -> pd.DataFrame:
    """Return features for all residential parcels in one assessment snapshot.

    Zone is resolved via a PostGIS spatial join (parcel centroid within
    WalthamZoning polygon) using the latest parcel geometry as the spatial
    reference; zoning boundaries are stable across the dataset's time range.

    YEAR_BUILT = 0 (unknown build date) is treated as year - 75, consistent
    with the project convention documented in CLAUDE.md.

    Returns a DataFrame with columns:
        LOC_ID, year_built, units, use_code, lot_size, bldg_val, land_val,
        total_val, bld_area, zone,
        building_age, land_value_ratio, years_since_sale, is_sfh.
    """
    engine = get_db()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(f"""
                SELECT
                    a."LOC_ID",
                    MAX(a."YEAR_BUILT")           AS "YEAR_BUILT",
                    SUM(a."UNITS")                AS "UNITS",
                    MIN(a."USE_CODE"::integer)     AS "USE_CODE",
                    MAX(a."LOT_SIZE")              AS "LOT_SIZE",
                    MAX(a."BLDG_VAL")              AS "BLDG_VAL",
                    MAX(a."LAND_VAL")              AS "LAND_VAL",
                    MAX(a."TOTAL_VAL")             AS "TOTAL_VAL",
                    MAX(a."BLD_AREA")              AS "BLD_AREA",
                    MAX(a."LS_DATE")               AS "LS_DATE",
                    MAX(a."SITE_ADDR")             AS "SITE_ADDR",
                    MAX(a."OWNER1")               AS "OWNER1",
                    MAX(a."OWN_CITY")             AS "OWN_CITY",
                    z."NAME"                       AS zone
                FROM "{table_name}" a
                LEFT JOIN "{_PAR_TABLE}" p
                    ON a."LOC_ID" = p."LOC_ID"
                    AND p."POLY_TYPE" = 'FEE'
                LEFT JOIN "WalthamZoning" z
                    ON ST_Within(ST_Centroid(p.geom), z.geom)
                WHERE {_RESIDENTIAL_FILTER}
                GROUP BY a."LOC_ID", z."NAME"
            """),
            conn,
        )

    # Drop duplicate LOC_IDs from rare zone-boundary edge cases
    df = df.drop_duplicates(subset=["LOC_ID"], keep="first")

    # building_age: YEAR_BUILT = 0 → assume structure is 75 years old
    df["building_age"] = (year - df["YEAR_BUILT"].replace(0, year - 75)).clip(lower=0)

    # Land-value ratio: high → building contributes little to assessed value
    df["land_value_ratio"] = df["LAND_VAL"] / (df["LAND_VAL"] + df["BLDG_VAL"] + 1)

    # Investor ownership: LLC/Trust in owner name, or owner mailing address is outside Waltham
    df["investor_owned"] = (
        df["OWNER1"].str.contains("LLC|TRUST", case=False, na=False)
        | (df["OWN_CITY"].str.strip().str.upper() != "WALTHAM")
    ).astype(int)

    # Years since last recorded sale
    df["LS_DATE"] = pd.to_datetime(df["LS_DATE"], errors="coerce")
    df["years_since_sale"] = year - df["LS_DATE"].dt.year

    # How many units short of the by-right max density the parcel is.
    # LOT_SIZE is in acres; zones without a DUA cap get NaN (imputed later).
    lot_size_safe = df["LOT_SIZE"].where(df["LOT_SIZE"] > 0)
    current_dua = df["UNITS"] / lot_size_safe
    df["UNDERDEVELOPED_DUA"] = (df["zone"].map(_ZONE_MAX_DUA) - current_dua).clip(lower=0)

    return df.drop(columns=["LS_DATE"])


def fetch_turnover_labels(tbl_old: str, tbl_new: str, yr_new: int) -> set:
    """Return the set of LOC_IDs that turned over between two consecutive snapshots.

    A parcel is considered turned over if:
    - Its MAX(YEAR_BUILT) increased and the old value was > 0 (redeveloped), or
    - Its old MAX(YEAR_BUILT) was 0 and it now has a recent build year (new on vacant).
    In both cases the new YEAR_BUILT must be within 3 years of yr_new.
    """
    engine = get_db()
    with engine.connect() as conn:
        redeveloped = pd.read_sql(
            text(f"""
                SELECT a."LOC_ID"
                FROM (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_new}" GROUP BY "LOC_ID") a
                JOIN (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_old}" GROUP BY "LOC_ID") b
                  ON a."LOC_ID" = b."LOC_ID"
                WHERE a.max_yb > b.max_yb
                  AND b.max_yb > 0
                  AND a.max_yb >= {yr_new - 3}
            """),
            conn,
        )
        new_on_vacant = pd.read_sql(
            text(f"""
                SELECT a."LOC_ID"
                FROM (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_new}" GROUP BY "LOC_ID") a
                JOIN (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_old}" GROUP BY "LOC_ID") b
                  ON a."LOC_ID" = b."LOC_ID"
                WHERE b.max_yb = 0
                  AND a.max_yb > 0
                  AND a.max_yb >= {yr_new - 3}
            """),
            conn,
        )
    return set(redeveloped["LOC_ID"]) | set(new_on_vacant["LOC_ID"])


def fetch_parcel_geometry() -> gpd.GeoDataFrame:
    """Return all parcel geometries from the latest snapshot.

    Returns a GeoDataFrame with columns: LOC_ID, geom.
    """
    engine = get_db()
    return gpd.read_postgis(
        f'SELECT "LOC_ID", "geom" FROM "{_PAR_TABLE}"',
        engine,
        geom_col="geom",
    )
