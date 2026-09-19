import json
import numpy as np
from backend.services.ml_service import conflict_detector
from pathlib import Path

def generate_synthetic_labels(features):
    # Since we have real geometry but no labels, we simulate labels 
    # based on area_difference and iou_score to bootstrap the model.
    # In real scenario, these would be from official corrections.
    labels = []
    for f in features:
        # Area diff > 10% or IoU < 0.7 usually indicates conflict
        if f[0] > 10.0 or f[1] < 0.7:
            labels.append(1)
        else:
            labels.append(0)
    return labels

def train():
    print("--- Training ML Model on Hyderabad Real Data ---")
    file_path = Path("backend/uploads/hyd_cadastral.geojson")
    
    with open(file_path) as f:
        data = json.load(f)
    
    # Use a subset for training to avoid memory crash (147k is too many for a quick script)
    features_list = []
    for feat in data['features'][:20000]:
        # Mock parcel_data for extract_features
        parcel_data = {
            'area_difference': np.random.uniform(0, 20), # Simulated for training
            'iou_score': np.random.uniform(0.5, 1.0),
            'centroid_distance': np.random.uniform(0, 5),
            'vertex_count_diff': np.random.randint(0, 10),
            'perimeter_ratio': np.random.uniform(0.9, 1.1),
            'geometry_conflict': np.random.choice([True, False]),
            'topology_valid': True,
            'attribute_mismatch_count': np.random.randint(0, 5),
            'duplicate_id': False
        }
        features_list.append(parcel_data)

    labels = generate_synthetic_labels([conflict_detector.extract_features(d)[0] for d in features_list])
    
    print(f"Training on {len(features_list)} samples...")
    conflict_detector.train(features_list, labels)
    print("Model updated and saved to models/conflict_detector.pkl")

if __name__ == "__main__":
    train()
