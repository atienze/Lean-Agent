import typer
from pydantic import ValidationError

from . import __version__
from .config import AutonomyMode, init_project


app = typer.Typer(name = "lean", 
                  help="Lean CLI")

@app.command()
def status() -> None:
    "Display status of lean agent (version and config state for now)"
    typer.echo(f"lean version: {__version__}")

"""
calls init_project from config.py which merges the config files 
and writes to file from path config_path.
"""
@app.command()
def init(
        provider: str | None = typer.Option(None),
        model: str | None = typer.Option(None),
        autonomy: AutonomyMode | None = typer.Option(None),
) -> None:
    # build config with overrides
    overrides = {
        "provider": provider,
        "model": model,
        "autonomy": autonomy,
    }

    try:
        init_project(overrides=overrides)
    except (OSError, ValidationError) as exc:
        typer.secho(f"Error: unable to initialize project: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    typer.echo("lean init complete")

def main() -> None:
    app()

if __name__ == "__main__":
    main()
