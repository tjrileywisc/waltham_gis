
import pandas as pd
import geopandas as gpd

from pathlib import Path
from sqlalchemy import text
from data.connect_db import get_db

# Per-zone rules loaded once at import time
_ZONE_RULES: pd.DataFrame = pd.read_csv(
    Path(__file__).resolve().parent.parent.parent / "data" / "zoning_rules_table.csv",
    skipinitialspace=True,
).set_index("District").apply(pd.to_numeric, errors="coerce")

# Max by-right DUA per zone (NaN where no cap is defined)
_ZONE_MAX_DUA: pd.Series = _ZONE_RULES["max DUA"]

# Minimum lot size per zone in acres (NaN where no minimum is defined; 0 → NaN)
_ZONE_MIN_LOT_ACRES: pd.Series = (
    _ZONE_RULES["lot area"]
    .replace(0, float("nan"))
    / 43_560
)

# One entry per distinct calendar year: (assess_table, year, taxpar_table).
# taxpar_table is None when no per-year parcel shapefile is available.
# All taxpar tables use the M308TaxPar_CY*_FY* naming convention.
ASSESSMENT_TABLES = [
    ("M308Assess_CY11_FY11", 2011, "M308TaxPar_CY11_FY11"),
    ("M308Assess_CY14_FY14", 2014, "M308TaxPar_CY14_FY14"),
    ("M308Assess_CY15_FY15", 2015, "M308TaxPar_CY15_FY15"),
    ("M308Assess_CY16_FY16", 2016, "M308TaxPar_CY16_FY16"),
    ("M308Assess_CY17_FY17", 2017, "M308TaxPar_CY17_FY17"),
    ("M308Assess_CY18_FY18", 2018, "M308TaxPar_CY18_FY18"),
    ("M308Assess_CY19_FY18", 2019, "M308TaxPar_CY19_FY18"),
    ("M308Assess_CY20_FY20", 2020, "M308TaxPar_CY20_FY20"),
    ("M308Assess_CY21_FY21", 2021, "M308TaxPar_CY21_FY21"),
    ("M308Assess_CY22_FY22", 2022, "M308TaxPar_CY22_FY22"),
    ("M308Assess_CY23_FY23", 2023, "M308TaxPar_CY23_FY23"),
    ("M308Assess_CY25_FY25", 2025, "M308TaxPar_CY25_FY25"),
    ("M308Assess_CY26_FY26", 2026, None),
]

# Adjacent snapshot pairs: (assess_old, assess_new, yr_old, yr_new, taxpar_old, taxpar_new)
CONSECUTIVE_PAIRS = [
    (ASSESSMENT_TABLES[i][0], ASSESSMENT_TABLES[i + 1][0],
     ASSESSMENT_TABLES[i][1], ASSESSMENT_TABLES[i + 1][1],
     ASSESSMENT_TABLES[i][2], ASSESSMENT_TABLES[i + 1][2])
    for i in range(len(ASSESSMENT_TABLES) - 1)
]

_PAR_TABLE = "M308TaxPar_CY25_FY25"

_RESIDENTIAL_FILTER = (
    'a."USE_CODE"::integer < 200'
    ' AND (a."USE_CODE"::integer < 132 OR a."USE_CODE"::integer > 140)'
)


