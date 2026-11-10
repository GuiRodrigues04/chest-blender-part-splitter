"""Run the complementary 0.9.9 audit suites serially; preserve logs and source hash."""
import hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SUITES = ["test_release_workflows.py", "test_release_state.py", "test_clearance_profiles.py",
          "test_connector_clearance_slivers.py", "test_material_manual_connectors_bugfix.py",
          "test_plane_limited.py", "test_plane_contact_contours.py"]
OUT = ROOT / "evidence" / "0.9.9"
LOGS = OUT / "complement_logs"
LOGS.mkdir(parents=True, exist_ok=True)

def run(suite):
    started = time.monotonic()
    env = os.environ.copy()
    env["PART_SPLITTER_ROOT"] = str(ROOT)
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--threads", "2",
                           "--python-exit-code", "1", "--python", str(ROOT / "tests" / suite)],
                          cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    raw = proc.stdout.decode("utf-8", "replace")
    (LOGS / (Path(suite).stem + ".log")).write_text(raw, encoding="utf-8")
    summaries = re.findall(r"Ran (\d+) tests? in ([\d.]+)s", raw)
    failures = re.findall(r"failures=(\d+)", raw)
    errors = re.findall(r"errors=(\d+)", raw)
    skipped = re.findall(r"skipped=(\d+)", raw)
    return {"suite": suite, "exit_code": proc.returncode, "passed": proc.returncode == 0 and bool(summaries) and "OK" in raw,
            "tests": int(summaries[-1][0]) if summaries else None,
            "unittest_seconds": float(summaries[-1][1]) if summaries else None,
            "failures": int(failures[-1]) if failures else 0, "errors": int(errors[-1]) if errors else 0,
            "skipped": int(skipped[-1]) if skipped else 0,
            "wall_seconds": round(time.monotonic()-started, 2),
            "fail_lines": re.findall(r"^(?:FAIL|ERROR): .+$", raw, re.M)}

if __name__ == "__main__":
    results = [run(suite) for suite in SUITES]
    src_files = sorted((ROOT / "src").rglob("*.py")) + [ROOT / "__init__.py", ROOT / "blender_manifest.toml"]
    digest = hashlib.sha256()
    for path in src_files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    report = {"phase": "complement", "source": str(ROOT), "source_sha256": digest.hexdigest(),
              "blender": BLENDER, "max_parallel_blender_processes": 1, "suites": results,
              "totals": {"suites": len(results), "passed": sum(r["passed"] for r in results),
                         "failed": sum(not r["passed"] for r in results),
                         "tests": sum(r["tests"] or 0 for r in results),
                         "failures": sum(r["failures"] for r in results),
                         "errors": sum(r["errors"] for r in results), "skipped": sum(r["skipped"] for r in results)}}
    (OUT / "audit_complement.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(bool(report["totals"]["failed"]))
