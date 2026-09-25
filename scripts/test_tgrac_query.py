import urllib.request
import urllib.parse
import ssl
import json
import time

ctx = ssl._create_unverified_context()
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LANDSYNC/1.0'}

# Let's test a small bbox or where=1=1 with resultRecordCount=5 to inspect features
endpoints_to_test = [
    {
        "service": "Bhunaksha_Cadastral",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0",
        "layer_name": "Cadastral 2.5m"
    },
    {
        "service": "Bhunaksha_Cadastral",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/1",
        "layer_name": "Cadastral 30cm"
    },
    {
        "service": "Bhunaksha_query",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer/0",
        "layer_name": "Full Cadastral"
    },
    {
        "service": "Bhunaksha_query",
        "url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer/7",
        "layer_name": "Cadastral"
    }
]

for ep in endpoints_to_test:
    print("=" * 60)
    print(f"Testing {ep['service']} - {ep['layer_name']}")
    query_url = f"{ep['url']}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "resultRecordCount": "5",
        "f": "json"
    }
    url = f"{query_url}?{urllib.parse.urlencode(params)}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
            elapsed = time.time() - t0
            raw = resp.read()
            data = json.loads(raw.decode('utf-8'))
            print(f"HTTP Status: {resp.status} in {elapsed:.2f}s")
            if "error" in data:
                print("ArcGIS Error:", data["error"])
            else:
                features = data.get("features", [])
                print(f"Features returned: {len(features)}")
                if features:
                    f0 = features[0]
                    print("First Feature Attributes:", f0.get("attributes"))
                    geom = f0.get("geometry", {})
                    rings = geom.get("rings", [])
                    print(f"First Feature Geometry Type: {data.get('geometryType')}")
                    print(f"Number of rings: {len(rings)}")
                    if rings:
                        print(f"First ring coordinate count: {len(rings[0])}")
                        print(f"First coordinate sample: {rings[0][:2]}")
                        # Calculate bbox of first feature
                        xs = [p[0] for r in rings for p in r]
                        ys = [p[1] for r in rings for p in r]
                        print(f"Feature extent: minx={min(xs)}, miny={min(ys)}, maxx={max(xs)}, maxy={max(ys)}")
    except Exception as e:
        print(f"Error querying {ep['layer_name']}: {e}")
