from typing import Any, Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from api_sentinel.models import TestRunResult

console = Console()

def print_run_summary(run_result: TestRunResult) -> None:
    """Prints a beautiful live test run result summary to the terminal."""
    # Summary metrics header
    status_color = "green" if run_result.failed_checks == 0 else "yellow"
    if run_result.passed_checks == 0:
        status_color = "red"

    # Build top panel
    summary_text = (
        f"[bold]Project:[/bold] {run_result.project_name}\n"
        f"[bold]Total Checks:[/bold] {run_result.total_checks}\n"
        f"[bold]Passed:[/bold] [green]{run_result.passed_checks}[/green]\n"
        f"[bold]Failed:[/bold] [red]{run_result.failed_checks}[/red]\n"
        f"[bold]Average Response Time:[/bold] {run_result.average_response_time_ms:.1f} ms"
    )
    
    console.print("\n")
    console.print(
        Panel(
            summary_text,
            title="[bold blue]API Sentinel - Execution Report[/bold blue]",
            border_style=status_color,
            expand=False
        )
    )
    console.print("\n[bold underline]Endpoint Checks:[/bold underline]")

    # Create table for checks
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Name", width=25)
    table.add_column("Method", width=8)
    table.add_column("Status", justify="right", width=8)
    table.add_column("Latency", justify="right", width=12)
    table.add_column("Verdict", justify="center", width=10)
    table.add_column("Details", width=40)

    for result in run_result.results:
        verdict = "[bold green]PASS[/bold green]" if result.passed else "[bold red]FAIL[/bold red]"
        
        status_str = str(result.actual_status) if result.actual_status is not None else "-"
        status_style = "green" if result.actual_status == result.expected_status else "red"
        
        latency_str = f"{result.response_time_ms:.1f} ms"
        
        error_details = result.error_message or ""
        if not result.passed and not error_details:
            error_details = f"Expected status {result.expected_status} but got {status_str}"

        table.add_row(
            result.name,
            result.method,
            f"[{status_style}]{status_str}[/{status_style}]",
            latency_str,
            verdict,
            f"[dim red]{error_details}[/dim red]" if not result.passed else "[dim green]OK[/dim green]"
        )

    console.print(table)
    console.print("\n")

def print_history_table(history: List[Dict[str, Any]]) -> None:
    """Displays a list of past test runs in a formatted Rich table."""
    if not history:
        console.print("[yellow]No run history found in database.[/yellow]")
        return

    table = Table(title="[bold blue]API Sentinel Run History[/bold blue]", show_header=True, header_style="bold cyan")
    table.add_column("Run ID", justify="right", style="dim")
    table.add_column("Project Name")
    table.add_column("Executed At")
    table.add_column("Checks (Passed/Total)")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Status")

    for run in history:
        # Format date for readability (removes fractional seconds/Z if present)
        date_str = run["started_at"].replace("T", " ").split(".")[0].replace("Z", "")
        
        total = run["total_checks"]
        passed = run["passed_checks"]
        failed = run["failed_checks"]
        
        ratio = f"{passed}/{total}"
        if failed == 0:
            status = "[bold green]ALL PASSED[/bold green]"
            ratio_styled = f"[green]{ratio}[/green]"
        elif passed == 0:
            status = "[bold red]ALL FAILED[/bold red]"
            ratio_styled = f"[red]{ratio}[/red]"
        else:
            status = "[bold yellow]PARTIAL FAIL[/bold yellow]"
            ratio_styled = f"[yellow]{ratio}[/yellow]"

        table.add_row(
            str(run["id"]),
            run["project_name"],
            date_str,
            ratio_styled,
            f"{run['average_response_time_ms']:.1f}",
            status
        )

    console.print(table)

def print_detailed_run_report(run_details: Dict[str, Any], check_results: List[Dict[str, Any]]) -> None:
    """Displays detailed test details for a past run retrieved from the database."""
    status_color = "green" if run_details["failed_checks"] == 0 else "yellow"
    if run_details["passed_checks"] == 0:
        status_color = "red"

    summary_text = (
        f"[bold]Run ID:[/bold] {run_details['id']}\n"
        f"[bold]Project:[/bold] {run_details['project_name']}\n"
        f"[bold]Started At:[/bold] {run_details['started_at']}\n"
        f"[bold]Finished At:[/bold] {run_details['finished_at']}\n"
        f"[bold]Checks:[/bold] {run_details['passed_checks']} passed, {run_details['failed_checks']} failed of {run_details['total_checks']} total\n"
        f"[bold]Average Response Time:[/bold] {run_details['average_response_time_ms']:.1f} ms"
    )

    console.print("\n")
    console.print(
        Panel(
            summary_text,
            title=f"[bold blue]Detailed Report for Run #{run_details['id']}[/bold blue]",
            border_style=status_color,
            expand=False
        )
    )

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Name", width=25)
    table.add_column("Method", width=8)
    table.add_column("URL", width=35)
    table.add_column("Expected Status", justify="right", width=16)
    table.add_column("Actual Status", justify="right", width=14)
    table.add_column("Latency", justify="right", width=12)
    table.add_column("Verdict", justify="center", width=10)
    table.add_column("Error Message", width=35)

    for check in check_results:
        verdict = "[bold green]PASS[/bold green]" if check["passed"] == 1 else "[bold red]FAIL[/bold red]"
        
        status_style = "green" if check["actual_status"] == check["expected_status"] else "red"
        actual_status_str = str(check["actual_status"]) if check["actual_status"] is not None else "-"
        
        table.add_row(
            check["check_name"],
            check["method"],
            check["url"],
            str(check["expected_status"]),
            f"[{status_style}]{actual_status_str}[/{status_style}]",
            f"{check['response_time_ms']:.1f} ms",
            verdict,
            f"[dim red]{check['error_message'] or ''}[/dim red]"
        )

    console.print(table)
    console.print("\n")


