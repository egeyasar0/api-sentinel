import json
import os
import sys
from typing import Optional
import typer
from rich.console import Console

from api_sentinel.config_loader import load_config, ConfigError
from api_sentinel.runner import run_checks
from api_sentinel.database import init_db, save_run, get_history, get_run, get_check_results
from api_sentinel.reporter import print_run_summary, print_history_table, print_detailed_run_report, generate_html_report
from api_sentinel.scheduler import run_scheduler

app = typer.Typer(
    name="api-sentinel",
    help="API Sentinel: API health check and contract testing tool.",
    no_args_is_help=True
)

console = Console()

# We can specify a default database path, or read it from an env var
DB_PATH = os.getenv("API_SENTINEL_DB", "api_sentinel.db")

@app.callback()
def callback():
    """API Sentinel CLI"""
    # Database is initialized individually by each command based on --db parameter
    pass

@app.command(name="run")
def run_cmd(
    config: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to the JSON configuration file listing API checks."
    ),
    timeout: float = typer.Option(
        10.0,
        "--timeout",
        "-t",
        help="Timeout in seconds for each HTTP request."
    ),
    db: str = typer.Option(
        "api_sentinel.db",
        "--db",
        envvar="API_SENTINEL_DB",
        help="Path to the SQLite database file."
    )
):
    """
    Runs all endpoint checks in the selected config file.
    """
    try:
        project_config = load_config(config)
    except ConfigError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Failed to load config:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Running checks for project '[bold]{project_config.project_name}[/bold]' targeting {project_config.base_url}...[/cyan]")
    
    try:
        init_db(db)
        run_result = run_checks(project_config, timeout_seconds=timeout)
    except Exception as e:
        console.print(f"[bold red]Execution Error during checks:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    try:
        run_id = save_run(run_result, db_path=db)
        console.print(f"[green]Saved test run results in history database. (Run ID: {run_id})[/green]")
    except Exception as e:
        console.print(f"[bold yellow]Warning:[/bold yellow] Failed to save test history to database: {str(e)}")

    print_run_summary(run_result)

@app.command(name="history")
def history_cmd(
    db: str = typer.Option(
        "api_sentinel.db",
        "--db",
        envvar="API_SENTINEL_DB",
        help="Path to the SQLite database file."
    )
):
    """
    Shows previous test runs stored in the SQLite database.
    """
    try:
        init_db(db)
        history = get_history(db_path=db)
        print_history_table(history)
    except Exception as e:
        console.print(f"[bold red]Database Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command(name="report")
def report_cmd(
    run_id: int = typer.Option(
        ...,
        "--run-id",
        "-r",
        help="ID of the test run to retrieve from history."
    ),
    db: str = typer.Option(
        "api_sentinel.db",
        "--db",
        envvar="API_SENTINEL_DB",
        help="Path to the SQLite database file."
    )
):
    """
    Shows a detailed report for a selected run ID.
    """
    try:
        init_db(db)
        run_details = get_run(run_id, db_path=db)
        if not run_details:
            console.print(f"[bold red]Error:[/bold red] Run with ID {run_id} not found in database.")
            raise typer.Exit(code=1)
            
        check_results = get_check_results(run_id, db_path=db)
        print_detailed_run_report(run_details, check_results)
    except Exception as e:
        console.print(f"[bold red]Error retrieving report:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command(name="export")
def export_cmd(
    run_id: int = typer.Option(
        ...,
        "--run-id",
        "-r",
        help="ID of the test run to export."
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format ('json' or 'html')."
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional file path to write the exported report. If not provided for html, defaults to reports/run-<run_id>.html"
    ),
    db: str = typer.Option(
        "api_sentinel.db",
        "--db",
        envvar="API_SENTINEL_DB",
        help="Path to the SQLite database file."
    )
):
    """
    Exports a run report as JSON or HTML.
    """
    format_lower = format.lower()
    if format_lower not in ["json", "html"]:
        console.print(f"[bold red]Error:[/bold red] Unsupported format '{format}'. Supported formats are 'json' and 'html'.")
        raise typer.Exit(code=1)

    try:
        init_db(db)
        run_details = get_run(run_id, db_path=db)
        if not run_details:
            console.print(f"[bold red]Error:[/bold red] Run with ID {run_id} not found in database.")
            raise typer.Exit(code=1)
            
        check_results = get_check_results(run_id, db_path=db)
        
        if format_lower == "json":
            # Build composite structure
            export_data = {
                "run_id": run_details["id"],
                "project_name": run_details["project_name"],
                "started_at": run_details["started_at"],
                "finished_at": run_details["finished_at"],
                "total_checks": run_details["total_checks"],
                "passed_checks": run_details["passed_checks"],
                "failed_checks": run_details["failed_checks"],
                "average_response_time_ms": run_details["average_response_time_ms"],
                "results": []
            }
            
            for check in check_results:
                export_data["results"].append({
                    "check_name": check["check_name"],
                    "method": check["method"],
                    "url": check["url"],
                    "expected_status": check["expected_status"],
                    "actual_status": check["actual_status"],
                    "response_time_ms": check["response_time_ms"],
                    "passed": True if check["passed"] == 1 else False,
                    "error_message": check["error_message"]
                })
                
            json_str = json.dumps(export_data, indent=2)
            if output:
                try:
                    out_path = os.path.abspath(output)
                    parent_dir = os.path.dirname(out_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(json_str)
                    console.print(f"[green]Successfully exported JSON report to {output}[/green]")
                except Exception as e:
                    console.print(f"[bold red]Error writing JSON file:[/bold red] {str(e)}")
                    raise typer.Exit(code=1)
            else:
                print(json_str)
                
        elif format_lower == "html":
            html_content = generate_html_report(run_details, check_results)
            dest_path = output if output else f"reports/run-{run_id}.html"
            
            try:
                out_path = os.path.abspath(dest_path)
                parent_dir = os.path.dirname(out_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                console.print(f"[green]Successfully exported HTML report to {dest_path}[/green]")
            except Exception as e:
                console.print(f"[bold red]Error writing HTML file:[/bold red] {str(e)}")
                raise typer.Exit(code=1)
                
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error exporting report:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command(name="init-config")
def init_config_cmd():
    """
    Interactively guides you to create an API Sentinel check configuration file.
    """
    console.print("[bold blue]API Sentinel - Configuration Creation Wizard[/bold blue]")
    console.print("This tool will guide you to create an API health check configuration file.\n")

    project_name = typer.prompt("Project Name", default="My API Project")
    
    # Prompt for Base URL with validation helper
    while True:
        base_url = typer.prompt("Base URL of the target API", default="http://127.0.0.1:8000")
        if base_url.startswith("http://") or base_url.startswith("https://"):
            break
        console.print("[bold red]Base URL must start with 'http://' or 'https://'[/bold red]")
        
    auth_type = typer.prompt("Authentication Type (none, bearer, api_key)", default="none").lower()
    while auth_type not in ["none", "bearer", "api_key"]:
        console.print("[bold red]Please select either 'none', 'bearer', or 'api_key'[/bold red]")
        auth_type = typer.prompt("Authentication Type (none, bearer, api_key)", default="none").lower()
        
    auth_config = None
    if auth_type != "none":
        auth_config = {"type": auth_type}
        if auth_type == "bearer":
            token_env = typer.prompt("Bearer Token environment variable name", default="API_BEARER_TOKEN")
            auth_config["token_env"] = token_env
        elif auth_type == "api_key":
            key_name = typer.prompt("API Key header name", default="X-API-Key")
            key_env = typer.prompt("API Key environment variable name", default="API_KEY")
            auth_config["key_name"] = key_name
            auth_config["key_env"] = key_env
            auth_config["location"] = "header"
    else:
        # User explicitly chose 'none' or we write a default empty or none type
        auth_config = {"type": "none"}

    checks = []
    
    # Add checks loop
    console.print("\n[bold cyan]Adding Check Endpoints:[/bold cyan]")
    while True:
        add_another = typer.confirm("Do you want to add a check endpoint?", default=True)
        if not add_another:
            if not checks:
                console.print("[bold yellow]Warning: You must add at least one check to create a valid config.[/bold yellow]")
                continue
            break
            
        check_name = typer.prompt("Check Name (e.g. Health check)")
        
        method = typer.prompt("HTTP Method (GET, POST, PUT, DELETE, PATCH)", default="GET").upper()
        while method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            console.print("[bold red]Method must be GET, POST, PUT, DELETE, or PATCH[/bold red]")
            method = typer.prompt("HTTP Method", default="GET").upper()
            
        path = typer.prompt("Endpoint path (e.g. /health)")
        while not path.startswith("/"):
            console.print("[bold red]Path must start with '/'[/bold red]")
            path = typer.prompt("Endpoint path (e.g. /health)")
            
        expected_status = typer.prompt("Expected Status Code", default=200, type=int)
        max_response_time_ms = typer.prompt("Max response time (ms)", default=1000, type=int)
        
        expected_fields_str = typer.prompt("Expected JSON fields (comma-separated, optional)", default="")
        expected_fields = None
        if expected_fields_str.strip():
            expected_fields = [f.strip() for f in expected_fields_str.split(",") if f.strip()]
            
        body = None
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            while True:
                body_str = typer.prompt("JSON Request Body (optional, enter raw JSON or leave empty)", default="", show_default=False)
                if not body_str.strip():
                    break
                try:
                    body = json.loads(body_str)
                    break
                except json.JSONDecodeError as e:
                    console.print(f"[bold red]Invalid JSON format: {str(e)}. Please try again.[/bold red]")

        check_entry = {
            "name": check_name,
            "method": method,
            "path": path,
            "expected_status": expected_status,
            "max_response_time_ms": max_response_time_ms
        }
        if expected_fields:
            check_entry["expected_fields"] = expected_fields
        if body is not None:
            check_entry["body"] = body
            
        checks.append(check_entry)
        console.print(f"[green]Check '{check_name}' added.[/green]")

    config_dict = {
        "project_name": project_name,
        "base_url": base_url,
    }
    if auth_config:
        config_dict["auth"] = auth_config
    config_dict["checks"] = checks

    console.print("\n[bold cyan]Config File Export:[/bold cyan]")
    output_path = typer.prompt("Output config path", default="generated_config.json")
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)
        console.print(f"\n[bold green]Success![/bold green] Configuration saved to [underline]{output_path}[/underline]")
    except Exception as e:
        console.print(f"[bold red]Failed to write config file: {str(e)}[/bold red]")
        raise typer.Exit(code=1)

@app.command(name="schedule")
def schedule_cmd(
    config: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to the JSON configuration file listing API checks."
    ),
    every: int = typer.Option(
        300,
        "--every",
        "-e",
        help="Interval in seconds between execution runs (minimum 5s)."
    ),
    webhook_env: Optional[str] = typer.Option(
        None,
        "--webhook-env",
        "-w",
        help="Environment variable name holding the Webhook URL."
    ),
    db: str = typer.Option(
        "api_sentinel.db",
        "--db",
        envvar="API_SENTINEL_DB",
        help="Path to the SQLite database file."
    )
):
    """
    Runs API checks periodically at a set interval.
    """
    try:
        project_config = load_config(config)
    except ConfigError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Failed to load config:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    try:
        init_db(db)
        run_scheduler(
            config=project_config,
            interval_seconds=every,
            webhook_env=webhook_env,
            db_path=db
        )
    except ValueError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Scheduler failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
