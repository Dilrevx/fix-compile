"""Example: Using Custom Prompt for proxy settings."""

from fix_compile import DockerFixer, GeneralFixer, PromptBuilder
from fix_compile.config import config_service

# Example 1: View built-in example prompts
print("=== Built-in Example Prompts ===")
examples = PromptBuilder.get_example_custom_prompts()
print(f"\nProxy Example:\n{examples['proxy']}")
print(f"\nChina Mirror Example:\n{examples['china_mirror']}")

# Example 2: Use GeneralFixer with custom prompt
print("\n=== Using GeneralFixer with Custom Prompt ===")

custom_prompt = """
All network operations must use HTTP/HTTPS proxy at 172.17.0.1:7890.
For Dockerfile:
- Set environment variables: ENV HTTP_PROXY=http://172.17.0.1:7890 HTTPS_PROXY=http://172.17.0.1:7890
- Apply proxy to all RUN commands that download packages (apt-get, pip, npm, etc.)
"""

fixer = GeneralFixer(custom_prompt=custom_prompt)

# Simulate an error
error_log = """
E: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/focal/main/binary-amd64/Packages
E: Unable to fetch some archives, maybe run apt-get update or try with --fix-missing?
"""

# Analyze the error (the fix will include proxy settings)
# suggestion = fixer.quick_analyze(error_log=error_log, cwd=".")
# print(f"Suggestion: {suggestion}")

# Example 3: Use DockerFixer with config-based custom prompt
print("\n=== Using DockerFixer with Config Custom Prompt ===")

# Load config (with custom prompt from .env or config file)
config_service.load_config(dev_mode=True)

# DockerFixer will automatically use custom prompt from config
docker_fixer = DockerFixer(config=config_service.config)

# Example 4: Build custom system prompt
print("\n=== Building Custom System Prompt ===")

custom_requirements = """
Environment Requirements:
1. Use Clash proxy at 172.17.0.1:7890 for all network operations
2. Set timezone to Asia/Shanghai
3. Use Tsinghua mirrors for pip packages
"""

full_prompt = PromptBuilder.build_system_prompt(custom_requirements)
print(f"Full System Prompt Preview (first 500 chars):\n{full_prompt[:500]}...")

# Example 5: No custom prompt (using default behavior)
print("\n=== Using Default Behavior (No Custom Prompt) ===")

default_fixer = GeneralFixer()  # No custom prompt
print("GeneralFixer initialized without custom prompt")

print("\n=== Examples Complete ===")
print("See docs/CUSTOM-PROMPT.md for more detailed usage instructions")
