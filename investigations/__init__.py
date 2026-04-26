
import logging
import geopandas as gpd

import matplotlib.pyplot as plt
import matplotlib.axes

def plot_parcel_at_scale(
    parcel_loc_id: str,
    gdf: gpd.GeoDataFrame,
    scale: float = 40.0,
    figsize: tuple = (8.5, 11.0),
    ax: matplotlib.axes.Axes | None = None,
) -> matplotlib.axes.Axes:
    """Plot parcels centered on a subject parcel at a given map scale.

    Args:
    * parcel_loc_id (str): LOC_ID of the subject parcel
    * gdf (gpd.GeoDataFrame): parcel geometries with a "LOC_ID" column
    * scale (float): feet represented by one inch on the plot (default 40, i.e. 1" = 40')
    * figsize (tuple): figure size in inches; ignored when ax is provided
    * ax: existing Axes to draw into; a new figure is created when None

    Returns:
    The matplotlib Axes containing the plot.
    """

    matches = gdf[gdf["LOC_ID"] == parcel_loc_id]
    if matches.empty:
        raise ValueError(f"LOC_ID {parcel_loc_id} not found in the GeoDataFrame")

    subject_geom = matches.geometry.iloc[0]
    cx, cy = subject_geom.centroid.x, subject_geom.centroid.y

    # Determine how many CRS units equal one foot
    crs = gdf.crs
    if crs is not None and crs.axis_info:
        unit = crs.axis_info[0].unit_name.lower()
        units_per_ft = 0.3048 if ("metre" in unit or "meter" in unit) else 1.0
    else:
        logging.warning("CRS is unknown; assuming CRS units are feet")
        units_per_ft = 1.0

    half_w = figsize[0] / 2 * scale * units_per_ft
    half_h = figsize[1] / 2 * scale * units_per_ft

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    gdf.plot(ax=ax, color="lightgray", edgecolor="white", linewidth=0.3)
    matches.plot(ax=ax, color="steelblue", edgecolor="navy", linewidth=1.0)

    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.set_axis_off()
    ax.set_title(f'{parcel_loc_id}  (1" = {scale:.0f}\')')

    return ax