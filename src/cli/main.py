"""Main CLI application for fix-compile (new unified CLI)."""

import shlex
from pathlib import Path
from typing import List, Optional

import typer

from cli.commands import config_app, docker_app
from fix_compile.config import config_service
from fix_compile.constants import PROJECT_NAME
from fix_compile.executor import ExecutionError, Executor
from fix_compile.schema import OperationType
from fix_compile.utils.io import cmd2hash, save_exec_output
from fix_compile.utils.ui import (
    console,
    error,
    info,
    print_dockerfile,
    success,
    warning,
)
from fix_compile.workflows.brain import AnalysisError, Analyzer

app = typer.Typer(
    name=PROJECT_NAME,
    help="Fix Docker build and runtime errors using LLM",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# -------------------------------
# Sub-Apps
# -------------------------------

app.add_typer(config_app, name="config")
app.add_typer(docker_app, name="docker")


# -------------------------------
# Command: exec (arbitrary command)
# -------------------------------
@app.command(
    name="exec",
    help="Execute an arbitrary command and cache its log"
    ". Example: fix-compile exec -- ls -la /app",
    no_args_is_help=True,
)
def exec_command(
    cmd: List[str] = typer.Argument(..., help="Command to execute"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", help="Working directory"),
    dev: bool = typer.Option(False, "--dev", help="Enable dev mode (.env)"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Override directory to store exec logs"
    ),
    # verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Execute an arbitrary command and cache its log."""
    config_service.load_config(dev_mode=dev)
    dir_config = config_service.config.dir_configs

    executor = Executor()

    try:
        result = executor.execute(cmd, cwd=str(cwd) if cwd else None, stream=True)

        if output is None:
            output = dir_config.cache_dir / cmd2hash(cmd, cwd or Path.cwd())
        save_exec_output(result, output)

        if result.success:
            success("Command executed successfully")
        else:
            warning(f"Command exited with code {result.exit_code}")
    except ExecutionError as e:
        error(f"Execution failed: {e}")
        raise typer.Exit(1)


# -------------------------------
# Command: fix (single-round analysis)
# -------------------------------
@app.command(
    name="fix",
    no_args_is_help=True,
    help="Analyze logs from file, text, or command execution.",
)
def fix_command(
    log_dir: Optional[Path] = typer.Option(
        None,
        "--log-dir",
        "--dir",
        help="Path to log file OR directory (reads latest log)",
    ),
    log_text: Optional[str] = typer.Option(
        None, "--text", "-t", help="Raw log text provided directly"
    ),
    # 3. 命令改为 str，用户体验更好：--cmd "make build"
    cmd: Optional[str] = typer.Option(
        None,
        "--cmd",
        "-c",
        help="Command to execute to generate log (e.g. 'docker build .')",
    ),
    # 4. 辅助参数
    cwd: Optional[Path] = typer.Option(None, help="Working directory for --cmd"),
    dev: bool = typer.Option(False, "--dev", help="Enable dev mode"),
):
    """Analyze a log using the LLM and output a single-round suggestion.

    Resolution order for the log:
    1) --text if provided
    2) --log-dir if points to an existing directory (read meta.json, stdout.txt or stderr.txt in it)
    3) --cmd: if provided, try reading --log-dir first; if missing, execute cmd, save output, and use it.
    """
    config_service.load_config(dev_mode=dev)
    dir_config = config_service.config.dir_configs

    analyzer = Analyzer()
    executor = Executor()

    try:
        # Resolve error log string
        error_log: Optional[str] = None

        # 1) Direct text
        if log_text:
            error_log = log_text
        # 2) Read file or directory saved via save_exec_output (stdout.txt/stderr.txt)
        elif log_dir and log_dir.exists():
            if log_dir.is_file():
                error_log = log_dir.read_text(encoding="utf-8")
            else:
                if not (log_dir / "meta.json").exists():
                    error(
                        "Log directory missing meta.json. Provide a valid save_exec_output folder."
                    )
                    raise typer.Exit(1)

                stdout_path = log_dir / "stdout.txt"
                stderr_path = log_dir / "stderr.txt"
                stdout = (
                    stdout_path.read_text(encoding="utf-8")
                    if stdout_path.exists()
                    else ""
                )
                stderr = (
                    stderr_path.read_text(encoding="utf-8")
                    if stderr_path.exists()
                    else ""
                )
                error_log = f"stdout: {stdout}\nstderr: {stderr}"
                if not error_log.strip():
                    error(
                        "Log directory missing stdout.txt and stderr.txt. Provide a valid save_exec_output folder."
                    )
                    raise typer.Exit(1)
        # 3) Execute command
        elif cmd:
            cmd = shlex.split(cmd)
            result = executor.execute(cmd, cwd=str(cwd) if cwd else None, stream=True)
            # Save to output directory (either provided or derived)
            if not log_dir:
                log_dir = dir_config.cache_dir / cmd2hash(cmd, cwd or Path.cwd())
            save_exec_output(result, log_dir)
            error_log = (result.stdout or "") + (result.stderr or "")

        if not error_log:
            warning("error log is empty. Maybe only non zero exit code?")

        # Perform analysis with minimal dockerfile context (generic mode)
        suggestion = analyzer.quick_analyze(
            dockerfile_content="",
            error_log=error_log,
            operation_type=OperationType.BUILD,
        )
        # Show suggestion content and summary
        print_dockerfile(suggestion.new_content, title="Suggested Content")
        info(
            f"Reason: {suggestion.reason}\n\n"
            f"Changes: {suggestion.changes_summary}\n\n"
            f"Confidence: {suggestion.confidence:.0%}"
        )
    except AnalysisError as e:
        error(f"Analysis failed: {e}")
        raise typer.Exit(1)
    except ExecutionError as e:
        error(f"Command execution failed: {e}")
        raise typer.Exit(1)


# -------------------------------
# Version and main
# -------------------------------
@app.command()
def version() -> None:
    """Show version information."""
    from fix_compile import __name__, __version__

    console.print(f"{__name__} version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print()
        warning("Interrupted by user")
        raise typer.Exit(code=130)


if __name__ == "__main__":
    main()
