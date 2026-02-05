"""Data models and schemas for fix-compile."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ============================================================================
# Enums
# ============================================================================


class ProblemType(str, Enum):
    """Types of Dockerfile build problems."""

    PATH_NOT_FOUND = "path_not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_SYNTAX = "invalid_syntax"
    MISSING_DEPENDENCY = "missing_dependency"
    IMAGE_NOT_FOUND = "image_not_found"
    BUILD_CONTEXT_ERROR = "build_context_error"
    UNKNOWN = "unknown"


class OperationType(str, Enum):
    """Type of operation being performed."""

    BUILD = "build"
    RUN = "run"


class FixStatus(str, Enum):
    """Status of a fix attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_RETRY = "needs_retry"


class FixType(str, Enum):
    """Type of fix suggestion."""

    COMMAND = "command"  # Fix by modifying/running a command
    FILE = "file"  # Fix by modifying file content
    DOCKER = "docker"  # Docker-specific fix (dockerfile)


# ============================================================================
# Dataclass Models
# ============================================================================


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


# ============================================================================
# Input Models (for Analyzer)
# ============================================================================


class GeneralAnalysisContext(BaseModel):
    """Input context for general analysis."""

    error_log: str = Field(description="Build/run error log")
    cwd: str = Field(default=".", description="Current working directory")
    previous_attempts: int = Field(
        default=0, description="Number of previous fix attempts"
    )


class DockerAnalysisContext(BaseModel):
    """Input context for LLM analysis (The Brain)."""

    dockerfile_content: str = Field(description="Content of the Dockerfile")
    error_log: str = Field(description="Build/run error log from Docker")
    operation_type: OperationType = Field(description="Build or run operation")
    dockerfile_path: str = Field(default="Dockerfile", description="Path to Dockerfile")
    build_context: str = Field(default=".", description="Docker build context path")
    previous_attempts: int = Field(
        default=0, description="Number of previous fix attempts"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "dockerfile_content": "FROM ubuntu:20.04\nRUN apt-get update",
                "error_log": "E: Failed to fetch http://archive.ubuntu.com/...",
                "operation_type": "build",
                "dockerfile_path": "Dockerfile",
                "build_context": ".",
                "previous_attempts": 0,
            }
        }


# ============================================================================
# Output Models (from Analyzer)
# ============================================================================


class FixSuggestion(BaseModel):
    """Fix suggestion from LLM (The Brain's output)."""

    reason: str = Field(description="Explanation of why this fix is needed")
    fix_type: FixType = Field(description="Type of fix (command, file, or docker)")

    # For command fixes
    command: Optional[str] = Field(
        default=None, description="Command to execute or modify"
    )
    command_explanation: Optional[str] = Field(
        default=None, description="Explanation of command fix"
    )

    # For file fixes
    file_path: Optional[str] = Field(
        default=None, description="Path to file to be modified (relative to cwd)"
    )
    new_content: Optional[str] = Field(
        default=None, description="New content for the file"
    )
    file_explanation: Optional[str] = Field(
        default=None, description="Explanation of file fix"
    )

    # For docker fixes
    dockerfile_path: Optional[str] = Field(
        default=None, description="Path to Dockerfile"
    )
    dockerfile_content: Optional[str] = Field(
        default=None, description="New Dockerfile content"
    )

    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    changes_summary: str = Field(description="Brief summary of changes made")

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Missing package in dependencies",
                "fix_type": "file",
                "file_path": "requirements.txt",
                "new_content": "numpy==1.24.0\npandas==2.0.0",
                "file_explanation": "Added missing numpy and pandas packages",
                "confidence": 0.85,
                "changes_summary": "Updated requirements.txt with missing dependencies",
            }
        }


# ============================================================================
# Execution Models (for Executor)
# ============================================================================


class CommandResult(BaseModel):
    """Result of a shell command execution."""

    exit_code: int = Field(description="Exit code of the command")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    success: bool = Field(description="Whether command succeeded")
    command: str = Field(description="Command that was executed")
    cwd: str = Field(default="", description="Working directory where command was run")

    @property
    def output(self) -> str:
        """Get combined output (prefer stderr for errors, stdout otherwise)."""
        if not self.success and self.stderr:
            return self.stderr
        return self.stdout or self.stderr


class DockerBuildConfig(BaseModel):
    """Configuration for Docker build operation."""

    context: str = Field(default=".", description="Build context path")
    dockerfile: str = Field(default="Dockerfile", description="Path to Dockerfile")
    tag: Optional[str] = Field(default=None, description="Image tag")
    build_args: dict[str, str] = Field(
        default_factory=dict, description="Build arguments"
    )
    no_cache: bool = Field(default=False, description="Don't use cache")


class DockerRunConfig(BaseModel):
    """Configuration for Docker run operation."""

    image: str = Field(description="Image to run")
    args: list[str] = Field(
        default_factory=list, description="Additional run arguments"
    )
    detach: bool = Field(default=False, description="Run in background")
    remove: bool = Field(default=True, description="Remove container after exit")


# ============================================================================
# Loop State Models
# ============================================================================


class LoopState(BaseModel):
    """State tracking for the fix loop."""

    current_attempt: int = Field(default=0, description="Current attempt number")
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    last_error: Optional[str] = Field(
        default=None, description="Last error encountered"
    )
    operation_type: OperationType = Field(description="Current operation type")
    build_succeeded: bool = Field(default=False, description="Whether build passed")
    run_succeeded: bool = Field(default=False, description="Whether run passed")

    def can_retry(self) -> bool:
        """Check if we can retry."""
        return self.current_attempt < self.max_attempts

    def increment_attempt(self) -> None:
        """Increment attempt counter."""
        self.current_attempt += 1
