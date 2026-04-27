
# Description

The goal of this repository is to communicate what's going on with the built environment in Waltham, MA using publicly available data.
The intended audience is city government and members of the community.

## Workflow

Most analysis should be carried out in Jupyter notebooks.

Plots are greatly appreciated (especially interactive ones) and anything that can be mapped.

## Style

Don't change the case of variables from the PostGIS database, I sometimes use QGIS in my workflow and don't want to be confused with joins.

## Tech stack

Code is written in python. Dependencies are managed with `uv`. Data is stored in a PostGRES/PostGIS database.

## Quirks to note

YEAR_BUILT may be empty or 0. In such cases, assume the value is '$CURRENT_YEAR - 75' where $CURRENT_YEAR should be the year associated with the dataset.

Residential land uses are tracked with USE_CODE values < 200, excluding the special-use codes 130-140.

## Data sources

Data comes from MassGIS primarily, but also the US Census.
