
import pandas as pd
import geopandas as gpd

from sqlalchemy import text
from data.connect_db import get_db

# One entry per distinct calendar year; prefer CY_FY matching tables where duplicates exist
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

# Adjacent snapshot pairs used for consecutive-year comparisons
CONSECUTIVE_PAIRS = [
    (ASSESSMENT_TABLES[i][0], ASSESSMENT_TABLES[i + 1][0],
     ASSESSMENT_TABLES[i][1], ASSESSMENT_TABLES[i + 1][1])
    for i in range(len(ASSESSMENT_TABLES) - 1)
]


def fetch_all_records() -> pd.DataFrame:
    """Return all M308Assess records across every available year.

    Returns a DataFrame with columns: LOC_ID, UNITS, YEAR_BUILT, USE_CODE,
    assessed_year.
    """
    engine = get_db()
    frames = []
    with engine.connect() as conn:
        for table_name, year in ASSESSMENT_TABLES:
            df = pd.read_sql(
                text(
                    f'SELECT "LOC_ID", "UNITS", "YEAR_BUILT", "USE_CODE"'
                    f' FROM "{table_name}"'
                ),
                conn,
            )
            df["assessed_year"] = year
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def fetch_redevelopment_counts() -> pd.DataFrame:
    """Count newly built parcels between each pair of consecutive snapshots.

    A parcel is counted as *redeveloped* when it existed in both snapshots
    (same LOC_ID), had a known prior building (MAX YEAR_BUILT > 0 across all
    records for that LOC_ID), and its MAX YEAR_BUILT increased to within 3
    years of the newer assessment year — indicating the old structure was
    replaced.

    A parcel is counted as *new_on_vacant* when it existed in both snapshots
    but had MAX YEAR_BUILT = 0 (no building on any record) in the older one,
    and now has a recent MAX YEAR_BUILT.

    Aggregating to LOC_ID before joining prevents double-counting parcels that
    have multiple assessment records (e.g. duplexes with one row per unit).

    Returns a DataFrame with columns: year, redeveloped, new_on_vacant.
    """
    engine = get_db()
    rows = []
    with engine.connect() as conn:
        for tbl_old, tbl_new, yr_old, yr_new in CONSECUTIVE_PAIRS:
            redeveloped = pd.read_sql(
                text(f"""
                    SELECT COUNT(*) AS cnt
                    FROM (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_new}" GROUP BY "LOC_ID") a
                    JOIN (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_old}" GROUP BY "LOC_ID") b
                      ON a."LOC_ID" = b."LOC_ID"
                    WHERE a.max_yb > b.max_yb
                      AND b.max_yb > 0
                      AND a.max_yb >= {yr_new - 3}
                """),
                conn,
            ).iloc[0]["cnt"]

            new_on_vacant = pd.read_sql(
                text(f"""
                    SELECT COUNT(*) AS cnt
                    FROM (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_new}" GROUP BY "LOC_ID") a
                    JOIN (SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb FROM "{tbl_old}" GROUP BY "LOC_ID") b
                      ON a."LOC_ID" = b."LOC_ID"
                    WHERE b.max_yb = 0
                      AND a.max_yb > 0
                      AND a.max_yb >= {yr_new - 3}
                """),
                conn,
            ).iloc[0]["cnt"]

            rows.append(
                {"year": yr_new, "redeveloped": redeveloped, "new_on_vacant": new_on_vacant}
            )

    return pd.DataFrame(rows)


def fetch_parcel_geometry():
    """Return all parcel geometries from the latest snapshot.

    Returns a GeoDataFrame with columns: LOC_ID, geom.
    """

    engine = get_db()
    return gpd.read_postgis(
        'SELECT "LOC_ID", "geom" FROM "M308TaxPar_CY25_FY25"',
        engine,
        geom_col="geom",
    )


