# LANDSYNC backend contract

This contract is the Day 3 handoff for the SIH26013 backend teammate. The frontend runs against the `contract/mock/` folder when `VITE_API_BASE_URL` is unset or when the header settings control selects demo mode. With `VITE_API_BASE_URL=http://127.0.0.1:8000`, it calls FastAPI directly. Implement to this spec and swap the env value, nothing else changes on either side.

## Endpoints

- `POST /api/upload`: accepts multipart form field `file`; returns `{ "dataset_id": "string" }`.
- `POST /api/process`: accepts `{ "dataset_id": "string" }`; returns `{ "job_status": "queued" | "processing" | "complete" | "failed" }`. The current frontend treats `complete` as a synchronous completion; if the backend returns `queued` or `processing`, provide a polling contract before changing that behavior.
- `GET /api/parcels`: returns every parcel as `Parcel[]`.
- `GET /api/conflicts`: returns only conflict parcels, sorted by priority (`HIGH`, `MEDIUM`, `LOW`) then confidence descending.
- `GET /api/parcels/{id}`: returns one complete `Parcel` or a normal 404 response.

## Parcel shape

`Parcel` preserves the original flat reconciliation fields. `boundaries` is an explicit addition to that source contract because the map requires geometry from both sources. `boundaries.drone_ori` is present only when `geometry_conflict` is true. Coordinates are GeoJSON Polygon coordinates in `[longitude, latitude]` order.

Day 2 additions are backward-compatible: `attribute_conflict: true` with `geometry_conflict: false` represents an attribute-only mismatch and must not include a drone boundary. Optional `duplicate_id: true` flags a parcel ID that occurs more than once in the reconciled result. Existing clients can omit `duplicate_id` and treat it as false.

```json
{
  "parcel_id": "1042",
  "confidence": 87,
  "priority": "HIGH",
  "area_difference": 24,
  "geometry_conflict": true,
  "attribute_conflict": false,
  "duplicate_id": false,
  "recommendation": "Field verification",
  "boundaries": {
    "cadastral": { "type": "Polygon", "coordinates": [[[77.5941, 12.9716]]] },
    "drone_ori": { "type": "Polygon", "coordinates": [[[77.5944, 12.9713]]] }
  }
}
```

The fixtures in `contract/mock/` are valid response bodies and can be loaded directly into Postman or FastAPI seed/test data. Upload/process are intentionally contract-only on Day 1; the UI consumes parcels and conflicts from fixtures.
