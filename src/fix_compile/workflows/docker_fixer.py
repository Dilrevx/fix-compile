"""Docker fixer with auto-fix pipeline."""

import json
import os
import shlex
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
    PreflightSuggestion,
)
from fix_compile.utils import ui
from fix_compile.utils.io import cmd2hash
from fix_compile.workflows.general_fixer import GeneralFixer


class DockerFixer:
    """Docker command executor with auto-fix capabilities."""

    _MAX_PREFLIGHT_BYTES = 200_000
    _MAX_PREFLIGHT_FILES = 50

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

    def _resolve_build_context(self, cmd: list[str], cwd: Path) -> Path:
        """Resolve build context path from docker build command."""
        if "build" not in cmd or not cmd:
            return cwd

        candidate = cmd[-1]
        if candidate.startswith("-"):
            return cwd

        return (cwd / candidate).resolve()

    def _extract_copy_sources(self, dockerfile_content: str) -> list[str]:
        """Extract COPY/ADD source paths from Dockerfile content."""
        sources: list[str] = []

        for raw_line in dockerfile_content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            upper = line.upper()
            if not (upper.startswith("COPY ") or upper.startswith("ADD ")):
                continue

            # JSON array form
            if "[" in line and "]" in line:
                json_part = line[line.find("[") : line.rfind("]") + 1]
                try:
                    data = json.loads(json_part)
                    if isinstance(data, list) and len(data) >= 2:
                        sources.extend(data[:-1])
                    continue
                except json.JSONDecodeError:
                    pass

            try:
                tokens = shlex.split(line)
            except ValueError:
                continue

            if len(tokens) < 3:
                continue

            args = tokens[1:]
            if any(arg.startswith("--from") for arg in args):
                continue

            args = [arg for arg in args if not arg.startswith("--")]
            if len(args) < 2:
                continue

            sources.extend(args[:-1])

        return sources

    def _collect_related_files(
        self,
        dockerfile_path: Path,
        build_context: Path,
    ) -> dict[str, str]:
        """Collect contents of files referenced by COPY/ADD for preflight."""
        related_files: dict[str, str] = {}

        dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
        sources = self._extract_copy_sources(dockerfile_content)

        def add_file(path: Path) -> None:
            if len(related_files) >= self._MAX_PREFLIGHT_FILES:
                return

            if not path.exists() or not path.is_file():
                return

            if path.stat().st_size > self._MAX_PREFLIGHT_BYTES:
                return

            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return

            try:
                relative_path = path.relative_to(build_context).as_posix()
            except ValueError:
                relative_path = path.as_posix()

            related_files[relative_path] = content

        for source in sources:
            if len(related_files) >= self._MAX_PREFLIGHT_FILES:
                break

            if "://" in source or "*" in source:
                continue

            source_path = (build_context / source).resolve()
            if not source_path.exists():
                continue

            if source_path.is_file():
                add_file(source_path)
                continue

            if source_path.is_dir():
                for child in sorted(source_path.rglob("*")):
                    if len(related_files) >= self._MAX_PREFLIGHT_FILES:
                        break
                    if child.is_file():
                        add_file(child)

        return related_files

    def _backup_file(self, file_path: Path) -> Path:
        """Backup a file to a .bak copy and return the backup path."""
        backup_path = Path(f"{file_path}.bak")
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path

    def _show_preflight_changes(self, suggestion: PreflightSuggestion) -> None:
        """Display preflight changes to user for review."""
        ui.info("\n📋 Preflight Custom Prompt Changes:")
        ui.info(f"Reason: {suggestion.reason}\n")
        ui.info(f"Changes Summary: {suggestion.changes_summary}\n")

        for change in suggestion.changes:
            title = f"{change.path}"
            ui.info(f"File: {change.path}")
            if change.explanation:
                ui.info(f"Explanation: {change.explanation}\n")

            if change.path.lower().endswith("dockerfile"):
                ui.print_dockerfile(change.new_content, title=title)
            else:
                ui.print_file_content(change.new_content, title=title)

    def _apply_preflight_changes(
        self,
        suggestion: PreflightSuggestion,
        build_context: Path,
    ) -> None:
        """Backup and apply preflight changes with user confirmation."""
        if not suggestion.changes:
            ui.info("No preflight changes required.")
            return

        self._show_preflight_changes(suggestion)

        for change in suggestion.changes:
            target_path = (build_context / change.path).resolve()
            if target_path.exists() and target_path.is_file():
                backup_path = self._backup_file(target_path)
                ui.info(f"Backup saved: {backup_path}")

        if not ui.confirm("Apply these changes before running Docker?", default=False):
            ui.info("Skipped applying preflight changes.")
            return

        for change in suggestion.changes:
            target_path = (build_context / change.path).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(change.new_content, encoding="utf-8")

        ui.success("Applied preflight changes.")

    def _maybe_preflight_custom_prompt(
        self,
        cmd: list[str],
        cwd: Path,
        dockerfile_path: Optional[Path],
        no_fix: bool,
    ) -> None:
        """Run preflight custom prompt compliance before Docker execution."""
        if no_fix:
            return

        if not self.config.CUSTOM_PROMPT or not self.config.CUSTOM_PROMPT.strip():
            return

        if not dockerfile_path or not dockerfile_path.exists():
            return

        build_context = self._resolve_build_context(cmd, cwd)
        dockerfile_content = dockerfile_path.read_text(encoding="utf-8")

        try:
            dockerfile_rel = dockerfile_path.resolve().relative_to(build_context)
            dockerfile_rel_path = dockerfile_rel.as_posix()
        except ValueError:
            dockerfile_rel_path = dockerfile_path.name

        related_files = self._collect_related_files(
            dockerfile_path=dockerfile_path,
            build_context=build_context,
        )

        suggestion = self.fixer.preflight_custom_prompt(
            dockerfile_path=dockerfile_rel_path,
            dockerfile_content=dockerfile_content,
            build_context=build_context.as_posix(),
            related_files=related_files,
        )

        self._apply_preflight_changes(suggestion, build_context)

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
        # 0. Preflight: apply custom prompt compliance changes before execution
        self._maybe_preflight_custom_prompt(
            cmd=cmd,
            cwd=cwd,
            dockerfile_path=dockerfile_path,
            no_fix=no_fix,
        )
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
