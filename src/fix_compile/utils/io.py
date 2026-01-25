import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from fix_compile.config import DirConfigs
from fix_compile.schema import CommandResult
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
        ui.error(msg)
        raise


def save_exec_output(content: CommandResult, dir_config: DirConfigs) -> None:
    """Save content to file and print success."""
    cmd_hash = hashlib.sha256(
        f"{content.command}|{content.cwd}".encode("utf-8")
    ).hexdigest()[:8]
    output_dir = dir_config.cache_dir / cmd_hash
    stdout_file = output_dir / "stdout.txt"
    stderr_file = output_dir / "stderr.txt"
    meta_file = output_dir / "meta.json"

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        stdout_file.write_text(content.stdout, encoding="utf-8")
        stderr_file.write_text(content.stderr, encoding="utf-8")
        meta_file.write_text(
            content.model_dump_json(
                indent=2,
                ensure_ascii=False,
                exclude={"stdout", "stderr"},
            ),
            encoding="utf-8",
        )
        # 复用 print_success 实现双写
        ui.success(f"Saved result to {output_dir}")

    except IOError as e:
        msg = f"Failed to save file {output_dir}: {e}"
        ui.error(msg)
