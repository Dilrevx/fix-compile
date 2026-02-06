"""Fix Docker build and runtime errors using LLM."""

import fix_compile.constants

__version__ = fix_compile.constants.__version__

from fix_compile.config import ConfigService

from .executor import Executor
from .schema import (
    CommandResult,
    DockerBuildConfig,
    DockerRunConfig,
    FixSuggestion,
    GeneralAnalysisContext,
)
from .utils.prompt_builder import PromptBuilder
from .workflows.docker_fixer import DockerFixer
from .workflows.general_fixer import GeneralFixer

__all__ = [
    "GeneralFixer",
    "Executor",
    "config",
    "GeneralAnalysisContext",
    "FixSuggestion",
    "CommandResult",
    "DockerBuildConfig",
    "DockerRunConfig",
    "DockerFixer",
    "PromptBuilder",
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
    "ConfigService",
]
