from api_sentinel.models import CheckConfig
from api_sentinel.validator import validate_response, get_nested_value

def test_get_nested_value_flat():
    data = {"status": "ok", "code": 200}
    exists, val = get_nested_value(data, "status")
    assert exists is True
    assert val == "ok"
    
    exists, val = get_nested_value(data, "missing")
    assert exists is False
    assert val is None

def test_get_nested_value_deep():
    data = {
        "user": {
            "email": "test@example.com",
            "profile": {
                "id": 42,
                "roles": ["admin", "editor"]
            }
        }
    }
    # Level 1 nested
    exists, val = get_nested_value(data, "user.email")
    assert exists is True
    assert val == "test@example.com"
    
    # Level 2 nested
    exists, val = get_nested_value(data, "user.profile.id")
    assert exists is True
    assert val == 42
    
    # Nested index lookup in list
    exists, val = get_nested_value(data, "user.profile.roles.1")
    assert exists is True
    assert val == "editor"
    
    # Non-existent deep paths
    exists, val = get_nested_value(data, "user.profile.age")
    assert exists is False

def test_validate_response_success():
    cfg = CheckConfig(
        name="Health",
        method="GET",
        path="/health",
        expected_status=200,
        max_response_time_ms=500,
        expected_fields=["status"]
    )
    
    # Successful scenario
    result = validate_response(
        name="Health",
        method="GET",
        url="http://localhost/health",
        actual_status=200,
        response_time_ms=120.0,
        response_body='{"status": "ok"}',
        check_cfg=cfg
    )
    
    assert result.passed is True
    assert result.valid_json is True
    assert result.error_message is None
    assert result.fields_missing == []

def test_validate_response_status_mismatch():
    cfg = CheckConfig(
        name="Health",
        path="/health",
        expected_status=200
    )
    
    result = validate_response(
        name="Health",
        method="GET",
        url="http://localhost/health",
        actual_status=500,
        response_time_ms=50.0,
        response_body='{"status": "error"}',
        check_cfg=cfg
    )
    
    assert result.passed is False
    assert "Expected status 200 but got 500" in result.error_message

def test_validate_response_timeout():
    cfg = CheckConfig(
        name="Health",
        path="/health",
        max_response_time_ms=100
    )
    
    result = validate_response(
        name="Health",
        method="GET",
        url="http://localhost/health",
        actual_status=200,
        response_time_ms=150.0,  # Exceeds max
        response_body='{"status": "ok"}',
        check_cfg=cfg
    )
    
    assert result.passed is False
    assert "exceeded limit of 100ms" in result.error_message

def test_validate_response_missing_fields():
    cfg = CheckConfig(
        name="Login",
        path="/login",
        expected_fields=["token", "user.email"]
    )
    
    # Missing user.email
    body = '{"token": "xyz", "user": {"role": "admin"}}'
    result = validate_response(
        name="Login",
        method="POST",
        url="http://localhost/login",
        actual_status=200,
        response_time_ms=100.0,
        response_body=body,
        check_cfg=cfg
    )
    
    assert result.passed is False
    assert "Missing expected field(s): user.email" in result.error_message
    assert result.fields_missing == ["user.email"]

def test_validate_response_invalid_json():
    cfg = CheckConfig(
        name="Login",
        path="/login",
        expected_fields=["token"]
    )
    
    result = validate_response(
        name="Login",
        method="POST",
        url="http://localhost/login",
        actual_status=200,
        response_time_ms=100.0,
        response_body="not json content",
        check_cfg=cfg
    )
    
    assert result.passed is False
    assert "Response body is not valid JSON" in result.error_message
    assert result.valid_json is False
