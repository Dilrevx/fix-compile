"""Analyze Dockerfile build errors."""

import re
from typing import Optional

from ..models import DockerfileProblem, ProblemType


class DockerfileAnalyzer:
    """Analyze Dockerfile build errors and identify problem types."""

    # Error patterns for different problem types
    ERROR_PATTERNS = {
        ProblemType.PATH_NOT_FOUND: [
            r"COPY|ADD.*No such file or directory",
            r"stat.*no such file or directory",
            r"cannot find path",
        ],
        ProblemType.PERMISSION_DENIED: [
            r"permission denied",
            r"Permission denied while trying to connect",
        ],
        ProblemType.MISSING_DEPENDENCY: [
            r"Command.*not found",
            r"ModuleNotFoundError",
            r"ImportError",
            r"cannot find -l",
        ],
        ProblemType.IMAGE_NOT_FOUND: [
            r"image not found",
            r"Error response from daemon.*not found",
        ],
        ProblemType.INVALID_SYNTAX: [
            r"syntax error",
            r"invalid syntax",
            r"Unexpected token",
        ],
        ProblemType.BUILD_CONTEXT_ERROR: [
            r"build context",
            r"context outside of",
        ],
    }

    @staticmethod
    def analyze(
        dockerfile_path: str, error_message: str, build_context: Optional[str] = None
    ) -> DockerfileProblem:
        """
        Analyze a Dockerfile build error.

        Args:
            dockerfile_path: Path to the Dockerfile
            error_message: The build error message
            build_context: The Docker build context directory

        Returns:
            DockerfileProblem with identified problem type
        """
        problem_type = DockerfileAnalyzer._identify_problem_type(error_message)

        return DockerfileProblem(
            dockerfile_path=dockerfile_path,
            error_message=error_message,
            problem_type=problem_type,
            build_context=build_context,
        )

    @staticmethod
    def _identify_problem_type(error_message: str) -> ProblemType:
        """Identify the problem type from error message."""
        error_lower = error_message.lower()

        for problem_type, patterns in DockerfileAnalyzer.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return problem_type

        return ProblemType.UNKNOWN
