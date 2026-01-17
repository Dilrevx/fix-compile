"""Example usage of DockerfileFixer."""

from src.fix_compile import DockerfileFixer


def example_fix_dockerfile():
    """Example of fixing a Dockerfile with path error."""

    # Initialize the fixer
    # Make sure OPENAI_API_KEY is set in your environment
    fixer = DockerfileFixer()

    # Example Dockerfile path
    dockerfile_path = "assets/examples/Dockerfile.bad"

    # Example error message
    error_message = """
    COPY failed: stat /myapp/nonexistent.txt: no such file or directory
    """

    # Fix the Dockerfile
    result = fixer.fix(
        dockerfile_path=dockerfile_path,
        error_message=error_message,
        build_context="/path/to/build/context",
    )

    print("Original Dockerfile:")
    print(result.original_dockerfile)
    print("\n" + "=" * 50 + "\n")

    print("Fixed Dockerfile:")
    print(result.fixed_dockerfile)
    print("\n" + "=" * 50 + "\n")

    print("Explanation:")
    print(result.explanation)
    print(f"\nConfidence: {result.confidence}")


if __name__ == "__main__":
    example_fix_dockerfile()
