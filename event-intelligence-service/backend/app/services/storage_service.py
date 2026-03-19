import json
import os
from pathlib import Path
from typing import Any

_S3_BUCKET = os.environ.get("S3_BUCKET_NAME")

if _S3_BUCKET:
    import boto3
    _s3 = boto3.client("s3")

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = STORAGE_DIR / "raw"
STANDARDISED_DIR = STORAGE_DIR / "standardised"


def _ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "news").mkdir(exist_ok=True)
    (RAW_DIR / "stocks").mkdir(exist_ok=True)
    STANDARDISED_DIR.mkdir(parents=True, exist_ok=True)


def save_raw(data: Any, subdir: str, filename: str) -> str:
    if _S3_BUCKET:
        key = f"raw/{subdir}/{filename}"
        _s3.put_object(Bucket=_S3_BUCKET, Key=key, Body=json.dumps(data, ensure_ascii=False))
        return f"s3://{_S3_BUCKET}/{key}"
    _ensure_dirs()
    path = RAW_DIR / subdir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)


def save_standardised(data: dict, filename: str) -> str:
    if _S3_BUCKET:
        key = f"standardised/{filename}"
        _s3.put_object(Bucket=_S3_BUCKET, Key=key, Body=json.dumps(data, ensure_ascii=False))
        return f"s3://{_S3_BUCKET}/{key}"
    _ensure_dirs()
    path = STANDARDISED_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)


def load_standardised(filename: str) -> dict | None:
    if _S3_BUCKET:
        try:
            obj = _s3.get_object(Bucket=_S3_BUCKET, Key=f"standardised/{filename}")
            return json.loads(obj["Body"].read())
        except _s3.exceptions.NoSuchKey:
            return None
    path = STANDARDISED_DIR / filename
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
