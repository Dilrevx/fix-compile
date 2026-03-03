"""File system tools for LLM interaction."""

import shlex
import subprocess
from pathlib import Path


def execute_command(cmd: str, cwd: str = ".") -> dict:
    """Execute a shell command and return LLM-friendly result.

    Args:
        cmd: Command to execute (will be parsed with shlex)
        cwd: Current working directory

    Returns:
        Dictionary with execution result:
        - success: Whether command succeeded
        - output: Combined stdout/stderr
        - exit_code: Exit code
        - error: Error message if failed
    """
    try:
        result = subprocess.run(
            shlex.split(cmd),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).strip()
        return {
            "success": result.returncode == 0,
            "output": output,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "exit_code": -1,
            "error": "Command timed out (10s)",
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "exit_code": -1,
            "error": str(e),
        }


def read_file_content(file_path: str, cwd: str = ".") -> str:
    """Read content of a file from the specified working directory.

    Args:
        file_path: Path to the file (relative to cwd)
        cwd: Current working directory

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
    """
    full_path = Path(cwd) / file_path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return full_path.read_text(encoding="utf-8")


def get_file_info(file_path: str, cwd: str = ".") -> dict:
    """Get information about a file.

    Args:
        file_path: Path to the file
        cwd: Current working directory

    Returns:
        Dictionary with file info (exists, is_dir, size, lines)
    """
    full_path = Path(cwd) / file_path

    if not full_path.exists():
        return {"exists": False, "path": file_path}

    info = {
        "exists": True,
        "path": file_path,
        "is_dir": full_path.is_dir(),
        "size_bytes": full_path.stat().st_size if full_path.is_file() else None,
    }

    if full_path.is_file():
        try:
            content = full_path.read_text(encoding="utf-8")
            info["lines"] = len(content.splitlines())
        except Exception:
            info["lines"] = None

    return info


def write_file_content(file_path: str, content: str, cwd: str = ".") -> dict:
    """Write content to a file in the specified working directory.

    Args:
        file_path: Path to the file (relative to cwd)
        content: Content to write
        cwd: Current working directory

    Returns:
        Dictionary with write result (success, path, error)
    """
    try:
        full_path = Path(cwd) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return {"success": True, "path": file_path}
    except Exception as e:
        return {"success": False, "path": file_path, "error": str(e)}


def backup_file(file_path: str, cwd: str = ".", suffix: str = ".bak") -> dict:
    """Create a backup of a file with the given suffix.

    Args:
        file_path: Path to the file (relative to cwd)
        cwd: Current working directory
        suffix: Backup suffix (default: .bak)

    Returns:
        Dictionary with backup result (success, path, backup_path, error)
    """
    try:
        full_path = Path(cwd) / file_path
        if not full_path.exists() or not full_path.is_file():
            return {
                "success": False,
                "path": file_path,
                "error": "File does not exist or is not a file",
            }

        backup_path = Path(f"{full_path}{suffix}")
        backup_path.write_text(full_path.read_text(encoding="utf-8"), encoding="utf-8")
        return {
            "success": True,
            "path": file_path,
            "backup_path": str(backup_path),
        }
    except Exception as e:
        return {"success": False, "path": file_path, "error": str(e)}


def list_directory(path: str = ".", cwd: str = ".") -> dict:
    """List entries in a directory.

    Args:
        path: Directory path (relative to cwd)
        cwd: Current working directory

    Returns:
        Dictionary with directory listing or error
    """
    try:
        full_path = Path(cwd) / path
        if not full_path.exists() or not full_path.is_dir():
            return {
                "success": False,
                "path": path,
                "error": "Directory does not exist",
            }

        entries = sorted([p.name for p in full_path.iterdir()])
        return {"success": True, "path": path, "entries": entries}
    except Exception as e:
        return {"success": False, "path": path, "error": str(e)}
