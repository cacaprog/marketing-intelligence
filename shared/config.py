from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "raw" / "b2b_attribution.db"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
TIME_DECAY_HALF_LIFE = 14  # days; matches SCM half-life used in generate_dataset.py

TRAIN_CUTOFF_DATE: str = "2024-03-01"
MODEL_DIR: Path = PROCESSED_DIR / "01-attribution" / "models"

DATASET_REFERENCE_DATE: str = "2024-09-25"
COHORT_WINDOWS: list[int] = [1, 3, 6, 9, 12]
