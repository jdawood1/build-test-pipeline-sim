from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import yaml


# ========= Exceptions (messages live in the classes; no inline strings at raise sites) =========
class ConfigError(Exception):
    """Base class for config-related errors."""


class NotMappingError(ConfigError):
    def __init__(self) -> None:
        super().__init__("Top-level YAML must be a mapping.")


class EmptyModuleNameError(ConfigError):
    def __init__(self) -> None:
        super().__init__("All modules must have a non-empty 'name'.")


class DuplicateModuleNamesError(ConfigError):
    def __init__(self, names: list[str]) -> None:
        super().__init__(f"Duplicate module names: {sorted(names)}")


class MissingPayloadError(ConfigError):
    def __init__(self, module_name: str | None) -> None:
        super().__init__(f"Module {module_name!r} missing 'payload'.")


class NegativeModuleSecondsError(ConfigError):
    def __init__(self, module_name: str | None) -> None:
        super().__init__(f"Module {module_name!r} has negative 'seconds'.")


class EmptyTestNameError(ConfigError):
    def __init__(self) -> None:
        super().__init__("All tests must have a non-empty 'name'.")


class UnknownModuleRefError(ConfigError):
    def __init__(self, test_name: str, target: str) -> None:
        super().__init__(f"Test {test_name!r} references unknown module {target!r}.")


class NegativeTestSecondsError(ConfigError):
    def __init__(self, test_name: str) -> None:
        super().__init__(f"Test {test_name!r} has negative 'seconds'.")


# =================================== Core helpers ===================================
def _digest(name: str, payload: str) -> str:
    """Deterministic artifact digest for a module (no sleep)."""
    return hashlib.sha256((name + payload).encode()).hexdigest()


def _do_work(name: str, payload: str, seconds: float) -> tuple[str, float]:
    """
    Simulate unit of work by sleeping a capped duration and returning a digest + duration.
    Digest is deterministic for (name, payload).
    """
    t0 = time.time()
    time.sleep(max(0.0, min(seconds, 2.0)))  # cap to keep CI fast
    digest = _digest(name, payload)
    return digest, time.time() - t0


def _load_config(config_path: str) -> dict[str, Any]:
    raw = Path(config_path).read_text(encoding="utf-8")
    cfg: Any = yaml.safe_load(raw) or {}
    if not isinstance(cfg, dict):
        raise NotMappingError()
    return dict(cfg)


def _validate_modules(mods: list[dict[str, Any]]) -> None:
    names = [str(m.get("name", "")).strip() for m in mods]
    if any(not n for n in names):
        raise EmptyModuleNameError()

    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise DuplicateModuleNamesError(dupes)

    for m in mods:
        if "payload" not in m:
            raise MissingPayloadError(m.get("name"))
        if "seconds" in m and float(m["seconds"]) < 0:
            raise NegativeModuleSecondsError(m.get("name"))


def _validate_tests(tests: list[dict[str, Any]], mod_names: set[str]) -> None:
    for t in tests:
        name = str(t.get("name", "")).strip()
        if not name:
            raise EmptyTestNameError()

        target = str(t.get("module", "")).strip()
        if target not in mod_names:
            raise UnknownModuleRefError(name, target)

        if "seconds" in t and float(t["seconds"]) < 0:
            raise NegativeTestSecondsError(name)


def validate_config(config_path: str) -> None:
    cfg = _load_config(config_path)
    modules = list(cfg.get("modules", []) or [])
    tests = list(cfg.get("tests", []) or [])
    _validate_modules(modules)
    _validate_tests(tests, {str(m.get("name")) for m in modules})


