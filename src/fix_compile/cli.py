"""Command-line interface for Dockerfile fixer."""

import argparse
import sys
from pathlib import Path

from .fixer import DockerfileFixer


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fix Dockerfile build errors using LLM"
    )
    parser.add_argument(
        "dockerfile",
        type=str,
        help="Path to the Dockerfile",
    )
    parser.add_argument(
        "--error",
        type=str,
        required=True,
        help="The build error message",
    )
    parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="Docker build context directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (if not specified, prints to stdout)",
    )

    args = parser.parse_args()

    # Verify Dockerfile exists
    dockerfile_path = Path(args.dockerfile)
    if not dockerfile_path.exists():
        print(f"Error: Dockerfile not found at {dockerfile_path}", file=sys.stderr)
        sys.exit(1)

    try:
        # Initialize fixer
        fixer = DockerfileFixer()

        # Fix the Dockerfile
        print("Analyzing Dockerfile and error...", file=sys.stderr)
        result = fixer.fix(
            dockerfile_path=str(dockerfile_path),
            error_message=args.error,
            build_context=args.context,
        )

        # Output the fixed Dockerfile
        if args.output:
            with open(args.output, "w") as f:
                f.write(result.fixed_dockerfile)
            print(f"Fixed Dockerfile saved to {args.output}", file=sys.stderr)
        else:
            print(result.fixed_dockerfile)

        # Print explanation
        if result.explanation:
            print(f"\nExplanation:\n{result.explanation}", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
