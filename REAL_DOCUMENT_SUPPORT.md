# LANDSYNC — Real Document Support & Capability Matrix

**Authoritative Multi-Format Document Ingestion Audit**  
**Date:** September 26, 2026  
**System:** LANDSYNC (SIH26013)  
**Engine:** Deterministic Hybrid GIS + 14-Feature Random Forest (`rf-tgrac-v1.0.0-b1f6d178`)

---

## 1. Capability Matrix

Every cell in this matrix has been verified against automated tests (`backend/tests/test_multi_format_ingestion.py`, `scripts/test_real_document_upload.py`, and API integration tests). Capabilities are marked supported only where verified code and test assertions exist.

| Format | Extension / Magic | Upload | Parse | OCR | Geometry Status | CRS Support | Reconciliation | ML Stream | Production Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **GeoJSON** | `.geojson` | **YES** | **YES** | N/A | Full Polygons | Validated / Reprojected (EPSG:4326) | **YES** | **YES** | **Production Ready** |
| **JSON** | `.json` (FeatureCollection) | **YES** | **YES** | N/A | Full Polygons | Validated / Reprojected (EPSG:4326) | **YES** | **YES** | **Production Ready** |
| **Shapefile ZIP** | `.zip` (`.shp`, `.shx`, `.dbf`, `.prj`) | **YES** | **YES** | N/A | Full Polygons | Extracted from `.prj` / User Hint | **YES** | **YES** | **Production Ready** |
| **CAD (DXF)** | `.dxf` (ASCII R2010/R2018) | **YES** | **YES** | N/A | Reconstructed Polygons | Strict Verification (CRS Required for projected units) | **YES** | **YES** | **Production Ready** |
| **KML** | `.kml` (Placemark Polygons) | **YES** | **YES** | N/A | Placemark Boundaries | Native WGS84 (EPSG:4326) | **YES** | **YES** | **Production Ready** |
| **KMZ** | `.kmz` (Zipped KML) | **YES** | **YES** | N/A | Placemark Boundaries | Native WGS84 (EPSG:4326) | **YES** | **YES** | **Production Ready** |
| **GeoPackage** | `.gpkg` (OGC GPKG) | **YES** | **YES** | N/A | Layer Polygons | Preserved / Reprojected (EPSG:4326) | **YES** | **YES** | **Production Ready** |
| **PDF (Text)** | `.pdf` (Digital Deeds/RoR) | **YES** | **YES** | N/A | Metadata Only (No Fake Geoms) | N/A (Text Record) | **Metadata Only** | Guarded (No Fake Geoms) | **Production Ready** |
| **PDF (Scan)** | `.pdf` (Scanned Image Pages) | **YES** | **YES** | **YES** | Metadata Only (No Fake Geoms) | N/A (Text Record) | **Metadata Only** | Guarded (No Fake Geoms) | **Production Ready** |
| **Images** | `.png`, `.jpg`, `.jpeg` | **YES** | **YES** | **YES** | Metadata Only (No Fake Geoms) | N/A (Scanned Deed) | **Metadata Only** | Guarded (No Fake Geoms) | **Production Ready** |
| **TIFF / GeoTIFF** | `.tif`, `.tiff` | **YES** | **YES** | N/A | Raster Footprint / Extent | Embedded Georeference (EPSG) | **Raster Context** | Background Layer | **Production Ready** |
| **CAD (DWG)** | `.dwg` (Autodesk Binary) | **YES** | Rejected with Guidance | N/A | Conversion Required | N/A | Guidance Provided | N/A | **Honest Conversion Advice** |

---

## 2. Integrity & Honesty Rules

1. **No Hallucinated / Fabricated Geometry:**  
   When a PDF deed or scanned image record is uploaded without vector coordinates, LANDSYNC extracts and structures the textual attributes (Survey Number, Area, Land Use, Classification, Pattadar) and marks `geometry_status: "METADATA_ONLY"`. Coordinates are **never** synthetically generated from pure text or diagram sketches.

2. **Strict Coordinate Reference System (CRS) Safety:**  
   CAD DXF drawings with local metric coordinates (e.g. UTM or site grid) trigger `CRS_REQUIRED` rather than assuming EPSG:4326 degrees, preventing catastrophic spatial displacement. Users can provide `crs_hint` (e.g. `EPSG:32644`).

3. **ML Feature & Weight Preservation:**  
   The verified model artifact (`rf-tgrac-v1.0.0-b1f6d178`) and its 14 geometric/attribute features are strictly unchanged. If required spatial features cannot be calculated (e.g., non-spatial records), ML inference is guarded with status `MODEL_UNAVAILABLE` or `INSUFFICIENT_EVIDENCE`.

4. **Honest DWG Support:**  
   Because Autodesk DWG is a proprietary binary format without a certified open-source parser, LANDSYNC does not pretend to parse DWG files with placeholder geometry. The upload router identifies DWG headers (`AC10...`) and gives immediate, actionable instructions to export as DXF (R2010/R2018 ASCII) via LibreCAD or AutoCAD.
