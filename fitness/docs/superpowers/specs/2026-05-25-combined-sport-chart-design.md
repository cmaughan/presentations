# Combined Sport Chart Design

## Goal

Fix sport chart legends and add a combined swim/bike/run distance chart.

## Scope

- Single-sport charts must label activity points by sport: `Swims`, `Rides`, or `Runs`.
- Keep each single-sport chart's yearly average line.
- Add `combined_distance_over_years.png`.
- The combined chart plots swim, bike, and run activities on the same axes in kilometers.
- The combined chart legend shows `Swims`, `Rides`, and `Runs`.
- Keep the existing CSV and three single-sport charts.

## Architecture

Add sport-specific plural labels and colors. Update the existing plotting helper to accept an activity label instead of hardcoding `Runs`. Add a combined plotting helper that groups activities by sport and plots each group on the same axes. Extend chart path generation and report output so the combined chart is written with the other generated files.

## Testing

Tests will cover:

- Single-sport label selection.
- Combined chart output path.
- Combined chart file creation.
- Report output writing the combined chart alongside the three single-sport charts.
