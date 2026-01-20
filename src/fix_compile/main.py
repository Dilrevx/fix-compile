"""Main CLI application for fix-compile."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .brain import AnalysisError, Analyzer
from .config_manager import (
    delete_config_value,
    get_config_dir_path,
    get_config_file_path,
    load_config_file,
    set_config_value,
    validate_config_key,
)
from .executor import ExecutionError, Executor
from .observability import setup_phoenix_tracing
from .schema import (
    AnalysisContext,
    DockerBuildConfig,
    DockerRunConfig,
    LoopState,
    OperationType,
)

console = Console()
app = typer.Typer(
    name="fix-compile",
    help="🔧 Fix Docker build and runtime errors using LLM",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Create subapps for command groups
config_app = typer.Typer(help="Manage configuration for fix-compile")
app.add_typer(config_app, name="config")

# Initialize Phoenix tracing on application startup
setup_phoenix_tracing(project_name="fix-compile", enabled=True)


# ============================================================================
# Command: analyze (Brain Mode - Read Only)
# ============================================================================


@app.command(name="analyze")
def analyze_command(
    log: Optional[Path] = typer.Option(
        None,
        "--log",
        "-l",
        help="Path to error log file (if not provided, reads from stdin)",
    ),
    file: Path = typer.Option(
        "Dockerfile",
        "--file",
        "-f",
        help="Path to Dockerfile",
        exists=True,
    ),
    context_path: str = typer.Option(
        ".",
        "--context",
        "-c",
        help="Docker build context path",
    ),
    operation: str = typer.Option(
        "build",
        "--operation",
        "-o",
        help="Operation type: build or run",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Save suggestion to file (JSON format)",
    ),
):
    """
    🧠 Analyze Docker errors and suggest fixes (read-only mode).

    This command only analyzes and suggests - it does NOT execute or modify files.

    Examples:

        # Analyze from log file
        fix-compile analyze --log error.txt --file Dockerfile

        # Analyze from stdin (pipe)
        docker build . 2>&1 | fix-compile analyze --file Dockerfile

        # Save suggestion to file
        fix-compile analyze --log error.txt --output suggestion.json
    """
    try:
        # Read error log
        if log:
            error_log = log.read_text()
        else:
            console.print("[yellow]Reading error log from stdin...[/yellow]")
            error_log = sys.stdin.read()
            if not error_log.strip():
                console.print("[red]Error: No input provided[/red]")
                raise typer.Exit(1)

        # Read Dockerfile
        dockerfile_content = file.read_text()

        # Create analysis context
        context = AnalysisContext(
            dockerfile_content=dockerfile_content,
            error_log=error_log,
            operation_type=OperationType(operation),
            dockerfile_path=str(file),
            build_context=context_path,
        )

        # Analyze
        analyzer = Analyzer()
        suggestion = analyzer.analyze(context)

        # Display suggestion
        console.print(
            Panel(
                f"[bold]Reason:[/bold]\n{suggestion.reason}\n\n"
                f"[bold]Changes:[/bold]\n{suggestion.changes_summary}\n\n"
                f"[bold]Confidence:[/bold] {suggestion.confidence:.0%}",
                title="🔍 Fix Suggestion",
                border_style="cyan",
            )
        )

        # Show diff preview
        console.print("\n[bold]New Dockerfile:[/bold]")
        syntax = Syntax(suggestion.new_content, "dockerfile", theme="monokai")
        console.print(syntax)

        # Save to file if requested
        if output:
            output.write_text(suggestion.model_dump_json(indent=2))
            console.print(f"\n[green]✓ Saved suggestion to {output}[/green]")

    except AnalysisError as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# Command: docker (Auto-Fix Loop)
# ============================================================================


@app.command(name="docker")
def docker_command(
    context_path: str = typer.Argument(
        ".",
        help="Docker build context path",
    ),
    file: Path = typer.Option(
        "Dockerfile",
        "--file",
        "-f",
        help="Path to Dockerfile",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Image tag (required if using --run)",
    ),
    build_only: bool = typer.Option(
        False,
        "--build-only",
        help="Only build, don't run the container",
    ),
    run_only: bool = typer.Option(
        False,
        "--run-only",
        help="Only run (assume image already built)",
    ),
    run_args: str = typer.Option(
        "",
        "--run-args",
        help="Additional arguments for docker run (e.g., '-p 8080:80 -e KEY=val')",
    ),
    retry: int = typer.Option(
        3,
        "--retry",
        help="Maximum fix retry attempts",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Auto-apply fixes without confirmation",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Build without cache",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
):
    """
    🔄 Auto-fix Docker build/run errors in a loop.

    This command will:
    1. Build the Docker image
    2. If build fails: analyze error, suggest fix, apply (with confirmation)
    3. Retry build with fix
    4. If --run flag: run the container and verify
    5. If run fails: analyze runtime error and fix

    Examples:

        # Build only with auto-fix
        fix-compile docker . --tag myapp:latest --build-only

        # Build and run with auto-fix
        fix-compile docker . --tag myapp:latest --run-args "-p 8080:80"

        # Run only (skip build)
        fix-compile docker --run-only --tag myapp:latest

        # Auto-apply fixes without asking
        fix-compile docker . --tag myapp:latest --yes
    """
    # Validate arguments
    if run_only and build_only:
        console.print("[red]Error: Cannot use both --run-only and --build-only[/red]")
        raise typer.Exit(1)

    if not run_only and not tag:
        console.print(
            "[yellow]Warning: No --tag specified, using 'fix-compile:latest'[/yellow]"
        )
        tag = "fix-compile:latest"

    # Initialize
    executor = Executor(verbose=verbose)
    analyzer = Analyzer()

    # Validate Dockerfile exists
    if not executor.file_exists(str(file)):
        console.print(f"[red]Error: Dockerfile not found: {file}[/red]")
        raise typer.Exit(1)

    # Initialize state
    state = LoopState(
        max_attempts=retry,
        operation_type=OperationType.BUILD,
    )

    try:
        # Phase 1: Build
        if not run_only:
            console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
            console.print("[bold cyan]Phase 1: Docker Build[/bold cyan]")
            console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

            build_succeeded = _build_loop(
                executor=executor,
                analyzer=analyzer,
                state=state,
                file=file,
                context_path=context_path,
                tag=tag,
                no_cache=no_cache,
                yes=yes,
            )

            if not build_succeeded:
                console.print("\n[red]❌ Build failed after all retry attempts[/red]")
                raise typer.Exit(1)

        # Phase 2: Run
        if not build_only:
            console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
            console.print("[bold cyan]Phase 2: Docker Run[/bold cyan]")
            console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

            # Reset state for run phase
            state.operation_type = OperationType.RUN
            state.current_attempt = 0

            run_succeeded = _run_loop(
                executor=executor,
                analyzer=analyzer,
                state=state,
                file=file,
                context_path=context_path,
                tag=tag,
                run_args=run_args,
                yes=yes,
            )

            if not run_succeeded:
                console.print("\n[red]❌ Run failed after all retry attempts[/red]")
                raise typer.Exit(1)

        # Success!
        console.print(f"\n[bold green]{'=' * 60}[/bold green]")
        console.print(
            "[bold green]✅ All operations completed successfully![/bold green]"
        )
        console.print(f"[bold green]{'=' * 60}[/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)


# ============================================================================
# Helper Functions
# ============================================================================


def _build_loop(
    executor: Executor,
    analyzer: Analyzer,
    state: LoopState,
    file: Path,
    context_path: str,
    tag: str,
    no_cache: bool,
    yes: bool,
) -> bool:
    """Execute the build loop with auto-fix."""

    while state.can_retry():
        state.increment_attempt()

        console.print(
            f"[bold]Attempt {state.current_attempt}/{state.max_attempts}[/bold]\n"
        )

        # Build
        config = DockerBuildConfig(
            context=context_path,
            dockerfile=str(file),
            tag=tag,
            no_cache=no_cache,
        )

        result = executor.docker_build(config)

        if result.success:
            console.print("[green]✅ Build succeeded![/green]")
            state.build_succeeded = True
            return True

        # Build failed
        console.print(f"\n[red]❌ Build failed (exit code {result.exit_code})[/red]\n")

        if not state.can_retry():
            return False

        # Analyze and fix
        if not _analyze_and_fix(
            executor=executor,
            analyzer=analyzer,
            state=state,
            file=file,
            context_path=context_path,
            error_log=result.output,
            yes=yes,
        ):
            return False

    return False


def _run_loop(
    executor: Executor,
    analyzer: Analyzer,
    state: LoopState,
    file: Path,
    context_path: str,
    tag: str,
    run_args: str,
    yes: bool,
) -> bool:
    """Execute the run loop with auto-fix."""

    while state.can_retry():
        state.increment_attempt()

        console.print(
            f"[bold]Run Attempt {state.current_attempt}/{state.max_attempts}[/bold]\n"
        )

        # Parse run args
        args_list = run_args.split() if run_args else []

        config = DockerRunConfig(
            image=tag,
            args=args_list,
            remove=True,
        )

        result = executor.docker_run(config)

        if result.success:
            console.print("[green]✅ Run succeeded![/green]")
            state.run_succeeded = True
            return True

        # Run failed
        console.print(f"\n[red]❌ Run failed (exit code {result.exit_code})[/red]\n")

        if not state.can_retry():
            return False

        # Analyze and fix
        if not _analyze_and_fix(
            executor=executor,
            analyzer=analyzer,
            state=state,
            file=file,
            context_path=context_path,
            error_log=result.output,
            yes=yes,
        ):
            return False

    return False


def _analyze_and_fix(
    executor: Executor,
    analyzer: Analyzer,
    state: LoopState,
    file: Path,
    context_path: str,
    error_log: str,
    yes: bool,
) -> bool:
    """Analyze error and apply fix."""

    try:
        # Read current Dockerfile
        dockerfile_content = executor.read_file(str(file))

        # Analyze
        context = AnalysisContext(
            dockerfile_content=dockerfile_content,
            error_log=error_log,
            operation_type=state.operation_type,
            dockerfile_path=str(file),
            build_context=context_path,
            previous_attempts=state.current_attempt - 1,
        )

        suggestion = analyzer.analyze(context)

        # Display suggestion
        console.print(
            Panel(
                f"[bold]Reason:[/bold]\n{suggestion.reason}\n\n"
                f"[bold]Changes:[/bold]\n{suggestion.changes_summary}\n\n"
                f"[bold]Confidence:[/bold] {suggestion.confidence:.0%}",
                title="💡 Fix Suggestion",
                border_style="yellow",
            )
        )

        # Ask for confirmation
        if not yes:
            apply = typer.confirm("\nApply this fix?", default=True)
            if not apply:
                console.print("[yellow]Fix rejected by user[/yellow]")
                return False

        # Apply fix
        executor.apply_fix(suggestion)
        return True

    except AnalysisError as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        return False
    except ExecutionError as e:
        console.print(f"[red]Execution failed: {e}[/red]")
        return False


# ============================================================================
# Command: config (Configuration Management)
# ============================================================================


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value."""
    if not validate_config_key(key):
        valid_keys = {
            "OPENAI_API_BASE",
            "OPENAI_API_KEY",
            "EXECUTOR_MODEL",
            "FIXER_MODEL",
            "LOG_LEVEL",
            "MAX_TOKENS",
            "TIMEOUT",
        }
        console.print(
            f"[red]Invalid configuration key: {key}[/red]\n"
            f"[yellow]Valid keys: {', '.join(sorted(valid_keys))}[/yellow]"
        )
        raise typer.Exit(1)

    try:
        set_config_value(key, value)
        console.print(f"[green]✓ Configuration saved:[/green] {key} = {value}")
        if key == "OPENAI_API_KEY":
            console.print("[dim](Sensitive value stored securely)[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to save configuration: {e}[/red]")
        raise typer.Exit(1)


