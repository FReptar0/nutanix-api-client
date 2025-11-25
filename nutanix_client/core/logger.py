"""
Centralized logging module for Nutanix API Client.
Provides structured logging with file rotation and console output.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class Logger:
    """
    Centralized logger for the application.
    Configures both file and console logging with rotation.
    """
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __init__(self, log_file: Path, log_level: str = 'INFO', 
                 max_size_mb: int = 10, backup_count: int = 5):
        """
        Initialize the logger.
        
        Args:
            log_file: Path to log file
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            max_size_mb: Maximum log file size in MB before rotation
            backup_count: Number of backup files to keep
        """
        # If already initialized, just return
        if Logger._instance is not None and Logger._logger is not None:
            return
        
        # Set class attributes
        Logger._instance = self
        
        # Create logger
        Logger._logger = logging.getLogger('nutanix-api-client')
        Logger._logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Remove existing handlers
        Logger._logger.handlers.clear()
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.setFormatter(file_formatter)
        Logger._logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        console_handler.setFormatter(console_formatter)
        Logger._logger.addHandler(console_handler)
    
    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get the logger instance."""
        if cls._instance is None or cls._logger is None:
            raise RuntimeError("Logger not initialized. Call Logger.__init__() first.")
        return cls._logger
    
    @classmethod
    def initialize(cls, log_file: Path, log_level: str = 'INFO',
                  max_size_mb: int = 10, backup_count: int = 5):
        """
        Initialize the logger (convenience method).
        
        Args:
            log_file: Path to log file
            log_level: Logging level
            max_size_mb: Maximum log file size in MB
            backup_count: Number of backup files to keep
            
        Returns:
            Logger instance
        """
        if cls._instance is not None:
            return cls._instance
        
        instance = cls(log_file, log_level, max_size_mb, backup_count)
        cls._instance = instance
        return instance


def get_logger() -> logging.Logger:
    """
    Convenience function to get the logger.
    
    Returns:
        Configured logger instance
    """
    return Logger.get_logger()
