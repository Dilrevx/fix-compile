"""Fix Docker build and runtime errors using LLM."""

__version__ = "0.2.0"

from .brain import Analyzer
from .config import config
from .executor import Executor
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
]
