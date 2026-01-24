"""Config CLI"""

import typer
from rich.table import Table

from fix_compile.config import Configs, config_service
from fix_compile.utils.ui import console, error, info, success, warning

# ============================================================================
# Command: config (Configuration Management)
# ============================================================================


config_app = typer.Typer(help="Manage configuration for fix-compile")


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value."""
    valid_keys = Configs.model_fields.keys() - {"dir_configs"}
    if key not in valid_keys:
        error(f"Invalid configuration key: {key}")
        info(f"Valid keys: {', '.join(sorted(valid_keys))}")
        raise typer.Exit(1)

    try:
        config_service.load_config()
        config = config_service.config
        setattr(config, key, value)
        config_service.save_config()

        success(f"Configuration saved: {key} = {value}")
    except Exception as e:
        error(f"Failed to save configuration: {e}")
        raise typer.Exit(1)


@config_app.command(name="get")
def config_get(key: str = typer.Argument(..., help="Configuration key")):
    """Get a configuration value."""
    valid_keys = Configs.model_fields.keys() - {"dir_configs"}
    if key not in valid_keys:
        error(f"Invalid configuration key: {key}")
        raise typer.Exit(1)

    try:
        config_service.load_config()
        config = config_service.config
        value = getattr(config, key)
        info(f"Configuration value for {key}: {value}")
    except Exception as e:
        error(f"Failed to read configuration: {e}")
        raise typer.Exit(1)


@config_app.command(name="list")
def config_list():
    """List all configuration values."""
    try:
        # Create table
        table = Table(
            title="Configuration Values",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Key", style="green")
        table.add_column("Value", style="white")

        # Load and display config
        config_service.load_config()
        config = config_service.config
        for key, value in config.model_dump(
            exclude={"dir_configs"},
        ).items():
            table.add_row(key, str(value))

        console.print(table)
        info("Use 'config get <key>' to retrieve specific values")
    except Exception as e:
        error(f"Failed to read configuration: {e}")
        raise typer.Exit(1)


@config_app.command(name="delete")
def config_delete(
    key: str = typer.Argument(..., help="Configuration key"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a configuration value."""
    valid_keys = Configs.model_fields.keys() - {"dir_configs"}
    if key not in valid_keys:
        error(f"Invalid configuration key: {key}")
        raise typer.Exit(1)

    try:
        if not confirm:
            if not typer.confirm(f"Delete configuration key '{key}'?"):
                warning("Cancelled")
                return

        config_service.load_config()
        config = config_service.config

        setattr(config, key, None)
        config_service.save_config()
        success(f"Configuration deleted: {key}")
    except Exception as e:
        error(f"Failed to delete configuration: {e}")
        raise typer.Exit(1)


@config_app.command(name="path")
def config_path():
    """Show configuration file and directory paths."""
    config_service.load_config()
    dir_config = config_service.config.dir_configs

    table = Table(
        title="Configuration Paths", show_header=True, header_style="bold cyan"
    )
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")

    # Placeholder values
    config_file = dir_config.config_file
    config_dir = dir_config.config_dir

    table.add_row("Config File", str(config_file))
    table.add_row("Config Directory", str(config_dir))

    console.print(table)
    info(f"File exists: {config_file.exists()}")
