# Bidirectional Merger Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `fetch_turnover_labels` to catch merger redevelopments (N old parcels → 1 new parcel) by adding a reverse centroid join, carry a `via_merger` flag through to the training data and map tooltip, and add an analysis cell characterizing resulting structure types.

**Architecture:** The existing forward CTE (new centroid within old boundary) is kept as-is; a new reverse CTE (old centroid within new boundary) is unioned with it. `BOOL_AND(via_merger)` ensures a parcel is flagged only when it was exclusively caught by the reverse direction. The function return type changes from `set` to `pd.DataFrame[LOC_ID, via_merger]`, which requires updating every caller.

**Tech Stack:** Python, pandas, geopandas, SQLAlchemy, PostGIS (`ST_Within`, `ST_Centroid`), Folium, Jupyter

---

## Files

- **Modify:** `investigations/development_regression/fetch.py` — `fetch_turnover_labels` SQL + return type
- **Modify:** `investigations/development_regression/notebook.ipynb` — training loop cell, new merger analysis cell, map cell

---

### Task 1: Rewrite centroid path in `fetch_turnover_labels`

**Files:**
- Modify: `investigations/development_regression/fetch.py:169-200`

- [ ] **Step 1: Replace the centroid-path SQL and return statement**

In `fetch.py`, replace the entire `if taxpar_old and taxpar_new:` block (lines 169–200) with:

```python
    if taxpar_old and taxpar_new:
        sql = f"""
            WITH
            old_yb AS (
                SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb
                FROM "{tbl_old}" GROUP BY "LOC_ID"
            ),
            new_yb AS (
                SELECT "LOC_ID", MAX("YEAR_BUILT") AS max_yb
                FROM "{tbl_new}" GROUP BY "LOC_ID"
            ),
            forward AS (
                SELECT DISTINCT
                    tp_old."LOC_ID" AS old_loc_id,
                    o.max_yb        AS old_yb,
                    n.max_yb        AS new_yb,
                    FALSE           AS via_merger
                FROM "{taxpar_new}" tp_new
                JOIN "{taxpar_old}" tp_old
                    ON ST_Within(ST_Centroid(tp_new.geom), tp_old.geom)
                JOIN new_yb n ON n."LOC_ID" = tp_new."LOC_ID"
                JOIN old_yb o ON o."LOC_ID" = tp_old."LOC_ID"
                WHERE tp_new."POLY_TYPE" = 'FEE'
                  AND tp_old."POLY_TYPE" = 'FEE'
            ),
            reverse AS (
                SELECT DISTINCT
                    tp_old."LOC_ID" AS old_loc_id,
                    o.max_yb        AS old_yb,
                    n.max_yb        AS new_yb,
                    TRUE            AS via_merger
                FROM "{taxpar_old}" tp_old
                JOIN "{taxpar_new}" tp_new
                    ON ST_Within(ST_Centroid(tp_old.geom), tp_new.geom)
                JOIN old_yb o ON o."LOC_ID" = tp_old."LOC_ID"
                JOIN new_yb n ON n."LOC_ID" = tp_new."LOC_ID"
                WHERE tp_old."POLY_TYPE" = 'FEE'
                  AND tp_new."POLY_TYPE" = 'FEE'
            ),
            matched AS (
                SELECT * FROM forward
                UNION ALL
                SELECT * FROM reverse
            )
            SELECT
                old_loc_id       AS "LOC_ID",
                BOOL_AND(via_merger) AS via_merger
            FROM matched
            WHERE (new_yb > old_yb AND old_yb > 0 AND new_yb >= {cutoff})
               OR (old_yb = 0 AND new_yb > 0 AND new_yb >= {cutoff})
            GROUP BY old_loc_id
        """
        with engine.connect() as conn:
            result = pd.read_sql(text(sql), conn)
        return result[["LOC_ID", "via_merger"]]
```

- [ ] **Step 2: Update the docstring**

