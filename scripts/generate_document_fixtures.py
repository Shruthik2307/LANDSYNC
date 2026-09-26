"""
scripts/generate_document_fixtures.py
=====================================
Generates mathematically valid, legally safe test documents for all target formats:
GeoJSON, JSON, PDF, PNG image, DXF CAD, Shapefile ZIP, KML, and GeoPackage.
"""

import json
import zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, mapping
from PIL import Image, ImageDraw, ImageFont
import ezdxf

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "documents"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# Coordinates in Sangareddy / Telangana (EPSG:4326)
COORDS_A = [(78.0850, 17.6150), (78.0870, 17.6150), (78.0870, 17.6170), (78.0850, 17.6170), (78.0850, 17.6150)]
COORDS_B = [(78.0875, 17.6150), (78.0895, 17.6150), (78.0895, 17.6170), (78.0875, 17.6170), (78.0875, 17.6150)]


def create_geojson():
    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(Polygon(COORDS_A)),
                "properties": {
                    "parcel_id": "CAD-TEST-101",
                    "survey_number": "101/A",
                    "land_use": "Agricultural",
                    "classification": "Patta",
                    "area": 4046.86,
                },
            }
        ],
    }
    with open(FIXTURES_DIR / "sample.geojson", "w") as f:
        json.dump(fc, f, indent=2)
    with open(FIXTURES_DIR / "sample.json", "w") as f:
        json.dump(fc, f, indent=2)
    print("[OK] Created sample.geojson & sample.json")


def create_pdf():
    # Use pypdf to generate a clean text-based land-record PDF
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    # Add a blank page
    page = writer.add_blank_page(width=612, height=792)
    
    # We can write text stream into PDF content
    text_content = (
        "BT /F1 14 Tf 72 720 Td (TELANGANA REVENUE DEPARTMENT - RECORD OF RIGHTS) Tj ET\n"
        "BT /F1 12 Tf 72 680 Td (Survey No: 101/A) Tj ET\n"
        "BT /F1 12 Tf 72 650 Td (Extent: 1.00 Acres) Tj ET\n"
        "BT /F1 12 Tf 72 620 Td (Land Use: Agricultural) Tj ET\n"
        "BT /F1 12 Tf 72 590 Td (Classification: Patta) Tj ET\n"
        "BT /F1 12 Tf 72 560 Td (Pattadar: Sri K. Ramesh) Tj ET\n"
        "BT /F1 12 Tf 72 530 Td (Khata No: 452) Tj ET\n"
    )
    # Write page content stream
    from pypdf.generic import DecodedStreamObject
    stream = DecodedStreamObject()
    stream.set_data(text_content.encode("utf-8"))
    page[NameObject("/Contents")] = stream

    # Add default font resource
    fonts = DictionaryObject()
    f1 = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    fonts[NameObject("/F1")] = f1
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})

    with open(FIXTURES_DIR / "sample.pdf", "wb") as f:
        writer.write(f)
    print("[OK] Created sample.pdf")


def create_image():
    # Create image with rendered text
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    lines = [
        "TELANGANA LAND REVENUE TITLE DEED",
        "Survey Number: 101/A",
        "Total Area: 1.00 Acres",
        "Land Use: Agricultural",
        "Classification: Patta",
        "Pattadar: Sri K. Ramesh",
    ]
    y = 60
    for line in lines:
        draw.text((60, y), line, fill=(0, 0, 0))
        y += 40

    img.save(FIXTURES_DIR / "sample_scan.png")
    img.save(FIXTURES_DIR / "sample_scan.jpg")
    img.save(FIXTURES_DIR / "sample_scan.tiff")
    print("[OK] Created sample_scan.png, sample_scan.jpg, sample_scan.tiff")


def create_dxf():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Add a closed LWPOLYLINE for a parcel in geographic degrees
    points = [(78.0850, 17.6150), (78.0870, 17.6150), (78.0870, 17.6170), (78.0850, 17.6170)]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "CADASTRAL_BOUNDARIES"})
    msp.add_text("101/A", dxfattribs={"height": 0.0005, "insert": (78.0860, 17.6160), "layer": "ANNOTATIONS"})
    doc.saveas(str(FIXTURES_DIR / "sample.dxf"))
    print("[OK] Created sample.dxf")


def create_shapefile():
    poly = Polygon(COORDS_A)
    gdf = gpd.GeoDataFrame(
        [
            {
                "parcel_id": "CAD-TEST-101",
                "survey_no": "101/A",
                "land_use": "Agricultural",
                "class": "Patta",
                "area": 4046.86,
                "geometry": poly,
            }
        ],
        crs="EPSG:4326",
    )
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_shp = Path(tmpdir) / "parcels.shp"
        gdf.to_file(tmp_shp)
        
        # Package into zip
        zip_path = FIXTURES_DIR / "sample_shapefile.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in Path(tmpdir).glob("parcels.*"):
                zf.write(f, arcname=f.name)
    print("[OK] Created sample_shapefile.zip")


def create_kml():
    kml_str = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Cadastral Survey KML</name>
    <Placemark>
      <name>101/A</name>
      <description>Agricultural Patta Land</description>
      <ExtendedData>
        <Data name="survey_no"><value>101/A</value></Data>
        <Data name="land_use"><value>Agricultural</value></Data>
        <Data name="classification"><value>Patta</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              78.0850,17.6150,0 78.0870,17.6150,0 78.0870,17.6170,0 78.0850,17.6170,0 78.0850,17.6150,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    with open(FIXTURES_DIR / "sample.kml", "w", encoding="utf-8") as f:
        f.write(kml_str)
    print("[OK] Created sample.kml")


def create_geopackage():
    poly = Polygon(COORDS_A)
    gdf = gpd.GeoDataFrame(
        [
            {
                "parcel_id": "CAD-TEST-101",
                "survey_no": "101/A",
                "land_use": "Agricultural",
                "classification": "Patta",
                "area": 4046.86,
                "geometry": poly,
            }
        ],
        crs="EPSG:4326",
    )
    gpkg_path = FIXTURES_DIR / "sample.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    gdf.to_file(gpkg_path, driver="GPKG", layer="cadastral_parcels")
    print("[OK] Created sample.gpkg")


if __name__ == "__main__":
    create_geojson()
    create_pdf()
    create_image()
    create_dxf()
    create_shapefile()
    create_kml()
    create_geopackage()
    print("All document test fixtures successfully generated.")
