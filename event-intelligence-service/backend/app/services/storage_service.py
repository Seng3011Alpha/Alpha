import json
import os
from pathlib import Path
from typing import Any

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = STORAGE_DIR / "raw"
STANDARDISED_DIR = STORAGE_DIR / "standardised"


def _ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "news").mkdir(exist_ok=True)
    (RAW_DIR / "stocks").mkdir(exist_ok=True)
    STANDARDISED_DIR.mkdir(parents=True, exist_ok=True)


def save_raw(data: Any, subdir: str, filename: str) -> str:
    _ensure_dirs()
    path = RAW_DIR / subdir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)


def save_standardised(data: dict, filename: str) -> str:
    _ensure_dirs()
    path = STANDARDISED_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)


def load_standardised(filename: str) -> dict | None:
    path = STANDARDISED_DIR / filename
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
