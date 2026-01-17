"""Dockerfile fixer using LangChain and LLM."""

import os
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from .analyzer import DockerfileAnalyzer
from .models import DockerfileProblem, FixResult


class DockerfileFixer:
    """Fix Dockerfile build errors using LLM."""

    FIX_PROMPT_TEMPLATE = """You are an expert Docker and DevOps engineer. Your task is to fix a Dockerfile that has build errors.

Dockerfile path: {dockerfile_path}
Build context: {build_context}
Problem type: {problem_type}

Original Dockerfile:
```dockerfile
{original_dockerfile}
```

Build error:
```
{error_message}
```

Please analyze the error and provide a fixed version of the Dockerfile that will resolve the build issue.
The fix should:
1. Address the root cause of the error
2. Maintain the original functionality
3. Follow Docker best practices
4. Be minimal and focused

Provide the fixed Dockerfile and a brief explanation of the changes made."""

    def __init__(
        self, llm: Optional[BaseChatModel] = None, api_key: Optional[str] = None
    ):
        """
        Initialize the Dockerfile fixer.

        Args:
            llm: Optional LangChain LLM instance. If not provided, will use OpenAI ChatGPT.
            api_key: Optional OpenAI API key. If not provided, will use OPENAI_API_KEY env var.
        """
        if llm is not None:
            self.llm = llm
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "No LLM provided and OPENAI_API_KEY environment variable not set. "
                    "Please provide an API key or a custom LLM instance."
                )
            self.llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=api_key,
                temperature=0.2,
            )

        self.analyzer = DockerfileAnalyzer()

    def fix(
        self,
        dockerfile_path: str,
        error_message: str,
        build_context: Optional[str] = None,
    ) -> FixResult:
        """
        Fix a Dockerfile build error.

        Args:
            dockerfile_path: Path to the Dockerfile
            error_message: The build error message
            build_context: The Docker build context directory

        Returns:
            FixResult with the fixed Dockerfile and explanation
        """
        # Read the original Dockerfile
        try:
            with open(dockerfile_path, "r") as f:
                original_dockerfile = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")

        # Analyze the problem
        problem = self.analyzer.analyze(dockerfile_path, error_message, build_context)

        # Get fix from LLM
        fixed_dockerfile, explanation = self._get_fix_from_llm(
            original_dockerfile=original_dockerfile,
            problem=problem,
        )

        return FixResult(
            success=True,
            original_dockerfile=original_dockerfile,
            fixed_dockerfile=fixed_dockerfile,
            explanation=explanation,
            confidence=0.8,  # Default confidence score
        )

    def _get_fix_from_llm(
        self, original_dockerfile: str, problem: DockerfileProblem
    ) -> tuple[str, str]:
        """
        Get fix recommendation from LLM.

        Args:
            original_dockerfile: Original Dockerfile content
            problem: Analyzed problem

        Returns:
            Tuple of (fixed_dockerfile, explanation)
        """
        prompt = PromptTemplate(
            template=self.FIX_PROMPT_TEMPLATE,
            input_variables=[
                "dockerfile_path",
                "build_context",
                "problem_type",
                "original_dockerfile",
                "error_message",
            ],
        )

        formatted_prompt = prompt.format(
            dockerfile_path=problem.dockerfile_path,
            build_context=problem.build_context or "root",
            problem_type=problem.problem_type.value
            if problem.problem_type
            else "unknown",
            original_dockerfile=original_dockerfile,
            error_message=problem.error_message,
        )

        response = self.llm.invoke(formatted_prompt)
        response_text = response.content

        # Parse the response to extract fixed Dockerfile and explanation
        fixed_dockerfile, explanation = self._parse_response(response_text)

        return fixed_dockerfile, explanation

    @staticmethod
    def _parse_response(response_text: str) -> tuple[str, str]:
        """
        Parse LLM response to extract fixed Dockerfile and explanation.

        Args:
            response_text: Raw response from LLM

        Returns:
            Tuple of (fixed_dockerfile, explanation)
        """
        # Look for Dockerfile in code blocks
        import re

        dockerfile_match = re.search(
            r"```dockerfile\n(.*?)\n```", response_text, re.DOTALL
        )

        if dockerfile_match:
            fixed_dockerfile = dockerfile_match.group(1).strip()
        else:
            # Fallback: look for any code block
            code_match = re.search(r"```\n(.*?)\n```", response_text, re.DOTALL)
            fixed_dockerfile = (
                code_match.group(1).strip() if code_match else response_text
            )

        # Extract explanation (everything before the code block or after)
        explanation = re.sub(r"```[\s\S]*?```", "", response_text).strip()

        return fixed_dockerfile, explanation
