import os
import httpx
import pytest
from unittest.mock import MagicMock, patch
from api_sentinel.models import ProjectConfig, CheckConfig
from api_sentinel.runner import run_checks

def test_token_fetch_success():
    config = ProjectConfig(
        project_name="Token Fetch test",
        base_url="http://localhost:8000",
        auth={
            "type": "token_fetch",
            "token_url": "/login",
            "method": "POST",
            "body": {
                "email_env": "API_SENTINEL_DEMO_EMAIL",
                "password_env": "API_SENTINEL_DEMO_PASSWORD"
            },
            "token_json_path": "auth.access_token",
            "header_name": "X-Auth-Token",
            "header_prefix": "Key"
        },
        checks=[
            CheckConfig(name="Protected", method="GET", path="/data")
        ]
    )

    mock_login_response = MagicMock()
    mock_login_response.status_code = 200
    mock_login_response.json.return_value = {
        "auth": {
            "access_token": "secret_token_abc123"
        }
    }

    mock_data_response = MagicMock()
    mock_data_response.status_code = 200
    mock_data_response.text = '{"data": "protected"}'

    with patch.dict("os.environ", {
        "API_SENTINEL_DEMO_EMAIL": "test@example.com",
        "API_SENTINEL_DEMO_PASSWORD": "mysecretpassword"
    }):
        with patch("httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_login_response
            mock_client.get.return_value = mock_data_response
            
            run_result = run_checks(config)
            
            mock_client.post.assert_called_once_with(
                "http://localhost:8000/login",
                json={
                    "email": "test@example.com",
                    "password": "mysecretpassword"
                }
            )
            
            mock_client.get.assert_called_once_with(
                "http://localhost:8000/data",
                headers={
                    "User-Agent": "APISentinel/1.0",
                    "X-Auth-Token": "Key secret_token_abc123"
                }
            )
            
            assert run_result.results[0].passed is True
            assert "secret_token_abc123" not in run_result.results[0].model_dump_json()

def test_token_fetch_missing_env_var():
    config = ProjectConfig(
        project_name="Token Fetch test",
        base_url="http://localhost:8000",
        auth={
            "type": "token_fetch",
            "token_url": "/login",
            "body": {
                "email_env": "API_SENTINEL_DEMO_EMAIL",
                "password_env": "API_SENTINEL_DEMO_PASSWORD"
            },
            "token_json_path": "token",
            "header_name": "Authorization"
        },
        checks=[CheckConfig(name="Protected", path="/data")]
    )

    with patch.dict("os.environ", {"API_SENTINEL_DEMO_EMAIL": "test@example.com"}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            run_checks(config)
        assert "Missing environment variable required for token fetch: API_SENTINEL_DEMO_PASSWORD" in str(excinfo.value)
        assert "mysecretpassword" not in str(excinfo.value)

def test_token_fetch_missing_json_path():
    config = ProjectConfig(
        project_name="Token Fetch test",
        base_url="http://localhost:8000",
        auth={
            "type": "token_fetch",
            "token_url": "/login",
            "body": {"email": "API_SENTINEL_DEMO_EMAIL"},
            "token_json_path": "missing.path",
            "header_name": "Authorization"
        },
        checks=[CheckConfig(name="Protected", path="/data")]
    )
    
    mock_login_response = MagicMock()
    mock_login_response.status_code = 200
    mock_login_response.json.return_value = {"other_field": "val"}

    with patch.dict("os.environ", {"API_SENTINEL_DEMO_EMAIL": "test@example.com"}):
        with patch("httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_login_response
            
            with pytest.raises(ValueError) as excinfo:
                run_checks(config)
            assert "Token JSON path 'missing.path' not found in response." in str(excinfo.value)
            assert "other_field" not in str(excinfo.value)

def test_token_fetch_concurrency():
    config = ProjectConfig(
        project_name="Token Fetch test",
        base_url="http://localhost:8000",
        auth={
            "type": "token_fetch",
            "token_url": "/login",
            "body": {"email": "API_SENTINEL_DEMO_EMAIL"},
            "token_json_path": "token",
            "header_name": "Authorization"
        },
        checks=[
            CheckConfig(name="C1", path="/h1"),
            CheckConfig(name="C2", path="/h2")
        ]
    )

    mock_login_response = MagicMock()
    mock_login_response.status_code = 200
    mock_login_response.json.return_value = {"token": "async_token"}

    mock_data_response = MagicMock()
    mock_data_response.status_code = 200
    mock_data_response.text = '{"ok": true}'

    with patch.dict("os.environ", {"API_SENTINEL_DEMO_EMAIL": "test@example.com"}):
        with patch("httpx.Client") as mock_sync_client_class:
            mock_sync_client = mock_sync_client_class.return_value.__enter__.return_value
            mock_sync_client.post.return_value = mock_login_response
            
            with patch("httpx.AsyncClient") as mock_async_client_class:
                mock_async_client = mock_async_client_class.return_value.__aenter__.return_value
                
                async def mock_get(*args, **kwargs):
                    return mock_data_response
                mock_async_client.get = mock_get
                
                run_result = run_checks(config, concurrency=2)
                
                mock_sync_client.post.assert_called_once()
                assert run_result.total_checks == 2