def fetch_turnover_geodata():
    """Return turned-over parcels with geometry for every consecutive year pair.

    Returns a GeoDataFrame with columns: LOC_ID, turnover_type, year, geom.
    turnover_type is either 'redeveloped' or 'new_on_vacant'.
    Geometry comes from the latest parcel table (M308TaxPar_CY25_FY25).
    """

    engine = get_db()
    frames = []
    with engine.connect() as conn:
        for tbl_old, tbl_new, yr_old, yr_new in CONSECUTIVE_PAIRS:
            redeveloped_ids = pd.read_sql(
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
            redeveloped_ids["turnover_type"] = "redeveloped"
            redeveloped_ids["year"] = yr_new

            new_on_vacant_ids = pd.read_sql(
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
            new_on_vacant_ids["turnover_type"] = "new_on_vacant"
            new_on_vacant_ids["year"] = yr_new

            frames.append(redeveloped_ids)
            frames.append(new_on_vacant_ids)

    turnover_df = pd.concat(frames, ignore_index=True)

    geom_gdf = fetch_parcel_geometry()
    return geom_gdf.merge(turnover_df, on="LOC_ID", how="inner")


def fetch_turnover_with_details() -> gpd.GeoDataFrame:
    """Return turned-over parcels with geometry and full assessment details for both snapshots.

    Useful for building tooltips that show what a parcel looked like before and after
    development activity was detected.

    Returns a GeoDataFrame with columns:
        LOC_ID, turnover_type, year_prev, year,
        year_built_prev, units_prev, use_code_prev,
        year_built_new,  units_new,  use_code_new,  geom.
    Geometry comes from the latest parcel table.
    """

    engine = get_db()
    frames = []
    with engine.connect() as conn:
        for tbl_old, tbl_new, yr_old, yr_new in CONSECUTIVE_PAIRS:
            redeveloped = pd.read_sql(
                text(f"""
                    SELECT
                        a."LOC_ID",
                        'redeveloped'          AS turnover_type,
                        {yr_old}               AS year_prev,
                        {yr_new}               AS year,
                        b.max_yb               AS year_built_prev,
                        b.total_units          AS units_prev,
                        b.use_code             AS use_code_prev,
                        a.max_yb               AS year_built_new,
                        a.total_units          AS units_new,
                        a.use_code             AS use_code_new
                    FROM (
                        SELECT "LOC_ID",
                               MAX("YEAR_BUILT")       AS max_yb,
                               SUM("UNITS")            AS total_units,
                               MIN("USE_CODE"::integer) AS use_code
                        FROM "{tbl_new}" GROUP BY "LOC_ID"
                    ) a
                    JOIN (
                        SELECT "LOC_ID",
                               MAX("YEAR_BUILT")       AS max_yb,
                               SUM("UNITS")            AS total_units,
                               MIN("USE_CODE"::integer) AS use_code
                        FROM "{tbl_old}" GROUP BY "LOC_ID"
                    ) b ON a."LOC_ID" = b."LOC_ID"
                    WHERE a.max_yb > b.max_yb
                      AND b.max_yb > 0
                      AND a.max_yb >= {yr_new - 3}
                """),
                conn,
            )

            new_on_vacant = pd.read_sql(
                text(f"""
                    SELECT
                        a."LOC_ID",
                        'new_on_vacant'        AS turnover_type,
                        {yr_old}               AS year_prev,
                        {yr_new}               AS year,
                        b.max_yb               AS year_built_prev,
                        b.total_units          AS units_prev,
                        b.use_code             AS use_code_prev,
                        a.max_yb               AS year_built_new,
                        a.total_units          AS units_new,
                        a.use_code             AS use_code_new
                    FROM (
                        SELECT "LOC_ID",
                               MAX("YEAR_BUILT")       AS max_yb,
                               SUM("UNITS")            AS total_units,
                               MIN("USE_CODE"::integer) AS use_code
                        FROM "{tbl_new}" GROUP BY "LOC_ID"
                    ) a
                    JOIN (
                        SELECT "LOC_ID",
                               MAX("YEAR_BUILT")       AS max_yb,
                               SUM("UNITS")            AS total_units,
                               MIN("USE_CODE"::integer) AS use_code
                        FROM "{tbl_old}" GROUP BY "LOC_ID"
                    ) b ON a."LOC_ID" = b."LOC_ID"
                    WHERE b.max_yb = 0
                      AND a.max_yb > 0
                      AND a.max_yb >= {yr_new - 3}
                """),
                conn,
            )

            frames.append(redeveloped)
            frames.append(new_on_vacant)

    turnover_df = pd.concat(frames, ignore_index=True)
    geom_gdf = fetch_parcel_geometry()
    return geom_gdf.merge(turnover_df, on="LOC_ID", how="inner")


def fetch_unit_decreases(tbl_old: str, tbl_new: str) -> gpd.GeoDataFrame:
    """Return parcels whose total unit count dropped between two assessment snapshots.

    Aggregates to LOC_ID before comparing so multi-record parcels (e.g. duplexes
    with one row per unit) are handled correctly.

    Returns a GeoDataFrame with columns:
        LOC_ID, units_old, units_new, units_lost, use_code, year_built, geom.
    Geometry comes from the latest parcel table.
    """

    engine = get_db()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(f"""
                SELECT
                    a."LOC_ID",
                    b.total_units                   AS units_old,
                    a.total_units                   AS units_new,
                    b.total_units - a.total_units   AS units_lost,
                    a.use_code,
                    a.max_yb                        AS year_built
                FROM (
                    SELECT "LOC_ID",
                           SUM("UNITS")              AS total_units,
                           MIN("USE_CODE"::integer)   AS use_code,
                           MAX("YEAR_BUILT")          AS max_yb
                    FROM "{tbl_new}" GROUP BY "LOC_ID"
                ) a
                JOIN (
                    SELECT "LOC_ID",
                           SUM("UNITS")              AS total_units
                    FROM "{tbl_old}" GROUP BY "LOC_ID"
                ) b ON a."LOC_ID" = b."LOC_ID"
                WHERE a.total_units < b.total_units
                ORDER BY units_lost DESC
            """),
            conn,
        )

    geom_gdf = fetch_parcel_geometry()
    return geom_gdf.merge(df, on="LOC_ID", how="inner")


def fetch_prop_id_splits() -> pd.DataFrame:
    """Detect potential condo conversions: multifamily residential LOC_IDs where
    PROP_ID count increases year-over-year, suggesting a single parcel was
    subdivided into individually assessed units.

    Restricted to non-101 residential parcels (USE_CODE 102-129, 141-199) in the
    older snapshot, since those are the use codes that can represent multifamily
    housing.  USE_CODE 101 (single-family) is excluded because a split there
    would not represent a conversion from rental stock.

    Returns a DataFrame with columns:
        year_prev, year, LOC_ID,
        prop_count_old, prop_count_new,
        units_old, units_new, units_change,
        use_codes_old, use_codes_new.
    Sorted by year then units_change ascending (largest losses first within year).
    """
    engine = get_db()
    frames = []
    with engine.connect() as conn:
        for tbl_old, tbl_new, yr_old, yr_new in CONSECUTIVE_PAIRS:
            df = pd.read_sql(
                text(f"""
                    SELECT
                        {yr_old}                        AS year_prev,
                        {yr_new}                        AS year,
                        a."LOC_ID",
                        b.prop_count                    AS prop_count_old,
                        a.prop_count                    AS prop_count_new,
                        b.total_units                   AS units_old,
                        a.total_units                   AS units_new,
                        a.total_units - b.total_units   AS units_change,
                        b.use_codes                     AS use_codes_old,
                        a.use_codes                     AS use_codes_new
                    FROM (
                        SELECT
                            "LOC_ID",
                            COUNT(DISTINCT "PROP_ID")                                        AS prop_count,
                            SUM("UNITS")                                                     AS total_units,
                            STRING_AGG(DISTINCT "USE_CODE"::text, ',' ORDER BY "USE_CODE"::text) AS use_codes
                        FROM "{tbl_new}"
                        GROUP BY "LOC_ID"
                    ) a
                    JOIN (
                        SELECT
                            "LOC_ID",
                            COUNT(DISTINCT "PROP_ID")                                        AS prop_count,
                            SUM("UNITS")                                                     AS total_units,
                            STRING_AGG(DISTINCT "USE_CODE"::text, ',' ORDER BY "USE_CODE"::text) AS use_codes
                        FROM "{tbl_old}"
                        WHERE "USE_CODE"::integer < 200
                          AND "USE_CODE"::integer != 101
                          AND ("USE_CODE"::integer < 130 OR "USE_CODE"::integer > 140)
                        GROUP BY "LOC_ID"
                    ) b ON a."LOC_ID" = b."LOC_ID"
                    WHERE a.prop_count > b.prop_count
                    ORDER BY units_change ASC
                """),
                conn,
            )
            frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


_RESIDENTIAL_FILTER = (
    '"USE_CODE"::integer < 200'
    ' AND ("USE_CODE"::integer < 130 OR "USE_CODE"::integer > 140)'
)


def fetch_units_by_year() -> pd.DataFrame:
    """Return total residential housing units for each assessment year.

    Residential parcels are those with USE_CODE < 200, excluding the
    special-use codes 130-140.
    Returns a DataFrame with columns: year, total_units, units_change.
    """
    engine = get_db()
    rows = []
    with engine.connect() as conn:
        for table_name, year in ASSESSMENT_TABLES:
            result = pd.read_sql(
                text(
                    f'SELECT SUM("UNITS") AS total_units'
                    f' FROM "{table_name}"'
                    f' WHERE {_RESIDENTIAL_FILTER}'
                ),
                conn,
            )
            rows.append({"year": year, "total_units": int(result.iloc[0]["total_units"])})

    df = pd.DataFrame(rows).sort_values("year")
    # Drop years where UNITS wasn't populated yet (all zeros)
    df = df[df["total_units"] > 0].reset_index(drop=True)
    df["units_change"] = df["total_units"].diff()
    return df
