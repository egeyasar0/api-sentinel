import json
import os
from pydantic import ValidationError
from api_sentinel.models import ProjectConfig

class ConfigError(Exception):
    """Base exception for config errors."""
    pass

class ConfigFileNotFoundError(ConfigError):
    """Raised when config file is not found."""
    pass

class ConfigInvalidJsonError(ConfigError):
    """Raised when config file is not valid JSON."""
    pass

class ConfigValidationError(ConfigError):
    """Raised when config schema validation fails."""
    pass

def load_config(config_path: str) -> ProjectConfig:
    """
    Loads, parses, and validates the ProjectConfig from a JSON file.
    
    Args:
        config_path: Path to the JSON configuration file.
        
    Returns:
        A validated ProjectConfig instance.
        
    Raises:
        ConfigFileNotFoundError: If the file does not exist.
        ConfigInvalidJsonError: If the JSON is malformed.
        ConfigValidationError: If Pydantic schema validation fails.
    """
    if not os.path.exists(config_path):
        raise ConfigFileNotFoundError(f"Configuration file not found: {config_path}")
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigInvalidJsonError(f"Invalid JSON format in config file: {str(e)}")
    except Exception as e:
        raise ConfigError(f"Failed to read config file: {str(e)}")

    try:
        return ProjectConfig(**data)
    except ValidationError as e:
        # Format Pydantic errors into a user-friendly string
        errors = []
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"[{loc}]: {msg}")
        error_details = "\n".join(errors)
        raise ConfigValidationError(
            f"Configuration validation failed:\n{error_details}"
        )
