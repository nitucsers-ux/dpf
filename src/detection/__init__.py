"""Feature-engineered deepfake detector."""
from .detector import FakeDetector, extract_features, featurise_dataset

__all__ = ["FakeDetector", "extract_features", "featurise_dataset"]
