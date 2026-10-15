"""Tests for configuration loading."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_settings_load():
    """Settings.load() must return a valid Settings object."""
    from config.settings import Settings
    s = Settings.load()
    assert s.data_dir
    assert s.database.path
    assert s.logging.level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def test_ai_disabled_by_default():
    """AI must be disabled when no provider/key is set."""
    from config.settings import Settings
    # Clear env to ensure default
    env_backup = {}
    for key in ("CAREEROS_AI_PROVIDER", "CAREEROS_AI_API_KEY"):
        env_backup[key] = os.environ.pop(key, None)

    s = Settings.load()
    assert not s.ai.enabled

    # Restore
    for key, val in env_backup.items():
        if val is not None:
            os.environ[key] = val


def test_ai_enabled_with_credentials():
    """AI should be enabled when both provider and key are set."""
    from config.settings import AISettings
    ai = AISettings(provider="openai", api_key="test-key")
    assert ai.enabled


def test_directories_are_strings():
    """All directory paths must be strings."""
    from config.settings import Settings
    s = Settings.load()
    assert isinstance(s.data_dir, str)
    assert isinstance(s.uploads_dir, str)
    assert isinstance(s.exports_dir, str)
    assert isinstance(s.backups_dir, str)
