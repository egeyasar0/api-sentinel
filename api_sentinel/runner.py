import os
import time
from datetime import datetime, timezone
from typing import Optional
import httpx
from api_sentinel.models import ProjectConfig, TestRunResult, CheckResult
from api_sentinel.validator import validate_response

def run_checks(config: ProjectConfig, timeout_seconds: float = 10.0) -> TestRunResult:
    """
    Executes all checks defined in the ProjectConfig using httpx.
    
    Args:
        config: The ProjectConfig containing checks and base_url.
        timeout_seconds: General request timeout.
        
    Returns:
        A TestRunResult summarizing the execution.
    """
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    results = []
    
    # Resolve authentication headers from environment variables
    auth_headers = {}
    if config.auth and config.auth.type != "none":
        if config.auth.type == "bearer":
            env_var = config.auth.token_env
            token = os.environ.get(env_var) if env_var else None
            if not token:
                raise ValueError(f"Missing environment variable {env_var} required for Bearer authentication.")
            auth_headers["Authorization"] = f"Bearer {token}"
        elif config.auth.type == "api_key":
            env_var = config.auth.key_env
            key_name = config.auth.key_name
            key = os.environ.get(env_var) if env_var else None
            if not key:
                raise ValueError(f"Missing environment variable {env_var} required for API key authentication.")
            auth_headers[key_name] = key

    # We use a single httpx Client for connection pooling
    with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
        for check in config.checks:
            # Construct full URL
            # Note: base_url is stripped of trailing slash, check.path starts with /
            url = f"{config.base_url}{check.path}"
            
            method = check.method.upper()
            headers = dict(check.headers or {})
            
            # Use 'User-Agent' to identify the tool
            if "User-Agent" not in headers:
                headers["User-Agent"] = "APISentinel/1.0"
                
            # Inject resolved auth headers (overrides manually defined values of the same key)
            for k, v in auth_headers.items():
                headers[k] = v
                
            actual_status: Optional[int] = None
            response_body: Optional[str] = None
            elapsed_ms = 0.0
            error_msg: Optional[str] = None
            
            start_time = time.perf_counter()
            try:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=check.body)
                elif method == "PUT":
                    response = client.put(url, headers=headers, json=check.body)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                elif method == "PATCH":
                    response = client.patch(url, headers=headers, json=check.body)
                elif method == "HEAD":
                    response = client.head(url, headers=headers)
                elif method == "OPTIONS":
                    response = client.options(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Measure time immediately after receiving response
                end_time = time.perf_counter()
                elapsed_ms = (end_time - start_time) * 1000.0
                
                actual_status = response.status_code
                response_body = response.text
                
            except httpx.ConnectError as e:
                end_time = time.perf_counter()
                elapsed_ms = (end_time - start_time) * 1000.0
                error_msg = f"Connection error: Could not connect to {config.base_url}."
            except httpx.TimeoutException as e:
                end_time = time.perf_counter()
                elapsed_ms = (end_time - start_time) * 1000.0
                error_msg = f"Request timed out after {timeout_seconds}s."
            except httpx.RequestError as e:
                end_time = time.perf_counter()
                elapsed_ms = (end_time - start_time) * 1000.0
                error_msg = f"HTTP request error: {str(e)}"
            except Exception as e:
                end_time = time.perf_counter()
                elapsed_ms = (end_time - start_time) * 1000.0
                error_msg = f"Unexpected execution error: {str(e)}"
                
            if error_msg:
                # If exception was raised, create a failed check result
                result = CheckResult(
                    name=check.name,
                    method=method,
                    url=url,
                    expected_status=check.expected_status,
                    actual_status=actual_status,
                    response_time_ms=elapsed_ms,
                    passed=False,
                    valid_json=False,
                    fields_checked=check.expected_fields or [],
                    fields_missing=check.expected_fields or [],
                    error_message=error_msg
                )
            else:
                # Run standard validation logic
                result = validate_response(
                    name=check.name,
                    method=method,
                    url=url,
                    actual_status=actual_status,
                    response_time_ms=elapsed_ms,
                    response_body=response_body,
                    check_cfg=check
                )
                
            results.append(result)

    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r.passed)
    failed_checks = total_checks - passed_checks
    
    avg_response_time = (
        sum(r.response_time_ms for r in results) / total_checks
        if total_checks > 0
        else 0.0
    )
    
    return TestRunResult(
        project_name=config.project_name,
        started_at=started_at,
        finished_at=finished_at,
        total_checks=total_checks,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        average_response_time_ms=avg_response_time,
        results=results
    )
