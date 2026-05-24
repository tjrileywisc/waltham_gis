# Nonconforming Lots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two fetch functions to `neighborhood_character/fetch.py`, then write a notebook that identifies residential parcels non-conforming on minimum lot size, prints summary stats (parcels, units, estimated population removed), and saves a Folium map (`published/nonconforming_lots.html`) where building footprints are colored red (non-conforming parcel) or green (conforming).

**Architecture:** Option A — conformance logic lives in the notebook, consistent with `illegal_zoning.ipynb`. `fetch.py` gets two thin DB-querying functions. The notebook loads all four tables, does the centroid spatial join to assign zones, reads the zoning CSV, computes `is_nonconforming`, and builds the map.

**Tech Stack:** Python 3.14, pandas, geopandas, SQLAlchemy, Folium, PostGIS (MassGIS schema), uv.

---

### Task 1: Extend fetch.py with two new functions

**Files:**
- Modify: `investigations/neighborhood_character/fetch.py`

- [ ] **Step 1: Add `fetch_waltham_zoning()` to fetch.py**

Open `investigations/neighborhood_character/fetch.py`. After the existing `fetch_parcel_geometry()` function, append:

```python
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
```

- [ ] **Step 2: Smoke-test both functions return data**

Run in a Python REPL or throwaway notebook cell (do not commit):

```python
from investigations.neighborhood_character.fetch import fetch_waltham_zoning, fetch_building_footprints

zones = fetch_waltham_zoning()
print(zones.shape)     # expect ~16 rows (one per zoning district)
print(zones["NAME"].unique())  # expect RA1, RA2, RA3, RA4, RB, RC, ...

buildings = fetch_building_footprints()
print(buildings.shape)  # expect ~16k rows
print(buildings.crs)    # expect EPSG:26986 (NAD83/Massachusetts)
```

- [ ] **Step 3: Commit**

```bash
git add investigations/neighborhood_character/fetch.py
git commit -m "feat: add fetch_waltham_zoning and fetch_building_footprints"
```

---

### Task 2: Write the notebook

**Files:**
- Create: `investigations/neighborhood_character/nonconforming_lots.ipynb`

Create a new Jupyter notebook at `investigations/neighborhood_character/nonconforming_lots.ipynb` and add the cells below in order.

- [ ] **Step 1: Cell 0 — Markdown intro**

```markdown
# Nonconforming lots: what would Waltham lose?

Waltham's zoning code sets minimum lot sizes for each residential district. A large share of existing parcels don't meet those minimums — they predate the rules or were created when standards were lower.

This notebook identifies which residential parcels are non-conforming on lot size, counts the housing units on those parcels, estimates the population that would be displaced, and maps the buildings that would have to go.
```

- [ ] **Step 2: Cell 1 — Imports and data fetch**

```python
import pandas as pd
import geopandas as gpd
import folium

from investigations.neighborhood_character.fetch import (
    fetch_residential_lot_sizes,
    fetch_parcel_geometry,
    fetch_waltham_zoning,
    fetch_building_footprints,
)

PEOPLE_PER_UNIT = 2.4  # Waltham Census ACS 5-year average household size

df       = fetch_residential_lot_sizes()   # LOC_ID, LOT_SIZE_SQFT, USE_CODE, UNITS, SITE_ADDR, lot_size_bin
parcels  = fetch_parcel_geometry()         # LOC_ID, geom
zones    = fetch_waltham_zoning()          # id, NAME, geom
buildings = fetch_building_footprints()   # geom, SHAPE_AREA

zoning_rules = pd.read_csv("data/zoning_rules_table.csv").set_index("District")
```

- [ ] **Step 3: Cell 2 — Zone assignment and conformance**

```python
# Merge assessor data onto parcel geometry (inner join keeps only residential parcels)
residential_gdf = parcels.merge(df, on="LOC_ID", how="inner")

# Assign each parcel to its zoning district via centroid spatial join
# (same technique as illegal_zoning.ipynb)
residential_gdf["parcel_geom"] = residential_gdf["geom"]
residential_gdf["geom"] = residential_gdf.centroid
zoned_gdf = residential_gdf.sjoin(zones[["NAME", "geom"]], how="left")
zoned_gdf["geom"] = zoned_gdf["parcel_geom"]
zoned_gdf = zoned_gdf.drop(columns=["parcel_geom", "index_right"])
zoned_gdf = zoned_gdf.rename(columns={"NAME": "zone"})
zoned_gdf = zoned_gdf[~zoned_gdf["zone"].isna()].copy()

# Attach minimum lot area (sq ft) from the zoning rules CSV
zoned_gdf["lot_area_min_sqft"] = zoned_gdf["zone"].map(zoning_rules["lot area"])

# Non-conforming: lot size is known to be below the zone minimum
# Parcels in zones with no minimum requirement are conforming by default
zoned_gdf["is_nonconforming"] = (
    zoned_gdf["lot_area_min_sqft"].notna()
    & (zoned_gdf["LOT_SIZE_SQFT"] < zoned_gdf["lot_area_min_sqft"])
)
```

