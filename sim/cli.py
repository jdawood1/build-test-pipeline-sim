import json

import click

from sim.runner import explain_config, run_pipeline, validate_config


@click.group()
def cli() -> None:
    """Build & test pipeline simulator."""


@cli.command()
@click.option("--config", required=True, help="YAML pipeline config")
@click.option("--out", "out_dir", required=True, help="Output directory for artifacts/logs")
@click.option("--dry", is_flag=True, help="Parse + validate only; no work is executed")
def run(config: str, out_dir: str, dry: bool) -> None:
    """Run the pipeline."""
    code = run_pipeline(config, out_dir, dry_run=dry)
    raise SystemExit(code)


@cli.command()
@click.option("--config", required=True, help="YAML pipeline config")
def validate(config: str) -> None:
    """Validate config schema and references."""
    validate_config(config)
    click.echo("OK")


@cli.command()
@click.option("--config", required=True, help="YAML pipeline config")
@click.option("--digests", is_flag=True, help="Include computed module digests in the plan")
def explain(config: str, digests: bool) -> None:
    """Print a concise, human-readable plan of what would run."""
    plan = explain_config(config, include_digests=digests)
    click.echo(json.dumps(plan, indent=2))


if __name__ == "__main__":
    cli()
