# Nonconforming Lots Impact Design

**Date:** 2026-05-23
**Branch:** lot-size-clustering
**Status:** Approved

## Goal

Identify residential parcels in Waltham that are non-conforming with their zoning district's minimum lot size requirement, then visualize and quantify what the city would lose if those non-conforming parcels were cleared: buildings removed, housing units lost, and estimated population displaced.

This is the direct follow-up to `binned_development.ipynb`, which showed the lot-size distribution. This notebook answers the conformance question: which parcels fall below the bar, and what's actually on them?

## Scope

- **Parcels included:** Residential use codes only — `USE_CODE < 200`, excluding 130–140.
- **Lot size source:** `LOT_SIZE` from `M308Assess_CY25_FY25`, converted from acres to sq ft (already in `fetch_residential_lot_sizes()`).
- **Minimum lot size source:** `data/zoning_rules_table.csv`, column `lot area` (sq ft). Zones with no minimum (NaN) are treated as conforming.
- **Zone assignment:** Parcel centroid spatial join to `WalthamZoning` table (same method as `illegal_zoning.ipynb`).
- **Buildings:** `structures_poly_308` footprints, assigned to parcels via building centroid within parcel polygon.
- **Population estimate:** Units on non-conforming parcels × 2.4 (Waltham Census average household size).

## Investigation Structure

```
investigations/neighborhood_character/
    fetch.py            # add fetch_waltham_zoning() and fetch_building_footprints()
    nonconforming_lots.ipynb   # new notebook
published/
    nonconforming_lots.html    # output map
```

## Data Flow

### fetch.py additions

Two new thin functions; existing functions unchanged:

**`fetch_waltham_zoning() -> gpd.GeoDataFrame`**
- Queries `WalthamZoning` for `id`, `NAME`, `geom`.
- Returns a GeoDataFrame in the native CRS (EPSG:26986, NAD83/Massachusetts).

**`fetch_building_footprints() -> gpd.GeoDataFrame`**
- Queries `structures_poly_308` for `geom`, `SHAPE_AREA`.
- Returns a GeoDataFrame in EPSG:26986.

### nonconforming_lots.ipynb

**Cell 0 — Markdown intro**
Frames the counterfactual: the city's zoning code sets minimum lot sizes that a large share of existing residential parcels don't meet. What would the city look like if we actually enforced that and cleared those parcels?

**Cell 1 — Data fetch**
```python
df        = fetch_residential_lot_sizes()     # LOC_ID, LOT_SIZE_SQFT, USE_CODE, UNITS, SITE_ADDR
parcels   = fetch_parcel_geometry()           # LOC_ID, geom
zones     = fetch_waltham_zoning()            # NAME, geom
buildings = fetch_building_footprints()       # geom, SHAPE_AREA
zoning_rules = pd.read_csv("data/zoning_rules_table.csv").set_index("District")
```

**Cell 2 — Zone assignment and conformance**
1. Merge `df` onto `parcels` (inner join on `LOC_ID`) → `residential_gdf`
2. Save polygon geometry as `parcel_geom` column; replace `geom` with `residential_gdf.centroid`; `sjoin` to `zones` (how="left") → assign `zone` column from `NAME`
3. Restore `geom = parcel_geom`; drop `parcel_geom` and `index_right`; drop rows where `zone` is NaN
4. Map each zone to its minimum lot area from `zoning_rules["lot area"]`; zones with NaN minimum → `lot_area_min_sqft = NaN`
5. `is_nonconforming = LOT_SIZE_SQFT < lot_area_min_sqft` (NaN minimum → False)

**Cell 3 — Summary stats**
```
Residential parcels analyzed:      N
Non-conforming (lot size):         N (X%)
Units on non-conforming parcels:   N
Estimated population removed:      N  (@ 2.4 people/unit)
```

**Cell 4 — Interactive map**
1. Building-to-parcel assignment: use building centroid `sjoin` with `residential_gdf` (predicate="within") to inherit `is_nonconforming`, `SITE_ADDR`, `LOT_SIZE_SQFT`, `zone`, `lot_area_min_sqft`, `UNITS`.
2. Convert both building GeoDataFrame and parcel GeoDataFrame to EPSG:4326.
3. Folium map with two GeoJson layers:
   - **Building footprints** (primary): red fill if `is_nonconforming`, green if conforming. Tooltip: address, lot size (sq ft), zone, minimum (sq ft), units.
   - **Parcel outlines** (underlayer, no fill): thin grey borders for context, togglable.
4. `LayerControl` to toggle each layer.
5. Save to `published/nonconforming_lots.html`.

## Key Implementation Notes

- The centroid sjoin pattern (set `geom` to centroid, sjoin, restore polygon) matches `illegal_zoning.ipynb` exactly.
- `zoning_rules["lot area"]` is already in sq ft in the CSV; no conversion needed.
- Some parcels may not spatially fall within any zone polygon (edge cases near city boundary); drop these.
- Buildings that do not fall within any residential parcel (e.g. commercial buildings, standalone garages) will be excluded by the inner sjoin — that is intentional.
- The `SHAPE_AREA` column from `structures_poly_308` is in m²; it is fetched for potential future use but not used in this notebook's statistics (units and population come from the assessor record).
- Average household size 2.4 is sourced from the US Census ACS 5-year estimates for Waltham.

## Out of Scope (Follow-up)

- Merging adjacent non-conforming lots to meet minimums and counting surviving parcels.
- Modeling what compliant replacement structures would look like (height, units).
- Disaggregating population impact by housing type (single-family vs. multi-family).
