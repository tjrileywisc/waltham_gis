import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""
    # Historical Commission Review

    Per Waltham's zoning code [section 23-2](https://ecode360.com/26936024), structures older than 75 years must go through Historical Commission Review. The Historical Commission is tasked
    to determine whether or not a structure should be preserved or if demoltion need not be denied to preserve historic character. Our zoning code has _long_ forbidden multi-family housing,
    meaning a lot of our housing stock is low density. Historical review could present a barrier to necessary development of housing. The more restrictive our zoning code is, the more structures
    could be subject to review. Given the subjective criteria allowed by the code, there's a possibility that we'd be stuck with insufficient housing that becomes increasingly expensive to maintain.
    """)
    return


@app.cell
def _():
    import pandas as pd
    import geopandas as gpd
    import datetime

    from data.connect_db import get_db

    from waltham.constants import MASSGIS_CRS

    conn = get_db()

    COMPARE_YEAR = datetime.date.today().year + 10
    return COMPARE_YEAR, conn, gpd, pd


@app.cell
def _(conn, gpd):
    parcels_query = f"""
    select
        "geom", "LOC_ID"
    from 
        \"M308TaxPar_CY25_FY25\"
    """

    parcels_df = gpd.read_postgis(parcels_query, conn, geom_col="geom")
    return (parcels_df,)


@app.cell
def _(COMPARE_YEAR, conn, pd):
    # fetch the data


    assess_query = f"""
    select
        "LOC_ID", "PROP_ID", "UNITS", "YEAR_BUILT", "USE_CODE"::integer, "STYLE"
    from
        \"M308Assess_CY25_FY25\"
    """

    assess_df = pd.read_sql(assess_query, conn)
    # assume age is 75, if unknown
    assess_df["IMPUTED"] = assess_df["YEAR_BUILT"].map(lambda x: x in [float("nan"), 0])
    assess_df["YEAR_BUILT"] = assess_df["YEAR_BUILT"].replace(0, COMPARE_YEAR - 75)
    assess_df["YEAR_BUILT"] = assess_df["YEAR_BUILT"].fillna(COMPARE_YEAR - 75)
    assess_df
    return (assess_df,)


@app.cell
def _(assess_df, parcels_df):
    properties_df = parcels_df.merge(assess_df, how="outer", on="LOC_ID")
    return (properties_df,)


@app.cell
def _(COMPARE_YEAR, properties_df):
    properties_df["HISTORIC"] = (COMPARE_YEAR - properties_df["YEAR_BUILT"]) >= 75
    properties_df
    return


@app.cell
def _(properties_df):
    # historic, and housing
    properties_df["HISTORIC_RESIDENTIAL"] = properties_df.apply(lambda row: row["HISTORIC"] and row["USE_CODE"] < 200, axis=1)
    properties_df[
        (properties_df["USE_CODE"] < 200) & 
        (properties_df["USE_CODE"].map(lambda x: x not in range(130, 141)))
    ]
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
