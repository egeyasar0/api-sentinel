import json
import pytest
from api_sentinel.config_loader import (
    load_config,
    ConfigFileNotFoundError,
    ConfigInvalidJsonError,
    ConfigValidationError
)
from api_sentinel.models import ProjectConfig

def test_load_valid_config(tmp_path):
    # Create a valid config file in the temp directory
    config_data = {
        "project_name": "Test Suite API",
        "base_url": "https://api.example.com",
        "checks": [
            {
                "name": "Health check",
                "method": "GET",
                "path": "/health",
                "expected_status": 200,
                "max_response_time_ms": 300,
                "expected_fields": ["status"]
            }
        ]
    }
    
    file_path = tmp_path / "valid_config.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    config = load_config(str(file_path))
    assert isinstance(config, ProjectConfig)
    assert config.project_name == "Test Suite API"
    assert config.base_url == "https://api.example.com"
    assert len(config.checks) == 1
    assert config.checks[0].name == "Health check"
    assert config.checks[0].method == "GET"
    assert config.checks[0].path == "/health"
    assert config.checks[0].expected_status == 200
    assert config.checks[0].max_response_time_ms == 300
    assert config.checks[0].expected_fields == ["status"]

def test_load_non_existent_file():
    with pytest.raises(ConfigFileNotFoundError):
        load_config("this_file_does_not_exist_xyz.json")

def test_load_invalid_json_format(tmp_path):
    file_path = tmp_path / "invalid_json.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{invalid json file")
        
    with pytest.raises(ConfigInvalidJsonError):
        load_config(str(file_path))

def test_load_invalid_pydantic_schema(tmp_path):
    # Invalid because checks is not a list
    config_data = {
        "project_name": "Invalid API",
        "base_url": "api.example.com",  # Missing schema (http/https)
        "checks": "not a list"
    }
    
    file_path = tmp_path / "invalid_schema.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    with pytest.raises(ConfigValidationError) as excinfo:
        load_config(str(file_path))
    
    assert "Configuration validation failed" in str(excinfo.value)

def test_invalid_path_fails_validation(tmp_path):
    # Path doesn't start with /
    config_data = {
        "project_name": "Invalid API",
        "base_url": "http://api.example.com",
        "checks": [
            {
                "name": "Bad path",
                "method": "GET",
                "path": "health"  # Should fail validation because it lacks leading slash
            }
        ]
    }
    
    file_path = tmp_path / "bad_path.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    with pytest.raises(ConfigValidationError) as excinfo:
        load_config(str(file_path))
    assert "Path must start with" in str(excinfo.value)

def test_invalid_method_fails_validation(tmp_path):
    # Invalid method string
    config_data = {
        "project_name": "Invalid API",
        "base_url": "http://api.example.com",
        "checks": [
            {
                "name": "Bad methodcheck",
                "method": "FLY",  # Should fail validation
                "path": "/health"
            }
        ]
    }
    
    file_path = tmp_path / "bad_method.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    with pytest.raises(ConfigValidationError) as excinfo:
        load_config(str(file_path))
    assert "Method must be one of" in str(excinfo.value)

def test_config_with_auth_none(tmp_path):
    config_data = {
        "project_name": "No Auth API",
        "base_url": "http://localhost",
        "auth": {"type": "none"},
        "checks": [{"name": "Check", "path": "/health"}]
    }
    file_path = tmp_path / "none_auth.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    config = load_config(str(file_path))
    assert config.auth is not None
    assert config.auth.type == "none"

def test_config_with_bearer_auth(tmp_path):
    config_data = {
        "project_name": "Bearer API",
        "base_url": "http://localhost",
        "auth": {"type": "bearer", "token_env": "MY_TEST_TOKEN_ENV"},
        "checks": [{"name": "Check", "path": "/health"}]
    }
    file_path = tmp_path / "bearer_auth.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    config = load_config(str(file_path))
    assert config.auth.type == "bearer"
    assert config.auth.token_env == "MY_TEST_TOKEN_ENV"

def test_config_with_bearer_missing_token_env(tmp_path):
    # Invalid: bearer type requires token_env
    config_data = {
        "project_name": "Invalid Bearer API",
        "base_url": "http://localhost",
        "auth": {"type": "bearer"},
        "checks": [{"name": "Check", "path": "/health"}]
    }
    file_path = tmp_path / "bearer_invalid.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    with pytest.raises(ConfigValidationError) as excinfo:
        load_config(str(file_path))
    assert "token_env is required" in str(excinfo.value)

def test_config_with_api_key_auth(tmp_path):
    config_data = {
        "project_name": "API Key API",
        "base_url": "http://localhost",
        "auth": {
            "type": "api_key",
            "key_name": "X-API-KEY-HEADER",
            "key_env": "MY_API_KEY_ENV"
        },
        "checks": [{"name": "Check", "path": "/health"}]
    }
    file_path = tmp_path / "api_key_auth.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    config = load_config(str(file_path))
    assert config.auth.type == "api_key"
    assert config.auth.key_name == "X-API-KEY-HEADER"
    assert config.auth.key_env == "MY_API_KEY_ENV"

