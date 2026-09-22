"""Business logic and data processing services"""
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from database import Dataset, Parcel
from config import UPLOAD_DIR, CONFIDENCE_THRESHOLD_HIGH, CONFIDENCE_THRESHOLD_MEDIUM, AREA_DIFFERENCE_THRESHOLD
import zipfile
import shutil


def save_uploaded_file(file_content: bytes, filename: str) -> tuple[str, Path]:
    """Save uploaded file and return dataset_id and file path"""
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}_{int(datetime.utcnow().timestamp())}"
    file_path = UPLOAD_DIR / f"{dataset_id}_{filename}"

    with open(file_path, "wb") as f:
        f.write(file_content)

    return dataset_id, file_path


def extract_geojson_from_upload(file_path: Path) -> Dict[str, Any]:
    """Extract GeoJSON data from uploaded file"""
    if file_path.suffix.lower() == ".zip":
        # Handle zipped shapefile or geojson
        extract_dir = file_path.parent / f"{file_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Look for .geojson or .json files
        for extracted_file in extract_dir.glob("*.geojson"):
            with open(extracted_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        for extracted_file in extract_dir.glob("*.json"):
            with open(extracted_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # TODO: Add shapefile parsing with geopandas if needed
        raise ValueError("No GeoJSON file found in ZIP archive")

    elif file_path.suffix.lower() in [".geojson", ".json"]:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def calculate_priority(confidence: int, area_diff: float, geometry_conflict: bool, attribute_conflict: bool) -> str:
    """Determine conflict priority based on multiple factors"""
    if confidence < CONFIDENCE_THRESHOLD_MEDIUM or area_diff > 20:
        return "HIGH"
    elif confidence < CONFIDENCE_THRESHOLD_HIGH or geometry_conflict or attribute_conflict:
        return "MEDIUM"
    else:
        return "LOW"


def generate_recommendation(parcel_data: Dict) -> str:
    """Generate human-readable recommendation"""
    confidence = parcel_data.get("confidence", 0)
    area_diff = parcel_data.get("area_difference", 0)
    geometry_conflict = parcel_data.get("geometry_conflict", False)
    attribute_conflict = parcel_data.get("attribute_conflict", False)
    priority = parcel_data.get("priority", "LOW")

    if priority == "HIGH":
        if area_diff > 25:
            return f"Escalate for resurvey — {area_diff:.1f}m² area discrepancy detected"
        elif attribute_conflict and geometry_conflict:
            return "Field verification required — both spatial and attribute conflicts detected"
        elif confidence < 70:
            return f"Low confidence match ({confidence}%) — requires manual review"
        else:
            return "Field verification required"

    elif priority == "MEDIUM":
        if geometry_conflict:
            return f"Schedule boundary check — {area_diff:.1f}m² difference detected"
        elif attribute_conflict:
            return "Review ownership attributes — attribute mismatch detected"
        else:
            return "Accept with survey note"

    else:
        if attribute_conflict:
            return "Verify owner name"
        elif area_diff > 0:
            return f"Auto-Harmonized — Minor {area_diff:.1f}m² variation within tolerance"
        else:
            return "No action required"


def process_geojson_dataset(dataset_id: str, geojson_data: Dict, db: Session) -> int:
    """Process GeoJSON dataset and create parcel records"""
    features = geojson_data.get("features", [])
    parcel_count = 0
    parcel_id_tracker = {}

    for feature in features:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        # Extract parcel ID
        parcel_id = properties.get("parcel_id") or properties.get("id") or f"P{parcel_count + 1:04d}"

        # Track duplicate IDs
        is_duplicate = parcel_id in parcel_id_tracker
        if is_duplicate:
            parcel_id_tracker[parcel_id] += 1
            parcel_id = f"{parcel_id}_dup{parcel_id_tracker[parcel_id]}"
        else:
            parcel_id_tracker[parcel_id] = 0

        # Extract areas
        area_cadastral = properties.get("area_cadastral_sqm", properties.get("area", 0))
        area_drone = properties.get("area_drone_sqm", area_cadastral)
        area_diff = abs(area_drone - area_cadastral)

        # Determine conflicts
        geometry_conflict = area_diff > AREA_DIFFERENCE_THRESHOLD
        attribute_conflict = properties.get("attribute_conflict", False)

        # Calculate confidence
        confidence = properties.get("confidence")
        if confidence is None:
            if geometry_conflict or attribute_conflict:
                confidence = max(60, 95 - int(area_diff * 2))
            else:
                confidence = 96

        # Determine priority
        priority = calculate_priority(confidence, area_diff, geometry_conflict, attribute_conflict)

        # Create cadastral boundary
        cadastral_boundary = {
            "type": "Polygon",
            "coordinates": geometry.get("coordinates", [])
        }

        # Create drone boundary if there's a geometry conflict
        drone_boundary = None
        if geometry_conflict and "drone_geometry" in properties:
            drone_boundary = properties["drone_geometry"]

        # Build recommendation
        parcel_info = {
            "confidence": confidence,
            "area_difference": area_diff,
            "geometry_conflict": geometry_conflict,
            "attribute_conflict": attribute_conflict,
            "priority": priority
        }
        recommendation = properties.get("recommendation") or generate_recommendation(parcel_info)

        # Create parcel record
        parcel = Parcel(
            parcel_id=parcel_id,
            dataset_id=dataset_id,
            confidence=confidence,
            priority=priority,
            area_difference=area_diff,
            geometry_conflict=geometry_conflict,
            attribute_conflict=attribute_conflict,
            duplicate_id=is_duplicate,
            recommendation=recommendation,
            cadastral_boundary=cadastral_boundary,
            drone_boundary=drone_boundary,
            survey_number=properties.get("survey_number"),
            owner_name=properties.get("owner_name"),
            land_use=properties.get("land_use"),
            area_cadastral_sqm=area_cadastral,
            area_drone_sqm=area_drone,
            village_name=properties.get("village_name")
        )

        db.add(parcel)
        parcel_count += 1

    db.commit()
    return parcel_count


def load_mock_data(db: Session) -> int:
    """Load mock parcels from contract fixtures for demo purposes"""
    from pathlib import Path
    import json

    mock_file = Path(__file__).parent.parent / "contract" / "mock" / "parcels.json"
    if not mock_file.exists():
        return 0

    with open(mock_file, 'r', encoding='utf-8') as f:
        parcels_data = json.load(f)

    dataset_id = "mock_dataset_demo"

    # Clear existing mock data
    db.query(Parcel).filter(Parcel.dataset_id == dataset_id).delete()
    db.commit()

    for parcel_data in parcels_data:
        parcel = Parcel(
            parcel_id=parcel_data["parcel_id"],
            dataset_id=dataset_id,
            confidence=parcel_data["confidence"],
            priority=parcel_data["priority"],
            area_difference=parcel_data["area_difference"],
            geometry_conflict=parcel_data["geometry_conflict"],
            attribute_conflict=parcel_data["attribute_conflict"],
            duplicate_id=parcel_data.get("duplicate_id", False),
            recommendation=parcel_data["recommendation"],
            cadastral_boundary=parcel_data["boundaries"]["cadastral"],
            drone_boundary=parcel_data["boundaries"].get("drone_ori")
        )
        db.add(parcel)

    db.commit()
    return len(parcels_data)


def parcel_to_response(parcel: Parcel) -> Dict[str, Any]:
    """Convert database parcel to API response format"""
    boundaries = {
        "cadastral": parcel.cadastral_boundary
    }
    if parcel.drone_boundary:
        boundaries["drone_ori"] = parcel.drone_boundary

    return {
        "parcel_id": parcel.parcel_id,
        "confidence": parcel.confidence,
        "priority": parcel.priority,
        "area_difference": parcel.area_difference,
        "geometry_conflict": parcel.geometry_conflict,
        "attribute_conflict": parcel.attribute_conflict,
        "duplicate_id": parcel.duplicate_id,
        "recommendation": parcel.recommendation,
        "boundaries": boundaries
    }
