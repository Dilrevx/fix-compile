"""Docker fixer with auto-fix pipeline."""

import os
from pathlib import Path
from typing import Optional

from fix_compile.config import Configs
from fix_compile.executor import Executor
from fix_compile.schema import (
    DockerAnalysisContext,
    GeneralAnalysisContext,
    OperationType,
)
from fix_compile.utils import ui
from fix_compile.utils.io import cmd2hash
from fix_compile.workflows.general_fixer import GeneralFixer


class DockerFixer:
    """Docker command executor with auto-fix capabilities."""

    def __init__(self, config: Configs):
        """
        Initialize Docker fixer.

        Args:
            config: Application configuration
        """
        self.config = config
        self.executor = Executor()
        self.fixer = GeneralFixer()

    def run_pipeline(
        self,
        cmd: list[str],
        cwd: Path,
        dockerfile_path: Optional[Path] = None,
        no_fix: bool = False,
        force_rerun: bool = False,
    ) -> None:
        """
        Run Docker command with auto-fix pipeline.

        Args:
            cmd: Docker command to execute
            cwd: Working directory
            dockerfile_path: Path to Dockerfile (for build commands)
            no_fix: Disable AI analysis and auto-fix
            force_rerun: Force re-execution even if cached log exists
        """
        # 1. Environment preparation: force DOCKER_BUILDKIT=0 for clear logs
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "0"

        # 2. Cache calculation
        task_hash = cmd2hash(cmd, cwd)
        log_dir = self.config.dir_configs.cache_dir / task_hash
        log_file = log_dir / "docker.log"

        # 3. Execution strategy
        # Check if we can skip execution
        if not force_rerun and log_file.exists():
            ui.info(f"📦 Using cached log from: {log_file}")
            error_log = log_file.read_text(encoding="utf-8")
            success = False  # Assume cached logs are from failures
        else:
            # Execute command with streaming output
            ui.info(f"🐳 Executing: {' '.join(cmd)}")

            # Ensure log directory exists
            log_dir.mkdir(parents=True, exist_ok=True)

            # Execute with custom environment
            result = self.executor.execute(
                cmd,
                cwd=str(cwd),
                stream=True,
            )

            # Save logs
            error_log = (result.stdout or "") + (result.stderr or "")
            log_file.write_text(error_log, encoding="utf-8")
            ui.debug(f"Saved log to: {log_file}")

            success = result.success

        # 4. Result handling
        if success:
            ui.success("✅ Docker command succeeded!")
            return

        ui.warning("❌ Docker command failed (exit code: non-zero)")
        ui.info(f"Log saved to: {log_file}")

        # 5. Smart fix (Fixer)
        if no_fix:
            ui.info("Auto-fix disabled (--no-fix)")
            return

        ui.info("🧠 Analyzing error with LLM...")

        # Read Dockerfile content if provided
        dockerfile_content = None
        if dockerfile_path and dockerfile_path.exists():
            dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
            ui.debug(f"Read Dockerfile from: {dockerfile_path}")

        # Determine operation type
        operation_type = OperationType.BUILD if "build" in cmd else OperationType.RUN

        # Build analysis context
        if dockerfile_content:
            # Docker-specific analysis
            context = DockerAnalysisContext(
                error_log=error_log,
                cwd=str(cwd),
                dockerfile_content=dockerfile_content,
                operation_type=operation_type,
                dockerfile_path=str(dockerfile_path),
                build_context=str(cwd),
            )
        else:
            # General analysis (for run commands without Dockerfile)
            context = GeneralAnalysisContext(
                error_log=error_log,
                cwd=str(cwd),
            )

        # Analyze and get suggestion
        suggestion = self.fixer.analyze(context)

        # Display suggestion details
        self._display_suggestion(suggestion)

    def _display_suggestion(self, suggestion) -> None:
        """Display fix suggestion to user."""
        ui.info("\n📋 Fix Suggestion:")
        ui.info(f"Reason: {suggestion.reason}\n")
        ui.info(f"Fix Type: {suggestion.fix_type.value}\n")

        if suggestion.fix_type.value == "command":
            ui.print_dockerfile(suggestion.command, title="Suggested Command")
            if suggestion.command_explanation:
                ui.info(f"Explanation: {suggestion.command_explanation}\n")
        elif suggestion.fix_type.value == "file":
            ui.info(f"File: {suggestion.file_path}\n")
            if suggestion.file_explanation:
                ui.info(f"Explanation: {suggestion.file_explanation}\n")
            ui.print_dockerfile(suggestion.new_content, title="Suggested File Content")
        elif suggestion.fix_type.value == "docker":
            ui.info(f"Dockerfile: {suggestion.dockerfile_path}\n")
            ui.print_dockerfile(
                suggestion.dockerfile_content, title="Suggested Dockerfile"
            )

        ui.info(
            f"Changes: {suggestion.changes_summary}\n"
            f"Confidence: {suggestion.confidence:.0%}\n"
        )

        ui.info(
            "💡 To apply the fix, review the suggestion and manually update your files."
        )