Replace the existing docstring for `fetch_turnover_labels` with:

```python
    """Return a DataFrame of OLD-snapshot LOC_IDs that turned over between two snapshots.

    Columns: LOC_ID (str), via_merger (bool).

    A parcel is considered turned over if:
    - Its MAX(YEAR_BUILT) increased and the old value was > 0 (redeveloped), or
    - Its old MAX(YEAR_BUILT) was 0 and it now has a recent build year (new on vacant).
    In both cases the new YEAR_BUILT must be >= min_year (defaults to yr_new - 3).

    When both taxpar_old and taxpar_new are provided, matching uses two centroid joins:
    - Forward: new parcel centroid within old parcel boundary (subdivisions, renames)
    - Reverse: old parcel centroid within new parcel boundary (mergers)
    via_merger is TRUE only for LOC_IDs exclusively caught by the reverse direction,
    i.e. the absorbed parcels in a merger that the forward direction would miss.
    Falls back to LOC_ID join (via_merger always False) when taxpar tables unavailable.
    """
```

- [ ] **Step 3: Update the return type annotation**

Change the function signature from:

```python
def fetch_turnover_labels(tbl_old: str, tbl_new: str, yr_new: int,
                          min_year: int | None = None,
                          taxpar_old: str | None = None,
                          taxpar_new: str | None = None) -> set:
```

to:

```python
def fetch_turnover_labels(tbl_old: str, tbl_new: str, yr_new: int,
                          min_year: int | None = None,
                          taxpar_old: str | None = None,
                          taxpar_new: str | None = None) -> pd.DataFrame:
```

---

### Task 2: Update fallback path to return DataFrame

**Files:**
- Modify: `investigations/development_regression/fetch.py:202-228`

- [ ] **Step 1: Replace the fallback return statement**

Replace the final line of `fetch_turnover_labels`:

```python
    return set(redeveloped["LOC_ID"]) | set(new_on_vacant["LOC_ID"])
```

with:

```python
    all_ids = set(redeveloped["LOC_ID"]) | set(new_on_vacant["LOC_ID"])
    return pd.DataFrame({"LOC_ID": sorted(all_ids), "via_merger": False})
```

- [ ] **Step 2: Commit fetch.py changes**

```bash
git add investigations/development_regression/fetch.py
git commit -m "Return DataFrame from fetch_turnover_labels with via_merger flag"
```

---

### Task 3: Update the training loop notebook cell

**Files:**
- Modify: `investigations/development_regression/notebook.ipynb` cell `a1b2c3d4-0004-0000-0000-000000000004`

- [ ] **Step 1: Replace the training loop cell source**

The cell has three lines that reference `labels` as a set — fix all of them and add `via_merger` tracking:

```python
frames = []
# Accumulates every LOC_ID that has turned over so far; these are excluded
# from all subsequent snapshot pairs and from the 2025 scoring.
ever_redeveloped = set()

# Use pairs through 2022→2023; hold out 2025 and 2026 for scoring
training_pairs = [(tbl_old, tbl_new, yr_old, yr_new, taxpar_old, taxpar_new)
                  for tbl_old, tbl_new, yr_old, yr_new, taxpar_old, taxpar_new
                  in fetch.CONSECUTIVE_PAIRS
                  if yr_new <= 2023]

for tbl_old, tbl_new, yr_old, yr_new, taxpar_old, taxpar_new in training_pairs:
    print(f"Fetching {yr_old}→{yr_new}...", end=" ", flush=True)
    features = fetch.fetch_features_for_snapshot(tbl_old, yr_old, par_table=taxpar_old)
    labels = fetch.fetch_turnover_labels(
        tbl_old, tbl_new, yr_new,
        taxpar_old=taxpar_old, taxpar_new=taxpar_new,
    )

    # Drop parcels already redeveloped in any prior period
    features = features[~features["LOC_ID"].isin(ever_redeveloped)]

    features["turnover"] = features["LOC_ID"].isin(labels["LOC_ID"]).astype(int)
    features = features.merge(labels[["LOC_ID", "via_merger"]], on="LOC_ID", how="left")
    features["via_merger"] = features["via_merger"].fillna(False)
    features["label_year"] = yr_new
    frames.append(features)
    n_pos = features["turnover"].sum()
    n_merger = (features["via_merger"] & (features["turnover"] == 1)).sum()
    print(f"{len(features):,} parcels, {n_pos} turned over ({n_pos/len(features)*100:.1f}%), {n_merger} via merger")

    ever_redeveloped.update(set(labels["LOC_ID"]))

data = pd.concat(frames, ignore_index=True)
print(f"\nTotal rows: {len(data):,} | Positives: {data['turnover'].sum()} ({data['turnover'].mean()*100:.2f}%)")
print(f"Via merger positives: {(data['via_merger'] & (data['turnover'] == 1)).sum()}")
print(f"Parcels excluded as previously redeveloped: {len(ever_redeveloped)}")
```

