"""Docker subcommand for fix-compile CLI."""

from pathlib import Path

import typer

from fix_compile.config import config_service
from fix_compile.workflows.docker_fixer import DockerFixer

docker_app = typer.Typer(help="Docker tools with auto-fix capabilities")


@docker_app.command(
    "build",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def build(
    ctx: typer.Context,
    tag: str = typer.Option("latest", "-t", "--tag", help="Image tag"),
    file: Path = typer.Option("Dockerfile", "-f", "--file", help="Dockerfile path"),
    no_fix: bool = typer.Option(False, "--no-fix", help="Disable AI analysis"),
    force: bool = typer.Option(
        False, "--force", help="Force re-execution (ignore cached logs)"
    ),
    dev: bool = typer.Option(False, "--dev", help="Dev mode"),
):
    """
    Build Docker image with optional auto-fix.

    Examples:
        fix-compile docker build
        fix-compile docker build -t myapp:v1 -f docker/Dockerfile
        fix-compile docker build --no-cache --build-arg VERSION=1.0
        fix-compile docker build --no-fix  # disable AI analysis
    """
    # 1. Load Config
    config_service.load_config(dev_mode=dev)
    config = config_service.config

    # 2. Reconstruct Command
    # Manually add tag and file back, plus any extra args from ctx.args
    cmd = ["docker", "build", "-t", tag, "-f", str(file)] + list(ctx.args)

    # 3. Run Pipeline
    fixer = DockerFixer(config)
    fixer.run_pipeline(
        cmd=cmd,
        cwd=Path.cwd(),
        dockerfile_path=file,
        no_fix=no_fix,
        force_rerun=force,
    )


@docker_app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run(
    ctx: typer.Context,
    no_fix: bool = typer.Option(False, "--no-fix", help="Disable AI analysis"),
    force: bool = typer.Option(
        False, "--force", help="Force re-execution (ignore cached logs)"
    ),
    dev: bool = typer.Option(False, "--dev", help="Dev mode"),
):
    """
    Run Docker container with optional auto-fix.

    Examples:
        fix-compile docker run myapp:latest
        fix-compile docker run -p 8080:80 myapp:latest
        fix-compile docker run --rm -it ubuntu bash
        fix-compile docker run --no-fix myapp:latest  # disable AI analysis
    """
    # 1. Load Config
    config_service.load_config(dev_mode=dev)
    config = config_service.config

    # 2. Reconstruct Command
    cmd = ["docker", "run"] + list(ctx.args)

    # 3. Run Pipeline
    fixer = DockerFixer(config)
    fixer.run_pipeline(
        cmd=cmd,
        cwd=Path.cwd(),
        no_fix=no_fix,
        force_rerun=force,
    )
