#!/usr/bin/env python3
"""Copy the latest Strava chart PNGs into this deck."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


CHART_FILES = (
    "swim_distance_over_years.png",
    "bike_distance_over_years.png",
    "run_distance_over_years.png",
    "combined_distance_over_years.png",
)


def copy_charts(source_dir: Path, target_dir: Path) -> list[Path]:
    copied = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in CHART_FILES:
        source = source_dir / filename
        if not source.exists():
            raise FileNotFoundError(f"Missing chart: {source}")
        target = target_dir / filename
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update fitness deck chart images.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("D:/dev/strava"),
        help="Directory containing generated Strava chart PNGs.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).resolve().parent / "screenshots",
        help="Deck screenshots directory to update.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    copied = copy_charts(args.source, args.target)
    for path in copied:
        print(f"updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
