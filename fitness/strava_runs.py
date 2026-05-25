import argparse
from collections import defaultdict
import csv
from datetime import date
import http.server
import json
import os
from pathlib import Path
import secrets
import socketserver
import time
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser


METERS_PER_MILE = 1609.344
METERS_PER_KILOMETER = 1000.0
RUN_SPORT_TYPES = {"Run", "TrailRun", "VirtualRun"}
SPORT_GROUPS = {
    "swim": {"Swim"},
    "bike": {"Ride", "GravelRide", "MountainBikeRide", "VirtualRide"},
    "run": RUN_SPORT_TYPES,
}
SPORT_TITLES = {
    "swim": "Swim",
    "bike": "Bike",
    "run": "Run",
}
SPORT_LABELS = {
    "swim": "Swims",
    "bike": "Rides",
    "run": "Runs",
}
SPORT_COLORS = {
    "swim": "#1f77b4",
    "bike": "#2ca02c",
    "run": "#d62728",
}
CHART_COLORS = {
    "figure_background": "#0d1117",
    "axes_background": "#161b22",
    "text": "#e6edf3",
    "grid": "#8b949e",
    "spine": "#8b949e",
    "legend_background": "#161b22",
    "legend_edge": "#30363d",
    "yearly_average": "#f2cc60",
}
DEFAULT_PLOT_FILES = {
    "swim": "swim_distance_over_years.png",
    "bike": "bike_distance_over_years.png",
    "run": "run_distance_over_years.png",
    "combined": "combined_distance_over_years.png",
}
AUTHORIZATION_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_SCOPE = "activity:read_all"
DEFAULT_TOKEN_FILE = ".strava_tokens.json"
DEFAULT_CSV_FILE = "activities_by_distance.csv"
DEFAULT_PLOT_OUTPUT = "screenshots"


class StravaApiError(RuntimeError):
    pass


def _raise_for_response(response, context):
    try:
        response.raise_for_status()
    except Exception as exc:
        raise StravaApiError(f"{context} failed: {response.status_code} {response.text}") from exc


def meters_to_miles(meters):
    return float(meters or 0.0) / METERS_PER_MILE


def meters_to_kilometers(meters):
    return float(meters or 0.0) / METERS_PER_KILOMETER


def filter_runs(activities):
    return [
        activity
        for activity in activities
        if activity.get("sport_type") in RUN_SPORT_TYPES or activity.get("type") in RUN_SPORT_TYPES
    ]


def activity_sport_type(activity):
    return activity.get("sport_type") or activity.get("type")


def classify_activity(activity):
    sport_type = activity_sport_type(activity)
    for sport, sport_types in SPORT_GROUPS.items():
        if sport_type in sport_types:
            return sport
    return None


def normalize_run(activity):
    start_date = activity.get("start_date_local") or activity.get("start_date") or ""
    return {
        "id": activity.get("id"),
        "date": start_date[:10],
        "name": activity.get("name", ""),
        "distance_miles": meters_to_miles(activity.get("distance", 0.0)),
    }


def normalize_activity(activity, sport):
    start_date = activity.get("start_date_local") or activity.get("start_date") or ""
    return {
        "sport": sport,
        "id": activity.get("id"),
        "date": start_date[:10],
        "name": activity.get("name", ""),
        "distance_kilometers": meters_to_kilometers(activity.get("distance", 0.0)),
    }


def sort_runs_by_distance(runs):
    return sorted(runs, key=lambda run: run["distance_miles"], reverse=True)


def sort_activities_by_distance(activities):
    return sorted(activities, key=lambda activity: activity["distance_kilometers"], reverse=True)


def prepare_plot_rows(runs):
    rows = [
        (date.fromisoformat(run["date"]), run["distance_kilometers"])
        for run in runs
        if run.get("date")
    ]
    return sorted(rows, key=lambda row: row[0])


def prepare_interactive_plot_rows(activities):
    rows = [
        {
            "date": date.fromisoformat(activity["date"]),
            "distance": activity["distance_kilometers"],
            "name": activity.get("name", ""),
            "id": activity.get("id"),
        }
        for activity in activities
        if activity.get("date")
    ]
    return sorted(rows, key=lambda row: row["date"])


def build_runs(activities):
    return [normalize_run(activity) for activity in filter_runs(activities)]


def build_sport_activities(activities):
    rows = []
    for activity in activities:
        sport = classify_activity(activity)
        if sport is not None:
            rows.append(normalize_activity(activity, sport))
    return rows


