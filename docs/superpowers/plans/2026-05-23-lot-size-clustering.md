# Lot Size Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an investigation that fetches residential parcel lot sizes from the 2025 assessor table, bins them to the nearest 500 sq ft, and produces a summary histogram and an interactive Folium map saved to `published/lot_size_clustering.html`.

**Architecture:** A `fetch.py` module handles all DB access and exposes one public function (`fetch_residential_lot_sizes`) plus a private testable helper (`_bin_lot_sizes`). The notebook imports from `fetch.py` and uses a separately fetched parcel geometry table to build the map. Tests cover only the pure transformation logic.

**Tech Stack:** Python 3.14, pandas, geopandas, SQLAlchemy, Folium, branca, matplotlib, pytest, PostGIS (MassGIS schema).

---

### Task 1: Scaffold the package and confirm the LOT_SIZE column exists

**Files:**
- Create: `investigations/lot_size_clustering/__init__.py`

- [ ] **Step 1: Create the package init file**

```python
# investigations/lot_size_clustering/__init__.py
# (empty — matches pattern of other investigation packages)
```

- [ ] **Step 2: Verify LOT_SIZE exists in the 2025 assessment table**

Run this in a Python REPL or a throwaway notebook cell (do not commit):

```python
from sqlalchemy import text
from data.connect_db import get_db

engine = get_db()
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'M308Assess_CY25_FY25'
        ORDER BY ordinal_position
    """))
    for row in result:
        print(row)
```

Expected: you see a row with `column_name = 'LOT_SIZE'`. If the column name differs, update every reference to `LOT_SIZE` in subsequent tasks.

- [ ] **Step 3: Commit the scaffold**

```bash
git add investigations/lot_size_clustering/__init__.py
git commit -m "feat: scaffold lot_size_clustering investigation package"
```

---

### Task 2: Write and test the binning helper

**Files:**
- Create: `tests/test_lot_size_clustering.py`
- Create: `investigations/lot_size_clustering/fetch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lot_size_clustering.py
import pandas as pd
import pytest
from investigations.lot_size_clustering.fetch import _bin_lot_sizes


def test_bin_lot_sizes_rounds_to_nearest_500():
    df = pd.DataFrame({
        "LOT_SIZE": [100, 400, 600, 900, 7500, 10000]
    })
    result = _bin_lot_sizes(df)
    assert list(result["lot_size_bin"]) == [0, 500, 500, 1000, 7500, 10000]


def test_bin_lot_sizes_does_not_mutate_input():
    df = pd.DataFrame({"LOT_SIZE": [1000]})
    _bin_lot_sizes(df)
    assert "lot_size_bin" not in df.columns


def test_bin_lot_sizes_preserves_other_columns():
    df = pd.DataFrame({"LOT_SIZE": [6000], "LOC_ID": ["F_123_456"], "SITE_ADDR": ["1 MAIN ST"]})
    result = _bin_lot_sizes(df)
    assert "LOC_ID" in result.columns
    assert "SITE_ADDR" in result.columns
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
uv run pytest tests/test_lot_size_clustering.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` because `fetch.py` doesn't exist yet.

- [ ] **Step 3: Create `fetch.py` with the helper**

```python
# investigations/lot_size_clustering/fetch.py
import pandas as pd
import geopandas as gpd

from sqlalchemy import text
from data.connect_db import get_db


def _bin_lot_sizes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lot_size_bin"] = (df["LOT_SIZE"] / 500).round() * 500
    return df


def fetch_residential_lot_sizes() -> pd.DataFrame:
    raise NotImplementedError


def fetch_parcel_geometry() -> gpd.GeoDataFrame:
    raise NotImplementedError
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/test_lot_size_clustering.py -v
```

Expected:
```
tests/test_lot_size_clustering.py::test_bin_lot_sizes_rounds_to_nearest_500 PASSED
tests/test_lot_size_clustering.py::test_bin_lot_sizes_does_not_mutate_input PASSED
tests/test_lot_size_clustering.py::test_bin_lot_sizes_preserves_other_columns PASSED
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_lot_size_clustering.py investigations/lot_size_clustering/fetch.py
git commit -m "feat: add lot_size_clustering fetch scaffold and binning tests"
```

