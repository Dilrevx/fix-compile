"""Docker fixer with auto-fix pipeline."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fix_compile.config import Configs
from fix_compile.executor import Executor
from fix_compile.schema import (
    CommandResult,
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
        # Pass custom_prompt from config to GeneralFixer
        self.fixer = GeneralFixer(custom_prompt=config.CUSTOM_PROMPT)

    def _execute_with_logging(
        self,
        cmd: list[str],
        cwd: str,
        stdout_file: Path,
        stderr_file: Path,
        env: dict = None,
    ) -> CommandResult:
        """
        Execute command with real-time output streaming and file logging.

        Args:
            cmd: Command to execute
            cwd: Working directory
            stdout_file: File to write stdout
            stderr_file: File to write stderr
            env: Environment variables

        Returns:
            CommandResult with execution details
        """
        import shlex

        cmd_str = shlex.join(cmd)
        ui.info(f"🐳 Executing: {cmd_str}")

        # Open files in write mode
        with (
            open(stdout_file, "w", encoding="utf-8") as f_out,
            open(stderr_file, "w", encoding="utf-8") as f_err,
        ):
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            stdout_lines = []
            stderr_lines = []

            # Read and write stdout in real-time
            while True:
                stdout_line = process.stdout.readline()
                if stdout_line:
                    stdout_lines.append(stdout_line)
                    # Write to console
                    ui.info(stdout_line.rstrip())
                    sys.stdout.flush()
                    # Write to file immediately
                    f_out.write(stdout_line)
                    f_out.flush()

                # Check if process is done
                if process.poll() is not None:
                    break

            # Capture remaining output
            remaining_stdout = process.stdout.read()
            if remaining_stdout:
                stdout_lines.append(remaining_stdout)
                ui.info(remaining_stdout.rstrip())
                f_out.write(remaining_stdout)

            # Read all stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                stderr_lines.append(stderr_output)
                f_err.write(stderr_output)

            exit_code = process.wait()

        return CommandResult(
            exit_code=exit_code,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            success=(exit_code == 0),
            command=cmd_str,
            cwd=cwd,
        )

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

        # Define log file paths following general_fixer structure
        stdout_file = log_dir / "stdout.txt"
        stderr_file = log_dir / "stderr.txt"
        metadata_file = log_dir / "metadata.json"

        # 3. Execution strategy
        # Check if we can skip execution
        if not force_rerun and stdout_file.exists() and stderr_file.exists():
            ui.info(f"📦 Using cached log from: {log_dir}")
            stdout = stdout_file.read_text(encoding="utf-8")
            stderr = stderr_file.read_text(encoding="utf-8")
            error_log = stdout + stderr
            success = False  # Assume cached logs are from failures
        else:
            # Ensure log directory exists
            log_dir.mkdir(parents=True, exist_ok=True)

            # Execute with real-time file logging
            result = self._execute_with_logging(
                cmd=cmd,
                cwd=str(cwd),
                stdout_file=stdout_file,
                stderr_file=stderr_file,
                env=env,
            )

            # Save metadata.json (excluding stdout/stderr)
            metadata = {
                "exit_code": result.exit_code,
                "success": result.success,
                "command": result.command,
                "cwd": result.cwd,
            }
            metadata_file.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            ui.debug(f"Saved logs to: {log_dir}")

            error_log = (result.stdout or "") + (result.stderr or "")
            success = result.success

        # 4. Result handling
        if success:
            ui.success("✅ Docker command succeeded!")
            return

        ui.warning("❌ Docker command failed (exit code: non-zero)")
        ui.info(f"Log saved to: {log_dir}")

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
