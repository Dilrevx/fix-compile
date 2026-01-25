"""Main CLI application for fix-compile (new unified CLI)."""

from pathlib import Path
from typing import List, Optional

import typer

from cli.commands import config_app, docker_app
from fix_compile.config import config_service
from fix_compile.constants import PROJECT_NAME
from fix_compile.schema import (
    AnalysisContext,
    OperationType,
)
from fix_compile.utils.io import save_exec_output
from fix_compile.utils.ui import (
    console,
    error,
    info,
    print_dockerfile,
    success,
    warning,
)
from fix_compile.workflows.brain import AnalysisError, Analyzer
from fix_compile.workflows.executor import ExecutionError, Executor

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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Execute an arbitrary command and cache its log."""
    config_service.load_config(dev_mode=dev)
    dir_config = config_service.config.dir_configs

    executor = Executor(verbose=verbose)

    try:
        result = executor.execute(list(cmd), cwd=str(cwd) if cwd else None, stream=True)

        save_exec_output(result, dir_config)

        if result.success:
            success("Command executed successfully")
        else:
            warning(f"Command exited with code {result.exit_code}")
    except ExecutionError as e:
        error(f"Execution failed: {e}")
        raise typer.Exit(1)


# -------------------------------
# Command: fixer (single-round analysis)
# -------------------------------
@app.command(name="fixer")
def fixer_command(
    log_file: Path = typer.Argument(..., help="Path to log file"),
    file: Path = typer.Option("Dockerfile", "--file", "-f", help="Path to Dockerfile"),
    context_path: str = typer.Option(
        ".", "--context", "-c", help="Docker build context"
    ),
    operation: str = typer.Option("build", "--operation", "-o", help="build|run"),
    dev: bool = typer.Option(False, "--dev", help="Enable dev mode (.env)"),
):
    """Analyze a log file and produce a single-round suggestion."""
    config_service.load_config(dev_mode=dev)
    config = config_service.config

    analyzer = Analyzer()
    executor = Executor()

    try:
        error_log = log_file.read_text(encoding="utf-8")
        dockerfile_content = executor.read_file(str(file))
        context = AnalysisContext(
            dockerfile_content=dockerfile_content,
            error_log=error_log,
            operation_type=OperationType(operation),
            dockerfile_path=str(file),
            build_context=context_path,
        )
        suggestion = analyzer.analyze(context)
        print_dockerfile(suggestion.new_content, title="Suggested Dockerfile")
        info(
            f"Reason: {suggestion.reason}\n\n"
            f"Changes: {suggestion.changes_summary}\n\n"
            f"Confidence: {suggestion.confidence:.0%}"
        )
    except AnalysisError as e:
        error(f"Analysis failed: {e}")
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
