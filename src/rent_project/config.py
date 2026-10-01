from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"
ADDRESSBASE_DIRECTORY_RAW = DATA_DIRECTORY / "raw" / "address-base-plus"
ADDRESSBASE_DIRECTORY_INTERIM = DATA_DIRECTORY / "interim" / "address-base-plus"