def ensure_access_token(session, client_id, client_secret, token, now=None):
    current_time = int(now if now is not None else time.time())
    if int(token.get("expires_at", 0)) > current_time + 60:
        return token

    response = session.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_response(response, "Refreshing Strava access token")
    return response.json()


def fetch_all_activities(session, access_token, per_page=200):
    activities = []
    page = 1
    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        response = session.get(
            ACTIVITIES_URL,
            headers=headers,
            params={"page": page, "per_page": per_page},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_response(response, f"Fetching Strava activities page {page}")
        page_items = response.json()
        if not page_items:
            return activities
        activities.extend(page_items)
        page += 1


def build_authorize_url(client_id, redirect_uri, state, scope=DEFAULT_SCOPE):
    return f"{AUTHORIZATION_URL}?{urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'approval_prompt': 'auto',
        'scope': scope,
        'state': state,
    })}"


def validate_granted_scope(granted_scope, required_scope=DEFAULT_SCOPE):
    granted_scopes = set((granted_scope or "").replace(",", " ").split())
    if required_scope not in granted_scopes:
        raise StravaApiError(
            f"Strava did not grant {required_scope}. Reauthorize and leave that scope checked."
        )


def load_token(path):
    token_path = Path(path)
    if not token_path.exists():
        return None
    return json.loads(token_path.read_text(encoding="utf-8"))


def save_token(path, token):
    token_path = Path(path)
    token_path.write_text(json.dumps(token, indent=2, sort_keys=True), encoding="utf-8")


def load_dotenv(path, env=None):
    target_env = os.environ if env is None else env
    env_path = Path(path)
    if not env_path.exists():
        return target_env

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in target_env:
            target_env[key] = value
    return target_env


def write_runs_csv(runs, path, unit="miles"):
    distance_field = f"distance_{unit}"
    fieldnames = ["date", "name", distance_field, "id"]
    sorted_runs = sort_runs_by_distance(runs)
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for run in sorted_runs:
            writer.writerow({
                "date": run["date"],
                "name": run["name"],
                distance_field: f"{run['distance_miles']:.2f}",
                "id": run["id"],
            })


def write_activities_csv(activities, path):
    fieldnames = ["sport", "date", "name", "distance_kilometers", "id"]
    sorted_activities = sort_activities_by_distance(activities)
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for activity in sorted_activities:
            writer.writerow({
                "sport": activity["sport"],
                "date": activity["date"],
                "name": activity["name"],
                "distance_kilometers": f"{activity['distance_kilometers']:.2f}",
                "id": activity["id"],
            })


def style_axis_for_dark_theme(axis, y_color=None, color_active_spine=None, show_facecolor=True):
    if show_facecolor:
        axis.set_facecolor(CHART_COLORS["axes_background"])
    axis.title.set_color(CHART_COLORS["text"])
    axis.xaxis.label.set_color(CHART_COLORS["text"])
    axis.yaxis.label.set_color(y_color or CHART_COLORS["text"])
    axis.tick_params(axis="x", colors=CHART_COLORS["text"])
    axis.tick_params(axis="y", colors=y_color or CHART_COLORS["text"])
    for spine in axis.spines.values():
        spine.set_color(CHART_COLORS["spine"])
    if color_active_spine:
        axis.spines[color_active_spine].set_color(y_color or CHART_COLORS["spine"])


def style_legend_for_dark_theme(legend):
    if legend is None:
        return
    frame = legend.get_frame()
    frame.set_facecolor(CHART_COLORS["legend_background"])
    frame.set_edgecolor(CHART_COLORS["legend_edge"])
    frame.set_alpha(0.95)
    for text in legend.get_texts():
        text.set_color(CHART_COLORS["text"])


