from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sim.runner import explain_config, run_pipeline, validate_config

SAMPLE = """\
modules:
  - name: core
    payload: "src@abc123"
    seconds: 0.0
tests:
  - name: unit-core
    module: core
    seconds: 0.0
    expected_digest: "4fc41e5669eafc53d839cd3f1f8c5fa4b5406f85ea35f94da8a4d9151e7523de"
"""

SAMPLE_FAIL = """\
modules:
  - name: core
    payload: "src@abc123"
    seconds: 0.0
tests:
  - name: unit-core
    module: core
    seconds: 0.0
    expected_digest: "WRONG"
"""


def _write(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_validate_and_explain():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = _write(tmp, "ok.yml", SAMPLE)
        validate_config(str(cfg))  # no exception
        plan = explain_config(str(cfg))
        assert plan["modules"][0]["name"] == "core"
        assert plan["tests"][0]["expects_digest"] is True


def test_run_success_and_outputs():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = _write(tmp, "ok.yml", SAMPLE)
        out = tmp / "build"
        code = run_pipeline(str(cfg), str(out))
        assert code == 0
        tel = (out / "telemetry.csv").read_text().splitlines()
        assert tel[0].startswith("stage,name,duration_s,meta")
        res = json.loads((out / "results.json").read_text())
        assert res["failures"] == 0
        assert "core" in res["artifacts"]


def test_run_failure_exit_code_one():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = _write(tmp, "bad.yml", SAMPLE_FAIL)
        out = tmp / "build"
        code = run_pipeline(str(cfg), str(out))
        assert code == 1
