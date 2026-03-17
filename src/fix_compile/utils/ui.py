"""
User Interface utilities for fix-compile.
Handles console output (via Rich) and logging integration.
"""

import logging

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from fix_compile.constants import PROJECT_NAME

# 1. 初始化 Rich Console 和 Logger
console = Console()
logger = logging.getLogger(PROJECT_NAME)


# ---------------------------------------------------------
# 1. Output Functions (UI + Logging)
# ---------------------------------------------------------


def debug(message: str) -> None:
    """Print debug message to console and log as DEBUG."""
    logger.debug(message)


def success(message: str) -> None:
    """Print success message to console and log as INFO."""
    console.print(f"[green]✓[/green] {escape(message)}")
    logger.info(message)


def error(message: str) -> None:
    """Print error message to console and log as ERROR."""
    console.print(f"[red]✗[/red] {escape(message)}")
    logger.error(message)


def warning(message: str) -> None:
    """Print warning message to console and log as WARNING."""
    console.print(f"[yellow]⚠[/yellow] {escape(message)}")
    logger.warning(message)


def info(message: str) -> None:
    """Print info message to console and log as INFO."""
    console.print(f"[blue]ℹ[/blue] {escape(message)}")
    logger.info(message)


def step(message: str) -> None:
    """Print a step execution message."""
    console.print(f"[bold blue]➤[/bold blue] {escape(message)}")
    logger.info(f"Step: {message}")


def confirm(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation in the console."""
    return Confirm.ask(message, default=default)


# ---------------------------------------------------------
# 2. Rich Visualization Components
# ---------------------------------------------------------


def print_dockerfile(dockerfile: str, title: str = "Dockerfile") -> None:
    """Print Dockerfile with syntax highlighting."""
    logger.debug(f"Displaying Dockerfile ({title}):\n{dockerfile}")

    syntax = Syntax(dockerfile, "dockerfile", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=title, expand=False, border_style="blue"))


def print_comparison(original: str, fixed: str) -> None:
    """Print side-by-side comparison (sequentially) of original and fixed."""
    logger.info("Displaying comparison between original and fixed Dockerfiles")

    console.print(
        Panel(
            Syntax(original, "dockerfile", theme="monokai", line_numbers=True),
            title="Original Dockerfile (Before)",
            style="red",
            expand=False,
        )
    )
    console.print(
        Panel(
            Syntax(fixed, "dockerfile", theme="monokai", line_numbers=True),
            title="Fixed Dockerfile (After)",
            style="green",
            expand=False,
        )
    )


def print_file_content(content: str, title: str = "File Content") -> None:
    """Print generic file content with syntax highlighting."""
    logger.debug(f"Displaying file content ({title})")

    syntax = Syntax(content, "text", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=title, expand=False, border_style="blue"))
