"""Main CLI application for fix-compile."""

import sys
from pathlib import Path
from typing import Optional

import typer

from fix_compile.utils.ui import (
    debug,
    error,
    info,
    print_dockerfile,
    step,
    success,
    warning,
)

from .schema import (
    AnalysisContext,
    DockerBuildConfig,
    DockerRunConfig,
    LoopState,
    OperationType,
)
from .workflows.brain import AnalysisError, Analyzer
from .workflows.executor import ExecutionError, Executor

# Create subapps for command groups

app.add_typer(config_app, name="config")

# TODO: Initialize Phoenix tracing on application startup
# setup_phoenix_tracing(project_name="fix-compile", enabled=True)


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
            warning("Reading error log from stdin...")
            error_log = sys.stdin.read()
            if not error_log.strip():
                error("No input provided")
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
        info(
            f"Reason: {suggestion.reason}\n\n"
            f"Changes: {suggestion.changes_summary}\n\n"
            f"Confidence: {suggestion.confidence:.0%}"
        )

        # Show new Dockerfile
        print_dockerfile(suggestion.new_content, title="New Dockerfile")

        # Save to file if requested
        if output:
            output.write_text(suggestion.model_dump_json(indent=2))
            success(f"Saved suggestion to {output}")

    except AnalysisError as e:
        error(f"Analysis failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        error(f"Error: {e}")
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
        error("Cannot use both --run-only and --build-only")
        raise typer.Exit(1)

    if not run_only and not tag:
        warning("No --tag specified, using 'fix-compile:latest'")
        tag = "fix-compile:latest"

    # Initialize
    executor = Executor(verbose=verbose)
    analyzer = Analyzer()

    # Validate Dockerfile exists
    if not executor.file_exists(str(file)):
        error(f"Dockerfile not found: {file}")
        raise typer.Exit(1)

    # Initialize state
    state = LoopState(
        max_attempts=retry,
        operation_type=OperationType.BUILD,
    )

    try:
        # Phase 1: Build
        if not run_only:
            step("Phase 1: Docker Build")

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
                error("Build failed after all retry attempts")
                raise typer.Exit(1)

        # Phase 2: Run
        if not build_only:
            step("Phase 2: Docker Run")

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
                error("Run failed after all retry attempts")
                raise typer.Exit(1)

        # Success!
        success("All operations completed successfully!")

    except KeyboardInterrupt:
        warning("Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        error(f"Fatal error: {e}")
        if verbose:
            import traceback

            debug(traceback.format_exc())
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

        info(f"Attempt {state.current_attempt}/{state.max_attempts}")

        # Build
        config = DockerBuildConfig(
            context=context_path,
            dockerfile=str(file),
            tag=tag,
            no_cache=no_cache,
        )

        result = executor.docker_build(config)

        if result.success:
            success("Build succeeded!")
            state.build_succeeded = True
            return True

        # Build failed
        error(f"Build failed (exit code {result.exit_code})")

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

        info(f"Run Attempt {state.current_attempt}/{state.max_attempts}")

        # Parse run args
        args_list = run_args.split() if run_args else []

        config = DockerRunConfig(
            image=tag,
            args=args_list,
            remove=True,
        )

        result = executor.docker_run(config)

        if result.success:
            success("Run succeeded!")
            state.run_succeeded = True
            return True

        # Run failed
        error(f"Run failed (exit code {result.exit_code})")

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
        info(
            f"Reason: {suggestion.reason}\n\n"
            f"Changes: {suggestion.changes_summary}\n\n"
            f"Confidence: {suggestion.confidence:.0%}"
        )

        # Ask for confirmation
        if not yes:
            apply = typer.confirm("Apply this fix?", default=True)
            if not apply:
                warning("Fix rejected by user")
                return False

        # Apply fix
        executor.apply_fix(suggestion)
        return True

    except AnalysisError as e:
        error(f"Analysis failed: {e}")
        return False
    except ExecutionError as e:
        error(f"Execution failed: {e}")
        return False


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
