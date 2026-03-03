"""Analyzer module - The Brain (LLM interaction logic)."""

import json
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from fix_compile.config import config_service
from fix_compile.tools import execute_command
from fix_compile.utils import ui
from fix_compile.utils.prompt_builder import PromptBuilder

from ..schema import FixSuggestion, FixType, GeneralAnalysisContext, PreflightSuggestion

# ============================================================================
# GeneralFixer Class
# ============================================================================


class GeneralFixer:
    """
    Handles all LLM-based analysis and fix generation.

    Philosophy: The Brain (Analyzer) knows nothing about subprocess or file I/O.
    It only takes text inputs and produces structured outputs.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ):
        """
        Initialize the analyzer.

        Args:
            model: Model name to use (defaults to config)
            api_key: API key (defaults to config)
            custom_prompt: User custom prompt to append to system prompt (defaults to config)
        """

        self.config = config_service.config
        self.model = model or self.config.FIXER_MODEL
        api_key_value = api_key or self.config.OPENAI_API_KEY.get_secret_value()
        self.custom_prompt = (
            custom_prompt if custom_prompt is not None else self.config.CUSTOM_PROMPT
        )

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
        ui.info("🧠 Analyzing error with LLM...")

        # Build system prompt with custom requirements
        system_prompt = PromptBuilder.build_system_prompt(self.custom_prompt)

        # Build user prompt with context about the environment
        user_prompt = self._build_user_prompt(context)

        try:
            # Call LLM with structured output
            messages = [
                SystemMessage(content=system_prompt),
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
            ui.success(f"Analysis complete (confidence: {fix.confidence:.0%})")
            ui.debug(f"Reason: {fix.reason}")
            ui.debug(f"Fix Type: {fix.fix_type.value}")

            # Display fix-specific information
            if fix.fix_type == FixType.COMMAND:
                ui.debug(f"Command: {fix.command}")
                if fix.command_explanation:
                    ui.debug(f"{fix.command_explanation}")
            elif fix.fix_type == FixType.FILE:
                ui.debug(f"File: {fix.file_path}")
                if fix.file_explanation:
                    ui.debug(f"{fix.file_explanation}")
            elif fix.fix_type == FixType.DOCKER:
                ui.debug(f"Dockerfile: {fix.dockerfile_path}")

            ui.debug(f"{fix.changes_summary}")
            ui.info("")  # Empty line for spacing

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

    def preflight_custom_prompt(
        self,
        dockerfile_path: str,
        dockerfile_content: str,
        build_context: str,
        related_files: dict[str, str],
    ) -> PreflightSuggestion:
        """
        Generate preflight changes to comply with custom prompt.

        Args:
            dockerfile_path: Path to Dockerfile (relative to build context)
            dockerfile_content: Dockerfile content
            build_context: Build context path
            related_files: Mapping of related file path to file content

        Returns:
            PreflightSuggestion with proposed changes
        """
        system_prompt = PromptBuilder.build_preflight_system_prompt(self.custom_prompt)
        user_prompt = self._build_preflight_user_prompt(
            dockerfile_path=dockerfile_path,
            dockerfile_content=dockerfile_content,
            build_context=build_context,
            related_files=related_files,
        )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = self.client.invoke(
                messages,
                temperature=0.2,
                max_tokens=self.config.MAX_TOKENS,
            )

            content = response.content
            if not content:
                ui.warning("LLM returned empty preflight response")
                return PreflightSuggestion(
                    reason="LLM returned empty response",
                    changes=[],
                    confidence=0.0,
                    changes_summary="No changes generated",
                )

            preflight_dict = json.loads(content)
            suggestion = PreflightSuggestion(**preflight_dict)

            ui.success(
                f"Preflight analysis complete (confidence: {suggestion.confidence:.0%})"
            )
            ui.debug(f"Preflight reason: {suggestion.reason}")
            ui.debug(f"Preflight changes: {len(suggestion.changes)}")

            return suggestion

        except ValidationError as e:
            ui.error(f"LLM preflight response validation failed: {e}")
            raise
        except json.JSONDecodeError as e:
            ui.error(f"Failed to parse LLM preflight JSON response: {e}")
            raise
        except Exception as e:
            ui.error(f"Preflight analysis failed: {e}")
            raise

    def _build_user_prompt(self, context: GeneralAnalysisContext) -> str:
        """Build the user prompt from context with file system information."""
        prompt_parts = [
            "=== ENVIRONMENT CONTEXT ===",
            f"Working Directory: {context.cwd}",
        ]

        # Try to list files in the current directory using ls command
        try:
            ls_result = execute_command("ls -la", cwd=context.cwd)
            if ls_result["success"] and ls_result["output"]:
                # Limit output to avoid token overflow
                lines = ls_result["output"].splitlines()
                if len(lines) > 25:
                    output = (
                        "\n".join(lines[:25]) + f"\n... ({len(lines) - 25} more items)"
                    )
                else:
                    output = ls_result["output"]
                prompt_parts.append(f"Directory listing:\n{output}")
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

    def _build_preflight_user_prompt(
        self,
        dockerfile_path: str,
        dockerfile_content: str,
        build_context: str,
        related_files: dict[str, str],
    ) -> str:
        """Build user prompt for preflight custom prompt compliance."""
        prompt_parts = [
            "=== PREFLIGHT CONTEXT ===",
            f"Build Context: {build_context}",
            f"Dockerfile Path: {dockerfile_path}",
            "",
            "=== DOCKERFILE ===",
            dockerfile_content,
        ]

        if related_files:
            prompt_parts.append("")
            prompt_parts.append("=== RELATED FILES (COPY/ADD SOURCES) ===")
            for path, content in related_files.items():
                prompt_parts.extend(
                    [
                        "",
                        f"--- File: {path} ---",
                        content,
                    ]
                )
        else:
            prompt_parts.extend(
                [
                    "",
                    "=== RELATED FILES (COPY/ADD SOURCES) ===",
                    "(No related files were provided)",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "Please return JSON only following the required schema.",
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
        cwd = Path(cwd).resolve().as_posix()

        context = GeneralAnalysisContext(
            error_log=error_log,
            cwd=cwd,
        )

        return self.analyze(context)
