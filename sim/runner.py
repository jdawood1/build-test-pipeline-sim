from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


def _do_work(name: str, payload: str, seconds: float) -> Tuple[str, float]:
    """
    Simulate unit of work by sleeping a capped duration and returning a digest + duration.
    Digest is deterministic for (name, payload).
    """
    t0 = time.time()
    time.sleep(max(0.0, min(seconds, 2.0)))  # cap to keep CI fast
    digest = hashlib.sha256((name + payload).encode()).hexdigest()
    return digest, time.time() - t0


def run_pipeline(config_path: str, out_dir: str) -> int:
    """
    Run a config-driven build+test pipeline.

    YAML schema (minimal):
      modules:
        - name: core
          payload: "src@abc123"
          seconds: 0.2
      tests:
        - name: unit-core
          module: core
          seconds: 0.1
          expected_digest: "<sha256 string>"   # optional; if present, must match

    Returns process exit code: 0 on success, 1 if any test fails.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cfg_raw = Path(config_path).read_text(encoding="utf-8")
    cfg = yaml.safe_load(cfg_raw) or {}
    modules = list(cfg.get("modules", []) or [])
    tests = list(cfg.get("tests", []) or [])

    telemetry_csv = out / "telemetry.csv"
    with telemetry_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["stage", "name", "duration_s", "meta"])

        # Build phase
        artifacts: Dict[str, Any] = {}
        for m in modules:
            name = str(m.get("name", "unnamed"))
            payload = str(m.get("payload", ""))
            seconds = float(m.get("seconds", 0.2))

            digest, dur = _do_work(name, payload, seconds)
            artifacts[name] = digest
            writer.writerow(["build", name, f"{dur:.4f}", digest])

        # Test phase
        failures = 0
        results = []
        for t in tests:
            t_name = str(t.get("name", "unnamed-test"))
            target = str(t.get("module", ""))
            seconds = float(t.get("seconds", 0.1))
            expected = t.get("expected_digest")

            _, tdur = _do_work(t_name, target, seconds)
            ok = (expected is None) or (expected == artifacts.get(target))

            results.append(
                {
                    "name": t_name,
                    "module": target,
                    "ok": ok,
                    "duration_s": round(tdur, 4),
                }
            )
            writer.writerow(["test", t_name, f"{tdur:.4f}", json.dumps({"ok": ok})])
            if not ok:
                failures += 1

    (out / "results.json").write_text(
        json.dumps(
            {"failures": failures, "tests": results, "artifacts": artifacts},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return 1 if failures else 0
