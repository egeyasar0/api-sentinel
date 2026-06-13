from unittest.mock import MagicMock, patch
import httpx
import pytest
from api_sentinel.models import ProjectConfig, CheckConfig
from api_sentinel.runner import run_checks

def test_run_checks_success():
    config = ProjectConfig(
        project_name="Test Project",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(
                name="Health check",
                method="GET",
                path="/health",
                expected_status=200,
                max_response_time_ms=500,
                expected_fields=["status"]
            )
        ]
    )

    # Setup mocked httpx client response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    
    with patch("httpx.Client") as mock_client_class:
        # Mock instance returned by httpx.Client() context manager
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.return_value = mock_response
        
        run_result = run_checks(config)
        
        # Verify call properties
        mock_client.get.assert_called_once_with(
            "http://localhost:8000/health",
            headers={"User-Agent": "APISentinel/1.0"}
        )
        
        # Verify output structures
        assert run_result.project_name == "Test Project"
        assert run_result.total_checks == 1
        assert run_result.passed_checks == 1
        assert run_result.failed_checks == 0
        assert len(run_result.results) == 1
        assert run_result.results[0].passed is True
        assert run_result.results[0].actual_status == 200

def test_run_checks_connection_error():
    config = ProjectConfig(
        project_name="Offline Project",
        base_url="http://dead-link",
        checks=[
            CheckConfig(
                name="Offline check",
                method="GET",
                path="/health",
                expected_status=200
            )
        ]
    )

    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        # Raise connection error
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        
        run_result = run_checks(config)
        
        assert run_result.total_checks == 1
        assert run_result.passed_checks == 0
        assert run_result.failed_checks == 1
        
        check_res = run_result.results[0]
        assert check_res.passed is False
        assert "Connection error" in check_res.error_message
        assert check_res.actual_status is None

def test_run_checks_timeout_error():
    config = ProjectConfig(
        project_name="Timeout Project",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(
                name="Slow check",
                method="GET",
                path="/health",
                expected_status=200
            )
        ]
    )

    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.TimeoutException("Read timed out")
        
        run_result = run_checks(config)
        
        assert run_result.total_checks == 1
        assert run_result.passed_checks == 0
        assert run_result.failed_checks == 1
        
        check_res = run_result.results[0]
        assert check_res.passed is False
        assert "Request timed out" in check_res.error_message

