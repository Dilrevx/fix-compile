"""Configuration file management for fix-compile."""

import json
from pathlib import Path
from typing import Any, Dict, Optional


# Get config directory
CONFIG_DIR = Path.home() / ".config" / "fix-compile"
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config_file() -> Dict[str, Any]:
    """
    Load configuration from file.

    Returns:
        Dict with configuration values, or empty dict if file doesn't exist
    """
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config_file(config: Dict[str, Any]) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary to save
    """
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_config_value(key: str, env_var: Optional[str] = None) -> Optional[str]:
    """
    Get configuration value from file or environment variable.

    Priority: config file > environment variable

    Args:
        key: Configuration key
        env_var: Environment variable name to check as fallback

    Returns:
        Configuration value or None
    """
    import os

    # Check config file first
    config = load_config_file()
    if key in config:
        return config[key]

    # Fall back to environment variable
    if env_var:
        return os.getenv(env_var)

    return None


def set_config_value(key: str, value: str) -> None:
    """
    Set configuration value in file.

    Args:
        key: Configuration key
        value: Configuration value
    """
    config = load_config_file()
    config[key] = value
    save_config_file(config)


def delete_config_value(key: str) -> None:
    """
    Delete configuration value from file.

    Args:
        key: Configuration key
    """
    config = load_config_file()
    if key in config:
        del config[key]
        save_config_file(config)


def list_all_config() -> Dict[str, Any]:
    """
    List all configuration values.

    Returns:
        All configuration values
    """
    return load_config_file()


def validate_config_key(key: str) -> bool:
    """
    Validate if a configuration key is valid.

    Valid keys:
    - OPENAI_API_BASE
    - OPENAI_API_KEY
    - EXECUTOR_MODEL
    - FIXER_MODEL
    - LOG_LEVEL
    - MAX_TOKENS
    - TIMEOUT

    Args:
        key: Configuration key to validate

    Returns:
        True if valid, False otherwise
    """
    valid_keys = {
        "OPENAI_API_BASE",
        "OPENAI_API_KEY",
        "EXECUTOR_MODEL",
        "FIXER_MODEL",
        "LOG_LEVEL",
        "MAX_TOKENS",
        "TIMEOUT",
    }
    return key in valid_keys


def get_config_file_path() -> Path:
    """
    Get the configuration file path.

    Returns:
        Path to configuration file
    """
    return CONFIG_FILE


def get_config_dir_path() -> Path:
    """
    Get the configuration directory path.

    Returns:
        Path to configuration directory
    """
    return CONFIG_DIR
