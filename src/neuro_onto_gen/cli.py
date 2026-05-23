"""Command line interface placeholder for future phases."""

import typer

app = typer.Typer(help="NeuroOntoGen command line interface.")


@app.callback()
def main() -> None:
    """NeuroOntoGen CLI."""
