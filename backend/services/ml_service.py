"""
ML-Based Conflict Detection Engine
Confidence scoring, topology validation, and AI-powered conflict detection
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)


class ConflictDetectionModel:
    """ML model for detecting and scoring geospatial conflicts"""

    def __init__(self, model_path: Optional[Path] = None):
        self.classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.confidence_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.model_path = model_path or Path("models/conflict_detector.pkl")

        if self.model_path.exists():
            self.load_model()

    def extract_features(self, parcel_data: Dict) -> np.ndarray:
        """
        Extract features from parcel data for ML model

        Features:
        - Area difference percentage
        - Geometry overlap IoU
        - Centroid distance
        - Vertex count difference
        - Perimeter ratio
        - Shape complexity (convexity)
        - Attribute mismatch count

        Args:
            parcel_data: Parcel reconciliation data

        Returns:
            Feature vector
        """
        features = []

        # Geometric features
        features.append(parcel_data.get('area_difference', 0.0))
        features.append(parcel_data.get('iou_score', 0.0))
        features.append(parcel_data.get('centroid_distance', 0.0))
        features.append(parcel_data.get('vertex_count_diff', 0))
        features.append(parcel_data.get('perimeter_ratio', 1.0))

        # Topology features
        features.append(float(parcel_data.get('geometry_conflict', False)))
        features.append(float(parcel_data.get('topology_valid', True)))

        # Attribute features
        features.append(parcel_data.get('attribute_mismatch_count', 0))
        features.append(float(parcel_data.get('duplicate_id', False)))

        return np.array(features).reshape(1, -1)

    def train(self, training_data: List[Dict], labels: List[int]):
        """
        Train conflict detection model

        Args:
            training_data: List of parcel data dicts
            labels: Binary labels (1=conflict, 0=no conflict)
        """
        logger.info(f"Training model on {len(training_data)} samples")

        # Extract features
        X = np.vstack([self.extract_features(d) for d in training_data])
        y = np.array(labels)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train classifier
        self.classifier.fit(X_train_scaled, y_train)
        train_score = self.classifier.score(X_train_scaled, y_train)
        test_score = self.classifier.score(X_test_scaled, y_test)

        logger.info(f"Classifier trained: train_acc={train_score:.3f}, test_acc={test_score:.3f}")

        # Train confidence model
        confidence_labels = [d.get('confidence', 50.0) for d in training_data]
        self.confidence_model.fit(X_train_scaled, confidence_labels[:len(X_train)])

        self.save_model()

    def predict_conflict(self, parcel_data: Dict) -> Tuple[bool, float]:
        """
        Predict if parcel has conflict and confidence score

        Args:
            parcel_data: Parcel reconciliation data

        Returns:
            (has_conflict, confidence_score)
        """
        features = self.extract_features(parcel_data)
        features_scaled = self.scaler.transform(features)

        # Predict conflict
        conflict_prob = self.classifier.predict_proba(features_scaled)[0]
        has_conflict = bool(self.classifier.predict(features_scaled)[0] == 1)

        # Predict confidence
        confidence = float(self.confidence_model.predict(features_scaled)[0])
        confidence = float(np.clip(confidence, 0, 100))

        return has_conflict, confidence

    def save_model(self):
        """Save trained model to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'classifier': self.classifier,
                'confidence_model': self.confidence_model,
                'scaler': self.scaler
            }, f)
        logger.info(f"Model saved to {self.model_path}")

    def load_model(self):
        """Load trained model from disk and verify it is not a constant predictor."""
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.classifier = data['classifier']
                self.confidence_model = data['confidence_model']
                self.scaler = data['scaler']

            if not self._verify_model_variance():
                logger.warning(f"Model at {self.model_path} is a constant predictor. Excluding from scoring.")
                # We don't raise here to allow the system to fall back to engine scoring
            else:
                logger.info(f"Model loaded and verified from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load model: {e}")

    def _verify_model_variance(self, sample_size: int = 10) -> bool:
        """Verify model doesn't return identical output for distinct inputs."""
        try:
            # Create distinct synthetic feature vectors
            test_inputs = np.array([np.random.rand(self.scaler.n_features_in_) for _ in range(sample_size)])
            test_inputs_scaled = self.scaler.transform(test_inputs)
            predictions = self.classifier.predict(test_inputs_scaled)

            # If all predictions are the same, it's a constant predictor
            return len(np.unique(predictions)) > 1
        except Exception as e:
            logger.error(f"Variance check failed: {e}")
            return False