- [ ] **Step 4: Cell 3 — Summary stats**

```python
total         = len(zoned_gdf)
nonconforming = int(zoned_gdf["is_nonconforming"].sum())
units_removed = int(zoned_gdf.loc[zoned_gdf["is_nonconforming"], "UNITS"].sum())
pop_removed   = int(units_removed * PEOPLE_PER_UNIT)

print(f"Residential parcels analyzed:         {total:,}")
print(f"Non-conforming (lot size too small):  {nonconforming:,} ({100 * nonconforming / total:.1f}%)")
print(f"Units on non-conforming parcels:      {units_removed:,}")
print(f"Estimated population removed:         {pop_removed:,}  (@ {PEOPLE_PER_UNIT} people/unit)")
```

Expected output: non-conforming percentage should be roughly 40–55% (consistent with `illegal_zoning.ipynb` which found ~48% non-conforming on parcel size).

- [ ] **Step 5: Cell 4 — Interactive map**

```python
# --- Assign each building to its residential parcel via centroid spatial join ---
bldg = buildings.copy()
bldg["bldg_polygon"] = bldg["geom"]
bldg["geom"] = bldg.centroid  # use centroid for sjoin

parcel_cols = ["LOC_ID", "geom", "is_nonconforming", "SITE_ADDR",
               "LOT_SIZE_SQFT", "zone", "lot_area_min_sqft", "UNITS"]

# right join: each building centroid is matched to the parcel that contains it
bldg_assigned = zoned_gdf[parcel_cols].sjoin(bldg, how="right", predicate="contains")

# Restore building polygon geometry; drop buildings not on any residential parcel
bldg_assigned["geom"] = bldg_assigned["bldg_polygon"]
bldg_assigned = bldg_assigned.drop(columns=["bldg_polygon", "index_left"])
bldg_assigned = bldg_assigned.dropna(subset=["LOC_ID"])
bldg_map_gdf = gpd.GeoDataFrame(bldg_assigned, geometry="geom", crs=buildings.crs).to_crs(epsg=4326)

# Parcel outlines layer (for context)
parcel_outlines = zoned_gdf[parcel_cols].to_crs(epsg=4326).copy()

# Human-readable minimum lot size string for tooltip
for gdf in [bldg_map_gdf, parcel_outlines]:
    gdf["lot_area_min_str"] = gdf["lot_area_min_sqft"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "none"
    )

# --- Build Folium map ---
bounds = bldg_map_gdf.total_bounds
center_lat = (bounds[1] + bounds[3]) / 2
center_lon = (bounds[0] + bounds[2]) / 2

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=14,
    tiles=None,
    max_bounds=True,
    min_lat=bounds[1] - 0.01,
    max_lat=bounds[3] + 0.01,
    min_lon=bounds[0] - 0.01,
    max_lon=bounds[2] + 0.01,
)
folium.TileLayer("CartoDB positron", control=False).add_to(m)

# Parcel outlines (underlayer, no fill)
folium.GeoJson(
    parcel_outlines,
    style_function=lambda _: {
        "fillOpacity": 0,
        "color": "#888888",
        "weight": 0.5,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["SITE_ADDR", "LOT_SIZE_SQFT", "zone", "lot_area_min_str", "UNITS"],
        aliases=["Address", "Lot size (sq ft)", "Zone", "Min lot size (sq ft)", "Units"],
    ),
    name="Parcel outlines",
).add_to(m)

# Building footprints: red = non-conforming parcel, green = conforming
def bldg_style(feature):
    return {
        "fillColor": "#d73027" if feature["properties"].get("is_nonconforming") else "#1a9850",
        "color": "white",
        "weight": 0.3,
        "fillOpacity": 0.75,
    }

folium.GeoJson(
    bldg_map_gdf,
    style_function=bldg_style,
    tooltip=folium.GeoJsonTooltip(
        fields=["SITE_ADDR", "LOT_SIZE_SQFT", "zone", "lot_area_min_str", "UNITS"],
        aliases=["Address", "Lot size (sq ft)", "Zone", "Min lot size (sq ft)", "Units"],
    ),
    name="Buildings (red = non-conforming parcel)",
).add_to(m)

folium.LayerControl().add_to(m)
m.save("published/nonconforming_lots.html")
m
```

- [ ] **Step 6: Run the full notebook top to bottom**

In Jupyter: Kernel → Restart & Run All.

Verify:
- Cell 3 prints reasonable numbers: non-conforming percentage 40–55%, units in the thousands, population estimate 2–4× units.
- Cell 4 renders a colored map of Waltham where buildings clearly split between red and green.
- `published/nonconforming_lots.html` is created.

Open `published/nonconforming_lots.html` in a browser and confirm:
- Buildings are colored (red/green).
- Tooltip shows address, lot size, zone, minimum, and units.
- Layer control toggles parcel outlines on/off.

- [ ] **Step 7: Commit**

```bash
git add investigations/neighborhood_character/nonconforming_lots.ipynb published/nonconforming_lots.html
git commit -m "feat: add nonconforming lots notebook and published map"
```
