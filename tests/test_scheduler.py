import os
import json
import pytest
from unittest.mock import MagicMock, patch
import httpx

from api_sentinel.models import ProjectConfig, CheckConfig, TestRunResult, CheckResult
from api_sentinel.scheduler import run_scheduler
from api_sentinel.notifier import send_failure_notification

def test_interval_validation():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[CheckConfig(name="Check", path="/health")]
    )
    with pytest.raises(ValueError) as excinfo:
        run_scheduler(config, interval_seconds=4)
    assert "Interval must be at least 5 seconds" in str(excinfo.value)

def test_scheduler_run_once():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[CheckConfig(name="Check", path="/health")]
    )
    
    mock_run_result = TestRunResult(
        project_name="Test Project",
        started_at="2026-06-07T10:00:00Z",
        finished_at="2026-06-07T10:00:01Z",
        total_checks=1,
        passed_checks=1,
        failed_checks=0,
        average_response_time_ms=10.0,
        results=[
            CheckResult(
                name="Check",
                method="GET",
                url="http://localhost:8000/health",
                expected_status=200,
                actual_status=200,
                response_time_ms=10.0,
                passed=True,
                valid_json=False
            )
        ]
    )

    with patch("api_sentinel.scheduler.run_checks", return_value=mock_run_result) as mock_run_checks:
        with patch("api_sentinel.scheduler.save_run", return_value=99) as mock_save_run:
            # Should run exactly once and exit without looping/sleeping
            run_scheduler(config, interval_seconds=5, run_once=True, db_path=":memory:")
            mock_run_checks.assert_called_once()
            mock_save_run.assert_called_once_with(mock_run_result, db_path=":memory:")

def test_webhook_payload_excludes_sensitive_data():
    mock_run_result = TestRunResult(
        project_name="Sensitive API",
        started_at="2026-06-07T10:00:00Z",
        finished_at="2026-06-07T10:00:01Z",
        total_checks=1,
        passed_checks=0,
        failed_checks=1,
        average_response_time_ms=120.0,
        results=[
            CheckResult(
                name="Failed Login Check",
                method="POST",
                url="http://localhost:8000/login",
                expected_status=200,
                actual_status=500,
                response_time_ms=120.0,
                passed=False,
                valid_json=False,
                error_message="Expected status 200 but got 500"
            )
        ]
    )

    # Let's intercept httpx.post to examine the JSON payload
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        send_failure_notification("http://my-webhook.internal", mock_run_result)
        
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        
        # Verify webhook URL
        assert called_args[0] == "http://my-webhook.internal"
        
        # Verify JSON payload content
        payload = called_kwargs["json"]
        assert payload["project_name"] == "Sensitive API"
        assert payload["status"] == "FAIL"
        assert payload["failed_checks_count"] == 1
        assert len(payload["failed_checks"]) == 1
        
        failed_check = payload["failed_checks"][0]
        assert failed_check["check_name"] == "Failed Login Check"
        assert failed_check["method"] == "POST"
        assert failed_check["url"] == "http://localhost:8000/login"
        assert failed_check["error_message"] == "Expected status 200 but got 500"
        
        # Ensure request headers, payloads, passwords or tokens are completely missing from the notification dictionary
        assert "headers" not in failed_check
        assert "body" not in failed_check
        assert "password" not in failed_check
        assert "token" not in failed_check
        assert "Authorization" not in failed_check

def test_missing_webhook_env_graceful():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[CheckConfig(name="Check", path="/health")]
    )
    
    mock_run_result = TestRunResult(
        project_name="Test Project",
        started_at="2026-06-07T10:00:00Z",
        finished_at="2026-06-07T10:00:01Z",
        total_checks=1,
        passed_checks=0,
        failed_checks=1,
        average_response_time_ms=10.0,
        results=[
            CheckResult(
                name="Check",
                method="GET",
                url="http://localhost:8000/health",
                expected_status=200,
                actual_status=500,
                response_time_ms=10.0,
                passed=False,
                valid_json=False,
                error_message="Expected 200 but got 500"
            )
        ]
    )

    with patch("api_sentinel.scheduler.run_checks", return_value=mock_run_result):
        with patch("api_sentinel.scheduler.save_run"):
            with patch("api_sentinel.scheduler.send_failure_notification") as mock_notify:
                with patch.dict("os.environ", {}, clear=True):
                    # Should run without crashing, skipping webhook triggers since env is empty
                    run_scheduler(
                        config, 
                        interval_seconds=5, 
                        webhook_env="MISSING_ENV_VAR", 
                        run_once=True,
                        db_path=":memory:"
                    )
                    mock_notify.assert_not_called()

def test_webhook_triggers_only_on_failure():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[CheckConfig(name="Check", path="/health")]
    )
    
    mock_success_result = TestRunResult(
        project_name="Test Project",
        started_at="2026-06-07T10:00:00Z",
        finished_at="2026-06-07T10:00:01Z",
        total_checks=1,
        passed_checks=1,
        failed_checks=0,
        average_response_time_ms=10.0,
        results=[
            CheckResult(
                name="Check",
                method="GET",
                url="http://localhost:8000/health",
                expected_status=200,
                actual_status=200,
                response_time_ms=10.0,
                passed=True,
                valid_json=False
            )
        ]
    )

    with patch("api_sentinel.scheduler.run_checks", return_value=mock_success_result):
        with patch("api_sentinel.scheduler.save_run"):
            with patch("api_sentinel.scheduler.send_failure_notification") as mock_notify:
                with patch.dict("os.environ", {"API_WEBHOOK": "http://webhook"}):
                    run_scheduler(
                        config, 
                        interval_seconds=5, 
                        webhook_env="API_WEBHOOK", 
                        run_once=True,
                        db_path=":memory:"
                    )
                    # Successful run -> NO notification
                    mock_notify.assert_not_called()

def test_webhook_failure_does_not_crash_scheduler():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[CheckConfig(name="Check", path="/health")]
    )
    
    mock_failed_result = TestRunResult(
        project_name="Test Project",
        started_at="2026-06-07T10:00:00Z",
        finished_at="2026-06-07T10:00:01Z",
        total_checks=1,
        passed_checks=0,
        failed_checks=1,
        average_response_time_ms=10.0,
        results=[
            CheckResult(
                name="Check",
                method="GET",
                url="http://localhost:8000/health",
                expected_status=200,
                actual_status=500,
                response_time_ms=10.0,
                passed=False,
                valid_json=False
            )
        ]
    )

    with patch("api_sentinel.scheduler.run_checks", return_value=mock_failed_result):
        with patch("api_sentinel.scheduler.save_run"):
            with patch("httpx.post", side_effect=httpx.ConnectError("Network is down")):
                with patch.dict("os.environ", {"API_WEBHOOK": "http://webhook"}):
                    # Scheduler runs through and handles httpx exception gracefully without crashing
                    run_scheduler(
                        config, 
                        interval_seconds=5, 
                        webhook_env="API_WEBHOOK", 
                        run_once=True,
                        db_path=":memory:"
                    )
