# Combined Chart Multi Axis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the combined chart use separate swim, bike, and run Y axes so each sport scales locally.

**Architecture:** Keep the combined plot helper in `strava_runs.py`, add a small axis-spec helper to make the layout testable, and update plotting to create one matplotlib axis per sport. The X axis remains shared and all distances remain kilometers.

**Tech Stack:** Python 3.10+, `matplotlib`, and `unittest`.

---

## File Structure

- Modify `strava_runs.py`: add `combined_axis_specs` and update `plot_combined_distance_over_time`.
- Modify `tests/test_strava_runs.py`: add tests for axis layout and keep combined chart output coverage.

### Task 1: Axis Layout Contract

- [ ] Write a failing test asserting swim uses the left axis, bike uses the right axis, and run uses an outward-offset right axis.
- [ ] Run the targeted test and verify it fails because `combined_axis_specs` does not exist.
- [ ] Implement `combined_axis_specs`.
- [ ] Run the targeted test and verify it passes.

### Task 2: Plot Implementation

- [ ] Update `plot_combined_distance_over_time` to create the axes described by `combined_axis_specs`.
- [ ] Run the combined chart file test and verify it passes.
- [ ] Run the full test suite and verify it passes.

### Task 3: Regenerate Output

- [ ] Run `python strava_runs.py --help`.
- [ ] Run `python strava_runs.py`.
- [ ] Confirm `combined_distance_over_years.png` is regenerated.
