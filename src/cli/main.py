"""Main CLI application for fix-compile."""

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from fix_compile import DockerfileFixer
from fix_compile.constants import PROJECT_NAME
from fix_compile.utils.ui import (
    console,
    info,
    print_comparison,
    print_dockerfile,
    success,
    warning,
)

app = typer.Typer(
    name=PROJECT_NAME,
    help="Fix Dockerfile build errors using LLM and LangChain",
    no_args_is_help=True,
)

from cli.config import config_app  # noqa: E402

app.add_typer(config_app, name="config")


@app.command()
def fix(
    dockerfile: Path = typer.Argument(
        ...,
        help="Path to the Dockerfile to fix",
        exists=True,
    ),
    error: str = typer.Option(
        ...,
        "--error",
        "-e",
        help="The Docker build error message",
    ),
    context: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Docker build context directory",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for the fixed Dockerfile",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    comparison: bool = typer.Option(
        False,
        "--comparison",
        help="Show side-by-side comparison of original and fixed Dockerfile",
    ),
) -> None:
    """
    Fix a Dockerfile build error using LLM.

    Example:
        fix-compile fix Dockerfile \\
            --error "COPY failed: stat /app/file.txt: no such file or directory" \\
            --context . \\
            --output Dockerfile.fixed
    """
    try:
        if verbose:
            info(f"Loading Dockerfile from {dockerfile}")

        # Load the Dockerfile
        # dockerfile_content = load_file(dockerfile)

        if verbose:
            info("Initializing DockerfileFixer")

        # Initialize the fixer
        fixer = DockerfileFixer()

        if verbose:
            info(f"Analyzing error: {error[:100]}...")

        # Fix the Dockerfile
        result = fixer.fix(
            dockerfile_path=str(dockerfile),
            error_message=error,
            build_context=str(context) if context else None,
        )

        # Display results
        console.print()

        if comparison:
            print_comparison(result.original_dockerfile, result.fixed_dockerfile)
        else:
            print_dockerfile(result.fixed_dockerfile, "Fixed Dockerfile")

        # Print explanation
        console.print()
        console.print(
            Panel(result.explanation, title="Analysis & Explanation", style="cyan")
        )

        # Print confidence score
        console.print()
        confidence_pct = int(result.confidence * 100)
        confidence_color = (
            "green"
            if confidence_pct >= 80
            else "yellow"
            if confidence_pct >= 60
            else "red"
        )
        console.print(
            f"Confidence Score: [{confidence_color}]{confidence_pct}%[/{confidence_color}]"
        )

        # Save if output path is specified
        if output:
            save_result(result.fixed_dockerfile, output)
        else:
            info("Use --output to save the fixed Dockerfile")

        console.print()
        success("Done!")

    except Exception as e:
        error(f"Unexpected error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def analyze(
    dockerfile: Path = typer.Argument(
        ...,
        help="Path to the Dockerfile to analyze",
        exists=True,
    ),
    error: str = typer.Option(
        ...,
        "--error",
        "-e",
        help="The Docker build error message",
    ),
    context: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Docker build context directory",
    ),
) -> None:
    """
    Analyze a Dockerfile build error and identify the problem type.

    Example:
        fix-compile analyze Dockerfile \\
            --error "COPY failed: stat /app/file.txt: no such file or directory"
    """
    try:
        from fix_compile.workflows.analyzer import DockerfileAnalyzer

        problem = DockerfileAnalyzer.analyze(
            dockerfile_path=str(dockerfile),
            error_message=error,
            build_context=str(context) if context else None,
        )

        console.print()
        console.print(f"[bold]Dockerfile:[/bold] {problem.dockerfile_path}")
        console.print(f"[bold]Error Type:[/bold] {problem.problem_type.value}")
        console.print(f"[bold]Error Message:[/bold] {problem.error_message}")
        if problem.build_context:
            console.print(f"[bold]Build Context:[/bold] {problem.build_context}")
        console.print()

    except Exception as e:
        error(f"Analysis failed: {e}")
        raise typer.Exit(code=1)


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
