"""
ML Model Training Script
Train conflict detection model on sample parcel data
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.ml_service import conflict_detector
from services.landsync_service import load_data, get_all_parcels
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def prepare_training_data():
    """Load parcels and prepare training dataset"""
    logger.info("Loading parcel data...")
    load_data()
    parcels = get_all_parcels()

    logger.info(f"Loaded {len(parcels)} parcels")

    # Create labels based on conflict flags
    training_data = []
    labels = []

    for parcel in parcels:
        training_data.append(parcel)
        # Label: 1 if any conflict, 0 otherwise
        has_conflict = (
            parcel['geometry_conflict'] or
            parcel['attribute_conflict'] or
            parcel['duplicate_id']
        )
        labels.append(1 if has_conflict else 0)

    return training_data, labels


def main():
    logger.info("=" * 60)
    logger.info("ML Conflict Detection Model Training")
    logger.info("=" * 60)

    # Prepare data
    training_data, labels = prepare_training_data()

    conflict_count = sum(labels)
    no_conflict_count = len(labels) - conflict_count

    logger.info(f"Training dataset: {len(training_data)} samples")
    logger.info(f"  Conflicts: {conflict_count}")
    logger.info(f"  No conflicts: {no_conflict_count}")

    if len(training_data) < 10:
        logger.warning("Dataset too small for meaningful training (< 10 samples)")
        logger.info("Model will use rule-based fallback")
        return

    # Train model
    logger.info("\nTraining ML model...")
    conflict_detector.train(training_data, labels)

    # Test predictions
    logger.info("\n" + "=" * 60)
    logger.info("Testing predictions on first 5 parcels:")
    logger.info("=" * 60)

    for i, parcel in enumerate(training_data[:5]):
        has_conflict, confidence = conflict_detector.predict_conflict(parcel)
        logger.info(
            f"Parcel {parcel['parcel_id']}: "
            f"conflict={has_conflict}, confidence={confidence:.1f}%, "
            f"priority={parcel['priority']}"
        )

    logger.info("\n" + "=" * 60)
    logger.info("Training complete! Model saved.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
