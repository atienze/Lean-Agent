import typer
from lean import __version__

app = typer.Typer(name = "lean", 
                  help="Lean CLI", 
                  version=__version__)

app.command()
def status() -> None:
    "Display status of lean agent (version and config state for now)"
    typer.echo(f"lean version: {__version__}")

def main() -> None:
    app()

if __name__ == "__main__":
    main()