def test_runner_bearer_auth_injection():
    config = ProjectConfig(
        project_name="Bearer Test Project",
        base_url="http://localhost:8000",
        auth={
            "type": "bearer",
            "token_env": "MY_SECRET_TOKEN"
        },
        checks=[
            CheckConfig(name="Protected Health check", method="GET", path="/health", expected_status=200)
        ]
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'

    with patch.dict("os.environ", {"MY_SECRET_TOKEN": "super_token_123"}):
        with patch("httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.get.return_value = mock_response
            
            run_result = run_checks(config)
            
            # Verify correct Authorization header was injected
            mock_client.get.assert_called_once_with(
                "http://localhost:8000/health",
                headers={
                    "User-Agent": "APISentinel/1.0",
                    "Authorization": "Bearer super_token_123"
                }
            )
            
            # Verify no secret is leaked in the CheckResult
            assert run_result.results[0].error_message is None
            result_json = run_result.results[0].model_dump_json()
            assert "super_token_123" not in result_json

def test_runner_bearer_auth_missing_env():
    config = ProjectConfig(
        project_name="Bearer Test Project",
        base_url="http://localhost:8000",
        auth={
            "type": "bearer",
            "token_env": "MY_SECRET_TOKEN"
        },
        checks=[
            CheckConfig(name="Protected Health check", method="GET", path="/health", expected_status=200)
        ]
    )

    # Empty env dict to simulate missing token environment variable
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            run_checks(config)
        assert "Missing environment variable MY_SECRET_TOKEN" in str(excinfo.value)

def test_runner_api_key_auth_injection():
    config = ProjectConfig(
        project_name="API Key Test Project",
        base_url="http://localhost:8000",
        auth={
            "type": "api_key",
            "key_name": "x-custom-api-key",
            "key_env": "MY_API_KEY"
        },
        checks=[
            CheckConfig(name="API Key check", method="GET", path="/health")
        ]
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'

    with patch.dict("os.environ", {"MY_API_KEY": "api_secret_key_987"}):
        with patch("httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.get.return_value = mock_response
            
            run_result = run_checks(config)
            
            # Verify key header injected
            mock_client.get.assert_called_once_with(
                "http://localhost:8000/health",
                headers={
                    "User-Agent": "APISentinel/1.0",
                    "x-custom-api-key": "api_secret_key_987"
                }
            )
            
            # Verify no secret leaked in logs
            result_json = run_result.results[0].model_dump_json()
            assert "api_secret_key_987" not in result_json

def test_runner_api_key_missing_env():
    config = ProjectConfig(
        project_name="API Key Test Project",
        base_url="http://localhost:8000",
        auth={
            "type": "api_key",
            "key_name": "x-custom-api-key",
            "key_env": "MY_API_KEY"
        },
        checks=[
            CheckConfig(name="API Key check", method="GET", path="/health")
        ]
    )

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            run_checks(config)
        assert "Missing environment variable MY_API_KEY" in str(excinfo.value)

def test_runner_head_method():
    config = ProjectConfig(
        project_name="HEAD Method Test",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(name="Head Check", method="HEAD", path="/health", expected_status=200)
        ]
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "" # HEAD has no body
    
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.head.return_value = mock_response
        
        run_result = run_checks(config)
        
        mock_client.head.assert_called_once_with(
            "http://localhost:8000/health",
            headers={"User-Agent": "APISentinel/1.0"}
        )
        assert run_result.results[0].passed is True
        assert run_result.results[0].actual_status == 200

def test_runner_options_method():
    config = ProjectConfig(
        project_name="OPTIONS Method Test",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(name="Options Check", method="OPTIONS", path="/health", expected_status=200)
        ]
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "GET, POST, OPTIONS"
    
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.options.return_value = mock_response
        
        run_result = run_checks(config)
        
        mock_client.options.assert_called_once_with(
            "http://localhost:8000/health",
            headers={"User-Agent": "APISentinel/1.0"}
        )
        assert run_result.results[0].passed is True
        assert run_result.results[0].actual_status == 200

def test_runner_retry_default_no_retries():
    config = ProjectConfig(
        project_name="Retry default",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(name="No retry check", method="GET", path="/health", expected_status=200)
        ]
    )
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        
        run_result = run_checks(config)
        
        assert mock_client.get.call_count == 1
        assert run_result.passed_checks == 0

def test_runner_retry_timeout_exceeded():
    config = ProjectConfig(
        project_name="Retry Project",
        base_url="http://localhost:8000",
        retries={"enabled": True, "max_attempts": 3, "backoff_seconds": 0.001},
        checks=[
            CheckConfig(name="Check R", method="GET", path="/health", expected_status=200)
        ]
    )
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        
        run_result = run_checks(config)
        
        assert mock_client.get.call_count == 3
        assert run_result.passed_checks == 0
        assert "Request failed after 3 attempts" in run_result.results[0].error_message

def test_runner_retry_success_eventually():
    config = ProjectConfig(
        project_name="Retry Project",
        base_url="http://localhost:8000",
        retries={"enabled": True, "max_attempts": 3, "backoff_seconds": 0.001},
        checks=[
            CheckConfig(name="Check R", method="GET", path="/health", expected_status=200)
        ]
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = [httpx.ConnectError("fail"), mock_response]
        
        run_result = run_checks(config)
        
        assert mock_client.get.call_count == 2
        assert run_result.passed_checks == 1
        assert run_result.results[0].passed is True
        assert "Succeeded after 2 attempts" in run_result.results[0].error_message

def test_runner_retry_5xx_retried():
    config = ProjectConfig(
        project_name="Retry Project",
        base_url="http://localhost:8000",
        retries={"enabled": True, "max_attempts": 3, "backoff_seconds": 0.001},
        checks=[
            CheckConfig(name="Check R", method="GET", path="/health", expected_status=200)
        ]
    )
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.text = "Server Error"
    
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.text = "OK"
    
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = [mock_500, mock_200]
        
        run_result = run_checks(config)
        
        assert mock_client.get.call_count == 2
        assert run_result.passed_checks == 1
        assert "Succeeded after 2 attempts" in run_result.results[0].error_message

def test_runner_retry_4xx_not_retried():
    config = ProjectConfig(
        project_name="Retry Project",
        base_url="http://localhost:8000",
        retries={"enabled": True, "max_attempts": 3, "backoff_seconds": 0.001},
        checks=[
            CheckConfig(name="Check R", method="GET", path="/health", expected_status=200)
        ]
    )
    mock_404 = MagicMock()
    mock_404.status_code = 404
    mock_404.text = "Not Found"
    
    with patch("httpx.Client") as mock_client_class:
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.return_value = mock_404
        
        run_result = run_checks(config)
        
        # 4xx is validation error, should not retry
        assert mock_client.get.call_count == 1
        assert run_result.passed_checks == 0
        assert "Expected status 200 but got 404" in run_result.results[0].error_message

def test_runner_concurrency_same_structure():
    config = ProjectConfig(
        project_name="Concurrent Project",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(name="C1", method="GET", path="/h1", expected_status=200),
            CheckConfig(name="C2", method="GET", path="/h2", expected_status=200),
        ]
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"ok": true}'
    
    with patch("httpx.AsyncClient") as mock_async_client_class:
        mock_client = mock_async_client_class.return_value.__aenter__.return_value
        
        async def mock_get(*args, **kwargs):
            return mock_response
        mock_client.get = mock_get
        
        run_result = run_checks(config, concurrency=2)
        
        assert run_result.total_checks == 2
        assert run_result.passed_checks == 2
        assert run_result.results[0].name == "C1"
        assert run_result.results[1].name == "C2"

def test_runner_concurrency_invalid():
    config = ProjectConfig(
        project_name="Concurrent Project",
        base_url="http://localhost:8000",
        checks=[
            CheckConfig(name="C1", method="GET", path="/h1", expected_status=200),
        ]
    )
    with pytest.raises(ValueError) as excinfo:
        run_checks(config, concurrency=0)
    assert "Concurrency must be at least 1" in str(excinfo.value)