- [ ] **Step 2: Verify the cell runs**

Run the training loop cell. Expected output format (counts will differ once centroid matching catches new mergers):

```
Fetching 2011→2014... 11,868 parcels, 40 turned over (0.3%), N via merger
...
Via merger positives: N
```

Confirm `via_merger` column exists in `data` and has some `True` values for positive rows.

---

### Task 4: Add merger structure analysis cell

**Files:**
- Modify: `investigations/development_regression/notebook.ipynb` — insert new cell after `a1b2c3d4-0004-0000-0000-000000000004`

- [ ] **Step 1: Insert the merger analysis cell**

Insert a new markdown cell after the training loop cell, then a code cell:

Markdown:
```markdown
## Merger redevelopment analysis

Parcels flagged `via_merger` were absorbed into a merged lot that then showed a
new `YEAR_BUILT`. For each such parcel we look up what was built on the resulting
merged lot (USE_CODE, building area, units) by finding the new-snapshot parcel
whose boundary contains the old centroid.
```

Code cell:

```python
from sqlalchemy import text as _text
from data.connect_db import get_db as _get_db

merger_outcomes = []

for tbl_old, tbl_new, yr_old, yr_new, taxpar_old, taxpar_new in training_pairs:
    if taxpar_old is None or taxpar_new is None:
        continue
    pair_key = f"{yr_old}→{yr_new}"
    pair_data = data[(data["label_year"] == yr_new) & data["via_merger"] & (data["turnover"] == 1)]
    if pair_data.empty:
        continue
    ids = tuple(pair_data["LOC_ID"].tolist())
    if len(ids) == 1:
        ids_sql = f"('{ids[0]}')"
    else:
        ids_sql = str(ids)

    sql = _text(f"""
        SELECT
            tp_old."LOC_ID"                   AS old_loc_id,
            MIN(a_new."USE_CODE"::integer)     AS use_code,
            MAX(a_new."BLD_AREA")              AS bld_area,
            SUM(a_new."UNITS")                 AS units,
            MAX(a_new."SITE_ADDR")             AS site_addr
        FROM "{taxpar_old}" tp_old
        JOIN "{taxpar_new}" tp_new
            ON ST_Within(ST_Centroid(tp_old.geom), tp_new.geom)
        JOIN "{tbl_new}" a_new ON a_new."LOC_ID" = tp_new."LOC_ID"
        WHERE tp_old."POLY_TYPE" = 'FEE'
          AND tp_new."POLY_TYPE" = 'FEE'
          AND tp_old."LOC_ID" IN {ids_sql}
        GROUP BY tp_old."LOC_ID"
    """)
    engine = _get_db()
    with engine.connect() as conn:
        result = pd.read_sql(sql, conn)
    result["pair"] = pair_key
    merger_outcomes.append(result)

if merger_outcomes:
    merger_df = pd.concat(merger_outcomes, ignore_index=True)
    print(f"{len(merger_df)} merger redevelopments with outcome data\n")
    print("USE_CODE distribution (101=SFH, 102=condo, 104=2-fam, 105=3-fam):")
    print(merger_df["use_code"].value_counts().to_string())
    print(f"\nMedian resulting BLD_AREA: {merger_df['bld_area'].median():,.0f} sq ft")
    print(f"Median resulting UNITS:    {merger_df['units'].median():.0f}")
    print()
    print(merger_df[["pair", "old_loc_id", "site_addr", "use_code", "bld_area", "units"]]
          .sort_values("bld_area", ascending=False)
          .to_string(index=False))
else:
    print("No merger outcomes found — check that training pairs have taxpar tables.")
```

