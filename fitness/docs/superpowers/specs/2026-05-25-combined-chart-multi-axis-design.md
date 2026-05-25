# Combined Chart Multi Axis Design

## Goal

Update the combined swim, bike, and run chart so each sport has its own Y axis and scales against its own distance range.

## Scope

- Keep `combined_distance_over_years.png` as the output file.
- Plot swims, rides, and runs on the same time-based X axis.
- Use three Y axes:
  - Swim on the left.
  - Bike on the right.
  - Run on a second right axis offset outward.
- Color each axis label and tick marks to match that sport's points.
- Keep distances in kilometers.
- Keep the legend entries `Swims`, `Rides`, and `Runs`.
- Leave the three single-sport charts unchanged.

## Testing

Tests will cover the axis layout metadata, combined chart file creation, and report generation continuing to write the combined chart.
