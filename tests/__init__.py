"""Tests for the fix_compile package."""

from fix_compile.schema import DockerfileProblem, ProblemType
from fix_compile.workflows.analyzer import DockerfileAnalyzer


def test_analyzer_identifies_path_not_found():
    """Test that analyzer correctly identifies path not found errors."""
    error_msg = "COPY failed: stat /app/file.txt: no such file or directory"

    problem = DockerfileAnalyzer.analyze(
        dockerfile_path="Dockerfile",
        error_message=error_msg,
    )

    assert problem.problem_type == ProblemType.PATH_NOT_FOUND
    assert problem.error_message == error_msg


def test_analyzer_identifies_permission_denied():
    """Test that analyzer correctly identifies permission denied errors."""
    error_msg = "permission denied while trying to connect to Docker daemon"

    problem = DockerfileAnalyzer.analyze(
        dockerfile_path="Dockerfile",
        error_message=error_msg,
    )

    assert problem.problem_type == ProblemType.PERMISSION_DENIED


def test_analyzer_identifies_missing_dependency():
    """Test that analyzer correctly identifies missing dependency errors."""
    error_msg = "apt-get: command not found"

    problem = DockerfileAnalyzer.analyze(
        dockerfile_path="Dockerfile",
        error_message=error_msg,
    )

    assert problem.problem_type == ProblemType.MISSING_DEPENDENCY


def test_dockerfile_problem_creation():
    """Test DockerfileProblem dataclass creation."""
    problem = DockerfileProblem(
        dockerfile_path="Dockerfile",
        error_message="Some error",
        problem_type=ProblemType.UNKNOWN,
    )

    assert problem.dockerfile_path == "Dockerfile"
    assert problem.error_message == "Some error"
    assert problem.problem_type == ProblemType.UNKNOWN
