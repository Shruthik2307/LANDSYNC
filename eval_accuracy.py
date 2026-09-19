import numpy as np
from backend.services.ml_service import conflict_detector

def eval_model():
    # Generate a test set of 1000 samples
    test_data = []
    labels = []
    for _ in range(1000):
        area_diff = np.random.uniform(0, 20)
        iou = np.random.uniform(0.5, 1.0)
        parcel_data = {
            'area_difference': area_diff,
            'iou_score': iou,
            'centroid_distance': np.random.uniform(0, 5),
            'vertex_count_diff': np.random.randint(0, 10),
            'perimeter_ratio': np.random.uniform(0.9, 1.1),
            'geometry_conflict': np.random.choice([True, False]),
            'topology_valid': True,
            'attribute_mismatch_count': np.random.randint(0, 5),
            'duplicate_id': False
        }
        test_data.append(parcel_data)
        # Ground truth based on same logic as trainer
        labels.append(1 if area_diff > 10.0 or iou < 0.7 else 0)

    # Predict
    correct = 0
    for i in range(len(test_data)):
        pred, _ = conflict_detector.predict_conflict(test_data[i])
        if pred == labels[i]:
            correct += 1
    
    print(f"Accuracy: {(correct/len(test_data))*100:.2f}%")

if __name__ == "__main__":
    eval_model()