- [ ] **Step 2: Run the analysis cell and note findings**

Run the cell. Check whether `use_code == 101` (SFH) dominates and whether `bld_area` median is notably higher than the city-wide residential median (~1,600 sq ft).

---

### Task 5: Update map cell

**Files:**
- Modify: `investigations/development_regression/notebook.ipynb` cell `a1b2c3d4-0015-0000-0000-000000000015`

- [ ] **Step 1: Update the `actual_ids` block**

In the map cell, replace:

```python
actual_ids = fetch.fetch_turnover_labels(
    "M308Assess_CY23_FY23", "M308Assess_CY26_FY26", 2026, min_year=2024,
    taxpar_old="M308TaxPar_CY23_FY23",  # no cy26 taxpar; falls back to LOC_ID for new side
)
actual_gdf = (
    geom[geom["LOC_ID"].isin(actual_ids)]
    .merge(scored[["LOC_ID", "SITE_ADDR"]], on="LOC_ID", how="left")
    .to_crs(epsg=4326)
)
print(f"{len(actual_gdf)} parcels actually redeveloped (YEAR_BUILT 2024–2026)")
```

with:

```python
actual_df = fetch.fetch_turnover_labels(
    "M308Assess_CY23_FY23", "M308Assess_CY26_FY26", 2026, min_year=2024,
    taxpar_old="M308TaxPar_CY23_FY23",  # no cy26 taxpar; falls back to LOC_ID for new side
)
actual_gdf = (
    geom[geom["LOC_ID"].isin(actual_df["LOC_ID"])]
    .merge(scored[["LOC_ID", "SITE_ADDR"]], on="LOC_ID", how="left")
    .merge(actual_df[["LOC_ID", "via_merger"]], on="LOC_ID", how="left")
    .to_crs(epsg=4326)
)
actual_gdf["via_merger"] = actual_gdf["via_merger"].fillna(False)
print(f"{len(actual_gdf)} parcels actually redeveloped (YEAR_BUILT 2024–2026), "
      f"{actual_gdf['via_merger'].sum()} via merger")
```

- [ ] **Step 2: Add `via_merger` to the actual layer tooltip**

Replace the `actual_layer` GeoJson tooltip:

```python
    tooltip=folium.GeoJsonTooltip(
        fields=["SITE_ADDR", "LOC_ID"],
        aliases=["Address", "LOC ID"],
    ),
```

with:

```python
    tooltip=folium.GeoJsonTooltip(
        fields=["SITE_ADDR", "LOC_ID", "via_merger"],
        aliases=["Address", "LOC ID", "Merged lot?"],
    ),
```

- [ ] **Step 3: Run the map cell and verify**

Run the map cell. Confirm:
- Print line shows counts without error
- `via_merger` column appears in the actual redevelopment tooltip when clicking a cyan parcel
- Map saves to `published/development_regression.html`

---

### Task 6: Commit notebook changes

- [ ] **Step 1: Commit**

```bash
git add investigations/development_regression/notebook.ipynb
git commit -m "Add via_merger tracking and merger structure analysis to regression notebook"
```
