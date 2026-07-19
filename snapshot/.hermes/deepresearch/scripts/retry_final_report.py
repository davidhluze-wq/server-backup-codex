#!/usr/bin/env python3
"""Retry only the failed final writer and reviewer for an existing DeepResearch run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_deepresearch import (
    OUTPUT_FILES,
    RUNS,
    FINAL_QUALITY_TIMEOUT,
    build_prompt,
    run_helper,
    run_final_writer_with_retry,
    run_hermes,
    save_role_output,
    update_indexes,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry the final DeepResearch writer without repeating source research")
    parser.add_argument("run_dir", help="Existing directory below ~/.hermes/deepresearch/runs")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout per agent in seconds")
    parser.add_argument("--toolsets", default="web")
    parser.add_argument("--upload", action="store_true", help="Also upload rebuilt artefacts to Google Drive")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if RUNS.resolve() not in run_dir.parents:
        parser.error("run_dir must be inside ~/.hermes/deepresearch/runs")
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file() or not (run_dir / "input.md").is_file():
        parser.error("run_dir is missing run_manifest.json or input.md")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mode = manifest.get("mode", "auto")
    compression = manifest.get("internal_compression", "caveman")
    issues = [issue for issue in manifest.get("known_issues", []) if not any(
        marker in issue for marker in ("final_report", "quality_review", "export_final", "final report unavailable")
    )]
    timings = dict(manifest.get("timings_seconds", {}))
    helpers = dict(manifest.get("helpers", {}))
    agents = dict(manifest.get("agents", {}))

    final, final_attempts = run_final_writer_with_retry(run_dir, mode, compression, args.timeout, args.toolsets)
    timings["final_report"] = final["elapsed_seconds"]
    agents["final_writer"] = final.get("profile")
    if final.get("fallback_used"):
        issues.append(f"final_report used fallback profile {final.get('profile')}")
    if final_attempts > 1:
        issues.append("final_report automatic retry succeeded" if final["returncode"] == 0 else "final_report automatic retry failed")
    if final["returncode"] != 0:
        issues.append(f"final_report return code {final['returncode']}")
    else:
        quality = run_hermes("quality_review", build_prompt("quality_review", run_dir, mode, compression), run_dir, min(args.timeout, FINAL_QUALITY_TIMEOUT), args.toolsets)
        save_role_output(run_dir, "quality_review", quality)
        timings["quality_review"] = quality["elapsed_seconds"]
        agents["quality_reviewer"] = quality.get("profile")
        if quality.get("fallback_used"):
            issues.append(f"quality_review used fallback profile {quality.get('profile')}")
        if quality["returncode"] != 0:
            issues.append(f"quality_review return code {quality['returncode']}")
        export_args = [str(run_dir)] + (["--upload"] if args.upload else [])
        helpers["export_final"] = run_helper("export_final.py", export_args, timeout=300)
        if helpers["export_final"]["returncode"] != 0:
            issues.append("export_final helper failed")

    manifest["agents"] = agents
    manifest["timings_seconds"] = timings
    manifest["helpers"] = helpers
    manifest["known_issues"] = issues
    manifest["status"] = "success" if not [issue for issue in issues if "fallback" not in issue] else "partial"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_indexes(manifest, run_dir)
    print(f"status={manifest['status']}")
    return 0 if manifest["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
