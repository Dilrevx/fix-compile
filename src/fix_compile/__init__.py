"""Fix Docker build and runtime errors using LLM."""

import fix_compile.constants

__version__ = fix_compile.constants.__version__

from fix_compile.config import ConfigService

from .schema import (
    AnalysisContext,
    CommandResult,
    DockerBuildConfig,
    DockerRunConfig,
    FixSuggestion,
)
from .workflows.brain import Analyzer
from .workflows.executor import Executor
from .workflows.fixer import DockerfileFixer, FixResult

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
