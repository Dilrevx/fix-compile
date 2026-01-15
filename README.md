# Dockerfile Fixer using LLM

A Python project that uses LangChain and LLM (OpenAI ChatGPT) to automatically detect and fix Dockerfile build errors.

## Features

- **Automatic Error Analysis**: Identifies the type of Dockerfile build error (path not found, missing dependencies, etc.)
- **LLM-powered Fixes**: Uses OpenAI's ChatGPT to generate fixes for Dockerfile issues
- **CLI Tool**: Command-line interface for easy integration into CI/CD pipelines
- **Type-safe**: Full type hints and Pydantic models
- **Extensible**: Easy to add new error types and custom LLM providers

## Prerequisites

- Python 3.11+
- uv package manager
- OpenAI API key (for ChatGPT access)

## Installation

1. Install dependencies using uv:

```bash
uv sync
```

2. Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### As a Python Library

```python
from src.fix_compile import DockerfileFixer

# Initialize the fixer
fixer = DockerfileFixer()

# Fix a Dockerfile
result = fixer.fix(
    dockerfile_path="path/to/Dockerfile",
    error_message="COPY failed: stat /app/file.txt: no such file or directory",
    build_context="/path/to/build/context"
)

print("Fixed Dockerfile:")
print(result.fixed_dockerfile)
print("\nExplanation:")
print(result.explanation)
```

### As a CLI Tool

```bash
# Fix a Dockerfile and print the result
python -m src.fix_compile.cli path/to/Dockerfile \
    --error "COPY failed: stat /app/file.txt: no such file or directory" \
    --context /path/to/build/context

# Save the fixed Dockerfile to a file
python -m src.fix_compile.cli path/to/Dockerfile \
    --error "COPY failed: stat /app/file.txt: no such file or directory" \
    --output path/to/Dockerfile.fixed
```

## Project Structure

```
src/fix_compile/
├── __init__.py          # Package exports
├── models.py            # Data models (DockerfileProblem, FixResult)
├── analyzer.py          # Dockerfile error analyzer
├── fixer.py             # Main DockerfileFixer class
└── cli.py               # Command-line interface
```

## Supported Error Types

- `PATH_NOT_FOUND`: Files or directories referenced in COPY/ADD commands don't exist
- `PERMISSION_DENIED`: Permission issues during build
- `MISSING_DEPENDENCY`: Missing system or language packages
- `IMAGE_NOT_FOUND`: Base image not found in registry
- `INVALID_SYNTAX`: Dockerfile syntax errors
- `BUILD_CONTEXT_ERROR`: Issues with build context configuration
- `UNKNOWN`: Other error types

## Configuration

### Custom LLM Provider

You can use a different LLM provider by passing a LangChain BaseChatModel instance:

```python
from langchain_anthropic import ChatAnthropic
from src.fix_compile import DockerfileFixer

# Use Anthropic Claude instead of OpenAI
llm = ChatAnthropic(model="claude-3-sonnet-20240229")
fixer = DockerfileFixer(llm=llm)
```

## Development

### Run Tests

```bash
uv run pytest
```

### Code Quality

Format code:
```bash
uv run black src/
```

Lint code:
```bash
uv run ruff check src/
```

Type checking:
```bash
uv run mypy src/
```

## License

See LICENSE file for details.
