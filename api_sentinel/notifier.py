import sys
import httpx
from rich.console import Console
from api_sentinel.models import TestRunResult

console = Console()

def send_failure_notification(webhook_url: str, run_result: TestRunResult, timeout_seconds: float = 5.0) -> bool:
    """
    Sends a failure notification webhook payload containing execution summaries.
    Ensures no sensitive data (auth headers, keys, bodies) is leaked.
    
    Args:
        webhook_url: The target endpoint URL.
        run_result: The TestRunResult object from the runner.
        timeout_seconds: Request timeout limit.
        
    Returns:
        True if the notification sent successfully, False otherwise.
    """
    # Filter failed checks and select only safe fields
    failures = []
    for check in run_result.results:
        if not check.passed:
            failures.append({
                "check_name": check.name,
                "method": check.method,
                "url": check.url,
                "expected_status": check.expected_status,
                "actual_status": check.actual_status,
                "response_time_ms": check.response_time_ms,
                "error_message": check.error_message or "Validation failed"
            })
            
    payload = {
        "project_name": run_result.project_name,
        "status": "FAIL",
        "total_checks": run_result.total_checks,
        "passed_checks": run_result.passed_checks,
        "failed_checks_count": run_result.failed_checks,
        "average_response_time_ms": run_result.average_response_time_ms,
        "failed_checks": failures
    }
    
    try:
        response = httpx.post(webhook_url, json=payload, timeout=timeout_seconds)
        if response.status_code >= 400:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] Webhook responded with status code {response.status_code}."
            )
            return False
        return True
    except httpx.HTTPError as e:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Webhook transmission failed: {str(e)}"
        )
        return False
    except Exception as e:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Unexpected webhook failure: {str(e)}"
        )
        return False