def plot_distance_over_time(activities, path, title, unit_label="kilometers", activity_label=None, color=None):
    rows = prepare_plot_rows(activities)
    if not rows:
        raise ValueError(f"No {title.lower()} rows available to plot.")

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    dates = [row[0] for row in rows]
    distances = [row[1] for row in rows]
    yearly_distances = defaultdict(list)
    for run_date, distance_value in rows:
        yearly_distances[run_date.year].append(distance_value)
    yearly_average_dates = [date(year, 7, 1) for year in sorted(yearly_distances)]
    yearly_averages = [
        sum(yearly_distances[year]) / len(yearly_distances[year])
        for year in sorted(yearly_distances)
    ]

    fig, ax = plt.subplots(
        figsize=single_sport_figure_size(),
        facecolor=CHART_COLORS["figure_background"],
    )
    ax.scatter(dates, distances, s=18, alpha=0.65, label=activity_label or title, color=color)
    if len(yearly_averages) > 1:
        ax.plot(
            yearly_average_dates,
            yearly_averages,
            color=CHART_COLORS["yearly_average"],
            linewidth=2,
            label="Yearly average",
        )
    ax.set_title(f"Strava {title} Distance Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Distance ({unit_label})")
    ax.grid(True, color=CHART_COLORS["grid"], alpha=0.30)
    legend = ax.legend()
    style_axis_for_dark_theme(ax)
    style_legend_for_dark_theme(legend)
    fig.autofmt_xdate()
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_run_distances(runs, path, unit_label="kilometers"):
    plot_distance_over_time(runs, path, title="Run", unit_label=unit_label, activity_label="Runs")


STRAVA_CLICK_SCRIPT = """
const chart = document.getElementById('{plot_id}');
chart.on('plotly_click', function(event) {
  if (!event.points || !event.points.length) {
    return;
  }
  const customdata = event.points[0].customdata;
  const activityId = Array.isArray(customdata) ? customdata[1] : null;
  if (!activityId) {
    return;
  }
  window.open(`https://www.strava.com/activities/${activityId}`, '_blank', 'noopener');
});
"""


def require_plotly_graph_objects():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RuntimeError("Install Plotly with `python -m pip install -r requirements.txt`.") from exc
    return go


def require_plotly_offline():
    try:
        import plotly.offline as offline
    except ImportError as exc:
        raise RuntimeError("Install Plotly with `python -m pip install -r requirements.txt`.") from exc
    return offline


def yearly_average_points(rows):
    yearly_distances = defaultdict(list)
    for row in rows:
        yearly_distances[row["date"].year].append(row["distance"])
    years = sorted(yearly_distances)
    return [
        (
            date(year, 7, 1),
            sum(yearly_distances[year]) / len(yearly_distances[year]),
        )
        for year in years
    ]


def interactive_chart_config():
    return {
        "displaylogo": False,
        "responsive": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    }


def apply_interactive_layout(fig, title, yaxis_title):
    fig.update_layout(
        template="plotly_dark",
        title={"text": title, "x": 0.02, "xanchor": "left"},
        paper_bgcolor=CHART_COLORS["figure_background"],
        plot_bgcolor=CHART_COLORS["axes_background"],
        font={"color": CHART_COLORS["text"], "family": "Inter, Helvetica Neue, sans-serif"},
        showlegend=False,
        hovermode="closest",
        autosize=True,
        margin={"l": 58, "r": 32, "t": 54, "b": 46},
        xaxis={
            "title": "Date",
            "gridcolor": "rgba(139, 148, 158, 0.30)",
            "linecolor": CHART_COLORS["spine"],
            "zeroline": False,
        },
        yaxis={
            "title": yaxis_title,
            "gridcolor": "rgba(139, 148, 158, 0.30)",
            "linecolor": CHART_COLORS["spine"],
            "zeroline": False,
        },
    )


def write_interactive_html(fig, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    offline = require_plotly_offline()
    chart_html = fig.to_html(
        include_plotlyjs="directory",
        full_html=False,
        config=interactive_chart_config(),
        post_script=STRAVA_CLICK_SCRIPT,
        default_width="100%",
        default_height="100%",
    )
    html = (
        "<html>\n"
        "<head>\n"
        '<meta charset="utf-8" />\n'
        "<style>\n"
        "html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #0d1117; }\n"
        "body > div { width: 100%; height: 100%; }\n"
        ".plotly-graph-div { width: 100% !important; height: 100% !important; }\n"
        "</style>\n"
        "</head>\n"
        f"<body>\n{chart_html}\n</body>\n"
        "</html>\n"
    )
    Path(path).write_text(html, encoding="utf-8")
    (Path(path).parent / "plotly.min.js").write_text(offline.get_plotlyjs(), encoding="utf-8")


def plot_interactive_distance_over_time(
    activities,
    path,
    title,
    unit_label="kilometers",
    activity_label=None,
    color=None,
):
    rows = prepare_interactive_plot_rows(activities)
    if not rows:
        raise ValueError(f"No {title.lower()} rows available to plot.")

    go = require_plotly_graph_objects()
    marker_color = color or CHART_COLORS["text"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[row["date"].isoformat() for row in rows],
            y=[row["distance"] for row in rows],
            customdata=[[row["name"], row["id"]] for row in rows],
            mode="markers",
            name=activity_label or title,
            marker={"color": marker_color, "size": 8, "opacity": 0.72},
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                "<br>%{x|%Y-%m-%d}"
                f"<br>%{{y:.2f}} {unit_label}"
                "<extra></extra>"
            ),
        )
    )

    average_points = yearly_average_points(rows)
    if len(average_points) > 1:
        fig.add_trace(
            go.Scatter(
                x=[point[0].isoformat() for point in average_points],
                y=[point[1] for point in average_points],
                mode="lines",
                name="Yearly average",
                line={"color": CHART_COLORS["yearly_average"], "width": 3},
                hovertemplate=(
                    "<b>Yearly average</b>"
                    "<br>%{x|%Y}"
                    f"<br>%{{y:.2f}} {unit_label}"
                    "<extra></extra>"
                ),
            )
        )

    apply_interactive_layout(
        fig,
        f"Strava {title} Distance Over Time",
        f"Distance ({unit_label})",
    )
    write_interactive_html(fig, path)


