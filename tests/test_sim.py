from pathlib import Path
import yaml
from sim.runner import run_pipeline
import hashlib


def digest(name: str, payload: str) -> str:
    return hashlib.sha256((name + payload).encode()).hexdigest()


def test_pipeline_end_to_end(tmp_path: Path):
    cfg = {
        "modules": [{"name": "core", "payload": "src@abc123", "seconds": 0.01}],
        "tests": [
            {
                "name": "unit-core",
                "module": "core",
                "seconds": 0.01,
                "expected_digest": digest("core", "src@abc123"),
            }
        ],
    }
    cfg_path = tmp_path / "pipeline.yml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    code = run_pipeline(str(cfg_path), str(tmp_path))
    assert code == 0
    assert (tmp_path / "telemetry.csv").exists()
    assert (tmp_path / "results.json").exists()
