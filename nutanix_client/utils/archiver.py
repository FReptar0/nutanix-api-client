"""
Utility functions for Nutanix API Client.
Provides file handling, archiving, and helper functions.
"""

import os
import sys
import shutil
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class FileArchiver:
    """Handles file archiving operations."""
    
    def __init__(self, success_path: Path, error_path: Path):
        """
        Initialize file archiver.
        
        Args:
            success_path: Path to success archive directory
            error_path: Path to error archive directory
        """
        self.success_path = success_path
        self.error_path = error_path
        self.logger = None
        
        # Ensure archive directories exist
        self.success_path.mkdir(parents=True, exist_ok=True)
        self.error_path.mkdir(parents=True, exist_ok=True)
    
    def _get_logger(self):
        """Lazy logger initialization."""
        if self.logger is None:
            from nutanix_client.core.logger import get_logger
            self.logger = get_logger()
        return self.logger
    
    def archive_success(self, file_path: Path) -> Path:
        """
        Archive a successfully processed file.
        
        Args:
            file_path: Path to file to archive
            
        Returns:
            Path to archived file
        """
        return self._archive_file(file_path, self.success_path, "success")
    
    def archive_error(self, file_path: Path, error_message: Optional[str] = None) -> Path:
        """
        Archive a file that failed processing.
        
        Args:
            file_path: Path to file to archive
            error_message: Optional error message to save alongside file
            
        Returns:
            Path to archived file
        """
        archived_file = self._archive_file(file_path, self.error_path, "error")
        
        # Save error log if provided
        if error_message:
            error_log_path = archived_file.with_suffix('.error.txt')
            try:
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write(f"Error occurred at: {datetime.now().isoformat()}\n")
                    f.write(f"Original file: {file_path}\n")
                    f.write(f"\nError message:\n{error_message}\n")
                self._get_logger().debug(f"Saved error log: {error_log_path}")
            except Exception as e:
                self._get_logger().warning(f"Could not save error log: {e}")
        
        return archived_file
    
    def _archive_file(self, file_path: Path, archive_dir: Path, 
                     archive_type: str) -> Path:
        """
        Archive a file to the specified directory with timestamp.
        
        Args:
            file_path: Path to file to archive
            archive_dir: Destination archive directory
            archive_type: Type of archive (for logging)
            
        Returns:
            Path to archived file
        """
        try:
            # Generate archived filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            archived_path = archive_dir / archived_filename
            
            # Move file to archive
            shutil.move(str(file_path), str(archived_path))
            
            self._get_logger().info(
                f"Archived file to {archive_type}: {file_path.name} -> {archived_path}"
            )
            
            return archived_path
            
        except Exception as e:
            self._get_logger().error(f"Failed to archive file {file_path}: {e}")
            raise
    
    def cleanup_old_archives(self, days: int, dry_run: bool = False) -> tuple[int, int]:
        """
        Delete archived files older than specified days.
        
        Args:
            days: Delete files older than this many days
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (files_deleted, total_size_freed_bytes)
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        files_deleted = 0
        size_freed = 0
        
        self._get_logger().info(
            f"Cleaning up archives older than {days} days "
            f"(before {cutoff_date.strftime('%Y-%m-%d')})"
        )
        
        for archive_dir in [self.success_path, self.error_path]:
            if not archive_dir.exists():
                continue
            
            for file_path in archive_dir.glob('*'):
                if not file_path.is_file():
                    continue
                
                # Check file modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if mtime < cutoff_date:
                    file_size = file_path.stat().st_size
                    
                    if dry_run:
                        self._get_logger().info(
                            f"Would delete: {file_path} "
                            f"({file_size / 1024:.1f} KB, modified {mtime.strftime('%Y-%m-%d')})"
                        )
                    else:
                        try:
                            file_path.unlink()
                            self._get_logger().info(f"Deleted: {file_path}")
                            files_deleted += 1
                            size_freed += file_size
                        except Exception as e:
                            self._get_logger().error(f"Failed to delete {file_path}: {e}")
        
        if not dry_run:
            self._get_logger().info(
                f"Cleanup complete: {files_deleted} files deleted, "
                f"{size_freed / 1024 / 1024:.2f} MB freed"
            )
        else:
            self._get_logger().info(f"Dry run: {files_deleted} files would be deleted")
        
        return files_deleted, size_freed


def validate_xml_file(file_path: Path) -> bool:
    """
    Validate that a file exists and appears to be XML.
    
    Args:
        file_path: Path to file to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        from nutanix_client.core.logger import get_logger
        logger = get_logger()
    except:
        # Logger not initialized yet, just use print
        logger = None
    
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        if logger:
            logger.error(msg)
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
        return False
    
    if not file_path.is_file():
        msg = f"Not a file: {file_path}"
        if logger:
            logger.error(msg)
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
        return False
    
    # Check file extension
    if file_path.suffix.lower() not in ['.xml', '.txt']:
        msg = f"File does not have .xml extension: {file_path}"
        if logger:
            logger.warning(msg)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)
    
    # Basic check for XML content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if not (first_line.startswith('<?xml') or first_line.startswith('<')):
                msg = f"File does not appear to be XML: {file_path}"
                if logger:
                    logger.error(msg)
                else:
                    print(f"ERROR: {msg}", file=sys.stderr)
                return False
    except Exception as e:
        msg = f"Error reading file {file_path}: {e}"
        if logger:
            logger.error(msg)
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
        return False
    
    return True


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    try:
        return file_path.stat().st_size / 1024 / 1024
    except Exception:
        return 0.0


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
