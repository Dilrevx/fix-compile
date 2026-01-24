"""Phoenix observability and tracing setup for debugging."""

import os
from typing import Optional

from phoenix.otel import register

from fix_compile.constants import PROJECT_NAME
from fix_compile.utils import ui


def setup_phoenix_tracing(
    project_name: str = PROJECT_NAME,
    endpoint: Optional[str] = None,
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
    """
    try:
        register(
            project_name=project_name,
            endpoint=endpoint,
            auto_instrument=True,  # Auto-instrument your app based on installed OI dependencies
        )

    except Exception as e:
        ui.warning(f"Failed to initialize Phoenix: {e}")


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
