import urllib.request
import ssl
import json

ctx = ssl._create_unverified_context()

services = {
    "Bhunaksha_Cadastral": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer",
    "Bhunaksha_query": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer"
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LANDSYNC/1.0'}

for name, base_url in services.items():
    print("=" * 60)
    print(f"SERVICE: {name}")
    print(f"URL: {base_url}")
    
    # 1. Fetch server metadata
    req = urllib.request.Request(f"{base_url}?f=pjson", headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        server_info = json.loads(resp.read().decode('utf-8'))
    
    print(f"Single Fused Map Cache: {server_info.get('singleFusedMapCache')}")
    print(f"Spatial Reference: {server_info.get('spatialReference')}")
    print(f"Initial Extent: {server_info.get('initialExtent')}")
    print(f"Full Extent: {server_info.get('fullExtent')}")
    print(f"Capabilities: {server_info.get('capabilities')}")
    print(f"Max Record Count: {server_info.get('maxRecordCount')}")
    
    layers = server_info.get("layers", [])
    print(f"\nLayers Count: {len(layers)}")
    for l in layers:
        lid = l['id']
        lname = l['name']
        print(f"\n--- Layer {lid}: {lname} ---")
        layer_url = f"{base_url}/{lid}?f=pjson"
        try:
            l_req = urllib.request.Request(layer_url, headers=headers)
            with urllib.request.urlopen(l_req, context=ctx, timeout=20) as l_resp:
                layer_info = json.loads(l_resp.read().decode('utf-8'))
            
            print(f"  Type: {layer_info.get('type')}")
            print(f"  Geometry Type: {layer_info.get('geometryType')}")
            print(f"  Capabilities: {layer_info.get('capabilities')}")
            print(f"  Max Record Count: {layer_info.get('maxRecordCount')}")
            print(f"  Supported Query Formats: {layer_info.get('supportedQueryFormats')}")
            print(f"  Supports Advanced Queries: {layer_info.get('supportsAdvancedQueries')}")
            print(f"  Supports Statistics: {layer_info.get('supportsStatistics')}")
            fields = layer_info.get('fields', [])
            field_names = [f.get('name') for f in fields]
            print(f"  Fields ({len(fields)}): {field_names[:10]}")
        except Exception as e:
            print(f"  Error inspecting layer {lid}: {e}")
