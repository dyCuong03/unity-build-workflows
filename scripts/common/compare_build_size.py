#!/usr/bin/env python3
"""
compare_build_size.py
Compare current build size against a stored baseline.
Outputs delta and percentage change. Saves new baseline if none exists.
"""

import argparse
import json
import os
import sys
from pathlib import Path


BASELINE_DIR = Path(".build-size-baselines")
ALERT_THRESHOLD_PCT = 20.0  # Warn if build grows by more than 20%


def get_dir_size_bytes(path: Path) -> int:
    """Recursively sum file sizes in a directory."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def human_bytes(size: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} TB"


def load_baseline(platform: str) -> dict | None:
    """Load baseline for a platform."""
    baseline_file = BASELINE_DIR / f"{platform.lower()}.json"
    if baseline_file.is_file():
        try:
            with open(baseline_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_baseline(platform: str, version: str, size_bytes: int) -> None:
    """Save current build as new baseline."""
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_file = BASELINE_DIR / f"{platform.lower()}.json"
    data = {
        "platform": platform,
        "version": version,
        "size_bytes": size_bytes,
        "size_human": human_bytes(size_bytes),
    }
    with open(baseline_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[compare_build_size] Saved new baseline: {human_bytes(size_bytes)} for {platform}")


def write_github_step_summary(report: dict) -> None:
    """Append size comparison to GitHub Step Summary."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not summary_file:
        return
    platform = report["platform"]
    current = report["current_size_human"]
    baseline = report.get("baseline_size_human", "N/A")
    delta_human = report.get("delta_human", "N/A")
    delta_pct = report.get("delta_pct")
    alert = report.get("alert", False)

    icon = "🚨" if alert else ("📉" if (delta_pct or 0) < 0 else "📦")

    lines = [
        f"\n### {icon} Build Size — {platform}\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Current | {current} |",
        f"| Baseline | {baseline} |",
    ]
    if delta_human != "N/A":
        lines.append(f"| Delta | {delta_human} ({delta_pct:+.1f}%) |")
    if alert:
        lines.append(f"\n> ⚠️ Build size increased by {delta_pct:.1f}% — exceeds {ALERT_THRESHOLD_PCT}% threshold\n")

    with open(summary_file, "a") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Unity build size against baseline")
    parser.add_argument("--build-path", required=True, help="Path to build output directory")
    parser.add_argument("--platform", required=True, help="Target platform")
    parser.add_argument("--version", required=True, help="Current build version")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Always update baseline after comparison",
    )
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=ALERT_THRESHOLD_PCT,
        help=f"Percent growth to trigger a warning (default: {ALERT_THRESHOLD_PCT})",
    )
    args = parser.parse_args()

    build_path = Path(args.build_path)
    if not build_path.exists():
        print(f"ERROR: Build path does not exist: {build_path}", file=sys.stderr)
        sys.exit(1)

    current_size = get_dir_size_bytes(build_path)
    baseline = load_baseline(args.platform)

    report: dict = {
        "platform": args.platform,
        "version": args.version,
        "current_size_bytes": current_size,
        "current_size_human": human_bytes(current_size),
    }

    if baseline:
        baseline_size = baseline["size_bytes"]
        delta = current_size - baseline_size
        delta_pct = (delta / baseline_size * 100) if baseline_size > 0 else 0.0
        alert = delta_pct > args.alert_threshold

        report.update(
            {
                "baseline_size_bytes": baseline_size,
                "baseline_size_human": human_bytes(baseline_size),
                "baseline_version": baseline.get("version", "unknown"),
                "delta_bytes": delta,
                "delta_human": human_bytes(abs(delta)),
                "delta_pct": delta_pct,
                "alert": alert,
            }
        )

        sign = "+" if delta >= 0 else "-"
        print(
            f"[compare_build_size] {args.platform}: "
            f"{human_bytes(current_size)} vs baseline {human_bytes(baseline_size)} "
            f"({sign}{abs(delta_pct):.1f}%)"
        )

        if alert:
            print(
                f"WARNING: Build size grew by {delta_pct:.1f}% "
                f"(threshold: {args.alert_threshold}%)",
                file=sys.stderr,
            )

        # Update baseline if growth is not alarming, or forced
        if not alert or args.update_baseline:
            save_baseline(args.platform, args.version, current_size)
    else:
        print(
            f"[compare_build_size] No baseline found for {args.platform}. "
            f"Current size: {human_bytes(current_size)}. Saving as baseline."
        )
        save_baseline(args.platform, args.version, current_size)

    write_github_step_summary(report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