def plot_interactive_combined_distance_over_time(activities, path, unit_label="kilometers"):
    go = require_plotly_graph_objects()
    fig = go.Figure()
    plotted = False

    for index, spec in enumerate(combined_axis_specs()):
        sport = spec["sport"]
        sport_activities = activities_for_sport(activities, sport)
        if not sport_activities:
            continue

        rows = prepare_interactive_plot_rows(sport_activities)
        yaxis_name = "y" if index == 0 else f"y{index + 1}"
        fig.add_trace(
            go.Scatter(
                x=[row["date"].isoformat() for row in rows],
                y=[row["distance"] for row in rows],
                yaxis=yaxis_name,
                customdata=[[row["name"], row["id"]] for row in rows],
                mode="markers",
                name=activity_label_for_sport(sport),
                marker={"color": SPORT_COLORS[sport], "size": 8, "opacity": 0.72},
                hovertemplate=(
                    f"<b>{SPORT_TITLES[sport]}</b>: %{{customdata[0]}}"
                    "<br>%{x|%Y-%m-%d}"
                    f"<br>%{{y:.2f}} {unit_label}"
                    "<extra></extra>"
                ),
            )
        )
        plotted = True

    if not plotted:
        raise ValueError("No swim, bike, or run rows available to plot.")

    apply_interactive_layout(
        fig,
        "Strava Swim, Bike, and Run Distance Over Time",
        f"{SPORT_LABELS['swim']} ({unit_label})",
    )
    fig.update_layout(
        margin={"l": 58, "r": 92, "t": 54, "b": 46},
        xaxis={"domain": [0.0, 0.88], "title": "Date", "gridcolor": "rgba(139, 148, 158, 0.30)"},
        yaxis={
            "title": {"text": f"{SPORT_LABELS['swim']} ({unit_label})", "font": {"color": SPORT_COLORS["swim"]}},
            "tickfont": {"color": SPORT_COLORS["swim"]},
            "gridcolor": "rgba(139, 148, 158, 0.30)",
            "linecolor": SPORT_COLORS["swim"],
            "zeroline": False,
        },
        yaxis2={
            "title": {"text": f"{SPORT_LABELS['bike']} ({unit_label})", "font": {"color": SPORT_COLORS["bike"]}},
            "tickfont": {"color": SPORT_COLORS["bike"]},
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "linecolor": SPORT_COLORS["bike"],
            "zeroline": False,
        },
        yaxis3={
            "title": {"text": f"{SPORT_LABELS['run']} ({unit_label})", "font": {"color": SPORT_COLORS["run"]}},
            "tickfont": {"color": SPORT_COLORS["run"]},
            "overlaying": "y",
            "side": "right",
            "anchor": "free",
            "position": 0.95,
            "showgrid": False,
            "linecolor": SPORT_COLORS["run"],
            "zeroline": False,
        },
    )
    write_interactive_html(fig, path)