---

### Task 3: Implement the two DB fetch functions

**Files:**
- Modify: `investigations/lot_size_clustering/fetch.py`

- [ ] **Step 1: Replace both `NotImplementedError` stubs with real implementations**

Replace the entire contents of `investigations/lot_size_clustering/fetch.py` with:

```python
# investigations/lot_size_clustering/fetch.py
import pandas as pd
import geopandas as gpd

from sqlalchemy import text
from data.connect_db import get_db

_RESIDENTIAL_FILTER = (
    '"USE_CODE"::integer < 200'
    ' AND ("USE_CODE"::integer < 130 OR "USE_CODE"::integer > 140)'
)


def _bin_lot_sizes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lot_size_bin"] = (df["LOT_SIZE"] / 500).round() * 500
    return df


def fetch_residential_lot_sizes() -> pd.DataFrame:
    """Return residential parcels with lot sizes from the 2025 assessment snapshot.

    Filters to USE_CODE < 200 (excl. 130-140) and LOT_SIZE > 0.
    Adds a `lot_size_bin` column: lot size rounded to the nearest 500 sq ft.
    """
    engine = get_db()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                f'SELECT "LOC_ID", "LOT_SIZE", "USE_CODE", "UNITS", "SITE_ADDR"'
                f' FROM "M308Assess_CY25_FY25"'
                f' WHERE {_RESIDENTIAL_FILTER}'
                f'   AND "LOT_SIZE" > 0'
            ),
            conn,
        )
    return _bin_lot_sizes(df)


def fetch_parcel_geometry() -> gpd.GeoDataFrame:
    """Return all parcel geometries from the 2025 snapshot."""
    engine = get_db()
    return gpd.read_postgis(
        'SELECT "LOC_ID", "geom" FROM "M308TaxPar_CY25_FY25"',
        engine,
        geom_col="geom",
    )
```

- [ ] **Step 2: Confirm the existing tests still pass**

```bash
uv run pytest tests/test_lot_size_clustering.py -v
```

Expected: all 3 tests PASS (no regressions from the rewrite).

- [ ] **Step 3: Smoke-test both functions return data**

Run in a Python REPL or throwaway notebook cell:

```python
from investigations.lot_size_clustering.fetch import fetch_residential_lot_sizes, fetch_parcel_geometry

df = fetch_residential_lot_sizes()
print(df.shape)           # expect (N, 6) with N in the thousands
print(df.dtypes)
print(df["lot_size_bin"].value_counts().head(10))

gdf = fetch_parcel_geometry()
print(gdf.shape)          # expect all parcels (~16k rows)
print(gdf.crs)
```

Expected: both calls return non-empty results, `lot_size_bin` is numeric, geometry CRS is NAD83/Massachusetts.

- [ ] **Step 4: Commit**

```bash
git add investigations/lot_size_clustering/fetch.py
git commit -m "feat: implement fetch_residential_lot_sizes and fetch_parcel_geometry"
```

---

### Task 4: Write the notebook

**Files:**
- Create: `investigations/lot_size_clustering/notebook.ipynb`

The notebook has four cells. Create a new Jupyter notebook and add the cells below in order.

- [ ] **Step 1: Cell 1 — Imports and data fetch**

```python
import matplotlib.pyplot as plt
import folium
import branca.colormap as cm
import pandas as pd

from investigations.lot_size_clustering.fetch import (
    fetch_residential_lot_sizes,
    fetch_parcel_geometry,
)

df = fetch_residential_lot_sizes()
```

- [ ] **Step 2: Cell 2 — Summary stats**

```python
print(f"Residential parcels with recorded lot size: {len(df):,}")
print(f"Min lot size:    {df['LOT_SIZE'].min():,.0f} sq ft")
print(f"Median lot size: {df['LOT_SIZE'].median():,.0f} sq ft")
print(f"Max lot size:    {df['LOT_SIZE'].max():,.0f} sq ft")
print(f"Modal bin:       {df['lot_size_bin'].mode().iloc[0]:,.0f} sq ft")
```

