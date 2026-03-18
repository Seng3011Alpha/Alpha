#tests for storage_service - saving and loading json from disc
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from app.services.storage_service import save_raw, save_standardized, load_standardized


SAMPLE_DATA = {"key": "value", "number": 42}
SAMPLE_DATASET = {
    "data_source": "test",
    "dataset_type": "Test",
    "dataset_id": "test-001",
    "time_object": {"timestamp": "2024-01-01 00:00:00", "timezone": "UTC"},
    "events": [],
}


class TestSaveRaw:
    def test_saves_file_and_returns_path(self, tmp_path):
        with patch("app.services.storage_service.RAW_DIR", tmp_path / "raw"), \
             patch("app.services.storage_service.STANDARDIZED_DIR", tmp_path / "standardised"):
            result = save_raw(SAMPLE_DATA, "stocks", "test_stocks.json")
            saved = Path(result)
            assert saved.exists()
            assert json.loads(saved.read_text()) == SAMPLE_DATA

    def test_creates_subdirectory(self, tmp_path):
        #check the news subdir gets made automatically
        with patch("app.services.storage_service.RAW_DIR", tmp_path / "raw"), \
             patch("app.services.storage_service.STANDARDIZED_DIR", tmp_path / "standardised"):
            save_raw(SAMPLE_DATA, "news", "test_news.json")
            assert (tmp_path / "raw" / "news").is_dir()


class TestSaveStandardised:
    def test_saves_file_and_returns_path(self, tmp_path):
        with patch("app.services.storage_service.RAW_DIR", tmp_path / "raw"), \
             patch("app.services.storage_service.STANDARDIZED_DIR", tmp_path / "standardised"):
            result = save_standardized(SAMPLE_DATASET, "combined_events.json")
            saved = Path(result)
            assert saved.exists()
            assert json.loads(saved.read_text()) == SAMPLE_DATASET

    def test_overwrites_existing_file(self, tmp_path):
        #second write should replace the first, not append
        std_dir = tmp_path / "standardised"
        with patch("app.services.storage_service.RAW_DIR", tmp_path / "raw"), \
             patch("app.services.storage_service.STANDARDIZED_DIR", std_dir):
            save_standardized({"version": 1}, "combined_events.json")
            save_standardized({"version": 2}, "combined_events.json")
            result = json.loads((std_dir / "combined_events.json").read_text())
            assert result["version"] == 2


class TestLoadStandardised:
    def test_returns_none_when_file_missing(self, tmp_path):
        with patch("app.services.storage_service.STANDARDIZED_DIR", tmp_path / "standardised"):
            result = load_standardized("does_not_exist.json")
            assert result is None

    def test_loads_existing_file(self, tmp_path):
        std_dir = tmp_path / "standardised"
        std_dir.mkdir(parents=True)
        (std_dir / "test.json").write_text(json.dumps(SAMPLE_DATASET))
        with patch("app.services.storage_service.STANDARDIZED_DIR", std_dir):
            result = load_standardized("test.json")
            assert result == SAMPLE_DATASET

    def test_returns_dict(self, tmp_path):
        std_dir = tmp_path / "standardised"
        std_dir.mkdir(parents=True)
        (std_dir / "test.json").write_text(json.dumps(SAMPLE_DATASET))
        with patch("app.services.storage_service.STANDARDIZED_DIR", std_dir):
            result = load_standardized("test.json")
            assert isinstance(result, dict)