def plot_combined_distance_over_time(activities, path, unit_label="kilometers"):
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    fig, base_ax = plt.subplots(
        figsize=combined_figure_size(),
        facecolor=CHART_COLORS["figure_background"],
    )
    axes = {}
    plotted = False
    handles = []
    labels = []

    for index, spec in enumerate(combined_axis_specs()):
        sport = spec["sport"]
        sport_activities = activities_for_sport(activities, sport)
        if not sport_activities:
            continue
        axis = base_ax if index == 0 else base_ax.twinx()
        axes[sport] = axis
        if spec["side"] == "right":
            axis.yaxis.set_label_position("right")
            axis.yaxis.tick_right()
        else:
            axis.yaxis.set_label_position("left")
            axis.yaxis.tick_left()
        if spec["offset"] is not None:
            axis.spines["right"].set_position(("axes", spec["offset"]))
        axis.set_ylabel(f"{SPORT_LABELS[sport]} ({unit_label})", color=SPORT_COLORS[sport])
        style_axis_for_dark_theme(
            axis,
            y_color=SPORT_COLORS[sport],
            color_active_spine=spec["side"],
            show_facecolor=(axis is base_ax),
        )

        rows = prepare_plot_rows(sport_activities)
        dates = [row[0] for row in rows]
        distances = [row[1] for row in rows]
        handle = axis.scatter(
            dates,
            distances,
            s=18,
            alpha=0.65,
            label=activity_label_for_sport(sport),
            color=SPORT_COLORS[sport],
        )
        handles.append(handle)
        labels.append(activity_label_for_sport(sport))
        plotted = True

    if not plotted:
        raise ValueError("No swim, bike, or run rows available to plot.")

    base_ax.set_title("Strava Swim, Bike, and Run Distance Over Time")
    base_ax.set_xlabel("Date")
    base_ax.grid(True, color=CHART_COLORS["grid"], alpha=0.30)
    legend = base_ax.legend(handles, labels)
    style_axis_for_dark_theme(base_ax, y_color=SPORT_COLORS["swim"], color_active_spine="left")
    style_legend_for_dark_theme(legend)
    fig.autofmt_xdate()
    fig.subplots_adjust(
        left=combined_subplot_left_margin(),
        right=combined_subplot_right_margin(),
        top=0.92,
        bottom=0.12,
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.1, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_output_paths(output_plot):
    if output_plot is None:
        return {sport: Path(filename) for sport, filename in DEFAULT_PLOT_FILES.items()}

    base_path = Path(output_plot)
    if base_path.suffix:
        stem = base_path.with_suffix("")
        suffix = base_path.suffix
        return {
            sport: stem.with_name(f"{stem.name}_{sport}{suffix}")
            for sport in DEFAULT_PLOT_FILES
        }

    return {
        sport: base_path / filename
        for sport, filename in DEFAULT_PLOT_FILES.items()
    }


def interactive_plot_output_paths(output_plot):
    return {
        sport: path.with_suffix(".html")
        for sport, path in plot_output_paths(output_plot).items()
    }


def activities_for_sport(activities, sport):
    return [activity for activity in activities if activity["sport"] == sport]


def activity_label_for_sport(sport):
    return SPORT_LABELS[sport]


def single_sport_figure_size():
    return (12, 6)


def combined_figure_size():
    return (24, 8)


def combined_subplot_left_margin():
    return 0.055


def combined_subplot_right_margin():
    return 0.935


def combined_axis_specs():
    return [
        {"sport": "swim", "side": "left", "offset": None},
        {"sport": "bike", "side": "right", "offset": None},
        {"sport": "run", "side": "right", "offset": 1.030},
    ]


def write_sport_charts(activities, output_paths):
    written = {}
    for sport in SPORT_GROUPS:
        sport_activities = activities_for_sport(activities, sport)
        if not sport_activities:
            continue
        output_path = output_paths[sport]
        plot_distance_over_time(
            sport_activities,
            output_path,
            title=SPORT_TITLES[sport],
            unit_label="kilometers",
            activity_label=activity_label_for_sport(sport),
            color=SPORT_COLORS[sport],
        )
        written[sport] = Path(output_path)
    plot_combined_distance_over_time(activities, output_paths["combined"], unit_label="kilometers")
    written["combined"] = Path(output_paths["combined"])
    return written


def write_sport_interactive_charts(activities, output_paths):
    written = {}
    for sport in SPORT_GROUPS:
        sport_activities = activities_for_sport(activities, sport)
        if not sport_activities:
            continue
        output_path = output_paths[sport]
        plot_interactive_distance_over_time(
            sport_activities,
            output_path,
            title=SPORT_TITLES[sport],
            unit_label="kilometers",
            activity_label=activity_label_for_sport(sport),
            color=SPORT_COLORS[sport],
        )
        written[sport] = Path(output_path)
    plot_interactive_combined_distance_over_time(activities, output_paths["combined"], unit_label="kilometers")
    written["combined"] = Path(output_paths["combined"])
    return written


def exchange_code_for_token(session, client_id, client_secret, code):
    response = session.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_response(response, "Exchanging Strava authorization code")
    return response.json()


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    server_version = "StravaOAuthCallback/1.0"

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        self.server.callback_query = query
        if "code" in query:
            body = "Strava authorization received. You can close this browser tab."
            self.send_response(200)
        else:
            body = f"Strava authorization failed: {query.get('error', ['missing code'])[0]}"
            self.send_response(400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        return


def authorize_with_browser(session, client_id, client_secret, port):
    redirect_uri = f"http://localhost:{port}/callback"
    state = secrets.token_urlsafe(24)
    authorize_url = build_authorize_url(client_id, redirect_uri, state)

    with socketserver.TCPServer(("localhost", port), OAuthCallbackHandler) as server:
        server.callback_query = {}
        print(f"Opening Strava authorization page: {authorize_url}")
        webbrowser.open(authorize_url)
        server.handle_request()

    query = server.callback_query
    if query.get("state", [""])[0] != state:
        raise StravaApiError("OAuth state did not match; authorization was not trusted.")
    if "error" in query:
        raise StravaApiError(f"Strava authorization failed: {query['error'][0]}")
    if "code" not in query:
        raise StravaApiError("Strava authorization failed: missing authorization code.")

    validate_granted_scope(query.get("scope", [""])[0])
    return exchange_code_for_token(session, client_id, client_secret, query["code"][0])


def require_credentials(env):
    client_id = env.get("STRAVA_CLIENT_ID")
    client_secret = env.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise StravaApiError(
            "Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in your environment or in a local .env file."
        )
    return client_id, client_secret


def convert_run_units(runs, unit):
    if unit == "miles":
        return runs
    converted = []
    for run in runs:
        row = dict(run)
        row["distance_miles"] = row["distance_miles"] * METERS_PER_MILE / METERS_PER_KILOMETER
        converted.append(row)
    return converted


def run_report(args):
    import requests

    load_dotenv(args.env_file)
    client_id, client_secret = require_credentials(os.environ)
    token_path = Path(args.token_file)
    session = requests.Session()

    token = load_token(token_path)
    if token is None:
        token = authorize_with_browser(session, client_id, client_secret, args.port)
        save_token(token_path, token)

    token = ensure_access_token(session, client_id, client_secret, token)
    save_token(token_path, token)

    activities = build_sport_activities(fetch_all_activities(session, token["access_token"], per_page=args.per_page))
    if not activities:
        print("No Strava swim, bike, or run activities were found for the granted scope.")
        return 1

    write_activities_csv(activities, args.output_csv)
    written_charts = write_sport_charts(activities, plot_output_paths(args.output_plot))
    written_interactive_charts = write_sport_interactive_charts(
        activities,
        interactive_plot_output_paths(args.output_plot),
    )
    print(f"Wrote {len(activities)} swim/bike/run activities to {args.output_csv}")
    for sport in SPORT_GROUPS:
        if sport in written_charts:
            print(f"Wrote {SPORT_TITLES[sport].lower()} chart to {written_charts[sport]}")
        else:
            print(f"No {SPORT_TITLES[sport].lower()} activities found; skipped chart.")
        if sport in written_interactive_charts:
            print(f"Wrote interactive {SPORT_TITLES[sport].lower()} chart to {written_interactive_charts[sport]}")
    if "combined" in written_charts:
        print(f"Wrote combined chart to {written_charts['combined']}")
    if "combined" in written_interactive_charts:
        print(f"Wrote interactive combined chart to {written_interactive_charts['combined']}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Fetch Strava swim, bike, and run activities and chart distance over time.")
    parser.add_argument("--output-csv", default=DEFAULT_CSV_FILE, help="CSV file for activities sorted by distance.")
    parser.add_argument(
        "--output-plot",
        default=DEFAULT_PLOT_OUTPUT,
        help="Chart output directory, or a PNG filename prefix. Defaults to the deck screenshots directory.",
    )
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE, help="Local OAuth token JSON file.")
    parser.add_argument("--env-file", default=".env", help="Optional .env file containing Strava credentials.")
    parser.add_argument("--port", type=int, default=8080, help="Localhost OAuth callback port.")
    parser.add_argument("--per-page", type=int, default=200, help="Activities to request per Strava page.")
    parser.add_argument("--unit", choices=("kilometers",), default="kilometers", help="Output distance unit.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_report(args)
    except StravaApiError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
