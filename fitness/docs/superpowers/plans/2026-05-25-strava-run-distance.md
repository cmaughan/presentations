# Strava Run Distance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that authorizes with Strava, fetches all runs, exports them by distance, and generates a run-distance chart across years.

**Architecture:** Keep the implementation in one script, `strava_runs.py`, with testable pure helpers for token expiry, pagination, filtering, normalization, CSV sorting, and plot data ordering. Live Strava calls stay behind small `requests.Session` functions so tests can use fake sessions without network access.

**Tech Stack:** Python 3.10+, `requests`, `matplotlib`, standard-library `csv`, `json`, `http.server`, `webbrowser`, and `unittest`.

---

## File Structure

- Create `strava_runs.py`: command-line script, OAuth flow, Strava API calls, data normalization, CSV export, and chart generation.
- Create `tests/test_strava_runs.py`: unit tests for non-interactive behavior and API-control flow with fake sessions.
- Create `requirements.txt`: runtime dependency list.
- Create `.gitignore`: ignore local token, env, output, and Python cache files.
- Update `docs/superpowers/specs/2026-05-25-strava-run-distance-design.md` only if implementation uncovers a spec mismatch.

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `tests/test_strava_runs.py`

- [ ] **Step 1: Create dependency and ignore files**

```text
requests>=2.31
matplotlib>=3.8
```

```gitignore
.env
.strava_tokens.json
runs_by_distance.csv
run_distance_over_years.png
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 2: Add initial import test**

```python
import unittest

import strava_runs


