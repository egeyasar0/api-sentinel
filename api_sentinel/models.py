from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, HttpUrl

class RetryConfig(BaseModel):
    enabled: bool = Field(True, description="Enable or disable retries")
    max_attempts: int = Field(3, ge=1, description="Maximum number of request attempts")
    backoff_seconds: float = Field(0.5, ge=0.0, description="Delay between retry attempts in seconds")

class CheckConfig(BaseModel):
    name: str = Field(..., description="Name of the API check")
    method: str = Field("GET", description="HTTP method to use (GET, POST, etc.)")
    path: str = Field(..., description="Endpoint path (must start with /)")
    expected_status: int = Field(200, description="Expected HTTP response status code")
    max_response_time_ms: int = Field(1000, description="Maximum allowed response time in milliseconds")
    body: Optional[Dict[str, Any]] = Field(None, description="Optional request body for POST/PUT/PATCH requests")
    headers: Optional[Dict[str, str]] = Field(None, description="Optional HTTP headers for the request")
    expected_fields: Optional[List[str]] = Field(None, description="List of fields expected in the JSON response")
    retries: Optional[RetryConfig] = Field(None, description="Optional per-check override for retry policy")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("Path must start with '/'")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        upper_v = v.upper()
        allowed = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        if upper_v not in allowed:
            raise ValueError(f"Method must be one of {allowed}")
        return upper_v


class AuthConfig(BaseModel):
    type: Literal["none", "bearer", "api_key"]
    token_env: Optional[str] = Field(None, description="Environment variable name for Bearer token")
    key_name: Optional[str] = Field(None, description="Header key name for API Key")
    key_env: Optional[str] = Field(None, description="Environment variable name for API Key")
    location: Literal["header"] = Field("header")

    @model_validator(mode="after")
    def validate_auth_params(self) -> 'AuthConfig':
        if self.type == "bearer":
            if not self.token_env:
                raise ValueError("token_env is required when auth type is 'bearer'")
        elif self.type == "api_key":
            if not self.key_name:
                raise ValueError("key_name is required when auth type is 'api_key'")
            if not self.key_env:
                raise ValueError("key_env is required when auth type is 'api_key'")
        return self

class ProjectConfig(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    base_url: str = Field(..., description="Base URL of the target API")
    auth: Optional[AuthConfig] = Field(default=None, description="Optional authentication settings")
    retries: Optional[RetryConfig] = Field(default=None, description="Optional global default retry policy")
    checks: List[CheckConfig] = Field(..., description="List of API check configurations")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        # Normalize trailing slash
        if v.endswith("/"):
            v = v.rstrip("/")
        # Verify base_url starts with http:// or https://
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("base_url must start with 'http://' or 'https://'")
        return v

class CheckResult(BaseModel):
    name: str
    method: str
    url: str
    expected_status: int
    actual_status: Optional[int]
    response_time_ms: float
    passed: bool
    valid_json: bool
    fields_checked: List[str] = Field(default_factory=list)
    fields_missing: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

class TestRunResult(BaseModel):
    __test__ = False
    
    project_name: str
    started_at: str
    finished_at: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    average_response_time_ms: float
    results: List[CheckResult]
