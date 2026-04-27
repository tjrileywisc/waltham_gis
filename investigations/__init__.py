
import logging
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.axes

from branca.element import MacroElement
from jinja2 import Template

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

class StreetViewPanel(MacroElement):
    """Slide-in panel showing an embedded map + Street View link on parcel click.

    Uses google.com/maps?output=embed (no API key required) for the embedded
    satellite view.  The Street View button opens a new tab.
    """

    _template = Template("""
        {%- macro script(this, kwargs) %}
        (function () {
            var mapVar = {{this._parent.get_name()}};
            var mapEl  = document.getElementById('{{this._parent.get_name()}}');

            // ── Panel DOM ──────────────────────────────────────────────
            var panel = document.createElement('div');
            panel.style.cssText =
                'position:fixed;top:0;right:0;width:38vw;height:100vh;'
                + 'background:#111;display:flex;flex-direction:column;'
                + 'z-index:9999;box-shadow:-4px 0 14px rgba(0,0,0,.55);'
                + 'transform:translateX(100%);transition:transform .3s ease;';

            // header
            var hdr = document.createElement('div');
            hdr.style.cssText =
                'padding:10px 14px;background:#222;color:#bbb;flex-shrink:0;'
                + 'font-size:13px;font-family:sans-serif;'
                + 'display:flex;align-items:center;justify-content:space-between;';
            hdr.innerHTML =
                '<span id="sv-addr-{{this._id}}" style="font-weight:600;overflow:hidden;'
                + 'text-overflow:ellipsis;white-space:nowrap;">Location</span>'
                + '<button id="sv-close-{{this._id}}" style="background:none;border:none;'
                + 'color:#999;font-size:20px;cursor:pointer;line-height:1;flex-shrink:0;'
                + 'margin-left:8px;">Click to hide</button>';

            // Street View button bar
            var btnBar = document.createElement('div');
            btnBar.style.cssText =
                'padding:8px 14px;background:#1a1a1a;flex-shrink:0;';
            btnBar.innerHTML =
                '<a id="sv-link-{{this._id}}" href="#" target="_blank" rel="noopener"'
                + ' style="display:inline-block;padding:6px 12px;background:#4285F4;'
                + 'color:white;border-radius:4px;font-size:12px;font-family:sans-serif;'
                + 'text-decoration:none;font-weight:600;">Open Street View</a>';

            // Embedded map iframe
            var iframe = document.createElement('iframe');
            iframe.id = 'sv-frame-{{this._id}}';
            iframe.style.cssText = 'flex:1;border:none;min-height:0;';
            iframe.src = 'about:blank';
            iframe.setAttribute('allowfullscreen', '');
            iframe.setAttribute('loading', 'lazy');
            iframe.setAttribute('referrerpolicy', 'no-referrer-when-downgrade');

            panel.appendChild(hdr);
            panel.appendChild(btnBar);
            panel.appendChild(iframe);
            document.body.appendChild(panel);

            // ── Close ──────────────────────────────────────────────────
            document.getElementById('sv-close-{{this._id}}').addEventListener('click', function () {
                panel.style.transform = 'translateX(100%)';
                iframe.src = 'about:blank';
                if (mapEl) { mapEl.style.maxWidth = ''; mapVar.invalidateSize(); }
            });

            // ── Parcel click ───────────────────────────────────────────
            {{this.layer_name}}.on('click', function (e) {
                var c     = e.layer.getBounds().getCenter();
                var lat   = c.lat.toFixed(6);
                var lng   = c.lng.toFixed(6);
                var props = e.layer.feature.properties;
                var loc   = props.SITE_ADDR || props.LOC_ID || (lat + ', ' + lng);
                var header = loc;

                document.getElementById('sv-addr-{{this._id}}').textContent = header;

                // Embedded satellite map (no API key required)
                iframe.src =
                    'https://www.google.com/maps?q=' + lat + ',' + lng
                    + '&t=k&z=19&output=embed';

                // Street View deep-link for the button
                document.getElementById('sv-link-{{this._id}}').href =
                    'https://www.google.com/maps?q=&layer=c&cbll=' + lat + ',' + lng + '&cbp=12,0,0,0,0';

                panel.style.transform = 'translateX(0)';
                if (mapEl) { mapEl.style.maxWidth = '62vw'; mapVar.invalidateSize(); }
            });
        })();
        {%- endmacro %}
    """)

    def __init__(self, layer_name):
        super().__init__()
        self._name = 'StreetViewPanel'
        self.layer_name = layer_name