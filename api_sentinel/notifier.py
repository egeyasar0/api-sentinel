import os
import sys
import httpx
from typing import Optional
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

def send_telegram_failure_notification(
    token: str, chat_id: str, run_result: TestRunResult, timeout_seconds: float = 5.0
) -> bool:
    """
    Sends a failure alert message to a Telegram chat.
    """
    failures = [c for c in run_result.results if not c.passed]
    
    text = (
        f"⚠️ API Sentinel Alert: Failures detected in project '{run_result.project_name}'\n"
        f"Total Checks: {run_result.total_checks}\n"
        f"Passed: {run_result.passed_checks}\n"
        f"Failed: {run_result.failed_checks}\n"
        f"Avg Latency: {run_result.average_response_time_ms:.1f} ms\n\n"
        f"Failed checks:\n"
    )
    for check in failures:
        text += (
            f"- {check.name} ({check.method} {check.url})\n"
            f"  Error: {check.error_message or 'Validation failed'}\n"
        )
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=timeout_seconds)
        if response.status_code >= 400:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] Telegram API responded with status code {response.status_code}."
            )
            return False
        return True
    except Exception as e:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Telegram notification failed: {str(e)}"
        )
        return False

def notify_failures(run_result: TestRunResult, webhook_url: Optional[str] = None) -> None:
    """
    Main notification router. Sends failure alerts via webhook and/or Telegram if configured.
    """
    if webhook_url:
        send_failure_notification(webhook_url, run_result)
        
    telegram_token = os.environ.get("API_SENTINEL_TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("API_SENTINEL_TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        send_telegram_failure_notification(telegram_token, telegram_chat_id, run_result)
