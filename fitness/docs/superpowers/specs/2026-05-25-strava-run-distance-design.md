# Strava Run Distance Report Design

## Goal

Create a small Python tool that connects to the user's Strava account, fetches all running activities, exports them by distance, and generates a chart showing run distance over time across years.

## Scope

- Use Strava OAuth in a local browser flow.
- Store OAuth tokens locally so repeat runs do not require reauthorization.
- Refresh expired access tokens automatically.
- Fetch all athlete activities from Strava using pagination.
- Filter activities to runs.
- Export a CSV sorted by distance.
- Generate a PNG chart of run distances over time.
- Include automated tests for the data and API-control behavior that can run without Strava credentials.

## Out Of Scope

- Uploading or modifying Strava activities.
- Webhooks.
- A hosted web application.
- Multi-athlete support.

## Architecture

The project will be a standalone Python script with small pure functions around the API workflow:

- Configuration reads Strava client credentials from environment variables or an optional local `.env` file.
- Authentication starts a temporary localhost callback server, opens the Strava authorization URL, exchanges the returned code for tokens, and saves them in `.strava_tokens.json`.
- Token refresh checks token expiry before API calls and refreshes through Strava's token endpoint when needed.
- Activity fetching calls `/api/v3/athlete/activities` with `page` and `per_page`, stopping when Strava returns an empty page.
- Run filtering accepts Strava activities whose `type` or `sport_type` identifies a run.
- Reporting converts meters to miles by default, writes `runs_by_distance.csv`, and saves `run_distance_over_years.png`.

## Data Flow

1. User runs the script.
2. Script loads credentials and existing tokens.
3. If tokens are missing, script completes the browser OAuth flow.
4. If the access token is expired, script refreshes and stores the new token payload.
5. Script fetches activities page-by-page.
6. Script filters running activities.
7. Script writes a distance-sorted CSV.
8. Script plots run distance by activity date and saves the PNG chart.

## Error Handling

- Missing `STRAVA_CLIENT_ID` or `STRAVA_CLIENT_SECRET`: print setup instructions and exit.
- OAuth callback missing an authorization code: print the callback error and exit.
- Token exchange or refresh failure: print Strava's response status and message.
- Activity request failure: stop with the failing page number and response details.
- No runs found: write an explanatory message and do not create misleading chart output.

## Testing

Tests will avoid live Strava calls. They will cover:

- Token refresh happens only when the saved token is expired.
- Activity pagination stops after an empty page.
- Run filtering includes `Run`, `TrailRun`, and `VirtualRun` style activities while excluding non-runs.
- Distance conversion from meters to miles.
- CSV rows are sorted by distance descending.
- Chart data is prepared in chronological order.

## User Setup

The user will set the Strava app's authorization callback domain to `localhost`, then provide:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`

The first run opens Strava in a browser for account authorization with `activity:read_all` scope.
