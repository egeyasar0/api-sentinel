import os
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx
from api_sentinel.models import ProjectConfig, CheckConfig, TestRunResult, CheckResult
from api_sentinel.validator import validate_response

async def execute_check_async_with_retries(
    client: httpx.AsyncClient,
    config: ProjectConfig,
    check: CheckConfig,
    auth_headers: dict,
    timeout_seconds: float
) -> CheckResult:
    """
    Executes a single check asynchronously using httpx.AsyncClient, retrying transient errors.
    """
    url = f"{config.base_url}{check.path}"
    method = check.method.upper()
    headers = dict(check.headers or {})
    
    if "User-Agent" not in headers:
        headers["User-Agent"] = "APISentinel/1.0"
        
    for k, v in auth_headers.items():
        headers[k] = v
        
    retry_cfg = check.retries or config.retries
    if retry_cfg and retry_cfg.enabled:
        max_attempts = retry_cfg.max_attempts
        backoff_seconds = retry_cfg.backoff_seconds
    else:
        max_attempts = 1
        backoff_seconds = 0.0

    result = None
    for attempt in range(1, max_attempts + 1):
        start_time = time.perf_counter()
        actual_status = None
        response_body = None
        elapsed_ms = 0.0
        error_msg = None
        try:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=check.body)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=check.body)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, json=check.body)
            elif method == "HEAD":
                response = await client.head(url, headers=headers)
            elif method == "OPTIONS":
                response = await client.options(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000.0
            actual_status = response.status_code
            response_body = response.text
        except httpx.ConnectError:
            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000.0
            error_msg = f"Connection error: Could not connect to {config.base_url}."
        except httpx.TimeoutException:
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

        is_transient = False
        if error_msg is not None:
            is_transient = True
        elif actual_status is not None and actual_status >= 500 and actual_status != check.expected_status:
            is_transient = True
            error_msg = f"Server returned status code {actual_status}."

        if is_transient:
            if attempt < max_attempts:
                await asyncio.sleep(backoff_seconds)
                continue
            else:
                final_error = f"Request failed after {max_attempts} attempts: {error_msg}"
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
                    error_message=final_error
                )
                break
        else:
            result = validate_response(
                name=check.name,
                method=method,
                url=url,
                actual_status=actual_status,
                response_time_ms=elapsed_ms,
                response_body=response_body,
                check_cfg=check
            )
            if attempt > 1 and result.passed:
                result.error_message = f"Succeeded after {attempt} attempts."
            elif attempt > 1 and not result.passed:
                result.error_message = f"Request failed after {attempt} attempts: {result.error_message or 'Validation failed'}"
            break
            
    return result

def run_checks(config: ProjectConfig, timeout_seconds: float = 10.0, concurrency: int = 1) -> TestRunResult:
    """
    Executes all checks defined in the ProjectConfig using httpx (either sequentially or concurrently).
    """
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1.")

    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
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

    results = []

    if concurrency > 1:
        # Run concurrently using AsyncClient
        async def run_all_async():
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
                sem = asyncio.Semaphore(concurrency)
                tasks_results = [None] * len(config.checks)
                
                async def worker(index, check):
                    async with sem:
                        res = await execute_check_async_with_retries(
                            client, config, check, auth_headers, timeout_seconds
                        )
                        tasks_results[index] = res
                
                await asyncio.gather(*(worker(i, check) for i, check in enumerate(config.checks)))
                return tasks_results

        results = asyncio.run(run_all_async())
    else:
        # Run sequentially using httpx.Client (synchronous)
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
            for check in config.checks:
                url = f"{config.base_url}{check.path}"
                method = check.method.upper()
                headers = dict(check.headers or {})
                
                if "User-Agent" not in headers:
                    headers["User-Agent"] = "APISentinel/1.0"
                    
                for k, v in auth_headers.items():
                    headers[k] = v

                retry_cfg = check.retries or config.retries
                if retry_cfg and retry_cfg.enabled:
                    max_attempts = retry_cfg.max_attempts
                    backoff_seconds = retry_cfg.backoff_seconds
                else:
                    max_attempts = 1
                    backoff_seconds = 0.0

                result = None
                for attempt in range(1, max_attempts + 1):
                    start_time = time.perf_counter()
                    actual_status = None
                    response_body = None
                    elapsed_ms = 0.0
                    error_msg = None
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
                        
                        end_time = time.perf_counter()
                        elapsed_ms = (end_time - start_time) * 1000.0
                        actual_status = response.status_code
                        response_body = response.text
                    except httpx.ConnectError:
                        end_time = time.perf_counter()
                        elapsed_ms = (end_time - start_time) * 1000.0
                        error_msg = f"Connection error: Could not connect to {config.base_url}."
                    except httpx.TimeoutException:
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

                    is_transient = False
                    if error_msg is not None:
                        is_transient = True
                    elif actual_status is not None and actual_status >= 500 and actual_status != check.expected_status:
                        is_transient = True
                        error_msg = f"Server returned status code {actual_status}."

                    if is_transient:
                        if attempt < max_attempts:
                            time.sleep(backoff_seconds)
                            continue
                        else:
                            final_error = f"Request failed after {max_attempts} attempts: {error_msg}"
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
                                error_message=final_error
                            )
                            break
                    else:
                        result = validate_response(
                            name=check.name,
                            method=method,
                            url=url,
                            actual_status=actual_status,
                            response_time_ms=elapsed_ms,
                            response_body=response_body,
                            check_cfg=check
                        )
                        if attempt > 1 and result.passed:
                            result.error_message = f"Succeeded after {attempt} attempts."
                        elif attempt > 1 and not result.passed:
                            result.error_message = f"Request failed after {attempt} attempts: {result.error_message or 'Validation failed'}"
                        break
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
