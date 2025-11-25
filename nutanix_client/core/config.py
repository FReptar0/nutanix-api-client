"""
Configuration management module for Nutanix API Client.
Loads and validates configuration from config.yaml.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any
import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """
    Configuration manager for the Nutanix API Client.
    Loads configuration from config.yaml and provides validated access to settings.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config.yaml. If None, searches in current directory.
        """
        if config_path is None:
            # Look for config.yaml in the config/ directory
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            raise ConfigError(
                f"Configuration file not found: {config_path}\n"
                f"Please copy config/config.example.yaml to config/config.yaml and configure it."
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigError(f"Error reading configuration file: {e}")
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required configuration is present."""
        required_fields = [
            'environment',
            'api.uat.url',
            'api.production.url',
            'jwt.issuer',
            'jwt.customer_id',
            'jwt.private_key_path',
            'paths.input',
            'paths.output',
            'paths.archive_success',
            'paths.archive_error',
            'logging.level.uat',
            'logging.level.production',
        ]
        
        missing_fields = []
        for field in required_fields:
            if not self._get_nested(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ConfigError(
                f"Missing required configuration fields:\n" +
                "\n".join(f"  - {field}" for field in missing_fields)
            )
        
        # Validate environment value
        env = self.environment
        if env not in ['uat', 'production']:
            raise ConfigError(
                f"Invalid environment '{env}'. Must be 'uat' or 'production'."
            )
        
        # Validate private key exists
        raw_key_path = self._get_nested('jwt.private_key_path')
        if not raw_key_path:
            raise ConfigError("Private key path not configured: jwt.private_key_path")
        
        private_key_path = Path(raw_key_path)
        if not private_key_path.is_absolute():
            # Make relative to project root (3 levels up from this file)
            project_root = Path(__file__).parent.parent.parent
            private_key_path = (project_root / private_key_path).resolve()
        
        if not private_key_path.exists():
            raise ConfigError(
                f"Private key file not found: {private_key_path}\n"
                f"Please ensure the private key exists at the configured path."
            )
        
        self._private_key_path_resolved = str(private_key_path)
    
    def _get_nested(self, key: str, default=None) -> Any:
        """
        Get a nested configuration value using dot notation.
        
        Args:
            key: Dot-separated key (e.g., 'api.uat.url')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    @property
    def environment(self) -> str:
        """Get current environment (uat or production)."""
        return self._config.get('environment', 'uat')
    
    @property
    def api_url(self) -> str:
        """Get API URL for current environment."""
        return self._get_nested(f'api.{self.environment}.url')
    
    @property
    def jwt_issuer(self) -> str:
        """Get JWT issuer."""
        return self._get_nested('jwt.issuer')
    
    @property
    def jwt_customer_id(self) -> str:
        """Get JWT customer ID."""
        return self._get_nested('jwt.customer_id')
    
    @property
    def jwt_private_key_path(self) -> str:
        """Get private key file path (resolved to absolute path)."""
        return self._private_key_path_resolved
    
    @property
    def jwt_token_expiry_minutes(self) -> int:
        """Get JWT token expiry in minutes."""
        return self._get_nested('jwt.token_expiry_minutes', 5)
    
    @property
    def input_path(self) -> Path:
        """Get input directory path."""
        return Path(self._get_nested('paths.input'))
    
    @property
    def output_path(self) -> Path:
        """Get output directory path."""
        return Path(self._get_nested('paths.output'))
    
    @property
    def archive_success_path(self) -> Path:
        """Get success archive directory path."""
        return Path(self._get_nested('paths.archive_success'))
    
    @property
    def archive_error_path(self) -> Path:
        """Get error archive directory path."""
        return Path(self._get_nested('paths.archive_error'))
    
    @property
    def log_level(self) -> str:
        """Get log level for current environment."""
        return self._get_nested(f'logging.level.{self.environment}', 'INFO')
    
    @property
    def log_file(self) -> Path:
        """Get log file path."""
        return Path(self._get_nested('logging.file', './logs/nutanix-api-client.log'))
    
    @property
    def log_max_size_mb(self) -> int:
        """Get maximum log file size in MB."""
        return self._get_nested('logging.max_size_mb', 10)
    
    @property
    def log_backup_count(self) -> int:
        """Get number of backup log files to keep."""
        return self._get_nested('logging.backup_count', 5)
    
    @property
    def api_timeout(self) -> int:
        """Get API request timeout in seconds."""
        return self._get_nested('api_settings.timeout', 30)
    
    @property
    def api_max_retries(self) -> int:
        """Get maximum retry attempts."""
        return self._get_nested('api_settings.max_retries', 3)
    
    @property
    def api_retry_delay(self) -> int:
        """Get delay between retries in seconds."""
        return self._get_nested('api_settings.retry_delay', 5)
    
    @property
    def default_retention_days(self) -> int:
        """Get default archive retention period in days."""
        return self._get_nested('archive_cleanup.default_retention_days', 30)
    
    def ensure_directories(self):
        """Create all required directories if they don't exist."""
        directories = [
            self.input_path,
            self.output_path,
            self.archive_success_path,
            self.archive_error_path,
            self.log_file.parent,
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ConfigError(f"Failed to create directory {directory}: {e}")
