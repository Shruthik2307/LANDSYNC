import os
import geopandas as gpd
from shapely.affinity import translate, scale

RAW_PATH = "data/sample/hyd_cadastral_raw.geojson"
DATA_DIR = "data/sample"
CAD_PATH = os.path.join(DATA_DIR, "cadastral.geojson")
MUN_PATH = os.path.join(DATA_DIR, "municipal.geojson")

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(RAW_PATH):
    raise FileNotFoundError(f"Missing input raw file: {RAW_PATH}")

print(f"Loading raw Hyderabad cadastral data from: {RAW_PATH}...")
gdf = gpd.read_file(RAW_PATH)

valid_parcels = gdf[gdf.geometry.notnull() & gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
slice_parcels = valid_parcels.head(25).copy()

if slice_parcels.crs is None:
    slice_parcels.set_crs(epsg=4326, inplace=True)
elif slice_parcels.crs.to_epsg() != 4326:
    slice_parcels = slice_parcels.to_crs(epsg=4326)

slice_parcels["parcel_id"] = [f"HYD-REV-{1000 + i}" for i in range(len(slice_parcels))]
slice_parcels["owner"] = [f"Landowner_{chr(65 + (i % 26))}" for i in range(len(slice_parcels))]
slice_parcels["land_use"] = "Residential"
slice_parcels["source"] = "Cadastral_Revenue_Dept"

cadastral_export = slice_parcels[["parcel_id", "owner", "land_use", "source", "geometry"]]
cadastral_export.to_file(CAD_PATH, driver="GeoJSON")
print(f"[OK] Saved baseline cadastral layer: {CAD_PATH} ({len(cadastral_export)} parcels)")

municipal_df = slice_parcels.copy()
municipal_df["source"] = "Municipal_Drone_Survey"

def introduce_discrepancy(geom, index):
    if index % 3 == 0:
        return translate(scale(geom, xfact=1.03, yfact=1.03), xoff=0.00003, yoff=0.00002)
    return geom

municipal_df["geometry"] = [
    introduce_discrepancy(geom, i) for i, geom in enumerate(municipal_df.geometry)
]

municipal_df.loc[2, "owner"] = "Disputed_Party_K"
municipal_df.loc[5, "land_use"] = "Commercial"
municipal_df.loc[8, "owner"] = "Encroached_Claimant_M"

municipal_export = municipal_df[["parcel_id", "owner", "land_use", "source", "geometry"]]
municipal_export.to_file(MUN_PATH, driver="GeoJSON")
print(f"[OK] Saved candidate municipal layer: {MUN_PATH} ({len(municipal_export)} parcels)")
