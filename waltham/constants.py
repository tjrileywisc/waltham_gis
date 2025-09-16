
SQ_FT_PER_ACRE = 43560

FT_PER_STORY = 14

# density required by MBTA Communities act, units per acre
MBTA_DENSITY = 15

# MassGIS CRS datum

# N.B. this is referenced on their webpage, but their API suggests EPSG:4326 by default, which is WGS84 (a global CRS)
# vs. this, which is a CRS for North America instead
MASSGIS_CRS = "NAD83"