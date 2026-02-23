from qgis.core import *
from qgis.PyQt.QtCore import QVariant

# -----------------------------
# USER SETTINGS
# -----------------------------
layer_name = "M308TaxPar_CY25_FY25"
id_field = "id"
target_id = 12164
adjacent_ids = [6876, 6842]
buffer_distance = 22.9  # 500 feet in meters

# -----------------------------
# LOAD LAYER
# -----------------------------
layer = QgsProject.instance().mapLayersByName(layer_name)[0]

# -----------------------------
# GET TARGET PARCEL
# -----------------------------
target_feat = next(layer.getFeatures(
    QgsFeatureRequest().setFilterExpression(f'"{id_field}" = {target_id}')
))
target_geom = target_feat.geometry()

# -----------------------------
# GET ADJACENT PARCELS
# -----------------------------
adj_expr = f'"{id_field}" IN ({",".join(map(str, adjacent_ids))})'
adj_feats = list(layer.getFeatures(
    QgsFeatureRequest().setFilterExpression(adj_expr)
))

adj_geoms = [f.geometry() for f in adj_feats]
adj_union = QgsGeometry.unaryUnion(adj_geoms)

# -----------------------------
# CONVERT TO LINEWORK (MULTIPOLYGON SAFE)
# -----------------------------
target_lines = target_geom.convertToType(QgsWkbTypes.LineGeometry, False)
adj_lines = adj_union.convertToType(QgsWkbTypes.LineGeometry, False)

# -----------------------------
# FIND SHARED EDGE
# -----------------------------
shared_edge = target_lines.intersection(adj_lines)

if shared_edge.isEmpty():
    raise Exception("No shared boundary found between parcels.")

# -----------------------------
# BUFFER SHARED EDGE
# -----------------------------
buffer_geom = shared_edge.buffer(buffer_distance, 20)

# Remove portion overlapping target parcel
buffer_no_target = buffer_geom.difference(target_geom)

# Keep only portion inside adjacent parcels
final_buffer = buffer_no_target.intersection(adj_union)

if final_buffer.isEmpty():
    raise Exception("Buffer created but does not fall within adjacent parcels.")

# -----------------------------
# CREATE OUTPUT LAYER
# -----------------------------
result_layer = QgsVectorLayer(
    f"Polygon?crs={layer.crs().authid()}",
    "Parcel_12164_Buffer_Into_6876_6842",
    "memory"
)

provider = result_layer.dataProvider()
provider.addAttributes([QgsField("source_id", QVariant.Int)])
result_layer.updateFields()

feat = QgsFeature()
feat.setGeometry(final_buffer)
feat.setAttributes([target_id])

provider.addFeature(feat)
result_layer.updateExtents()

QgsProject.instance().addMapLayer(result_layer)

print("✔ 500 ft buffer created INTO parcels 6876 and 6842 only.")