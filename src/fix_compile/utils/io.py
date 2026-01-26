import hashlib
import json
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

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


def cmd2hash(cmd: list[str] | str, cwd: Path | str) -> str:
    """Generate a SHA256 hash for a command and cwd. Used to locate log dirs."""
    if isinstance(cmd, list):
        cmd = shlex.join(cmd)
    if isinstance(cwd, Path):
        cwd = str(cwd.resolve())

    hash_input = f"{cmd}|{cwd}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:8]


def save_exec_output(
    content: CommandResult,
    output_dir: Optional[Path],
) -> None:
    """
    Save content to output_dir/ and print success.
    """

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
