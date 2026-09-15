import typer
from lean import __version__
from . import config

app = typer.Typer(name = "lean", 
                  help="Lean CLI", 
                  version=__version__)

app.command()
def status() -> None:
    "Display status of lean agent (version and config state for now)"
    typer.echo(f"lean version: {__version__}")

app.command()
def init(
        provider: str | None = typer.Option(None),
        model: str | None = typer.Option(None),
        autonomy: AutonomyMode | None = typer.Option(None),
) -> None:
    # build config with overrides
    cfg = config.default_config()

    if provider is not None:
        cfg.provider = provider

    if model is not None:
        cfg.model = model

    if autonomy is not None:
        cfg.autonomy = autonomy

    config.save_config(cfg)

    print("lean init complete")

def main() -> None:
    app()

if __name__ == "__main__":
    main()
