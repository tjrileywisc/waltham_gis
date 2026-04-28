
# for lack of a better name, track any of Waltham's specific applications of non-zoning quirks in this file
# for example, if we have a specific set of extra abutters collection rules to add on top of what the state
# requires, that sort of thing should go in here

import logging
import geopandas as gpd
def collect_abutters(parcel_loc_id: str, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
    """Per MGL 40A Section 11, we're required to notify every abutter within a 300 foot buffer of the property
    line that is the subject of a public hearing.

    This simply extends a buffer of the specified distance and tracks any parcels that intersect.

    N.B. be sure to include neighboring communities in the dataframe if it is
    possible that abutters may be in a neighboring community, otherwise these parcels will not be included.

    The GeoDataFrame must use a projected CRS with feet as the linear unit (e.g. NAD83 / Massachusetts
    Mainland, EPSG:26986) so that the 300-foot buffer distance is interpreted correctly.

    Args:
    * parcel_loc_id (str): the LOC_ID associated with the parcel of interest
    * gdf (gpd.GeoDataFrame): a GeoPandas data frame containing the parcel of interest and any possible abutters,
      with a "LOC_ID" column and polygon geometry column

    Returns:
    A GeoDataFrame of abutter parcels (excluding the subject parcel itself), or None if the parcel is not found.

    """

    ABUTTER_DIST = 300.0 # ft

    matches = gdf[gdf["LOC_ID"] == parcel_loc_id]
    if matches.empty:
        logging.warning(f"LOC_ID {parcel_loc_id} not found in the data")
        return None

    subject_geom = matches.geometry.iloc[0]
    buffer = subject_geom.buffer(distance=ABUTTER_DIST)

    return gdf[gdf.intersects(buffer) & (gdf["LOC_ID"] != parcel_loc_id)]

