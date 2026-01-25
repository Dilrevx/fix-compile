"""Tests for the new architecture."""

import pytest

from fix_compile.schema import (
    AnalysisContext,
    CommandResult,
    DockerBuildConfig,
    FixSuggestion,
    LoopState,
    OperationType,
)


class TestSchema:
    """Test data models."""

    def test_analysis_context_creation(self):
        """Test creating an analysis context."""
        context = AnalysisContext(
            dockerfile_content="FROM ubuntu:22.04",
            error_log="Error: failed to build",
            operation_type=OperationType.BUILD,
        )

        assert context.dockerfile_content == "FROM ubuntu:22.04"
        assert context.error_log == "Error: failed to build"
        assert context.operation_type == OperationType.BUILD
        assert context.dockerfile_path == "Dockerfile"
        assert context.build_context == "."
        assert context.previous_attempts == 0

    def test_fix_suggestion_validation(self):
        """Test fix suggestion validation."""
        suggestion = FixSuggestion(
            reason="Base image is outdated",
            file_path="Dockerfile",
            new_content="FROM ubuntu:24.04",
            confidence=0.95,
            changes_summary="Updated base image",
        )

        assert suggestion.confidence == 0.95
        assert 0.0 <= suggestion.confidence <= 1.0

    def test_command_result(self):
        """Test command result model."""
        result = CommandResult(
            exit_code=0,
            stdout="Success",
            stderr="",
            success=True,
            command="docker build .",
            cwd="/home/user/project",
        )

        assert result.success
        assert result.output == "Success"

    def test_command_result_error(self):
        """Test command result with error."""
        result = CommandResult(
            exit_code=1,
            stdout="",
            stderr="Build failed",
            success=False,
            command="docker build .",
            cwd="/home/user/project",
        )

        assert not result.success
        assert result.output == "Build failed"

    def test_loop_state(self):
        """Test loop state management."""
        state = LoopState(
            max_attempts=3,
            operation_type=OperationType.BUILD,
        )

        assert state.can_retry()
        assert state.current_attempt == 0

        state.increment_attempt()
        assert state.current_attempt == 1
        assert state.can_retry()

        state.increment_attempt()
        state.increment_attempt()
        assert state.current_attempt == 3
        assert not state.can_retry()

    def test_docker_build_config(self):
        """Test Docker build config."""
        config = DockerBuildConfig(
            context="./app",
            dockerfile="Dockerfile.prod",
            tag="myapp:v1.0",
            no_cache=True,
        )

        assert config.context == "./app"
        assert config.dockerfile == "Dockerfile.prod"
        assert config.tag == "myapp:v1.0"
        assert config.no_cache is True


class TestExecutor:
    """Test executor functionality."""

    def test_executor_import(self):
        """Test that executor can be imported."""
        from fix_compile.workflows.executor import Executor

        executor = Executor(verbose=False)
        assert executor is not None

    def test_executor_file_exists(self):
        """Test file exists check."""
        from fix_compile.workflows.executor import Executor

        executor = Executor()
        # This file should exist
        assert executor.file_exists("pyproject.toml")
        # This file should not exist
        assert not executor.file_exists("nonexistent.txt")


class TestBrain:
    """Test brain/analyzer functionality."""

    def test_analyzer_import(self):
        """Test that analyzer can be imported."""
        from fix_compile.workflows.brain import Analyzer

        # Don't initialize without API key
        assert Analyzer is not None

    def test_analyzer_prompt_building(self):
        """Test prompt building logic."""

        # Create a mock analyzer (don't call API)
        context = AnalysisContext(
            dockerfile_content="FROM ubuntu:20.04",
            error_log="Error occurred",
            operation_type=OperationType.BUILD,
            previous_attempts=2,
        )

        # We can't test the actual prompt without mocking,
        # but we can test the context validation
        assert context.previous_attempts == 2


class TestConfig:
    """Test configuration."""

    def test_config_import(self):
        """Test that config can be imported."""
        from fix_compile.config import config

        assert config is not None
        assert hasattr(config, "FIXER_MODEL")
        assert hasattr(config, "MAX_TOKENS")
        assert hasattr(config, "TIMEOUT")

    def test_config_defaults(self):
        """Test config default values."""
        from fix_compile.config import config

        assert config.MAX_TOKENS == 32768
        assert config.TIMEOUT == 300
        assert config.LOG_LEVEL == "INFO"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
