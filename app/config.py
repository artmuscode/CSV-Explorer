"""Application configuration classes."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Default application configuration."""

    SECRET_KEY = "dev"

    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True

    CSV_DIR = BASE_DIR / "data" / "csv"
    DUCKDB_PATH = BASE_DIR / "data" / "app.duckdb"

    PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100

    MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    DOWNLOAD_TIMEOUT = 30

    ALLOW_PRIVATE_URLS = False
    SCAN_ON_STARTUP = True


class TestConfig(Config):
    """Configuration used by the test suite."""

    TESTING = True
    SCAN_ON_STARTUP = False
    SECRET_KEY = "test"