def explain_config(config_path: str, *, include_digests: bool = False) -> dict[str, Any]:
    """
    Return a concise plan of what would run. If include_digests=True,
    compute and include each module's expected digest (no sleeping).
    """
    cfg = _load_config(config_path)
    modules: list[dict[str, Any]] = list(cfg.get("modules", []) or [])
    tests: list[dict[str, Any]] = list(cfg.get("tests", []) or [])

    mod_list: list[dict[str, Any]] = []
    for m in modules:
        name = str(m.get("name"))
        payload = str(m.get("payload"))
        seconds = float(m.get("seconds", 0.2))
        item: dict[str, Any] = {"name": name, "payload": payload, "seconds": seconds}
        if include_digests:
            item["expected_digest"] = _digest(name, payload)
        mod_list.append(item)

    test_list: list[dict[str, Any]] = [
        {
            "name": t.get("name"),
            "module": t.get("module"),
            "seconds": float(t.get("seconds", 0.1)),
            "expects_digest": t.get("expected_digest") is not None,
        }
        for t in tests
    ]

    return {"modules": mod_list, "tests": test_list}


# =================================== Output helpers ===================================
def _try_parquet_exports(
    out: Path, telemetry_rows: list[dict[str, Any]], results_obj: dict[str, Any]
) -> None:
    """Best-effort Parquet exports using pandas+pyarrow if available."""
    try:
        import pandas as pd  # removed: type: ignore

        if telemetry_rows:
            pd.DataFrame(telemetry_rows).to_parquet(out / "telemetry.parquet", index=False)

        tests_df = pd.DataFrame(results_obj.get("tests", []))
        tests_df.to_parquet(out / "results.parquet", index=False)
    except Exception as e:  # pragma: no cover
        (out / "parquet_export_failed.txt").write_text(
            f"Parquet export skipped or failed: {type(e).__name__}: {e}\n"
            "Install pandas+pyarrow (see requirements-dev.txt) to enable.",
            encoding="utf-8",
        )


def _write_html_report(
    out: Path, results_obj: dict[str, Any], telemetry_rows: list[dict[str, Any]]
) -> None:
    from html import escape

    tests: list[dict[str, Any]] = results_obj.get("tests", [])
    test_rows = "".join(
        (
            f"<tr>"
            f"<td>{escape(str(t.get('name', '')))}</td>"
            f"<td>{escape(str(t.get('module', '')))}</td>"
            f"<td class=\"{'ok' if t.get('ok') else 'fail'}\">"
            f"{'PASS' if t.get('ok') else 'FAIL'}</td>"
            f"<td>{t.get('duration_s')}</td>"
            f"</tr>"
        )
        for t in tests
    )

    tele_rows = "".join(
        (
            f"<tr>"
            f"<td>{escape(str(r.get('stage', '')))}</td>"
            f"<td>{escape(str(r.get('name', '')))}</td>"
            f"<td>{r.get('duration_s')}</td>"
            f"<td><pre style=\"margin:0\">{escape(json.dumps(r.get('meta')))}</pre></td>"
            f"</tr>"
        )
        for r in telemetry_rows
    )

    passed = sum(1 for t in tests if t.get("ok"))
    failed = sum(1 for t in tests if not t.get("ok"))
    artifacts_cnt = len(results_obj.get("artifacts", {}))

    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Pipeline Report</title>