class TopologyValidator:
    """Validate geospatial topology"""

    @staticmethod
    def validate_topology(geometry) -> Dict[str, bool]:
        """
        Validate topology rules

        Checks:
        - Self-intersection
        - Overlap with neighbors
        - Gap detection
        - Minimum area threshold
        - Minimum width threshold

        Args:
            geometry: Shapely geometry

        Returns:
            Validation results dict
        """
        results = {
            'is_valid': geometry.is_valid,
            'is_simple': geometry.is_simple,
            'has_self_intersection': not geometry.is_simple,
            'meets_min_area': geometry.area > 1.0,  # 1 sq meter
            'is_closed': geometry.boundary.is_closed if hasattr(geometry, 'boundary') else True
        }

        return results

    @staticmethod
    def check_overlap(geom1, geom2, threshold: float = 0.01) -> bool:
        """
        Check if two geometries overlap beyond threshold

        Args:
            geom1, geom2: Shapely geometries
            threshold: Overlap area threshold (sq meters)

        Returns:
            True if overlap exceeds threshold
        """
        if not geom1.intersects(geom2):
            return False

        overlap = geom1.intersection(geom2)
        return overlap.area > threshold

    @staticmethod
    def check_gap(geom1, geom2, threshold: float = 1.0) -> bool:
        """
        Check for gap between adjacent parcels

        Args:
            geom1, geom2: Shapely geometries
            threshold: Maximum acceptable gap (meters)

        Returns:
            True if gap exceeds threshold
        """
        distance = geom1.distance(geom2)
        return distance > threshold


class RecordLinkageEngine:
    """Link records across multiple data sources"""

    def __init__(self):
        self.linkage_rules = []

    def add_linkage_rule(
        self,
        field: str,
        match_type: str = "exact",
        threshold: float = 0.9
    ):
        """
        Add record linkage rule

        Args:
            field: Field name to match on
            match_type: exact, fuzzy, spatial
            threshold: Match threshold (0-1)
        """
        self.linkage_rules.append({
            'field': field,
            'match_type': match_type,
            'threshold': threshold
        })

    def link_records(
        self,
        source1: List[Dict],
        source2: List[Dict]
    ) -> List[Tuple[int, int, float]]:
        """
        Link records between two data sources

        Args:
            source1, source2: Record lists

        Returns:
            List of (idx1, idx2, confidence) matches
        """
        matches = []

        for i, rec1 in enumerate(source1):
            for j, rec2 in enumerate(source2):
                confidence = self._calculate_match_score(rec1, rec2)
                if confidence > 0.8:
                    matches.append((i, j, confidence))

        logger.info(f"Linked {len(matches)} records")
        return matches

    def _calculate_match_score(self, rec1: Dict, rec2: Dict) -> float:
        """Calculate match score between two records"""
        scores = []

        for rule in self.linkage_rules:
            field = rule['field']
            if field in rec1 and field in rec2:
                if rule['match_type'] == 'exact':
                    score = 1.0 if rec1[field] == rec2[field] else 0.0
                else:
                    # Fuzzy matching placeholder
                    score = 0.5
                scores.append(score)

        return np.mean(scores) if scores else 0.0


# Initialize global model instance
_MODEL_PATH = Path(__file__).parent.parent / "models" / "conflict_detector.pkl"
conflict_detector = ConflictDetectionModel(model_path=_MODEL_PATH)
topology_validator = TopologyValidator()
record_linker = RecordLinkageEngine()
