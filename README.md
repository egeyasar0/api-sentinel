<p align="center">
  <img src="assets/logo.png" alt="API Sentinel Logo" width="120" />
</p>

# API Sentinel

A lightweight API health check and contract testing tool for developers.

API Sentinel is a local, configuration-driven utility designed to help developers validate HTTP API responses, measure latency, verify response structures, and track execution history.

---

## Features

- **Configuration-Driven**: Define check suites in a simple JSON file.
- **Contract & Field Validation**: Helps validate that response status codes match expectations and checking for the presence of specific top-level or nested keys (e.g., `user.email`).
- **HTTP client execution**: Powered by `httpx` to support common HTTP verbs (GET, POST, PUT, DELETE, PATCH) with timeout limits.
- **Local Scheduled Runs**: Runs checks repeatedly at a chosen interval while the CLI process is active.
- **Webhook Alerts**: Sends optional failure notifications for failed runs using a webhook URL loaded from an environment variable.
- **Local History Tracking**: Records run metrics and check logs into a local SQLite database file.
- **Rich Terminal Reports**: Colorized console outputs summarizing execution pass rates and individual endpoint statuses.
- **Local Web Dashboard**: Built with Streamlit for inspecting historical runs and viewing latency trends.

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
  cli.py
  config_loader.py
  dashboard.py
  database.py
  models.py
  notifier.py
  reporter.py
  runner.py
  scheduler.py
  validator.py

examples/
  api_checks.json
  authenticated_api_checks.example.json
  demo_api.py
  public_api_checks.json

tests/
  test_config_loader.py
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

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
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
python main.py run --config examples/api_checks.json
```

---

## Testing a Public API

API Sentinel can also test external endpoints. An example configuration file is provided to verify a public API:

```bash
python main.py run --config examples/public_api_checks.json
```

*Note: Results of external API checks may vary depending on internet connectivity, network latency, and the availability of the target service.*

---

## Real-World Usage Flow

Here is a typical end-to-end workflow to run, audit, and schedule local API health checks:

1. **Run a health check suite**:
   ```bash
   python main.py run --config examples/public_api_checks.json
   ```
2. **Find the Run ID in your history**:
   ```bash
   python main.py history
   ```
3. **Export a standalone HTML report** (for sharing or archiving):
   ```bash
   python main.py export --run-id <run_id> --format html --output reports/latest.html
   ```
4. **Schedule ongoing local health checks** (repeating every 5 minutes):
   ```bash
   python main.py schedule --config examples/public_api_checks.json --every 300
   ```

> [!NOTE]
> All exported reports and local run data are saved under the `reports/` folder. These generated files are intended for local audit use and are ignored in `.gitignore`, so they should generally not be committed to source control.

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

## Running Tests

Automated tests can be executed with `pytest` from the root directory:

```bash
pytest
```

For verbose output:
```bash
pytest -v
```

---

## Authentication Support

API Sentinel provides basic, environment-variable based authentication support for API health checks. It supports:
- **No Auth**: No authorization header will be attached.
- **Bearer Token**: Reads a Bearer token value from a configured environment variable name at runtime and injects `Authorization: Bearer <value>`.
- **API Key Header**: Reads an API key value from a configured environment variable name at runtime and injects `<key_name>: <value>`.

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

---

## Future Improvements

- **OpenAPI Schema Validation**: Auto-generate checks from OpenAPI descriptions.
- **More Advanced Notification Targets**: Add native Slack, Discord, and Email notification targets.
- **Improved Nested JSON Validation**: Support complex JSON path traversals.
- **Interactive TUI (Terminal User Interface)**: For live terminal monitoring.
