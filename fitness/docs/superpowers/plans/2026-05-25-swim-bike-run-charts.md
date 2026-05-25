# Swim Bike Run Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the Strava report from run-only output to swim, human-powered bike, and run charts in kilometers.

**Architecture:** Keep the single `strava_runs.py` script, but replace run-specific filtering and reporting helpers with sport-group helpers. Fetch activities once, normalize matching swim/bike/run activities into a shared row shape, write one combined CSV, and render one chart per sport group.

**Tech Stack:** Python 3.10+, `requests`, `matplotlib`, standard-library `csv`, `json`, `http.server`, `webbrowser`, and `unittest`.

---

## File Structure

- Modify `strava_runs.py`: add sport group constants, grouping helpers, kilometer-first normalization, three-chart report output, and updated CLI defaults.
- Modify `tests/test_strava_runs.py`: replace run-only expectations with swim/bike/run behavior tests while preserving auth, pagination, and output coverage.

### Task 1: Sport Grouping

**Files:**
- Modify: `tests/test_strava_runs.py`
- Modify: `strava_runs.py`

- [ ] **Step 1: Write failing tests**

Add tests expecting:

```python
self.assertEqual(strava_runs.classify_activity({"sport_type": "Swim"}), "swim")
self.assertEqual(strava_runs.classify_activity({"sport_type": "Ride"}), "bike")
self.assertEqual(strava_runs.classify_activity({"sport_type": "GravelRide"}), "bike")
self.assertEqual(strava_runs.classify_activity({"sport_type": "MountainBikeRide"}), "bike")
self.assertEqual(strava_runs.classify_activity({"sport_type": "VirtualRide"}), "bike")
self.assertEqual(strava_runs.classify_activity({"sport_type": "Run"}), "run")
self.assertEqual(strava_runs.classify_activity({"sport_type": "TrailRun"}), "run")
self.assertEqual(strava_runs.classify_activity({"sport_type": "VirtualRun"}), "run")
self.assertIsNone(strava_runs.classify_activity({"sport_type": "EBikeRide"}))
self.assertIsNone(strava_runs.classify_activity({"sport_type": "EMountainBikeRide"}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because `classify_activity` does not exist.

- [ ] **Step 3: Implement grouping**

Add `SPORT_GROUPS`, `SPORT_TITLES`, `DEFAULT_PLOT_FILES`, `activity_sport_type`, and `classify_activity`.

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS for the new grouping tests.

### Task 2: Kilometer Normalization And CSV

**Files:**
- Modify: `tests/test_strava_runs.py`
- Modify: `strava_runs.py`

- [ ] **Step 1: Write failing tests**

Add tests expecting `normalize_activity(activity, "run")` to return `sport`, `date`, `name`, `distance_kilometers`, and `id`; `build_sport_activities` to include swim/bike/run and exclude e-bike; and `write_activities_csv` to write `sport,date,name,distance_kilometers,id`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because generalized helpers do not exist or still use run-only names.

- [ ] **Step 3: Implement normalization and CSV**

Add `normalize_activity`, `build_sport_activities`, `sort_activities_by_distance`, `prepare_plot_rows` using `distance_kilometers`, and `write_activities_csv`. Keep compatibility wrappers only where tests or CLI still need them.

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS for normalization and CSV tests.

### Task 3: Three Chart Report Output

**Files:**
- Modify: `tests/test_strava_runs.py`
- Modify: `strava_runs.py`

- [ ] **Step 1: Write failing tests**

Add tests expecting `plot_output_paths(None)` to return the three default files and `write_sport_charts` to create separate swim, bike, and run PNGs from grouped activities.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because chart path and multi-chart helpers do not exist.

- [ ] **Step 3: Implement chart helpers and report wiring**

Rename chart titles to use each sport title, add `plot_output_paths`, `write_sport_charts`, update `run_report`, default CSV name, parser help text, and default unit to kilometers. Keep `--output-plot` as an optional directory or filename prefix control.

- [ ] **Step 4: Run full tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

### Task 4: Verification

**Files:**
- Read: `strava_runs.py`
- Read: `tests/test_strava_runs.py`

- [ ] **Step 1: Install dependencies**

Run: `python -m pip install -r requirements.txt`

Expected: dependencies installed or already satisfied.

- [ ] **Step 2: Run tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

- [ ] **Step 3: Run help**

Run: `python strava_runs.py --help`

Expected: help mentions CSV, chart output directory/prefix, token file, port, per-page, and unit.
