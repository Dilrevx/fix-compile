"""Fix Docker build and runtime errors using LLM."""

__version__ = "0.2.0"

from .brain import Analyzer
from .config import config
from .config_manager import (
    delete_config_value,
    get_config_dir_path,
    get_config_file_path,
    list_all_config,
    load_config_file,
    save_config_file,
    set_config_value,
    validate_config_key,
)
from .executor import Executor
from .fixer import DockerfileFixer, FixResult
from .observability import get_phoenix_status, setup_phoenix_tracing
from .schema import (
    AnalysisContext,
    CommandResult,
    DockerBuildConfig,
    DockerRunConfig,
    FixSuggestion,
)

__all__ = [
    "Analyzer",
    "Executor",
    "config",
    "AnalysisContext",
    "FixSuggestion",
    "CommandResult",
    "DockerBuildConfig",
    "DockerRunConfig",
    "DockerfileFixer",
    "FixResult",
    "setup_phoenix_tracing",
    "get_phoenix_status",
    "set_config_value",
    "get_config_value",
    "delete_config_value",
    "list_all_config",
    "load_config_file",
    "save_config_file",
    "validate_config_key",
    "get_config_file_path",
    "get_config_dir_path",
]
