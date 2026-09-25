import urllib.request
import urllib.parse
import ssl
import json
import time

ctx = ssl._create_unverified_context()
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LANDSYNC/1.0'}

# Test bbox queries
test_cases = [
    {
        "service": "Bhunaksha_Cadastral - Layer 0 (Cadastral 2.5m)",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query",
        "bbox": "79.65,18.67,79.69,18.71"
    },
    {
        "service": "Bhunaksha_Cadastral - Layer 1 (Cadastral 30cm)",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/1/query",
        "bbox": "77.92,16.45,77.93,16.47"
    },
    {
        "service": "Bhunaksha_query - Layer 7 (Cadastral)",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer/7/query",
        "bbox": "78.06,17.60,78.08,17.62"
    },
    {
        "service": "Bhunaksha_Cadastral - Layer 0 with Sangareddy bbox",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0/query",
        "bbox": "78.06,17.60,78.08,17.62"
    }
]

for tc in test_cases:
    print("=" * 60)
    print(f"Testing spatial bbox query on {tc['service']}")
    minx, miny, maxx, maxy = tc["bbox"].split(",")
    # ArcGIS geometry format for envelope:
    # geometry=xmin,ymin,xmax,ymax or {"xmin":...,"ymin":...,"xmax":...,"ymax":...,"spatialReference":{"wkid":4326}}
    # Let's test standard envelope string first
    params = {
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "4326",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json"
    }
    url = f"{tc['url']}?{urllib.parse.urlencode(params)}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
            elapsed = time.time() - t0
            raw = resp.read()
            data = json.loads(raw.decode('utf-8'))
            if "error" in data:
                print("Error:", data["error"])
            else:
                features = data.get("features", [])
                print(f"Status 200 in {elapsed:.2f}s | Features returned: {len(features)}")
                if features:
                    f0 = features[0]
                    print(f"First Object ID: {f0.get('attributes', {}).get('OBJECTID') or f0.get('attributes', {}).get('OBJECTID_12')}")
                    print(f"Attributes keys: {list(f0.get('attributes', {}).keys())[:8]}")
                    print(f"Sample attrs: {dict(list(f0.get('attributes', {}).items())[:5])}")
    except Exception as e:
        print("Exception:", e)
