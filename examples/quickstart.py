"""Quick start example for fix-compile."""

from fix_compile import AnalysisContext, Executor, OperationType

# Example 1: Quick analysis
print("=" * 60)
print("Example 1: Quick Analysis")
print("=" * 60)

dockerfile = """FROM ubuntu:20.04
RUN apt-get update && apt-get install -y python3
COPY app.py /app/
CMD ["python3", "/app/app.py"]
"""

error_log = """
Step 2/4 : RUN apt-get update && apt-get install -y python3
 ---> Running in abc123def456
Err:1 http://archive.ubuntu.com/ubuntu focal InRelease
  Could not connect to archive.ubuntu.com:80
E: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/focal/InRelease
"""

# Create context
context = AnalysisContext(
    dockerfile_content=dockerfile,
    error_log=error_log,
    operation_type=OperationType.BUILD,
)

print(f"Dockerfile:\n{dockerfile}")
print(f"\nError:\n{error_log}")

# Uncomment to actually run analysis (requires API key)
# analyzer = Analyzer()
# suggestion = analyzer.analyze(context)
# print(f"\nSuggestion:\n{suggestion.model_dump_json(indent=2)}")


# Example 2: Executor usage
print("\n" + "=" * 60)
print("Example 2: Executor Usage")
print("=" * 60)

executor = Executor(verbose=True)

# Check if Docker is available
result = executor.execute(["docker", "--version"], stream=False)
print(f"\nDocker version: {result.stdout.strip()}")
print(f"Command succeeded: {result.success}")

# Example 3: Reading files
print("\n" + "=" * 60)
print("Example 3: File Operations")
print("=" * 60)

try:
    content = executor.read_file("README.md")
    lines = content.split("\n")
    print("README.md first 3 lines:")
    for line in lines[:3]:
        print(f"  {line}")
except Exception as e:
    print(f"Error reading README.md: {e}")

print("\n" + "=" * 60)
print("Examples completed!")
print("=" * 60)
