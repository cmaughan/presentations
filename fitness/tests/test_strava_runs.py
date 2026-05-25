from pathlib import Path
import io
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import strava_runs


class SmokeTests(unittest.TestCase):
    def test_module_imports(self):
        self.assertTrue(hasattr(strava_runs, "main"))


class ActivityTransformationTests(unittest.TestCase):
    def test_classifies_swim_bike_and_run_sports(self):
        self.assertEqual(strava_runs.classify_activity({"sport_type": "Swim"}), "swim")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "Ride"}), "bike")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "GravelRide"}), "bike")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "MountainBikeRide"}), "bike")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "VirtualRide"}), "bike")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "Run"}), "run")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "TrailRun"}), "run")
        self.assertEqual(strava_runs.classify_activity({"sport_type": "VirtualRun"}), "run")

    def test_excludes_ebike_sports_from_bike_group(self):
        self.assertIsNone(strava_runs.classify_activity({"sport_type": "EBikeRide"}))
        self.assertIsNone(strava_runs.classify_activity({"sport_type": "EMountainBikeRide"}))

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

    def test_normalizes_activity_distance_to_kilometers(self):
        activity = {
            "id": 42,
            "name": "Morning Run",
            "distance": 5000.0,
            "start_date_local": "2024-05-20T07:30:00Z",
            "sport_type": "Run",
        }
        row = strava_runs.normalize_activity(activity, "run")
        self.assertEqual(row["sport"], "run")
        self.assertEqual(row["id"], 42)
        self.assertEqual(row["name"], "Morning Run")
        self.assertEqual(row["date"], "2024-05-20")
        self.assertAlmostEqual(row["distance_kilometers"], 5.0)

    def test_builds_sport_activities_and_excludes_ebikes(self):
        activities = [
            {"id": 1, "name": "Swim", "distance": 1000, "sport_type": "Swim", "start_date_local": "2024-01-01T00:00:00Z"},
            {"id": 2, "name": "Ride", "distance": 20000, "sport_type": "Ride", "start_date_local": "2024-01-02T00:00:00Z"},
            {"id": 3, "name": "Run", "distance": 5000, "sport_type": "Run", "start_date_local": "2024-01-03T00:00:00Z"},
            {"id": 4, "name": "Ebike", "distance": 30000, "sport_type": "EBikeRide", "start_date_local": "2024-01-04T00:00:00Z"},
        ]
        rows = strava_runs.build_sport_activities(activities)
        self.assertEqual([row["sport"] for row in rows], ["swim", "bike", "run"])
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])

    def test_sorts_activities_by_distance_descending(self):
        activities = [
            {"id": 1, "distance_kilometers": 3.0},
            {"id": 2, "distance_kilometers": 10.0},
            {"id": 3, "distance_kilometers": 5.0},
        ]
        self.assertEqual([r["id"] for r in strava_runs.sort_activities_by_distance(activities)], [2, 3, 1])

    def test_sorts_runs_by_distance_descending(self):
        runs = [
            {"id": 1, "distance_miles": 3.0},
            {"id": 2, "distance_miles": 10.0},
            {"id": 3, "distance_miles": 5.0},
        ]
        self.assertEqual([r["id"] for r in strava_runs.sort_runs_by_distance(runs)], [2, 3, 1])

    def test_prepares_plot_rows_chronologically(self):
        runs = [
            {"date": "2023-01-02", "distance_kilometers": 5.0},
            {"date": "2021-06-01", "distance_kilometers": 2.0},
        ]
        rows = strava_runs.prepare_plot_rows(runs)
        self.assertEqual([row[0].isoformat() for row in rows], ["2021-06-01", "2023-01-02"])


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


