import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

def generate_synthetic_data(samples=5000):
    np.random.seed(42)
    # Features: IoU (0-1), AreaDelta (0-1), AttributeMatch (0-1)
    iou = np.random.uniform(0, 1, samples)
    area_delta = np.random.uniform(0, 1, samples)
    attr_match = np.random.uniform(0, 1, samples)
    
    # Label: 0 = No Conflict, 1 = Minor Conflict, 2 = Critical Conflict
    # Logic: Low IoU + High AreaDelta = Critical
    labels = []
    for i in range(samples):
        score = (1 - iou[i]) * 0.5 + area_delta[i] * 0.3 + (1 - attr_match[i]) * 0.2
        if score > 0.7:
            labels.append(2)
        elif score > 0.4:
            labels.append(1)
        else:
            labels.append(0)
            
    return pd.DataFrame({'iou': iou, 'area_delta': area_delta, 'attr_match': attr_match}), np.array(labels)

def train():
    print("Generating synthetic geospatial conflict data...")
    X, y = generate_synthetic_data()
    
    print("Training RandomForestClassifier...")
    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    clf.fit(X, y)
    
    # Save model
    os.makedirs("backend/models", exist_ok=True)
    model_path = "backend/models/conflict_detector.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    
    print(f"Model saved to {model_path}")
    
    # Test one sample
    test_sample = np.array([[0.2, 0.8, 0.1]]) # Low IoU, High Delta, Low Match -> Should be Critical (2)
    prediction = clf.predict(test_sample)
    print(f"Test Sample [0.2, 0.8, 0.1] Prediction: {prediction[0]}")

if __name__ == "__main__":
    train()
