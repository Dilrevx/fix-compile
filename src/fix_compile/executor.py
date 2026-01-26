"""Executor module - The Hand (subprocess and file operations)."""

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fix_compile.schema import (
    CommandResult,
    DockerBuildConfig,
    DockerRunConfig,
    FixSuggestion,
)
from fix_compile.utils import ui


class ExecutionError(Exception):
    """Raised when command execution fails critically."""

    pass


class Executor:
    """
    Handles all subprocess calls and file I/O operations.

    Philosophy: The Hand (Executor) knows nothing about LLMs or intelligence.
    It only executes commands, captures output, and manipulates files.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the executor.

        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose

    def execute(
        self, cmd: list[str], cwd: Optional[str] = None, stream: bool = True
    ) -> CommandResult:
        """
        Execute a shell command and capture output.

        Args:
            cmd: Command to execute as a list
            cwd: Working directory for the command
            stream: Whether to stream output to stdout in real-time

        Returns:
            CommandResult with exit code and captured output
        """
        cmd_str = shlex.join(cmd)
        # cmd_str = subprocess.list2cmdline(cmd) # subprocess api

        ui.info(f"Executing command: [bold]{cmd_str}[/bold]")

        try:
            if stream:
                # Stream mode: show output in real-time, capture stderr
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                stdout_lines = []
                stderr_lines = []

                # Read stdout and stderr
                while True:
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        stdout_lines.append(stdout_line)
                        ui.info(stdout_line.rstrip())
                        sys.stdout.flush()

                    # Check if process is done
                    if process.poll() is not None:
                        break

                # Capture remaining stderr
                stderr_output = process.stderr.read()
                if stderr_output:
                    stderr_lines.append(stderr_output)

                exit_code = process.wait()
                stdout = "".join(stdout_lines)
                stderr = "".join(stderr_lines)

            else:
                # Silent mode: just capture output
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                )
                exit_code = result.returncode
                stdout = result.stdout
                stderr = result.stderr

            return CommandResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                success=(exit_code == 0),
                command=cmd_str,
                cwd=cwd or str(Path.cwd()),
            )

        except FileNotFoundError as e:
            raise ExecutionError(f"Command not found: {cmd[0]}") from e
        except Exception as e:
            raise ExecutionError(f"Failed to execute command: {e}") from e

    def docker_build(self, config: DockerBuildConfig) -> CommandResult:
        """
        Execute docker build command.

        Args:
            config: Docker build configuration

        Returns:
            CommandResult with build output
        """
        cmd = ["docker", "build"]

        if config.tag:
            cmd.extend(["-t", config.tag])

        if config.no_cache:
            cmd.append("--no-cache")

        if config.dockerfile != "Dockerfile":
            cmd.extend(["-f", config.dockerfile])

        for key, value in config.build_args.items():
            cmd.extend(["--build-arg", f"{key}={value}"])

        cmd.append(config.context)

        return self.execute(cmd, stream=True)

    def docker_run(self, config: DockerRunConfig) -> CommandResult:
        """
        Execute docker run command.

        Args:
            config: Docker run configuration

        Returns:
            CommandResult with run output
        """
        cmd = ["docker", "run"]

        if config.remove:
            cmd.append("--rm")

        if config.detach:
            cmd.append("-d")

        cmd.extend(config.args)
        cmd.append(config.image)

        return self.execute(cmd, stream=True)

    def read_file(self, file_path: str) -> str:
        """
        Read file content.

        Args:
            file_path: Path to file

        Returns:
            File content as string

        Raises:
            ExecutionError: If file cannot be read
        """
        try:
            path = Path(file_path)
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ExecutionError(f"File not found: {file_path}")
        except Exception as e:
            raise ExecutionError(f"Failed to read {file_path}: {e}")

    def write_file(self, file_path: str, content: str) -> None:
        """
        Write content to file.

        Args:
            file_path: Path to file
            content: Content to write

        Raises:
            ExecutionError: If file cannot be written
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            if self.verbose:
                ui.debug(f"[green]✓[/green] Wrote {file_path}")

        except Exception as e:
            raise ExecutionError(f"Failed to write {file_path}: {e}")

    def apply_fix(self, fix: FixSuggestion) -> None:
        """
        Apply a fix suggestion by writing the new content to the file.

        Args:
            fix: Fix suggestion with file path and new content

        Raises:
            ExecutionError: If fix cannot be applied
        """
        ui.info(f"\n[yellow]Applying fix to {fix.file_path}...[/yellow]")
        ui.info(f"[dim]{fix.changes_summary}[/dim]")

        # Create backup
        backup_path = f"{fix.file_path}.backup"
        try:
            original_content = self.read_file(fix.file_path)
            self.write_file(backup_path, original_content)
            ui.info(f"[dim]Backup created: {backup_path}[/dim]")
        except ExecutionError:
            ui.info("[yellow]Warning: Could not create backup[/yellow]")

        # Apply fix
        self.write_file(fix.file_path, fix.new_content)
        ui.info("[green]✓ Fix applied successfully[/green]\n")

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).exists()

    def get_absolute_path(self, file_path: str) -> str:
        """Get absolute path for a file."""
        return str(Path(file_path).resolve())
