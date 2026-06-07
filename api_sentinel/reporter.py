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
