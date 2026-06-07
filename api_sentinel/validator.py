import json
from typing import Any, Dict, List, Optional, Tuple
from api_sentinel.models import CheckConfig, CheckResult

def get_nested_value(data: Any, path: str) -> Tuple[bool, Any]:
    """
    Traverses a dictionary/list structure using dot notation (e.g., 'user.profile.id').
    
    Returns:
        A tuple of (field_exists: bool, value: Any)
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return False, None
        elif isinstance(current, list):
            # Try to parse part as list index
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return False, None
            except ValueError:
                return False, None
        else:
            return False, None
    return True, current

def validate_response(
    name: str,
    method: str,
    url: str,
    actual_status: Optional[int],
    response_time_ms: float,
    response_body: Optional[str],
    check_cfg: CheckConfig
) -> CheckResult:
    """
    Validates the result of an HTTP call against configuration requirements.
    
    Checks:
    1. HTTP status code matches expected_status.
    2. Response time is within max_response_time_ms.
    3. Expected JSON fields exist in response (if specified).
    """
    passed = True
    errors = []
    valid_json = False
    fields_checked = check_cfg.expected_fields or []
    fields_missing = []
    
    # 1. Validate status code
    if actual_status is None:
        passed = False
        errors.append("No response status received (connection failed)")
    elif actual_status != check_cfg.expected_status:
        passed = False
        errors.append(f"Expected status {check_cfg.expected_status} but got {actual_status}")

    # 2. Validate response time
    if response_time_ms > check_cfg.max_response_time_ms:
        passed = False
        errors.append(
            f"Response time {response_time_ms:.1f}ms exceeded limit of {check_cfg.max_response_time_ms}ms"
        )

    # 3. Validate JSON fields if expected
    if fields_checked:
        if not response_body:
            passed = False
            valid_json = False
            fields_missing = list(fields_checked)
            errors.append("Expected JSON response but received empty body")
        else:
            try:
                json_data = json.loads(response_body)
                valid_json = True
                
                for field in fields_checked:
                    exists, _ = get_nested_value(json_data, field)
                    if not exists:
                        passed = False
                        fields_missing.append(field)
                
                if fields_missing:
                    errors.append(f"Missing expected field(s): {', '.join(fields_missing)}")
            except json.JSONDecodeError:
                passed = False
                valid_json = False
                fields_missing = list(fields_checked)
                errors.append("Response body is not valid JSON")

    error_msg = "; ".join(errors) if errors else None
    
    return CheckResult(
        name=name,
        method=method,
        url=url,
        expected_status=check_cfg.expected_status,
        actual_status=actual_status,
        response_time_ms=response_time_ms,
        passed=passed,
        valid_json=valid_json,
        fields_checked=fields_checked,
        fields_missing=fields_missing,
        error_message=error_msg
    )
