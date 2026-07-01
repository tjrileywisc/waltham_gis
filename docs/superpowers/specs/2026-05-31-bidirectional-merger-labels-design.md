# Design: Bidirectional Centroid Matching for Merger Redevelopment Labels

**Date:** 2026-05-31
**Branch:** show-redevelopment-actual

## Problem

`fetch_turnover_labels` uses one-directional centroid matching: it finds new parcels
whose centroid falls within an old parcel's boundary, then checks whether YEAR_BUILT
increased. This correctly labels subdivisions and simple LOC_ID renames.

It misses **mergers** (N old parcels → 1 new parcel): the new parcel centroid falls
inside only one of the old boundaries, so the other N-1 old LOC_IDs are silently
labeled negative even when the merged lot was developed.

## Solution

Extend `fetch_turnover_labels` with a **reverse CTE** — old parcel centroid within
new parcel boundary — and union it with the existing forward CTE. The same
YEAR_BUILT cutoff applies to both directions. A `BOOL_AND(via_merger)` aggregation
flags a LOC_ID as `via_merger = TRUE` only when it was exclusively caught by the
reverse direction (i.e., it is one of the "extra" absorbed parcels, not the primary
parcel already matched by the forward direction).

The fallback path (no taxpar geometry tables) returns the same DataFrame shape with
`via_merger = False` for all rows — no merger detection is possible without geometry.

## Data Layer Changes (`fetch.py`)

### `fetch_turnover_labels` signature
Unchanged. New return type: `pd.DataFrame` with columns `["LOC_ID", "via_merger"]`
instead of `set`. This is a breaking change; all callers must be updated.

### SQL structure (centroid path)
```sql
WITH
old_yb AS (...),
new_yb AS (...),
forward AS (
    -- existing: new centroid within old boundary
    SELECT ..., FALSE AS via_merger
    FROM "{taxpar_new}" tp_new
    JOIN "{taxpar_old}" tp_old ON ST_Within(ST_Centroid(tp_new.geom), tp_old.geom)
    ...
),
reverse AS (
    -- new: old centroid within new boundary (catches merger parcels)
    SELECT ..., TRUE AS via_merger
    FROM "{taxpar_old}" tp_old
    JOIN "{taxpar_new}" tp_new ON ST_Within(ST_Centroid(tp_old.geom), tp_new.geom)
    ...
),
matched AS (SELECT * FROM forward UNION ALL SELECT * FROM reverse)
SELECT
    old_loc_id AS "LOC_ID",
    BOOL_AND(via_merger) AS via_merger   -- TRUE only if exclusively reverse-matched
FROM matched
WHERE (new_yb > old_yb AND old_yb > 0 AND new_yb >= {cutoff})
   OR (old_yb = 0 AND new_yb > 0 AND new_yb >= {cutoff})
GROUP BY old_loc_id
```

### Caller updates
| Location | Before | After |
|---|---|---|
| Training loop — label check | `features["LOC_ID"].isin(labels)` | `features["LOC_ID"].isin(labels["LOC_ID"])` |
| Training loop — ever_redeveloped | `ever_redeveloped.update(labels)` | `ever_redeveloped.update(set(labels["LOC_ID"]))` |
| Map cell — actual_ids | `geom["LOC_ID"].isin(actual_ids)` | `geom["LOC_ID"].isin(actual_df["LOC_ID"])` |

## Notebook Changes

### Training loop cell
After fetching labels, merge `via_merger` onto the features DataFrame for
analysis. It is **not** added to `feature_cols` — it is a label artifact
(only populated for positives) and would cause data leakage if used as a
training feature.

```python
features["turnover"] = features["LOC_ID"].isin(labels["LOC_ID"]).astype(int)
features = features.merge(labels[["LOC_ID", "via_merger"]], on="LOC_ID", how="left")
features["via_merger"] = features["via_merger"].fillna(False)
```

### Merger structure analysis cell (new)
After the training data is assembled, a summary cell joins `via_merger = True`
positives back to the *new* snapshot's assessment data to inspect resulting
structure type: USE_CODE distribution, median BLD_AREA, UNITS. Tests the
hypothesis that lot mergers typically produce large single-family homes.

### Map cell
- `actual_ids` (set) → `actual_df` (DataFrame); geometry filter uses
  `actual_df["LOC_ID"]`
- `via_merger` added to `actual_gdf` for tooltip display ("Merged lot?" field)
- No layer color changes; orange disappeared-parcels layer remains as-is

## Map Behavior After Change

| Parcel type | Layer(s) shown |
|---|---|
| Redeveloped, same LOC_ID | Cyan outline |
| Merger redevelopment (via_merger) | Orange dashed (geometry from 2023 taxpar; old LOC_ID absent from 2025 geom) |
| Disappeared, no construction | Orange dashed only |

Merger redevelopments appear orange-only (not cyan) because their old LOC_IDs
are absent from the 2025 geometry table used to draw the cyan layer. This is
intentional — orange means "something changed here" and is informative without
requiring a third color.

## Out of Scope
- Adding `via_merger` as a model training feature
- Changing the `fetch_disappeared_parcels` function
- Buffer-distance fallback for parcels with no overlapping new geometry
