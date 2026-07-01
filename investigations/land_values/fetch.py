
import pandas as pd
from sqlalchemy import text
from data.connect_db import get_db

INFLATION_RATE = 2.5
BASE_YEAR = 2026

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

_RESIDENTIAL = '"USE_CODE"::integer < 200 AND ("USE_CODE"::integer < 130 OR "USE_CODE"::integer > 140)'


def _normalize(series: pd.Series, year: int) -> pd.Series:
    rate = 1 + INFLATION_RATE / 100
    return series / (rate ** (year - BASE_YEAR))


def fetch_cohort_data() -> pd.DataFrame:
    """Residential parcels present in every snapshot, with LAND_VAL and BLDG_VAL
    normalized to BASE_YEAR constant dollars.

    Returns columns: PROP_ID, assessed_year, LAND_VAL, BLDG_VAL
    """
    cohort_parts = [
        f'SELECT "PROP_ID" FROM "{table}" WHERE {_RESIDENTIAL}'
        for table, _ in ASSESSMENT_TABLES
    ]
    cohort_cte = "\n    INTERSECT\n    ".join(cohort_parts)

    union_parts = [
        f"""SELECT "PROP_ID", "LAND_VAL", "BLDG_VAL", {year} AS assessed_year
        FROM "{table}"
        WHERE "PROP_ID" IN (SELECT "PROP_ID" FROM cohort)
        AND {_RESIDENTIAL}"""
        for table, year in ASSESSMENT_TABLES
    ]
    sql = text(f"""
        WITH cohort AS ({cohort_cte})
        {" UNION ALL ".join(union_parts)}
    """)

    engine = get_db()
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    for year in df["assessed_year"].unique():
        mask = df["assessed_year"] == year
        df.loc[mask, "LAND_VAL"] = _normalize(df.loc[mask, "LAND_VAL"], year)
        df.loc[mask, "BLDG_VAL"] = _normalize(df.loc[mask, "BLDG_VAL"], year)

    both_zero = (df["LAND_VAL"].fillna(0) == 0) & (df["BLDG_VAL"].fillna(0) == 0)
    return df[~both_zero].reset_index(drop=True)
