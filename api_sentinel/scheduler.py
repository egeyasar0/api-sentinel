import os
import time
from datetime import datetime
from typing import Optional
from rich.console import Console

from api_sentinel.models import ProjectConfig
from api_sentinel.runner import run_checks
from api_sentinel.database import save_run
from api_sentinel.notifier import send_failure_notification

console = Console()

def run_scheduler(
    config: ProjectConfig,
    interval_seconds: int,
    webhook_env: Optional[str] = None,
    db_path: str = "api_sentinel.db",
    run_once: bool = False
) -> None:
    """
    Executes check suites repeatedly every N seconds.
    Saves results, prints summaries, and fires webhooks on failure.
    
    Args:
        config: Loaded ProjectConfig
        interval_seconds: Time to sleep between runs (min 5s)
        webhook_env: Name of the environment variable containing webhook URL
        db_path: SQLite DB file name
        run_once: If True, executes only one iteration (for testing)
    """
    if interval_seconds < 5:
        raise ValueError("Interval must be at least 5 seconds to avoid tight CPU loops.")

    webhook_url = None
    if webhook_env:
        webhook_url = os.environ.get(webhook_env)
        if not webhook_url:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] Webhook environment variable '{webhook_env}' is not set. Notifications will be skipped."
            )

    console.print(
        f"[cyan]Scheduler initialized. Running checks every {interval_seconds}s for project '[bold]{config.project_name}[/bold]'...[/cyan]"
    )
    console.print("[dim]Press Ctrl+C to stop the scheduler.[/dim]\n")

    try:
        while True:
            # 1. Run checks
            try:
                run_result = run_checks(config)
            except Exception as e:
                console.print(f"[bold red]Scheduler Error executing checks:[/bold red] {str(e)}")
                if run_once:
                    break
                time.sleep(interval_seconds)
                continue

            # 2. Save history
            try:
                run_id = save_run(run_result, db_path=db_path)
            except Exception as e:
                console.print(f"[bold yellow]Warning:[/bold yellow] Failed to save test history: {str(e)}")
                run_id = None

            # 3. Print concise summary
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_lbl = f"Run #{run_id}" if run_id else "Unsaved Run"
            
            if run_result.failed_checks == 0:
                status_text = "[green]ALL PASSED[/green]"
            else:
                status_text = f"[bold red]{run_result.failed_checks} FAILED[/bold red]"
                
            console.print(
                f"[{timestamp_str}] {run_lbl}: {run_result.total_checks} checks, "
                f"{run_result.passed_checks} passed, {status_text}. "
                f"Avg latency: {run_result.average_response_time_ms:.1f} ms"
            )

            # 4. Trigger Webhook Alert if failed
            if run_result.failed_checks > 0 and webhook_url:
                console.print("[cyan]Triggering failure webhook notification...[/cyan]")
                # We do not print the actual webhook URL for security reasons
                send_failure_notification(webhook_url, run_result)

            if run_once:
                break
                
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        console.print("\n[bold green]Scheduler stopped by user.[/bold green]")
