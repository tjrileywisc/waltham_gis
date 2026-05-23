# Lot Size Clustering Design

**Date:** 2026-05-23  
**Branch:** land-value-clustering  
**Status:** Approved

## Goal

Visualize the distribution of residential lot sizes in Waltham by binning each parcel to the nearest 500 sq ft. This is the first step toward understanding how many residential parcels are non-conforming relative to their zone's minimum lot area, and what the city would look like if non-conforming lots were merged to meet minimums.

This notebook focuses only on the distribution. Zoning conformance analysis and merge modeling are follow-up investigations.

## Scope

- **Parcels included:** Residential use codes only — `USE_CODE < 200`, excluding 130–140.
- **Data source:** `M308Assess_CY25_FY25` (2025 snapshot; 2026 has known issues with `UNITS`).
- **Lot size field:** `LOT_SIZE` column in the assessment table (MassGIS-standardized, sq ft).
- **Filtering:** Records where `LOT_SIZE` is 0 or null are excluded.

## Investigation Structure

```
investigations/lot_size_clustering/
    fetch.py       # data access
    notebook.ipynb # analysis and visualization
```

## Data Flow

### `fetch.py`

One public function: `fetch_residential_lot_sizes() -> pd.DataFrame`

- Queries `M308Assess_CY25_FY25` for `LOC_ID`, `LOT_SIZE`, `USE_CODE`, `UNITS`, `SITE_ADDR`.
- Filters: residential USE_CODE (< 200, excl 130–140), `LOT_SIZE > 0`.
- Adds `lot_size_bin` column: `(LOT_SIZE / 500).round() * 500` (nearest 500 sq ft).
- Returns a plain DataFrame (no geometry).

### `notebook.ipynb`

**Section 1 — Summary stats**  
Total residential parcels with a recorded lot size. Min, max, median lot size. Modal bin.

**Section 2 — Histogram**  
Matplotlib bar chart. X-axis: lot-size bin labels ("0–500", "500–1,000", …). Y-axis: parcel count. Useful for seeing where the mass of the distribution sits.

**Section 3 — Interactive map**  
Folium choropleth. Geometry from `M308TaxPar_CY25_FY25`, joined to the fetch result on `LOC_ID`. Each parcel colored by `lot_size_bin`. Tooltip: `SITE_ADDR`, `LOT_SIZE`, `lot_size_bin`. Saved to `published/lot_size_clustering.html`.

## Key Implementation Notes

- The residential USE_CODE filter is `USE_CODE::integer < 200 AND (USE_CODE::integer < 130 OR USE_CODE::integer > 140)` — consistent with the rest of the codebase.
- The `LOT_SIZE` column is confirmed present in the 2025 assessment table.
- Parcel geometry is fetched separately (as in `development_turnover/fetch.py`) and merged in the notebook.
- The `lot_size_bin` label on the map should be a string for Folium compatibility.

## Out of Scope (Follow-up)

- Zoning district lookup and minimum lot area conformance check.
- Merging non-conforming adjacent lots and counting surviving parcels.
- Population impact estimation.
