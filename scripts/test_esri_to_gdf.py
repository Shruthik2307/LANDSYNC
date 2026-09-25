import urllib.request
import urllib.parse
import ssl
import json
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
import geopandas as gpd

ctx = ssl._create_unverified_context()
headers = {'User-Agent': 'Mozilla/5.0 LANDSYNC/1.0'}

url = "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query"
params = {
    "geometry": "78.06,17.60,78.08,17.62",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outSR": "4326",
    "outFields": "*",
    "returnGeometry": "true",
    "f": "json"
}

req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=headers)
with urllib.request.urlopen(req, context=ctx) as r:
    data = json.loads(r.read())

features = data.get("features", [])
print(f"Loaded {len(features)} real features from TGRAC")

def esri_rings_to_geometry(rings):
    if not rings:
        return None
    polygons = []
    for ring in rings:
        if len(ring) >= 3:
            try:
                p = Polygon(ring)
                if not p.is_valid:
                    p = make_valid(p)
                if not p.is_empty:
                    polygons.append(p)
            except Exception as e:
                pass
    if not polygons:
        return None
    if len(polygons) == 1:
        return polygons[0]
    # If multiple polygons, union them or return MultiPolygon
    from shapely.ops import unary_union
    try:
        u = unary_union(polygons)
        return u
    except Exception:
        return MultiPolygon([p for p in polygons if p.geom_type == 'Polygon'])

records = []
for f in features:
    attrs = dict(f.get("attributes", {}))
    rings = f.get("geometry", {}).get("rings", [])
    geom = esri_rings_to_geometry(rings)
    if geom:
        attrs["geometry"] = geom
        records.append(attrs)

gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
print(f"Created GeoDataFrame with {len(gdf)} rows, CRS: {gdf.crs}")
print("Columns:", list(gdf.columns)[:10])
print("First row parcel identifier candidates:", {k: gdf.iloc[0].get(k) for k in ['OBJECTID', 'OBJECTID_12', 'Parcel_num', 'V_Name']})
print("Geometry types:", gdf.geometry.geom_type.value_counts().to_dict())