def fetch_features_for_snapshot(table_name: str, year: int,
                                par_table: str | None = None) -> pd.DataFrame:
    """Return features for all residential parcels in one assessment snapshot.

    Zone is resolved via a PostGIS spatial join (parcel centroid within
    WalthamZoning polygon) using par_table for parcel geometry.  Pass the
    taxpar table from the same calendar year so that the LOC_ID join and
    centroid are drawn from the matching snapshot, not the 2025 baseline.
    Falls back to _PAR_TABLE when par_table is None (e.g. the 2026 snapshot
    which has no dedicated taxpar table).

    YEAR_BUILT = 0 (unknown build date) is treated as year - 75, consistent
    with the project convention documented in CLAUDE.md.

    Returns a DataFrame with columns:
        LOC_ID, YEAR_BUILT, UNITS, USE_CODE, LOT_SIZE, BLDG_VAL, LAND_VAL,
        TOTAL_VAL, BLD_AREA, SITE_ADDR, OWNER1, OWN_CITY, zone,
        building_age, land_value_ratio, EMPTY_LOT, meets_min_lot_size,
        investor_owned, years_since_sale, UNDERDEVELOPED_DUA.
    """
    _par = par_table or _PAR_TABLE
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
                LEFT JOIN "{_par}" p
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

    # Developable or potentially developable vacant land (USE_CODE 130 or 131)
    df["EMPTY_LOT"] = df["USE_CODE"].isin([130, 131]).astype(int)

    # Whether the parcel meets the by-right minimum lot size for its zone.
    # LOT_SIZE is in acres; _ZONE_MIN_LOT_ACRES converts sq-ft minimums from the
    # zoning table. NaN where the zone has no defined minimum (e.g. BC, I).
    min_lot = df["zone"].map(_ZONE_MIN_LOT_ACRES)
    df["meets_min_lot_size"] = (df["LOT_SIZE"] >= min_lot).astype("Int8").where(min_lot.notna())

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


def fetch_turnover_labels(tbl_old: str, tbl_new: str, yr_new: int,
                          min_year: int | None = None,
                          taxpar_old: str | None = None,
                          taxpar_new: str | None = None) -> set:
    """Return the set of OLD-snapshot LOC_IDs that turned over between two snapshots.

    A parcel is considered turned over if:
    - Its MAX(YEAR_BUILT) increased and the old value was > 0 (redeveloped), or
    - Its old MAX(YEAR_BUILT) was 0 and it now has a recent build year (new on vacant).
    In both cases the new YEAR_BUILT must be >= min_year (defaults to yr_new - 3).

    When both taxpar_old and taxpar_new are provided, parcels are matched by
    centroid: if the centroid of a new parcel falls within an old parcel's boundary,
    they are treated as the same physical parcel regardless of LOC_ID changes.
    Returns OLD-snapshot loc_ids so results align with features DataFrames keyed on
    the old snapshot. Falls back to LOC_ID join when taxpar tables are unavailable.
    """
    cutoff = min_year if min_year is not None else yr_new - 3
    engine = get_db()

    if taxpar_old and taxpar_new:
        # Centroid-based matching: new parcel centroid falls within old parcel boundary.
        sql = f"""
            WITH
            old_yb AS (
                SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb
                FROM "{tbl_old}" GROUP BY "LOC_ID"
            ),
            new_yb AS (
                SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb
                FROM "{tbl_new}" GROUP BY "LOC_ID"
            ),
            matched AS (
                SELECT DISTINCT
                    tp_old."LOC_ID" AS old_loc_id,
                    o.max_yb        AS old_yb,
                    n.max_yb        AS new_yb
                FROM "{taxpar_new}" tp_new
                JOIN "{taxpar_old}" tp_old
                    ON ST_Within(ST_Centroid(tp_new.geom), tp_old.geom)
                JOIN new_yb n ON n."LOC_ID" = tp_new."LOC_ID"
                JOIN old_yb o ON o."LOC_ID" = tp_old."LOC_ID"
                WHERE tp_new."POLY_TYPE" = 'FEE'
                  AND tp_old."POLY_TYPE" = 'FEE'
            )
            SELECT old_loc_id AS "LOC_ID" FROM matched
            WHERE (new_yb > old_yb AND old_yb > 0 AND new_yb >= {cutoff})
               OR (old_yb = 0 AND new_yb > 0 AND new_yb >= {cutoff})
        """
        with engine.connect() as conn:
            result = pd.read_sql(text(sql), conn)
        return set(result["LOC_ID"])

    # Fallback: plain LOC_ID join for snapshots without per-year taxpar tables
    with engine.connect() as conn:
        redeveloped = pd.read_sql(
            text(f"""
                SELECT a."LOC_ID"
                FROM (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_new}" GROUP BY "LOC_ID") a
                JOIN (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_old}" GROUP BY "LOC_ID") b
                  ON a."LOC_ID" = b."LOC_ID"
                WHERE a.max_yb > b.max_yb
                  AND b.max_yb > 0
                  AND a.max_yb >= {cutoff}
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
                  AND a.max_yb >= {cutoff}
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