<style>
  body {{
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI,
      Roboto, Arial;
    margin: 24px;
  }}
  header {{ margin-bottom: 20px; }}
  .summary {{ display: flex; gap: 16px; margin: 12px 0; }}
  .chip {{ padding: 6px 10px; border-radius: 999px; background:#f2f2f2; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 14px; }}
  th {{ background: #f8fafc; text-align: left; }}
  .ok {{ color: #065f46; font-weight: 600; }}
  .fail {{ color: #991b1b; font-weight: 600; }}
  footer {{ color: #6b7280; font-size: 12px; }}
</style>
<header>
  <h1>Build & Test Pipeline Report</h1>
  <div class="summary">
    <div class="chip">Artifacts: <strong>{artifacts_cnt}</strong></div>
    <div class="chip">Passed: <strong>{passed}</strong></div>
    <div class="chip">Failed: <strong>{failed}</strong></div>
  </div>
</header>

<section>
  <h2>Test Results</h2>
  <table>
    <thead><tr><th>Name</th><th>Module</th><th>OK</th><th>Duration (s)</th></tr></thead>
    <tbody>
      {test_rows}
    </tbody>
  </table>
</section>

<section>
  <h2>Telemetry</h2>
  <table>
    <thead><tr><th>Stage</th><th>Name</th><th>Duration (s)</th><th>Meta</th></tr></thead>
    <tbody>
      {tele_rows}
    </tbody>
  </table>
</section>

<footer>
  Generated by build-test-pipeline-sim
</footer>
</html>
"""
    (out / "report.html").write_text(html, encoding="utf-8")


# =================================== Entry point ===================================
def run_pipeline(config_path: str, out_dir: str, *, dry_run: bool = False) -> int:
    """
    Run a config-driven build+test pipeline.
    Returns exit code: 0 on success, 1 if any test fails, 2 for config errors.
    """
    try:
        validate_config(config_path)
        cfg = _load_config(config_path)
    except ConfigError as e:
        print(json.dumps({"error": "config_error", "message": str(e)}))
        return 2

    modules: list[dict[str, Any]] = list(cfg.get("modules", []) or [])
    tests: list[dict[str, Any]] = list(cfg.get("tests", []) or [])

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    telemetry_csv = out / "telemetry.csv"
    ndjson_path = out / "events.ndjson"
    artifacts: dict[str, str] = {}
    failures = 0
    results: list[dict[str, Any]] = []
    telemetry_rows: list[dict[str, Any]] = []

    # Define once; assign in branches (avoids mypy redefinition)
    results_obj: dict[str, Any]

    # Dry-run: write headers + empty results
    if dry_run:
        with telemetry_csv.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["stage", "name", "duration_s", "meta"])
        ndjson_path.write_text("", encoding="utf-8")
        results_obj = {"dry_run": True, "artifacts": {}, "tests": [], "failures": 0}
        (out / "results.json").write_text(json.dumps(results_obj, indent=2), encoding="utf-8")
        _write_html_report(out, results_obj, telemetry_rows)
        return 0

    # Normal run
    with (
        telemetry_csv.open("w", newline="", encoding="utf-8") as f_csv,
        ndjson_path.open("w", encoding="utf-8") as f_nd,
    ):
        writer = csv.writer(f_csv)
        writer.writerow(["stage", "name", "duration_s", "meta"])

        # Build
        for m in modules:
            name = str(m["name"])
            payload = str(m.get("payload", ""))
            seconds = float(m.get("seconds", 0.2))
            digest, dur = _do_work(name, payload, seconds)
            artifacts[name] = digest
            row = {"stage": "build", "name": name, "duration_s": round(dur, 4), "meta": digest}
            telemetry_rows.append(row)
            writer.writerow(["build", name, f"{dur:.4f}", digest])
            f_nd.write(json.dumps(row, ensure_ascii=False) + "\n")

        # Test
        for t in tests:
            t_name = str(t["name"])
            target = str(t.get("module", ""))
            seconds = float(t.get("seconds", 0.1))
            expected = t.get("expected_digest")

            _, tdur = _do_work(t_name, target, seconds)
            ok = (expected is None) or (expected == artifacts.get(target))

            t_row = {"name": t_name, "module": target, "ok": ok, "duration_s": round(tdur, 4)}
            results.append(t_row)
            meta = {"ok": ok}
            tele = {"stage": "test", "name": t_name, "duration_s": round(tdur, 4), "meta": meta}
            telemetry_rows.append(tele)

            writer.writerow(["test", t_name, f"{tdur:.4f}", json.dumps(meta)])
            f_nd.write(json.dumps(tele, ensure_ascii=False) + "\n")

            if not ok:
                failures += 1

    # Single (unannotated) assignment — no redefinition
    results_obj = {"failures": failures, "tests": results, "artifacts": artifacts}
    (out / "results.json").write_text(json.dumps(results_obj, indent=2), encoding="utf-8")

    _try_parquet_exports(out, telemetry_rows, results_obj)
    _write_html_report(out, results_obj, telemetry_rows)

    return 1 if failures else 0
