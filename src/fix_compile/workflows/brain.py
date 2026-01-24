"""Analyzer module - The Brain (LLM interaction logic)."""

import json
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError
from rich.console import Console

from ..schema import AnalysisContext, FixSuggestion

console = Console()


class AnalysisError(Exception):
    """Raised when analysis fails."""

    pass


class Analyzer:
    """
    Handles all LLM-based analysis and fix generation.

    Philosophy: The Brain (Analyzer) knows nothing about subprocess or file I/O.
    It only takes text inputs and produces structured outputs.
    """

    SYSTEM_PROMPT = """You are an expert Docker and DevOps engineer specialized in diagnosing and fixing Docker build and runtime errors.

Your task is to analyze Docker errors and provide precise, actionable fixes.

Guidelines:
1. Analyze the error log carefully to identify the root cause
2. Provide a fix that addresses the root cause, not just symptoms
3. Maintain the original functionality and intent of the Dockerfile
4. Follow Docker best practices (layer caching, minimal layers, security)
5. Be minimal - only change what's necessary
6. Always provide a clear explanation of what went wrong and why your fix works

You MUST respond with valid JSON matching this exact schema:
{
    "reason": "Detailed explanation of the error and why it occurred",
    "file_path": "Path to the file to modify (usually 'Dockerfile')",
    "new_content": "Complete new content of the file",
    "confidence": 0.85,
    "changes_summary": "Brief summary of changes made"
}"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the analyzer.

        Args:
            model: Model name to use (defaults to config)
            api_key: API key (defaults to config)
        """
        self.model = model or config.FIXER_MODEL
        api_key_value = api_key or config.OPENAI_API_KEY.get_secret_value()

        self.client = OpenAI(
            api_key=api_key_value,
            base_url=config.OPENAI_API_BASE,
        )

    def analyze(self, context: AnalysisContext) -> FixSuggestion:
        """
        Analyze the context and generate a fix suggestion.

        Args:
            context: Analysis context with Dockerfile and error log

        Returns:
            FixSuggestion with the proposed fix

        Raises:
            AnalysisError: If analysis fails
        """
        console.print("\n[cyan]🧠 Analyzing error with LLM...[/cyan]")

        # Build user prompt
        user_prompt = self._build_user_prompt(context)

        try:
            # Call LLM with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=config.MAX_TOKENS,
            )

            # Parse response
            content = response.choices[0].message.content
            if not content:
                raise AnalysisError("LLM returned empty response")

            # Parse JSON and validate with Pydantic
            fix_dict = json.loads(content)
            fix = FixSuggestion(**fix_dict)

            console.print(
                f"[green]✓ Analysis complete (confidence: {fix.confidence:.0%})[/green]"
            )
            console.print(f"[dim]{fix.reason}[/dim]\n")

            return fix

        except ValidationError as e:
            raise AnalysisError(f"LLM response validation failed: {e}")
        except json.JSONDecodeError as e:
            raise AnalysisError(f"Failed to parse LLM JSON response: {e}")
        except Exception as e:
            raise AnalysisError(f"Analysis failed: {e}")

    def _build_user_prompt(self, context: AnalysisContext) -> str:
        """Build the user prompt from context."""
        prompt_parts = [
            f"Operation: Docker {context.operation_type.value}",
            f"Dockerfile path: {context.dockerfile_path}",
            f"Build context: {context.build_context}",
        ]

        if context.previous_attempts > 0:
            prompt_parts.append(
                f"⚠️ Previous fix attempts: {context.previous_attempts} (be more careful!)"
            )

        prompt_parts.extend(
            [
                "",
                "=== DOCKERFILE ===",
                "```dockerfile",
                context.dockerfile_content,
                "```",
                "",
                "=== ERROR LOG ===",
                "```",
                context.error_log,
                "```",
                "",
                "Please analyze this error and provide a fix as JSON.",
            ]
        )

        return "\n".join(prompt_parts)

    def quick_analyze(
        self,
        dockerfile_content: str,
        error_log: str,
        operation_type: str = "build",
    ) -> FixSuggestion:
        """
        Quick analysis with minimal setup.

        Args:
            dockerfile_content: Dockerfile content
            error_log: Error log
            operation_type: "build" or "run"

        Returns:
            FixSuggestion
        """
        from ..schema import OperationType

        context = AnalysisContext(
            dockerfile_content=dockerfile_content,
            error_log=error_log,
            operation_type=OperationType(operation_type),
        )

        return self.analyze(context)
