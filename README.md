<p align="center">
  <img src="assets/logo.png" alt="API Sentinel Logo" width="120" />
</p>

# API Sentinel

[![Tests](https://github.com/egeyasar0/api-sentinel/actions/workflows/tests.yml/badge.svg)](https://github.com/egeyasar0/api-sentinel/actions/workflows/tests.yml)

A lightweight API health check and contract testing tool for developers, useful for development and lightweight auditing.

---

## Features

- **Configuration-Driven API Checks**: Define API checks in a simple JSON file.
- **Status Code & Response Field Validation**: Verify expected status codes and check for specific top-level or nested keys in JSON responses.
- **Retry Policies for Transient Failures**: Automatically retry transient errors (timeouts, connection issues, or unexpected 5xx responses) with configurable attempts and backoffs.
- **Optional Concurrent Checks**: Speed up test suite execution using the `--concurrency` CLI option.
- **Local Scheduled Runs**: Periodically run health check suites locally at a chosen interval.
- **Webhook Failure Alerts**: Send POST webhook alerts to an endpoint loaded securely from environment variables.
- **Telegram Failure Alerts**: Send failure alerts directly to a Telegram chat using environment variables (`API_SENTINEL_TELEGRAM_BOT_TOKEN`, `API_SENTINEL_TELEGRAM_CHAT_ID`).
- **SQLite History Tracking**: Automatically save all test run metadata and individual check results to a local SQLite database.
- **Rich Terminal Reports**: Visual execution summaries with colorized tables in the terminal.
- **HTML Report Export**: Export stand-alone, self-contained HTML report files with inline styles.
- **Streamlit Dashboard**: A local web dashboard with project, status, and date range filters plus check search.
- **Public API Example Config**: A ready-made config file for testing external public endpoints.
- **Environment-Variable Based Auth**: Support for standard No Auth, Bearer Token, and API Key authentication headers.
- **Dynamic Token Fetch Support**: Programmatically log in once per run, extract a token from JSON response paths, and apply it to subsequent requests.
- **Custom Database Path**: Target any SQLite database file location using the `--db` option.
- **Comprehensive HTTP Verb Support**: Support for `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, and `OPTIONS` request methods.

---

## Tech Stack

- **Python**: Core runtime
- **HTTP Client**: `httpx`
- **Configuration Parsing**: `pydantic` (v2)
- **CLI Commands**: `typer`
- **Terminal Formats**: `rich`
- **Database**: SQLite (built-in standard library)
- **Dashboard**: `streamlit`
- **Tests**: `pytest`

---

## Project Structure

```text
api_sentinel/
  cli.py           # CLI commands definition
  config_loader.py # Loader and parser for config files
  dashboard.py     # Streamlit web dashboard
  database.py      # SQLite database access and operations
  models.py        # Pydantic configuration schemas and validation
  notifier.py      # Webhook and Telegram alert dispatcher
  reporter.py      # CLI execution tables and HTML report generators
  runner.py        # Synchronous and concurrent check execution loop
  scheduler.py     # Local scheduled timing loops
  validator.py     # Response status and body validation helpers

examples/
  api_checks.json
  authenticated_api_checks.example.json
  demo_api.py
  public_api_checks.json
  token_fetch_api_checks.example.json

tests/
  test_auth_token_fetch.py
  test_cli_export.py
  test_config_loader.py
  test_database.py
  test_runner.py
  test_scheduler.py
  test_validator.py

assets/
  logo.png

screenshots/
  cli-report.png
  history.png
  dashboard.png

.github/workflows/tests.yml
main.py
requirements.txt
pytest.ini
```

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/egeyasar0/api-sentinel.git
   cd api-sentinel
   ```

2. **Set up a Virtual Environment**:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   * **Windows (Command Prompt)**:
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate.bat
     ```
   * **macOS/Linux**:
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```

3. **Install the Package**:
   * **Option A: Standard dependency installation**:
     ```bash
     pip install -r requirements.txt
     ```
   * **Option B: Editable installation (recommends for console script)**:
     ```bash
     pip install -e .
     ```

---

## Running the Demo API

A FastAPI mock API is provided to test the tool locally without calling external services.

Start the demo server:
```bash
python -m uvicorn examples.demo_api:app --reload
```
The server will run on `http://127.0.0.1:8000`.

---

## Creating Configuration via Wizard

To create a configuration file interactively without manually writing JSON:
```bash
python main.py init-config
```
This command prompts you for project metadata, authentication details, and the checks you want to add, and exports them directly to a JSON file.

---

## Running API Checks

To execute the check suite against your API:
```bash
# Using main.py directly
python main.py run --config examples/api_checks.json

# Using the installed console script
api-sentinel run --config examples/api_checks.json
```

---

## Testing a Public API

API Sentinel can also test external endpoints. An example configuration file is provided to verify a public API:

```bash
# Using main.py directly
python main.py run --config examples/public_api_checks.json

# Using the installed console script
api-sentinel run --config examples/public_api_checks.json
```

*Note: Results of external API checks may vary depending on internet connectivity, network latency, and the availability of the target service.*

---

## Real-World Usage Flow

Here is a typical end-to-end workflow to run, audit, and schedule local API health checks:

1. **Run a health check suite sequentially**:
   ```bash
   python main.py run --config examples/public_api_checks.json
   ```
2. **Run a health check suite concurrently** (e.g. concurrency limit of 5):
   ```bash
   python main.py run --config examples/public_api_checks.json --concurrency 5
   ```
3. **Find the Run ID in your history**:
   ```bash
   python main.py history
   ```
4. **Export a standalone HTML report** (for sharing or archiving):
   ```bash
   python main.py export --run-id <run_id> --format html --output reports/latest.html
   ```
5. **Schedule ongoing local health checks** (repeating every 5 minutes):
   ```bash
   python main.py schedule --config examples/public_api_checks.json --every 300
   ```

> [!NOTE]
> Exported report files are saved under the `reports/` folder by default. Local run history is stored in the SQLite database file. Generated reports and local database files are intended for local use and should generally not be committed to source control.

---

## Scheduled Runs & Webhook Notifications

API Sentinel provides a developer-focused, local scheduling command to execute your API health checks repeatedly at set intervals:

```bash
# Run checks every 300 seconds
python main.py schedule --config examples/api_checks.json --every 300
```

### Validation
- The `--every` interval must be at least 5 seconds to prevent accidental tight CPU execution loops.

### Failure Webhook Alerts
You can optionally configure a failure webhook to trigger notifications on runs containing failed checks. The webhook URL is resolved from an environment variable to keep configurations clean:

```bash
# Trigger webhook POST notifications using URL stored in environment variable API_SENTINEL_WEBHOOK_URL
python main.py schedule --config examples/api_checks.json --every 300 --webhook-env API_SENTINEL_WEBHOOK_URL
```

### Telegram Failure Alerts
You can also configure failure alerts to be sent directly to a Telegram chat. The alerts will trigger automatically when the following environment variables are present in your session:
* `API_SENTINEL_TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
* `API_SENTINEL_TELEGRAM_CHAT_ID`: The chat ID of the target channel or user.

These alerts are sent directly from the process memory and the credentials are never printed, logged, or saved to the database.

### Limitations
- **Local Loop Only**: The scheduling loop executes locally within the active CLI process. If you terminate the terminal command (e.g. via `Ctrl+C`), checks will stop running.
- **Not a Production Monitoring System**: This local loop is meant as a developer-focused scheduling helper. It does not replace enterprise-grade uptime monitoring platforms.
- **Secrets Resolution**: The webhook URLs must be loaded via environment variables and should not be persisted in configuration files, database tables, or test summary exports.

---

## Viewing History

To view a summary of all past runs recorded in the local SQLite database:
```bash
python main.py history
```

For custom database locations, you can pass the `--db` option to any database command (`run`, `history`, `report`, `export`, `schedule`):
```bash
python main.py history --db my_custom_database.db
```

---

## Exporting Reports

To see past runs and identify their **Run IDs**, display the history table:
```bash
python main.py history
```

To view a detailed CLI report for a specific run:
```bash
python main.py report --run-id 1
```

### JSON Export
To export the run data as raw JSON (useful for integration with other tools):
- **Stdout output**:
  ```bash
  python main.py export --run-id 1 --format json
  ```
- **File output**:
  ```bash
  python main.py export --run-id 1 --format json --output reports/run-1.json
  ```

### HTML Export
To export the run data as a standalone HTML file that can be opened in any web browser:
- **Default path** (saves to `reports/run-1.html`):
  ```bash
  python main.py export --run-id 1 --format html
  ```
- **Custom path**:
  ```bash
  python main.py export --run-id 1 --format html --output reports/run-1.html
  ```

*Note: The generated HTML file is fully self-contained, meaning it embeds all required CSS styling directly. It requires no external network connections (no CDNs) and no JavaScript to load, making it fast and easy to archive or share.*


---

## Running the Dashboard

To view history and latency metrics in a local browser interface:
```bash
streamlit run api_sentinel/dashboard.py
```

---

## Running Tests & Coverage

Automated tests can be executed with `pytest` from the root directory:

```bash
pytest
```

To run tests with code coverage metrics and show missing lines:
```bash
pytest --cov=api_sentinel --cov-report=term-missing
```

---

## Authentication Support

API Sentinel provides basic, environment-variable based authentication support for API health checks. It supports:
- **No Auth**: No authorization header will be attached.
- **Bearer Token**: Reads a Bearer token value from a configured environment variable name at runtime and injects `Authorization: Bearer <value>`.
- **API Key Header**: Reads an API key value from a configured environment variable name at runtime and injects `<key_name>: <value>`.
- **Dynamic Token Fetch**: Logs in dynamically once per execution run, extracts a token from the JSON response using a dot path, and injects it into subsequent check requests.

To configure dynamic token fetch:
```json
"auth": {
  "type": "token_fetch",
  "token_url": "/login",
  "method": "POST",
  "body": {
    "email": "API_SENTINEL_DEMO_EMAIL",
    "password": "API_SENTINEL_DEMO_PASSWORD"
  },
  "token_json_path": "token",
  "header_name": "Authorization",
  "header_prefix": "Bearer"
}
```

### Design Guidelines:
- Real secrets are resolved dynamically from your environment at execution runtime. **They are never stored in the configuration file.** The configuration file only contains the *name* of the environment variable.
- Auth headers and secrets are never printed in CLI reports or recorded in the local SQLite history database to prevent credential leaks.
- Avoid committing configuration files that contain real credentials (always use environment variables).

---

## Example Config

An example configuration file (`examples/api_checks.json`) looks like this:

```json
{
  "project_name": "Demo API",
  "base_url": "http://127.0.0.1:8000",
  "checks": [
    {
      "name": "Health check",
      "method": "GET",
      "path": "/health",
      "expected_status": 200,
      "max_response_time_ms": 500,
      "expected_fields": ["status"]
    },
    {
      "name": "Get users",
      "method": "GET",
      "path": "/users",
      "expected_status": 200,
      "max_response_time_ms": 1000,
      "expected_fields": ["users"]
    },
    {
      "name": "Login",
      "method": "POST",
      "path": "/login",
      "expected_status": 200,
      "max_response_time_ms": 1000,
      "body": {
        "email": "test@example.com",
        "password": "password123"
      },
      "expected_fields": ["token", "user.email"]
    }
  ]
}
```

---

## Production-Readiness Considerations

API Sentinel is a reliable, developer-focused local tool suitable for development workflows and lightweight API auditing. It is not designed to replace full production monitoring platforms.

Please consider the following:
- **Local Scope**: Scheduled checks run only while the CLI process remains active in your terminal. They do not run as a background service or daemon.
- **SQLite History**: Run records are stored in a local SQLite database file, which is intended for local querying and developer auditing.
- **Secrets Resolution**: Sensitive authentication tokens, request bodies, and notification configurations are resolved from local environment variables and are never committed to your repository.

---

## Screenshots & Demo Artifacts

### CLI Execution Report
Visual summary generated in the console on check completion:
![CLI Execution Report](screenshots/cli-report.png)

### Run History
History list showing past runs stored in SQLite:
![Run History](screenshots/history.png)

### Streamlit Dashboard
Web dashboard featuring latency trend charts and explorer tables:
![Streamlit Dashboard](screenshots/dashboard.png)

### Standalone HTML Reports
Exported run history files (`reports/run-<run_id>.html`) can be opened directly in any browser for auditing and sharing.

*Note: Adding a recorded demo GIF of the CLI execution and scheduling loop is planned as a future documentation improvement.*
