# GATES: Enterprise Features

- [ ] G1: Export to GeoJSON works
  CHECK: curl -X GET "http://localhost:8000/api/export?dataset_id=sample" > export.json && jq . export.json
  EXPECT: "FeatureCollection"
  EVIDENCE: pending

- [ ] G2: Manual Override (Verify/Reject) updates DB
  CHECK: curl -X POST "http://localhost:8000/api/ml/label" -H "Content-Type: application/json" -d '{"parcel_id": "1042", "label": 0}' && curl -X GET "http://localhost:8000/api/parcels/1042" | grep '"official_label": 0'
  EXPECT: "official_label": 0
  EVIDENCE: pending

- [ ] G3: Export file contains correct parcel count
  CHECK: curl -X GET "http://localhost:8000/api/export?dataset_id=sample" | grep -o '"features":\s*\[' | wc -l
  EXPECT: 1
  EVIDENCE: pending
