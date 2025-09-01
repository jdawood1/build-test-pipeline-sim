# Build & Test Pipeline Simulator

[![CI](https://github.com/jdawood1/build-test-pipeline-sim/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jdawood1/build-test-pipeline-sim/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Config‑driven build & test pipeline simulator.  
Takes a YAML config of modules + tests, simulates builds and test runs with structured telemetry, and writes artifacts + reports.  
Useful as a lightweight demo of CI/CD pipelines.

---

## Run in 30 seconds

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt

# run pipeline
python -m sim.cli run --config sample/pipeline.yml --out build/
```

**Outputs**
- `build/telemetry.csv` (CSV log of build/test stages)
- `build/results.json` (artifacts + test results summary)

---

## Requirements
- Python 3.11+
- See `requirements.txt` for dependencies:
  - click, pyyaml, pytest

---

## Sample Config (`sample/pipeline.yml`)

```yaml
modules:
  - name: core
    payload: "src@abc123"
    seconds: 0.1
  - name: utils
    payload: "src@def456"
    seconds: 0.1

tests:
  - name: unit-core
    module: core
    seconds: 0.05
    expected_digest: "<sha256 string>"
  - name: unit-utils
    module: utils
    seconds: 0.05
    expected_digest: "WRONG_DIGEST"
```

---

## Repo Structure
```
build-test-pipeline-sim/
  sim/
    __init__.py
    cli.py        # CLI (Click)
    runner.py     # core logic
  sample/
    pipeline.yml  # example config
  tests/
    test_sim.py   # e2e pytest
  pytest.ini
  requirements.txt
  README.md
```

---

## Roadmap
- [ ] Add richer validation errors (duplicate modules, bad digests)
- [ ] Support multiple pipelines per config
- [ ] Export additional formats (NDJSON, Parquet)
- [ ] Add optional latency simulation per test

---

## License
MIT © 2025 John Dawood
