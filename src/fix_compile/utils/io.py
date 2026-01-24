import json
from pathlib import Path
from typing import Any, Dict

from fix_compile.utils import ui

# ---------------------------------------------------------
# 3. Helper / IO Functions
# ---------------------------------------------------------


def format_json(data: Dict[str, Any]) -> str:
    """Format dictionary as pretty JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def load_file(file_path: Path) -> str:
    """Load file content with error handling."""
    try:
        content = file_path.read_text(encoding="utf-8")
        ui.debug(f"Loaded file: {file_path}")
        return content
    except FileNotFoundError:
        msg = f"File not found: {file_path}"
        ui.error(msg)
        raise
    except IOError as e:
        msg = f"Failed to read file {file_path}: {e}"
        ui.exception(msg)  # Log stack trace
        raise


def save_result(content: str, output_path: Path) -> None:
    """Save content to file and print success."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        # 复用 print_success 实现双写
        ui.success(f"Saved result to {output_path}")

    except IOError as e:
        msg = f"Failed to save file {output_path}: {e}"
        ui.exception(msg)
        raise
