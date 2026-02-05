"""Analyzer module - The Brain (LLM interaction logic)."""

import json
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from rich.console import Console

from fix_compile.config import config_service
from fix_compile.utils import ui

from ..schema import FixSuggestion, FixType, GeneralAnalysisContext

console = Console()


# ============================================================================
# File System Tools
# ============================================================================


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


def list_files_in_directory(dir_path: str = ".", cwd: str = ".") -> list[str]:
    """List files in a directory.

    Args:
        dir_path: Directory path (relative to cwd), default "."
        cwd: Current working directory

    Returns:
        List of file names/paths
    """
    full_path = Path(cwd) / dir_path
    if not full_path.exists():
        return []

    files = []
    for item in full_path.iterdir():
        rel_path = item.relative_to(cwd)
        files.append(str(rel_path))
    return sorted(files)


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


# ============================================================================
# GeneralFixer Class
# ============================================================================


class GeneralFixer:
    """
    Handles all LLM-based analysis and fix generation.

    Philosophy: The Brain (Analyzer) knows nothing about subprocess or file I/O.
    It only takes text inputs and produces structured outputs.
    """

    SYSTEM_PROMPT = """You are an expert problem solver for general errors in computing environments.

Your task is to analyze error logs and provide precise, actionable fixes.
The fix can be one of three types:
1. COMMAND: Modify or run a shell command
2. FILE: Modify a file in the current working directory
3. DOCKER: Modify a Dockerfile (for Docker-specific errors)

Guidelines:
1. Analyze the error log carefully to identify the root cause
2. Provide a fix that addresses the root cause, not just symptoms
3. Choose the most appropriate fix type:
   - Use COMMAND if the fix is to change/run a command
   - Use FILE if the fix requires modifying application files (config, source code, requirements, etc.)
   - Use DOCKER if the error is Docker-related and needs Dockerfile changes
4. Be minimal - only change what's necessary
5. Always provide a clear explanation of what went wrong and why your fix works
6. Consider the current working directory when specifying file paths (use relative paths)

You MUST respond with valid JSON matching this exact schema based on the fix type:

For COMMAND fixes:
{
    "reason": "Detailed explanation of the root cause",
    "fix_type": "command",
    "command": "The complete command to execute or the modified command",
    "command_explanation": "Explanation of what this command does and why it fixes the issue",
    "confidence": 0.85,
    "changes_summary": "Brief summary of the command change"
}

For FILE fixes:
{
    "reason": "Detailed explanation of the root cause",
    "fix_type": "file",
    "file_path": "Path to file (relative to cwd, e.g., 'src/config.py' or 'requirements.txt')",
    "new_content": "Complete new content of the file",
    "file_explanation": "Explanation of what was changed in the file and why",
    "confidence": 0.85,
    "changes_summary": "Brief summary of file changes"
}

For DOCKER fixes:
{
    "reason": "Detailed explanation of the Docker error",
    "fix_type": "docker",
    "dockerfile_path": "Path to Dockerfile (e.g., 'Dockerfile')",
    "dockerfile_content": "Complete new Dockerfile content",
    "confidence": 0.85,
    "changes_summary": "Brief summary of Dockerfile changes"
}"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the analyzer.

        Args:
            model: Model name to use (defaults to config)
            api_key: API key (defaults to config)
        """

        self.config = config_service.config
        self.model = model or self.config.FIXER_MODEL
        api_key_value = api_key or self.config.OPENAI_API_KEY.get_secret_value()

        self.client = ChatOpenAI(
            model=self.model,
            api_key=api_key_value,
            base_url=self.config.OPENAI_API_BASE,
        )

    def analyze(self, context: GeneralAnalysisContext) -> FixSuggestion:
        """
        Analyze the context and generate a fix suggestion.

        Args:
            context: Analysis context with error log and current working directory

        Returns:
            FixSuggestion with the proposed fix

        Raises:
            AnalysisError: If analysis fails
        """
        console.print("\n[cyan]🧠 Analyzing error with LLM...[/cyan]")

        # Build user prompt with context about the environment
        user_prompt = self._build_user_prompt(context)

        try:
            # Call LLM with structured output
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            response = self.client.invoke(
                messages,
                temperature=0.2,
                max_tokens=self.config.MAX_TOKENS,
            )

            # Parse response
            content = response.content
            if not content:
                ui.warning("LLM returned empty response")
                return FixSuggestion(
                    reason="LLM returned empty response",
                    fix_type=FixType.COMMAND,
                    command="",
                    confidence=0.0,
                    changes_summary="",
                )

            # Parse JSON and validate with Pydantic
            fix_dict = json.loads(content)
            fix = FixSuggestion(**fix_dict)

            # Log the fix suggestion
            console.print(
                f"[green]✓ Analysis complete (confidence: {fix.confidence:.0%})[/green]"
            )
            console.print(f"[dim]Reason: {fix.reason}[/dim]")
            console.print(f"[dim]Fix Type: {fix.fix_type.value}[/dim]")

            # Display fix-specific information
            if fix.fix_type == FixType.COMMAND:
                console.print(f"[dim]Command: {fix.command}[/dim]")
                if fix.command_explanation:
                    console.print(f"[dim]{fix.command_explanation}[/dim]")
            elif fix.fix_type == FixType.FILE:
                console.print(f"[dim]File: {fix.file_path}[/dim]")
                if fix.file_explanation:
                    console.print(f"[dim]{fix.file_explanation}[/dim]")
            elif fix.fix_type == FixType.DOCKER:
                console.print(f"[dim]Dockerfile: {fix.dockerfile_path}[/dim]")

            console.print(f"[dim]{fix.changes_summary}[/dim]\n")

            return fix

        except ValidationError as e:
            ui.error(f"LLM response validation failed: {e}")
            raise
        except json.JSONDecodeError as e:
            ui.error(f"Failed to parse LLM JSON response: {e}")
            raise
        except Exception as e:
            ui.error(f"Analysis failed: {e}")
            raise

    def _build_user_prompt(self, context: GeneralAnalysisContext) -> str:
        """Build the user prompt from context with file system information."""
        prompt_parts = [
            "=== ENVIRONMENT CONTEXT ===",
            f"Working Directory: {context.cwd}",
        ]

        # Try to list files in the current directory
        try:
            files = list_files_in_directory(".", cwd=context.cwd)
            if files:
                prompt_parts.append(f"Files in cwd (first 20): {files[:20]}")
        except Exception:
            pass

        # Add error log
        prompt_parts.extend(
            [
                "",
                "=== ERROR LOG ===",
                context.error_log,
            ]
        )

        # Add context about previous attempts
        if context.previous_attempts > 0:
            prompt_parts.insert(
                0,
                f"⚠️ Previous fix attempts: {context.previous_attempts} (be more careful!)",
            )

        prompt_parts.extend(
            [
                "",
                "Please analyze this error and provide a fix as JSON.",
                "Include the appropriate fix_type (command, file, or docker) based on the error.",
            ]
        )

        return "\n".join(prompt_parts)

    def quick_analyze(
        self,
        error_log: str,
        cwd: str = ".",
    ) -> FixSuggestion:
        """
        Quick analysis with minimal setup.

        Args:
            error_log: Error log
            cwd: Current working directory (default: ".")
        Returns:
            FixSuggestion
        """

        context = GeneralAnalysisContext(
            error_log=error_log,
            cwd=cwd,
        )

        return self.analyze(context)