class SmokeTests(unittest.TestCase):
    def test_module_imports(self):
        self.assertTrue(hasattr(strava_runs, "main"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because `strava_runs` does not exist yet.

- [ ] **Step 4: Add minimal script file**

```python
def main():
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

### Task 2: Activity Transformation Helpers

**Files:**
- Modify: `strava_runs.py`
- Modify: `tests/test_strava_runs.py`

- [ ] **Step 1: Write failing tests for run filtering, normalization, sorting, and chart ordering**

```python
class ActivityTransformationTests(unittest.TestCase):
    def test_filters_run_sport_types(self):
        activities = [
            {"id": 1, "sport_type": "Run"},
            {"id": 2, "sport_type": "TrailRun"},
            {"id": 3, "type": "VirtualRun"},
            {"id": 4, "sport_type": "Ride"},
        ]
        self.assertEqual([a["id"] for a in strava_runs.filter_runs(activities)], [1, 2, 3])

    def test_normalizes_run_distance_to_miles(self):
        activity = {
            "id": 42,
            "name": "Morning Run",
            "distance": 1609.344,
            "start_date_local": "2024-05-20T07:30:00Z",
            "sport_type": "Run",
        }
        run = strava_runs.normalize_run(activity)
        self.assertEqual(run["id"], 42)
        self.assertEqual(run["name"], "Morning Run")
        self.assertEqual(run["date"], "2024-05-20")
        self.assertAlmostEqual(run["distance_miles"], 1.0)

    def test_sorts_runs_by_distance_descending(self):
        runs = [
            {"id": 1, "distance_miles": 3.0},
            {"id": 2, "distance_miles": 10.0},
            {"id": 3, "distance_miles": 5.0},
        ]
        self.assertEqual([r["id"] for r in strava_runs.sort_runs_by_distance(runs)], [2, 3, 1])

    def test_prepares_plot_rows_chronologically(self):
        runs = [
            {"date": "2023-01-02", "distance_miles": 5.0},
            {"date": "2021-06-01", "distance_miles": 2.0},
        ]
        rows = strava_runs.prepare_plot_rows(runs)
        self.assertEqual([row[0].isoformat() for row in rows], ["2021-06-01", "2023-01-02"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Implement helpers**

Implement `RUN_SPORT_TYPES`, `meters_to_miles`, `filter_runs`, `normalize_run`, `sort_runs_by_distance`, and `prepare_plot_rows`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

### Task 3: Token and Pagination Behavior

**Files:**
- Modify: `strava_runs.py`
- Modify: `tests/test_strava_runs.py`

- [ ] **Step 1: Write failing tests for token refresh and pagination**

```python
class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)


class FakeSession:
    def __init__(self, pages=None, token_payload=None):
        self.pages = pages or []
        self.token_payload = token_payload
        self.get_calls = []
        self.post_calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.get_calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        page = params["page"]
        return FakeResponse(self.pages[page - 1])

    def post(self, url, data=None, timeout=None):
        self.post_calls.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse(self.token_payload)


class ApiBehaviorTests(unittest.TestCase):
    def test_refreshes_expired_token(self):
        session = FakeSession(token_payload={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_at": 9999999999,
        })
        token = {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 1}
        refreshed = strava_runs.ensure_access_token(session, "123", "secret", token, now=100)
        self.assertEqual(refreshed["access_token"], "new-access")
        self.assertEqual(session.post_calls[0]["data"]["grant_type"], "refresh_token")

    def test_reuses_unexpired_token(self):
        session = FakeSession(token_payload={})
        token = {"access_token": "current", "refresh_token": "refresh", "expires_at": 5000}
        reused = strava_runs.ensure_access_token(session, "123", "secret", token, now=100)
        self.assertEqual(reused, token)
        self.assertEqual(session.post_calls, [])

    def test_fetches_activities_until_empty_page(self):
        session = FakeSession(pages=[
            [{"id": 1}],
            [{"id": 2}],
            [],
        ])
        activities = strava_runs.fetch_all_activities(session, "token", per_page=2)
        self.assertEqual([a["id"] for a in activities], [1, 2])
        self.assertEqual([call["params"]["page"] for call in session.get_calls], [1, 2, 3])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because token and pagination functions do not exist.

- [ ] **Step 3: Implement API behavior helpers**

Implement `ensure_access_token`, `fetch_all_activities`, constants for Strava endpoints, and `StravaApiError`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

### Task 4: CSV, Plot, and CLI

**Files:**
- Modify: `strava_runs.py`
- Modify: `tests/test_strava_runs.py`

- [ ] **Step 1: Write failing tests for CSV output**

```python
class OutputTests(unittest.TestCase):
    def test_writes_distance_sorted_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runs.csv"
            runs = [
                {"id": 1, "date": "2024-01-02", "name": "Short", "distance_miles": 3.0},
                {"id": 2, "date": "2024-01-03", "name": "Long", "distance_miles": 8.0},
            ]
            strava_runs.write_runs_csv(runs, path)
            content = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(content[0], "date,name,distance_miles,id")
        self.assertIn("2024-01-03,Long,8.00,2", content[1])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: FAIL because `write_runs_csv` does not exist.

- [ ] **Step 3: Implement CSV output**

Implement `write_runs_csv`.

- [ ] **Step 4: Implement plot and CLI entry point**

Implement `plot_run_distances`, `.env` loading, credential loading, token file load/save, localhost OAuth callback, `build_authorize_url`, `exchange_code_for_token`, `run_report`, and `main`.

- [ ] **Step 5: Run full tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

### Task 5: Manual Verification

**Files:**
- Read: `strava_runs.py`
- Read: `requirements.txt`

- [ ] **Step 1: Verify dependencies are importable or document install command**

Run: `python -m pip install -r requirements.txt`

Expected: dependencies are already satisfied or install successfully.

- [ ] **Step 2: Run tests**

Run: `python -m unittest tests.test_strava_runs -v`

Expected: PASS.

- [ ] **Step 3: Run help**

Run: `python strava_runs.py --help`

Expected: command exits 0 and shows options for output CSV, output plot, token file, port, and unit.

- [ ] **Step 4: Do not run live OAuth without user credentials**

Expected: live run is not attempted unless `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` are available.