- [ ] **Step 3: Cell 3 — Histogram**

```python
# Cap at 99th percentile to keep the common range readable
p99 = df["LOT_SIZE"].quantile(0.99)
plot_df = df[df["LOT_SIZE"] <= p99].copy()

bin_counts = (
    plot_df.groupby("lot_size_bin")
    .size()
    .reset_index(name="count")
    .sort_values("lot_size_bin")
)

fig, ax = plt.subplots(figsize=(14, 5))
ax.bar(
    bin_counts["lot_size_bin"],
    bin_counts["count"],
    width=450,
    color="steelblue",
    edgecolor="white",
)
ax.set_xlabel("Lot size bin (sq ft, nearest 500)")
ax.set_ylabel("Number of parcels")
ax.set_title("Residential lot size distribution — Waltham 2025 (capped at 99th percentile)")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
```

- [ ] **Step 4: Cell 4 — Interactive map**

```python
all_parcels = fetch_parcel_geometry()

# Join lot size bins onto geometry; parcels with no assessment record get no fill
map_gdf = all_parcels.merge(
    df[["LOC_ID", "LOT_SIZE", "lot_size_bin", "SITE_ADDR", "UNITS"]],
    on="LOC_ID",
    how="left",
).to_crs(epsg=4326)

map_gdf["lot_size_bin_str"] = map_gdf["lot_size_bin"].apply(
    lambda x: f"{x:,.0f}" if pd.notna(x) else "n/a"
)

# Color scale: light yellow → dark blue, capped at the 95th percentile of bins
vmax = df["lot_size_bin"].quantile(0.95)
colormap = cm.LinearColormap(
    colors=["#ffffcc", "#41b6c4", "#253494"],
    vmin=0,
    vmax=vmax,
    caption="Lot size bin (sq ft)",
)

def style_fn(feature):
    val = feature["properties"].get("lot_size_bin")
    if val is None or pd.isna(val):
        return {"fillColor": "#cccccc", "color": "white", "weight": 0.3, "fillOpacity": 0.4}
    return {
        "fillColor": colormap(min(val, vmax)),
        "color": "white",
        "weight": 0.3,
        "fillOpacity": 0.75,
    }

bounds = map_gdf.total_bounds
center_lat = (bounds[1] + bounds[3]) / 2
center_lon = (bounds[0] + bounds[2]) / 2

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=13,
    tiles=None,
    max_bounds=True,
    min_lat=bounds[1] - 0.01,
    max_lat=bounds[3] + 0.01,
    min_lon=bounds[0] - 0.01,
    max_lon=bounds[2] + 0.01,
)
folium.TileLayer("CartoDB positron", control=False).add_to(m)

folium.GeoJson(
    map_gdf,
    style_function=style_fn,
    tooltip=folium.GeoJsonTooltip(
        fields=["SITE_ADDR", "LOT_SIZE", "lot_size_bin_str", "UNITS"],
        aliases=["Address", "Lot size (sq ft)", "Bin (sq ft)", "Units"],
    ),
    name="Lot size by parcel",
).add_to(m)

colormap.add_to(m)
folium.LayerControl().add_to(m)

m.save("published/lot_size_clustering.html")
m
```

- [ ] **Step 5: Run the full notebook top to bottom**

In Jupyter: Kernel → Restart & Run All.

Verify:
- Cell 2 prints reasonable numbers (median should be in the 5,000–15,000 sq ft range for a suburban city).
- Cell 3 produces a bar chart with the bulk of parcels in the lower bins.
- Cell 4 renders a colored map of Waltham and saves `published/lot_size_clustering.html`.

Open `published/lot_size_clustering.html` in a browser and confirm parcels are colored, the tooltip shows address/lot size/bin/units, and the legend is visible.

- [ ] **Step 6: Commit**

```bash
git add investigations/lot_size_clustering/notebook.ipynb published/lot_size_clustering.html
git commit -m "feat: add lot size clustering notebook and published map"
```
