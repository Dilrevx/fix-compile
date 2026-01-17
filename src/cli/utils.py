"""CLI utilities and helpers for fix-compile."""

import json
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel

console = Console()


class CLIError(Exception):
    """CLI-specific error."""

    pass


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_dockerfile(dockerfile: str, title: str = "Dockerfile") -> None:
    """Print Dockerfile with syntax highlighting."""
    syntax = Syntax(dockerfile, "dockerfile", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=title, expand=False))


def print_comparison(original: str, fixed: str) -> None:
    """Print side-by-side comparison of original and fixed Dockerfiles."""
    console.print(
        Panel(
            Syntax(original, "dockerfile", theme="monokai", line_numbers=True),
            title="Original Dockerfile",
            style="red",
        )
    )
    console.print(
        Panel(
            Syntax(fixed, "dockerfile", theme="monokai", line_numbers=True),
            title="Fixed Dockerfile",
            style="green",
        )
    )


def save_result(content: str, output_path: Path) -> None:
    """Save result to file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        print_success(f"Saved to {output_path}")
    except IOError as e:
        raise CLIError(f"Failed to save file: {e}")


def load_file(file_path: Path) -> str:
    """Load file content."""
    try:
        return file_path.read_text()
    except FileNotFoundError:
        raise CLIError(f"File not found: {file_path}")
    except IOError as e:
        raise CLIError(f"Failed to read file: {e}")


def format_json(data: dict) -> str:
    """Format dictionary as pretty JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False)
