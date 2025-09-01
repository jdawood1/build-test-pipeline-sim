import click
from .runner import run_pipeline


@click.group()
def cli():
    pass


@cli.command()
@click.option("--config", required=True, help="YAML pipeline config")
@click.option(
    "--out", "out_dir", required=True, help="Output directory for artifacts/logs"
)
def run(config, out_dir):
    code = run_pipeline(config, out_dir)
    raise SystemExit(code)


if __name__ == "__main__":
    cli()
