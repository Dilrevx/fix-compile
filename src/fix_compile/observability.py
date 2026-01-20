"""Phoenix observability and tracing setup for debugging."""

import os
from typing import Optional

from rich.console import Console

console = Console()


def setup_phoenix_tracing(
    project_name: str = "fix-compile",
    endpoint: Optional[str] = None,
    enabled: bool = True,
) -> None:
    """
    Setup Phoenix tracing for LangChain instrumentation.

    This enables observability for LangChain operations including:
    - LLM calls (prompts, responses, tokens)
    - Chain execution
    - Tool usage
    - Memory operations

    Args:
        project_name: Project name for Phoenix
        endpoint: Phoenix server endpoint (e.g., http://localhost:6006).
                 If not provided, uses PHOENIX_ENDPOINT env var or defaults to localhost:6006
        enabled: Whether to enable tracing (default: True)

    Example:
        >>> from fix_compile.observability import setup_phoenix_tracing
        >>> setup_phoenix_tracing(project_name="fix-compile")
        >>> # Now all LangChain calls are automatically traced
    """
    if not enabled:
        console.print("[dim]Phoenix tracing disabled[/dim]")
        return

    try:
        import phoenix as px
        from phoenix.otel import register_tracer

        # Determine Phoenix endpoint
        phoenix_endpoint = endpoint or os.getenv(
            "PHOENIX_ENDPOINT", "http://localhost:6006"
        )

        console.print(
            "[cyan]🔍 Initializing Phoenix tracing[/cyan]",
            f"[dim](project: {project_name}, endpoint: {phoenix_endpoint})[/dim]",
        )

        # Register Phoenix tracer
        tracer_provider = px.initialize_tracer(
            project_name=project_name,
            endpoint=phoenix_endpoint,
        )

        # The tracer provider is automatically used by LangChain
        console.print("[green]✓ Phoenix tracing initialized[/green]")
        console.print(
            "[dim]Trace data will be sent to Phoenix at", f"{phoenix_endpoint}[/dim]"
        )

    except ImportError:
        console.print(
            "[yellow]⚠ Phoenix not installed. "
            "Install with: uv add arize-phoenix[langchain][/yellow]"
        )
    except Exception as e:
        console.print(f"[yellow]⚠ Failed to initialize Phoenix: {e}[/yellow]")


def get_phoenix_status() -> dict:
    """
    Get the current Phoenix tracing status.

    Returns:
        Dict with status information
    """
    try:
        import phoenix as px

        return {
            "enabled": True,
            "phoenix_version": px.__version__,
            "project_name": os.getenv("PHOENIX_PROJECT_NAME", "fix-compile"),
            "endpoint": os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006"),
        }
    except ImportError:
        return {
            "enabled": False,
            "reason": "Phoenix not installed",
        }
