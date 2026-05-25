# Swim Bike Run Charts Design

## Goal

Extend the Strava report script so it produces separate kilometer-based distance charts for swims, human-powered bike rides, and runs.

## Scope

- Keep the existing Strava OAuth flow, token storage, and activity pagination.
- Group activities into three sport categories:
  - Swim: `Swim`
  - Bike: `Ride`, `GravelRide`, `MountainBikeRide`, `VirtualRide`
  - Run: `Run`, `TrailRun`, `VirtualRun`
- Exclude e-bike activity types from the bike chart.
- Use kilometers as the default distance unit for charts and CSV output.
- Produce three charts:
  - `swim_distance_over_years.png`
  - `bike_distance_over_years.png`
  - `run_distance_over_years.png`
- Produce a combined CSV containing `sport`, `date`, `name`, `distance_kilometers`, and `id`.

## Architecture

Generalize the current run-specific helpers into activity-group helpers while preserving the single-file script. Filtering will classify each Strava activity by `sport_type` first and fallback to deprecated `type`. Report generation will fetch all activities once, group and normalize them, write one combined distance-sorted CSV, and create one chart for each sport group that has data.

## Error Handling

- Missing credentials, OAuth failures, token refresh failures, and API failures remain unchanged.
- If no swim, bike, or run activities are found, the script exits with a clear message.
- If a specific sport has no activities, the script skips that chart and prints that no chart was written for that sport.

## Testing

Tests will cover:

- Swim, bike, and run grouping.
- Exclusion of `EBikeRide` and `EMountainBikeRide`.
- Kilometer conversion as the default normalized distance.
- Combined CSV output with a `sport` column.
- Plot output path generation for all three sport groups.
- Report behavior writing three charts from one fetched activity set.
