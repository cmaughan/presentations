# Combined Chart Wide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make only the combined chart twice as wide.

**Architecture:** Add figure-size helpers in `strava_runs.py`, use `single_sport_figure_size()` for individual charts and `combined_figure_size()` for the combined chart.

**Tech Stack:** Python 3.10+, `matplotlib`, and `unittest`.

---

## File Structure

- Modify `strava_runs.py`: add figure-size helpers and use them in chart creation.
- Modify `tests/test_strava_runs.py`: add figure-size tests.

### Task 1: Figure Size Helpers

- [ ] Write failing tests for `single_sport_figure_size() == (12, 6)` and `combined_figure_size() == (24, 6)`.
- [ ] Run targeted tests and verify failure.
- [ ] Add helpers and use them in plotting.
- [ ] Run full test suite.
- [ ] Run `python strava_runs.py` to regenerate charts.
