from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "raw" / "b2b_attribution.db"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
TIME_DECAY_HALF_LIFE = 14  # days; matches SCM half-life used in generate_dataset.py
