"""Prompt builder for constructing system prompts with custom user requirements."""

from typing import Optional


class PromptBuilder:
    """Builder for constructing complete system prompts with user customizations."""

    BASE_SYSTEM_PROMPT = """You are an expert problem solver for general errors in computing environments.

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

    @staticmethod
    def build_system_prompt(custom_prompt: Optional[str] = None) -> str:
        """
        Build complete system prompt with optional user customizations.

        Args:
            custom_prompt: User custom prompt to append (e.g., proxy settings, environment requirements)

        Returns:
            Complete system prompt string

        Example:
            >>> builder = PromptBuilder()
            >>> prompt = builder.build_system_prompt(
            ...     "All Dockerfile installations must use proxy at 172.17.0.1:7890"
            ... )
        """
        prompt_parts = [PromptBuilder.BASE_SYSTEM_PROMPT]

        # Append custom prompt if provided
        if custom_prompt and custom_prompt.strip():
            prompt_parts.extend(
                [
                    "",
                    "=== USER CUSTOM REQUIREMENTS ===",
                    "The following are user-specific requirements that MUST be followed in all fixes:",
                    custom_prompt.strip(),
                    "",
                    "IMPORTANT: All fixes MUST comply with the above custom requirements.",
                ]
            )

        return "\n".join(prompt_parts)

    @staticmethod
    def get_example_custom_prompts() -> dict[str, str]:
        """
        Get example custom prompts for reference.

        Returns:
            Dictionary of example names to custom prompt strings
        """
        return {
            "proxy": """All network operations must use HTTP/HTTPS proxy at 172.17.0.1:7890.
For Dockerfile:
- Set environment variables: ENV HTTP_PROXY=http://172.17.0.1:7890 HTTPS_PROXY=http://172.17.0.1:7890
- Apply proxy to all RUN commands that download packages (apt-get, pip, npm, etc.)
- Ensure proxy is used for wget, curl, git clone, and similar commands""",
            "china_mirror": """Use China mirror sources for package installations:
- For apt: Use Tsinghua/Aliyun mirrors
- For pip: Use https://pypi.tuna.tsinghua.edu.cn/simple
- For npm: Use https://registry.npmmirror.com
- For Docker: Use Docker Hub mirror if available""",
            "security": """All fixes must follow security best practices:
- Never run containers as root (use USER directive)
- Pin package versions explicitly
- Minimize layer count and image size
- Remove build dependencies after installation
- Use multi-stage builds when possible""",
            "timezone": """Set timezone to Asia/Shanghai in all containers:
- Add: ENV TZ=Asia/Shanghai
- Install and configure tzdata package
- Create symlink: ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime""",
        }
