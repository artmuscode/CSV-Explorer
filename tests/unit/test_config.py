from app.config import Config


def test_default_config_page_size_is_25_and_max_page_size_is_100():
    assert Config.PAGE_SIZE == 25
    assert Config.MAX_PAGE_SIZE == 100


def test_default_config_blocks_private_urls_and_scans_on_startup():
    assert Config.ALLOW_PRIVATE_URLS is False
    assert Config.SCAN_ON_STARTUP is True
