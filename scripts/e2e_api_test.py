"""
scripts/e2e_api_test.py — Live API integration test.
Run after starting: cd backend && python -m uvicorn main:app --port 8000
"""
import urllib.request, urllib.error, json, sys

BASE = 'http://127.0.0.1:8000'
passed = 0
failed = 0

def check(name, cond, info=''):
    global passed, failed
    if cond:
        print(f'  PASS  {name}')
        passed += 1
    else:
        print(f'  FAIL  {name}  {info}')
        failed += 1

def get(path):
    with urllib.request.urlopen(f'{BASE}{path}', timeout=10) as r:
        return json.loads(r.read()), r.status

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f'{BASE}{path}', data=data,
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()), r.status

def run_all():
    global passed, failed
    passed = 0
    failed = 0

# 1. Health
print('\n=== 1. /api/health ===')
h, s = get('/api/health')
check('HTTP 200', s == 200)
check('engine loaded', h.get('engine') == 'loaded')
check('parcel_count > 0', h.get('parcel_count', 0) > 0)
check('engine_crs EPSG:3857', h.get('engine_crs') == 'EPSG:3857')
check('demo_fixture_mode present', 'demo_fixture_mode' in h)
check('data_state present', 'data_state' in h)

# 2. Parcels
print('\n=== 2. /api/parcels ===')
parcels, s = get('/api/parcels')
check('HTTP 200', s == 200)
check('returns list', isinstance(parcels, list))
check('has parcels', len(parcels) > 0)
p = parcels[0]
for field in ('parcel_id', 'confidence', 'priority', 'area_difference',
              'geometry_conflict', 'attribute_conflict', 'recommendation', 'boundaries'):
    check(f'has field: {field}', field in p)
check('has cadastral boundary', 'cadastral' in p.get('boundaries', {}))
geom = p.get('boundaries', {}).get('cadastral', {})
check('geometry type present', geom.get('type') in ('Polygon', 'MultiPolygon'))
coords = geom.get('coordinates', [[]])
check('coordinates nested list', isinstance(coords, list) and len(coords) > 0)
if coords and coords[0]:
    pt = coords[0][0]
    check('GeoJSON lng valid for India (60-100)', isinstance(pt, list) and 60 < pt[0] < 100)
    check('GeoJSON lat valid for India (5-40)', isinstance(pt, list) and 5 < pt[1] < 40)
    check('GeoJSON order [lng, lat] - 2 elements', isinstance(pt, list) and len(pt) == 2)

# 3. Conflicts
print('\n=== 3. /api/conflicts ===')
conflicts, s = get('/api/conflicts')
check('HTTP 200', s == 200)
check('returns list', isinstance(conflicts, list))
if conflicts:
    c = conflicts[0]
    check('has parcel_id', 'parcel_id' in c)
    check('has geometry_conflict', 'geometry_conflict' in c)
    check('geometry_conflict is bool', isinstance(c.get('geometry_conflict'), bool))

# 4. Parcel by ID
print('\n=== 4. /api/parcels/{id} ===')
pid = parcels[0]['parcel_id']
p1, s = get(f'/api/parcels/{pid}')
check('HTTP 200', s == 200)
check('returns correct parcel_id', p1.get('parcel_id') == pid)
try:
    get('/api/parcels/DOES_NOT_EXIST_XYZ')
    check('404 for unknown parcel', False)
except urllib.error.HTTPError as e:
    check('404 for unknown parcel', e.code == 404)

# 5. ML Status
print('\n=== 5. /api/ml/status ===')
ml, s = get('/api/ml/status')
check('HTTP 200', s == 200)
check('model_status OK', ml.get('model_status') == 'OK')
check('14 canonical features', len(ml.get('feature_names', [])) == 14)
check('accuracy >= 0.85', ml.get('accuracy', 0) >= 0.85)
check('VERIFIED in accuracy_status', 'VERIFIED' in str(ml.get('accuracy_status', '')))
check('has model_version', 'model_version' in ml)
check('has confusion_matrix', ml.get('confusion_matrix') is not None)

# 6. ML Predict class 0
print('\n=== 6. /api/ml/predict (class 0) ===')
pred, s = post('/api/ml/predict', {'iou': 0.9999, 'area_delta': 0.0001, 'attr_match': 1.0})
check('HTTP 200', s == 200)
check('conflict_level == 0', pred.get('conflict_level') == 0)
check('conflict_label No Conflict', pred.get('conflict_label') == 'No Conflict')
check('confidence > 80', pred.get('confidence', 0) > 80)
check('has probability', pred.get('probability') is not None)
check('model_status OK', pred.get('model_status') == 'OK')

# 7. ML Predict class 2
print('\n=== 7. /api/ml/predict (class 2) ===')
pred2, s = post('/api/ml/predict', {'iou': 0.05, 'area_delta': 0.95, 'attr_match': 0.0})
check('HTTP 200', s == 200)
check('conflict_level == 2', pred2.get('conflict_level') == 2)
check('conflict_label Critical Conflict', pred2.get('conflict_label') == 'Critical Conflict')
check('reasoning mentions low overlap', 'Low spatial overlap' in pred2.get('reasoning', ''))

# 8. ML metrics endpoint
print('\n=== 8. /api/ml/predict-metrics ===')
pred3, s = post('/api/ml/predict-metrics', {
    'spatial_metrics': {
        'iou': 0.9999, 'area_ratio': 0.9999, 'area_difference_m2': 0.001,
        'centroid_distance_m': 0.00001, 'hausdorff_distance_m': 0.00001,
        'boundary_displacement_m': 0.00001, 'shape_similarity': 0.9999,
        'overlap_pct_of_cadastral': 99.99, 'compactness_difference': 0.0,
        'perimeter_difference_m': 0.0,
    },
    'attribute_metrics': {
        'survey_number_match': True, 'land_use_match': True, 'classification_match': True,
    }
})
check('HTTP 200', s == 200)
check('model_status OK', pred3.get('model_status') == 'OK')
check('conflict_level == 0', pred3.get('conflict_level') == 0)

# 9. OOD detection
print('\n=== 9. OOD detection ===')
try:
    post('/api/ml/predict', {'iou': -0.5, 'area_delta': 0.1, 'attr_match': 0.5})
    check('422 for OOD input', False)
except urllib.error.HTTPError as e:
    check('422 for OOD input', e.code == 422)

# 10. Process
print('\n=== 10. /api/process ===')
proc, s = post('/api/process', {'dataset_id': 'sample'})
check('HTTP 200', s == 200)
check('job_status complete', proc.get('job_status') == 'complete')

# 12. Manual label override (DetailPanel workflow)
print('\n=== 12. /api/ml/label ===')
label_resp, s = post('/api/ml/label', {'parcel_id': 'HYD-REV-1000', 'label': 0})
check('HTTP 200', s == 200)
check('status success', label_resp.get('status') == 'success')

# 13. Satellite tile proxy
print('\n=== 13. /api/satellite-tile ===')
try:
    with urllib.request.urlopen(f'{BASE}/api/satellite-tile/10/512/340', timeout=10) as r:
        check('HTTP 200 or 204', r.status in (200, 204))
except Exception as e:
    check('HTTP 200 or 204', False, str(e))

if __name__ == '__main__':
    print(f'\n{"="*60}')
    print(f'E2E RESULTS: {passed} passed, {failed} failed out of {passed+failed} checks')
    sys.exit(0 if failed == 0 else 1)

