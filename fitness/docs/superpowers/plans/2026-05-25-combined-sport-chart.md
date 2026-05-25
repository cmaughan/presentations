# Combined Sport Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix chart legends so they match each sport and add a combined swim/bike/run chart.

**Architecture:** Keep chart generation in `strava_runs.py`. Add sport label/color constants, pass labels into the single-sport plot helper, add a combined chart helper, and include the combined output in path generation and report output.

**Tech Stack:** Python 3.10+, `matplotlib`, and `unittest`.

---

## File Structure

- Modify `strava_runs.py`: chart labels, combined output file, combined plot helper, report output.
- Modify `tests/test_strava_runs.py`: tests for labels, paths, combined file creation, and report output.
- Modify `.gitignore`: ignore `combined_distance_over_years.png`.

### Task 1: Labels And Paths

- [ ] Write failing tests for `activity_label_for_sport("swim") == "Swims"` and for `plot_output_paths(None)["combined"] == Path("combined_distance_over_years.png")`.
- [ ] Run `python -m unittest tests.test_strava_runs -v` and verify failure.
- [ ] Add `SPORT_LABELS`, `SPORT_COLORS`, and a combined default plot path.
- [ ] Run tests and verify pass.

### Task 2: Combined Chart

- [ ] Write failing test for `plot_combined_distance_over_time` creating a PNG from swim, bike, and run rows.
- [ ] Run targeted test and verify failure.
- [ ] Implement `plot_combined_distance_over_time`.
- [ ] Run targeted test and verify pass.

### Task 3: Report Wiring

- [ ] Extend report test to require `combined_distance_over_years.png`.
- [ ] Run targeted test and verify failure.
- [ ] Update `write_sport_charts`, `run_report`, and `.gitignore`.
- [ ] Run full tests and verify pass.

### Task 4: Final Verification

- [ ] Run `python -m pip install -r requirements.txt`.
- [ ] Run `python -m unittest tests.test_strava_runs -v`.
- [ ] Run `python strava_runs.py --help`.
- [ ] Run `python strava_runs.py` to regenerate all charts.
