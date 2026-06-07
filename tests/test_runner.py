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