class OutputTests(unittest.TestCase):
    def assert_png_corner_is_dark(self, path):
        import matplotlib.image as mpimg

        image = mpimg.imread(path)
        corner_rgb = image[5, 5, :3]
        self.assertLess(float(corner_rgb.mean()), 0.25)

    def test_writes_distance_sorted_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "activities.csv"
            activities = [
                {"sport": "run", "id": 1, "date": "2024-01-02", "name": "Short", "distance_kilometers": 3.0},
                {"sport": "bike", "id": 2, "date": "2024-01-03", "name": "Long", "distance_kilometers": 80.0},
            ]
            strava_runs.write_activities_csv(activities, path)
            content = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(content[0], "sport,date,name,distance_kilometers,id")
        self.assertIn("bike,2024-01-03,Long,80.00,2", content[1])

    def test_build_authorize_url_requests_run_read_scope(self):
        url = strava_runs.build_authorize_url("123", "http://localhost:8080/callback", "state-token")
        self.assertIn("https://www.strava.com/oauth/authorize?", url)
        self.assertIn("client_id=123", url)
        self.assertIn("response_type=code", url)
        self.assertIn("scope=activity%3Aread_all", url)
        self.assertIn("state=state-token", url)

    def test_validate_granted_scope_accepts_required_scope(self):
        strava_runs.validate_granted_scope("read activity:read_all")

    def test_validate_granted_scope_rejects_missing_required_scope(self):
        with self.assertRaises(strava_runs.StravaApiError):
            strava_runs.validate_granted_scope("read activity:read")

    def test_saves_and_loads_token_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tokens.json"
            token = {"access_token": "access", "refresh_token": "refresh", "expires_at": 123}
            strava_runs.save_token(path, token)
            self.assertEqual(strava_runs.load_token(path), token)

    def test_load_dotenv_reads_key_value_pairs_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text(
                "STRAVA_CLIENT_ID=from-file\n"
                "STRAVA_CLIENT_SECRET='quoted-secret'\n"
                "# ignored\n",
                encoding="utf-8",
            )
            env = {"STRAVA_CLIENT_ID": "from-env"}
            strava_runs.load_dotenv(path, env)
        self.assertEqual(env["STRAVA_CLIENT_ID"], "from-env")
        self.assertEqual(env["STRAVA_CLIENT_SECRET"], "quoted-secret")

    def test_builds_runs_from_activities(self):
        activities = [
            {"id": 1, "name": "Ride", "distance": 5000, "sport_type": "Ride", "start_date_local": "2024-01-01T00:00:00Z"},
            {"id": 2, "name": "Run", "distance": 3218.688, "sport_type": "Run", "start_date_local": "2024-01-02T00:00:00Z"},
        ]
        runs = strava_runs.build_runs(activities)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["name"], "Run")
        self.assertAlmostEqual(runs[0]["distance_miles"], 2.0)

    def test_plot_run_distances_creates_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "plot.png"
            runs = [
                {"date": "2022-01-02", "distance_kilometers": 3.0},
                {"date": "2023-03-04", "distance_kilometers": 5.0},
            ]
            strava_runs.plot_distance_over_time(runs, path, title="Run")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)
            self.assert_png_corner_is_dark(path)

    def test_default_plot_output_paths_include_three_sports(self):
        paths = strava_runs.plot_output_paths(None)
        self.assertEqual(paths["swim"], Path("swim_distance_over_years.png"))
        self.assertEqual(paths["bike"], Path("bike_distance_over_years.png"))
        self.assertEqual(paths["run"], Path("run_distance_over_years.png"))
        self.assertEqual(paths["combined"], Path("combined_distance_over_years.png"))

    def test_activity_label_for_sport_uses_plural_sport_names(self):
        self.assertEqual(strava_runs.activity_label_for_sport("swim"), "Swims")
        self.assertEqual(strava_runs.activity_label_for_sport("bike"), "Rides")
        self.assertEqual(strava_runs.activity_label_for_sport("run"), "Runs")

    def test_figure_sizes_keep_single_sport_normal_and_combined_wide_and_taller(self):
        self.assertEqual(strava_runs.single_sport_figure_size(), (12, 6))
        self.assertEqual(strava_runs.combined_figure_size(), (24, 8))

    def test_plot_output_paths_can_use_directory(self):
        paths = strava_runs.plot_output_paths("charts")
        self.assertEqual(paths["swim"], Path("charts") / "swim_distance_over_years.png")
        self.assertEqual(paths["bike"], Path("charts") / "bike_distance_over_years.png")
        self.assertEqual(paths["run"], Path("charts") / "run_distance_over_years.png")
        self.assertEqual(paths["combined"], Path("charts") / "combined_distance_over_years.png")

    def test_plot_output_paths_can_use_filename_prefix(self):
        paths = strava_runs.plot_output_paths("chart.png")
        self.assertEqual(paths["swim"], Path("chart_swim.png"))
        self.assertEqual(paths["bike"], Path("chart_bike.png"))
        self.assertEqual(paths["run"], Path("chart_run.png"))
        self.assertEqual(paths["combined"], Path("chart_combined.png"))

    def test_interactive_plot_output_paths_use_html_suffix(self):
        directory_paths = strava_runs.interactive_plot_output_paths("charts")
        self.assertEqual(directory_paths["swim"], Path("charts") / "swim_distance_over_years.html")
        self.assertEqual(directory_paths["bike"], Path("charts") / "bike_distance_over_years.html")
        self.assertEqual(directory_paths["run"], Path("charts") / "run_distance_over_years.html")
        self.assertEqual(directory_paths["combined"], Path("charts") / "combined_distance_over_years.html")

        prefix_paths = strava_runs.interactive_plot_output_paths("chart.png")
        self.assertEqual(prefix_paths["swim"], Path("chart_swim.html"))
        self.assertEqual(prefix_paths["bike"], Path("chart_bike.html"))
        self.assertEqual(prefix_paths["run"], Path("chart_run.html"))
        self.assertEqual(prefix_paths["combined"], Path("chart_combined.html"))

    def test_interactive_distance_chart_embeds_hover_titles_and_strava_click_urls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run.html"
            activities = [
                {
                    "sport": "run",
                    "id": 12345,
                    "date": "2024-01-03",
                    "name": "Lunch Run",
                    "distance_kilometers": 10.0,
                },
                {
                    "sport": "run",
                    "id": 67890,
                    "date": "2024-01-10",
                    "name": "Evening Run",
                    "distance_kilometers": 5.0,
                },
            ]
            strava_runs.plot_interactive_distance_over_time(
                activities,
                path,
                title="Run",
                activity_label="Runs",
                color="#d62728",
            )
            content = path.read_text(encoding="utf-8")
            bundled_plotly_exists = (path.parent / "plotly.min.js").exists()

        self.assertIn("Lunch Run", content)
        self.assertIn("12345", content)
        self.assertIn("plotly_click", content)
        self.assertIn("https://www.strava.com/activities/", content)
        self.assertIn("plotly.min.js", content)
        self.assertNotIn("https://cdn.plot.ly", content)
        self.assertTrue(bundled_plotly_exists)
        self.assertIn("html, body", content)
        self.assertIn("overflow: hidden", content)
        self.assertIn("height:100%; width:100%;", content)
        self.assertNotIn("height:620px", content)
        self.assertIn('"showlegend":false', content)

    def test_writes_sport_charts_for_each_group_with_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            activities = [
                {"sport": "swim", "date": "2024-01-01", "distance_kilometers": 1.5},
                {"sport": "bike", "date": "2024-01-02", "distance_kilometers": 40.0},
                {"sport": "run", "date": "2024-01-03", "distance_kilometers": 10.0},
            ]
            written = strava_runs.write_sport_charts(activities, strava_runs.plot_output_paths(output_dir))
            self.assertEqual(set(written), {"swim", "bike", "run", "combined"})
            for path in written.values():
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)

    def test_combined_chart_creates_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "combined.png"
            activities = [
                {"sport": "swim", "date": "2024-01-01", "distance_kilometers": 1.5},
                {"sport": "bike", "date": "2024-01-02", "distance_kilometers": 40.0},
                {"sport": "run", "date": "2024-01-03", "distance_kilometers": 10.0},
            ]
            strava_runs.plot_combined_distance_over_time(activities, path)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)
            self.assert_png_corner_is_dark(path)

    def test_combined_axis_specs_use_three_sport_specific_axes(self):
        specs = strava_runs.combined_axis_specs()
        self.assertEqual([spec["sport"] for spec in specs], ["swim", "bike", "run"])
        self.assertEqual([spec["side"] for spec in specs], ["left", "right", "right"])
        self.assertIsNone(specs[0]["offset"])
        self.assertIsNone(specs[1]["offset"])
        self.assertEqual(specs[2]["offset"], 1.030)
        self.assertEqual(strava_runs.combined_subplot_left_margin(), 0.055)
        self.assertEqual(strava_runs.combined_subplot_right_margin(), 0.935)

    def test_parser_defaults_to_kilometers_and_combined_csv(self):
        args = strava_runs.build_parser().parse_args([])
        self.assertEqual(args.unit, "kilometers")
        self.assertEqual(args.output_csv, "activities_by_distance.csv")
        self.assertEqual(args.output_plot, "screenshots")

    def test_run_report_writes_combined_csv_and_three_charts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "charts"
            csv_path = Path(temp_dir) / "activities.csv"
            token_path = Path(temp_dir) / "token.json"
            strava_runs.save_token(token_path, {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": 9999999999,
            })
            session = FakeSession(pages=[
                [
                    {"id": 1, "name": "Swim", "distance": 1500, "sport_type": "Swim", "start_date_local": "2024-01-01T00:00:00Z"},
                    {"id": 2, "name": "Ride", "distance": 40000, "sport_type": "Ride", "start_date_local": "2024-01-02T00:00:00Z"},
                    {"id": 3, "name": "Run", "distance": 10000, "sport_type": "Run", "start_date_local": "2024-01-03T00:00:00Z"},
                    {"id": 4, "name": "Ebike", "distance": 30000, "sport_type": "EBikeRide", "start_date_local": "2024-01-04T00:00:00Z"},
                ],
                [],
            ])
            args = SimpleNamespace(
                env_file=Path(temp_dir) / "missing.env",
                token_file=token_path,
                output_csv=csv_path,
                output_plot=output_dir,
                port=8080,
                per_page=200,
                unit="kilometers",
            )
            with patch.dict(os.environ, {"STRAVA_CLIENT_ID": "123", "STRAVA_CLIENT_SECRET": "secret"}):
                with patch("requests.Session", return_value=session):
                    with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        result = strava_runs.run_report(args)

            self.assertEqual(result, 0)
            self.assertIn("Wrote combined chart", stdout.getvalue())
            csv_lines = csv_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(csv_lines[0], "sport,date,name,distance_kilometers,id")
            self.assertNotIn("Ebike", "\n".join(csv_lines))
            self.assertTrue((output_dir / "swim_distance_over_years.png").exists())
            self.assertTrue((output_dir / "bike_distance_over_years.png").exists())
            self.assertTrue((output_dir / "run_distance_over_years.png").exists())
            self.assertTrue((output_dir / "combined_distance_over_years.png").exists())
            self.assertTrue((output_dir / "swim_distance_over_years.html").exists())
            self.assertTrue((output_dir / "bike_distance_over_years.html").exists())
            self.assertTrue((output_dir / "run_distance_over_years.html").exists())
            self.assertTrue((output_dir / "combined_distance_over_years.html").exists())