@config_app.command(name="get")
def config_get(key: str = typer.Argument(..., help="Configuration key")):
    """Get a configuration value."""
    if not validate_config_key(key):
        console.print(f"[red]Invalid configuration key: {key}[/red]")
        raise typer.Exit(1)

    try:
        config_data = load_config_file()
        if key in config_data:
            value = config_data[key]
            if key == "OPENAI_API_KEY":
                # Only show masked value for security
                masked = (
                    value[:10] + "*" * (len(value) - 10)
                    if len(value) > 10
                    else "*" * len(value)
                )
                console.print(f"[cyan]{key}:[/cyan] {masked}")
            else:
                console.print(f"[cyan]{key}:[/cyan] {value}")
        else:
            console.print(f"[yellow]Configuration key not found: {key}[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to read configuration: {e}[/red]")
        raise typer.Exit(1)


@config_app.command(name="list")
def config_list():
    """List all configuration values."""
    try:
        config_data = load_config_file()

        if not config_data:
            console.print(
                "[yellow]No configuration found. Use 'config set' to add values.[/yellow]"
            )
            return

        # Create table
        table = Table(
            title="Configuration Values", show_header=True, header_style="bold cyan"
        )
        table.add_column("Key", style="green")
        table.add_column("Value", style="white")

        for key, value in sorted(config_data.items()):
            if key == "OPENAI_API_KEY":
                # Mask sensitive values
                masked = (
                    value[:10] + "*" * (len(value) - 10)
                    if len(value) > 10
                    else "*" * len(value)
                )
                table.add_row(key, f"[dim]{masked}[/dim]")
            else:
                table.add_row(key, str(value))

        console.print(table)
        console.print(f"\n[dim]Configuration file: {get_config_file_path()}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to read configuration: {e}[/red]")
        raise typer.Exit(1)


@config_app.command(name="delete")
def config_delete(
    key: str = typer.Argument(..., help="Configuration key"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a configuration value."""
    if not validate_config_key(key):
        console.print(f"[red]Invalid configuration key: {key}[/red]")
        raise typer.Exit(1)

    try:
        config_data = load_config_file()
        if key not in config_data:
            console.print(f"[yellow]Configuration key not found: {key}[/yellow]")
            return

        if not confirm:
            if not typer.confirm(f"Delete configuration key '{key}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        delete_config_value(key)
        console.print(f"[green]✓ Configuration deleted: {key}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to delete configuration: {e}[/red]")
        raise typer.Exit(1)


@config_app.command(name="path")
def config_path():
    """Show configuration file and directory paths."""
    config_file = get_config_file_path()
    config_dir = get_config_dir_path()

    table = Table(
        title="Configuration Paths", show_header=True, header_style="bold cyan"
    )
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")

    table.add_row("Config File", str(config_file))
    table.add_row("Config Directory", str(config_dir))

    console.print(table)
    console.print(f"\n[dim]File exists: {config_file.exists()}[/dim]")


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
