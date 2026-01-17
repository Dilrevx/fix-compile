"""Data models for Dockerfile fixing."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProblemType(str, Enum):
    """Types of Dockerfile build problems."""

    PATH_NOT_FOUND = "path_not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_SYNTAX = "invalid_syntax"
    MISSING_DEPENDENCY = "missing_dependency"
    IMAGE_NOT_FOUND = "image_not_found"
    BUILD_CONTEXT_ERROR = "build_context_error"
    UNKNOWN = "unknown"


@dataclass
class DockerfileProblem:
    """Represents a Dockerfile build problem."""

    dockerfile_path: str
    error_message: str
    problem_type: Optional[ProblemType] = None
    build_context: Optional[str] = None


@dataclass
class FixResult:
    """Result of a Dockerfile fix attempt."""

    success: bool
    original_dockerfile: str
    fixed_dockerfile: str
    explanation: str
    confidence: float  # 0.0 to 1.0