def generate_html_report(run_details: Dict[str, Any], check_results: List[Dict[str, Any]]) -> str:
    """
    Generates a standalone HTML report from execution statistics and check logs.
    """
    project_name = html_escape(run_details.get("project_name", "Unknown Project"))
    run_id = run_details.get("id", "N/A")
    started_at = html_escape(run_details.get("started_at", "N/A").replace("T", " ").split(".")[0].replace("Z", ""))
    finished_at = html_escape(run_details.get("finished_at", "N/A").replace("T", " ").split(".")[0].replace("Z", ""))
    total_checks = run_details.get("total_checks", 0)
    passed_checks = run_details.get("passed_checks", 0)
    failed_checks = run_details.get("failed_checks", 0)
    avg_latency = run_details.get("average_response_time_ms", 0.0)

    rows = []
    for check in check_results:
        check_name = html_escape(check.get("check_name", "N/A"))
        method = html_escape(check.get("method", "GET"))
        url = html_escape(check.get("url", ""))
        expected_status = check.get("expected_status", 200)
        actual_status = check.get("actual_status")
        actual_status_str = str(actual_status) if actual_status is not None else "-"
        response_time = check.get("response_time_ms", 0.0)
        passed = check.get("passed") == 1
        
        verdict_badge = '<span class="badge pass">PASS</span>' if passed else '<span class="badge fail">FAIL</span>'
        
        status_style = 'color: #00876c; font-weight: bold;' if passed else 'color: #ca1a1a; font-weight: bold;'
        if actual_status is not None and actual_status != expected_status:
            status_style = 'color: #ca1a1a; font-weight: bold;'
            
        err_msg = html_escape(check.get("error_message") or "")
        details_cell = ""
        if not passed:
            details_cell = f'<span class="error-message">{err_msg or "Validation failed"}</span>'
        else:
            details_cell = '<span style="color: #777;">OK</span>'

        rows.append(f"""
                <tr>
                    <td><strong>{check_name}</strong></td>
                    <td><span class="method">{method}</span></td>
                    <td><span class="code">{url}</span></td>
                    <td>{expected_status}</td>
                    <td><span style="{status_style}">{actual_status_str}</span></td>
                    <td>{response_time:.1f} ms</td>
                    <td>{verdict_badge}</td>
                    <td>{details_cell}</td>
                </tr>""")

    tbody_rows = "\n".join(rows)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Sentinel Report - {project_name} (Run #{run_id})</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f6f9;
            color: #333;
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #fff;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        header {{
            border-bottom: 2px solid #eef2f5;
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }}
        h1 {{
            margin: 0;
            color: #1e88e5;
            font-size: 2rem;
        }}
        .run-meta {{
            color: #666;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        .stat-card {{
            background-color: #f8f9fa;
            border-radius: 6px;
            padding: 1.25rem;
            text-align: center;
            border-top: 4px solid #ccd1d9;
        }}
        .stat-card.passed {{ border-top-color: #2ec4b6; }}
        .stat-card.failed {{ border-top-color: #e71d36; }}
        .stat-value {{
            font-size: 1.75rem;
            font-weight: bold;
            margin-bottom: 0.25rem;
        }}
        .stat-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            color: #777;
            letter-spacing: 0.5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            text-align: left;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #eef2f5;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        tr:hover {{
            background-color: #fcfdfe;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge.pass {{
            background-color: #e6f7f4;
            color: #00876c;
        }}
        .badge.fail {{
            background-color: #fdf2f2;
            color: #ca1a1a;
        }}
        .method {{
            font-family: monospace;
            font-weight: bold;
        }}
        .error-message {{
            font-size: 0.85rem;
            color: #ca1a1a;
            word-break: break-all;
        }}
        .code {{
            font-family: monospace;
            background-color: #f8f9fa;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>API Sentinel Report - {project_name}</h1>
            <div class="run-meta">
                <strong>Run ID:</strong> #{run_id} &bull; 
                <strong>Executed At:</strong> {started_at} &bull; 
                <strong>Finished At:</strong> {finished_at}
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_checks}</div>
                <div class="stat-label">Total Checks</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value" style="color: #00876c;">{passed_checks}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value" style="color: #ca1a1a;">{failed_checks}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_latency:.1f} ms</div>
                <div class="stat-label">Avg Response Time</div>
            </div>
        </div>
        
        <h2>Endpoint Check Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Check Name</th>
                    <th>Method</th>
                    <th>URL</th>
                    <th>Expected</th>
                    <th>Actual</th>
                    <th>Latency</th>
                    <th>Verdict</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>{tbody_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    return html_content


def html_escape(text: str) -> str:
    """Escapes HTML special characters in string values."""
    if not isinstance(text, str):
        return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

