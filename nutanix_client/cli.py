"""
CLI module for Nutanix API Client.
Handles all command-line interface operations.
"""

import sys
import argparse
import time
from pathlib import Path
from typing import Optional

from nutanix_client.core.config import Config, ConfigError
from nutanix_client.core.logger import Logger, get_logger
from nutanix_client.handlers.jwt_handler import JWTHandler, JWTError
from nutanix_client.handlers.xml_transformer import XMLTransformer, XMLTransformError
from nutanix_client.handlers.api_client import APIClient, APIError
from nutanix_client.utils.archiver import (
    FileArchiver,
    validate_xml_file,
    format_duration,
)


# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_API_ERROR = 3
EXIT_NETWORK_ERROR = 4


class NutanixAPIClient:
    """Main application controller."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the application.
        
        Args:
            config_path: Optional path to config file
        """
        try:
            # Load configuration
            self.config = Config(config_path)
        except ConfigError as e:
            print(f"Configuration Error: {e}", file=sys.stderr)
            sys.exit(EXIT_CONFIG_ERROR)
        except Exception as e:
            print(f"Initialization Error: {e}", file=sys.stderr)
            sys.exit(EXIT_CONFIG_ERROR)
        
        # Initialize logger (must be done before other components)
        try:
            Logger.initialize(
                self.config.log_file,
                self.config.log_level,
                self.config.log_max_size_mb,
                self.config.log_backup_count
            )
            self.logger = get_logger()
            
            self.logger.info("=" * 70)
            self.logger.info("Nutanix API Client Starting")
            self.logger.info(f"Environment: {self.config.environment.upper()}")
            self.logger.info(f"API URL: {self.config.api_url}")
            self.logger.info("=" * 70)
        except Exception as e:
            print(f"Logger Initialization Error: {e}", file=sys.stderr)
            sys.exit(EXIT_CONFIG_ERROR)
        
        # Ensure required directories exist
        try:
            self.config.ensure_directories()
        except Exception as e:
            self.logger.error(f"Failed to create directories: {e}")
            sys.exit(EXIT_CONFIG_ERROR)
        
        # Initialize components
        try:
            self.jwt_handler = JWTHandler(
                self.config.jwt_private_key_path,
                self.config.jwt_issuer,
                self.config.jwt_customer_id,
                self.config.jwt_token_expiry_minutes
            )
            
            self.xml_transformer = XMLTransformer()
            
            self.api_client = APIClient(
                self.config.api_url,
                self.config.api_timeout,
                self.config.api_max_retries,
                self.config.api_retry_delay
            )
            
            self.archiver = FileArchiver(
                self.config.archive_success_path,
                self.config.archive_error_path
            )
        except JWTError as e:
            self.logger.error(f"JWT Handler initialization failed: {e}")
            sys.exit(EXIT_AUTH_ERROR)
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            sys.exit(EXIT_CONFIG_ERROR)
    
    def process_file(self, input_file: Path) -> int:
        """
        Process a single XML file.
        
        Args:
            input_file: Path to input XML file
            
        Returns:
            Exit code
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing file: {input_file}")
            
            # Validate input file
            if not validate_xml_file(input_file):
                raise Exception("Input file validation failed")
            
            # Step 1: Generate JWT token
            self.logger.info("Step 1/4: Generating JWT token...")
            try:
                jwt_token = self.jwt_handler.generate_token()
            except JWTError as e:
                self.logger.error(f"JWT generation failed: {e}")
                self.archiver.archive_error(input_file, str(e))
                return EXIT_AUTH_ERROR
            
            # Step 2: Transform XML (add SOAP envelope if needed)
            self.logger.info("Step 2/4: Transforming XML...")
            try:
                transformed_xml = self.xml_transformer.transform_file(input_file)
            except XMLTransformError as e:
                self.logger.error(f"XML transformation failed: {e}")
                self.archiver.archive_error(input_file, str(e))
                return EXIT_CONFIG_ERROR
            
            # Step 3: Post to API
            self.logger.info("Step 3/4: Posting to Nutanix API...")
            try:
                response_xml = self.api_client.post_purchase_order(jwt_token, transformed_xml)
            except APIError as e:
                error_msg = str(e)
                self.logger.error(f"API request failed: {error_msg}")
                self.archiver.archive_error(input_file, error_msg)
                
                # Determine appropriate exit code
                if "Authentication" in error_msg or "401" in error_msg:
                    return EXIT_AUTH_ERROR
                elif "Connection" in error_msg or "Timeout" in error_msg:
                    return EXIT_NETWORK_ERROR
                else:
                    return EXIT_API_ERROR
            
            # Step 4: Save response and archive
            self.logger.info("Step 4/4: Saving response and archiving...")
            
            # Extract PO number for response filename
            po_number = self.api_client.extract_po_number(transformed_xml)
            
            # Save response
            response_file = self.api_client.save_response(
                response_xml,
                self.config.output_path,
                po_number
            )
            
            # Archive processed file
            archived_file = self.archiver.archive_success(input_file)
            
            # Success summary
            duration = time.time() - start_time
            self.logger.info("=" * 70)
            self.logger.info("✓ Processing completed successfully")
            self.logger.info(f"  Duration: {format_duration(duration)}")
            self.logger.info(f"  PO Number: {po_number or 'N/A'}")
            self.logger.info(f"  Response: {response_file}")
            self.logger.info(f"  Archived: {archived_file}")
            self.logger.info("=" * 70)
            
            return EXIT_SUCCESS
            
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            try:
                self.archiver.archive_error(input_file, str(e))
            except Exception as archive_error:
                self.logger.error(f"Failed to archive error file: {archive_error}")
            
            return EXIT_CONFIG_ERROR
    
    def watch_directory(self) -> int:
        """
        Watch input directory for new files and process them.
        
        Returns:
            Exit code (only returns on error or interruption)
        """
        self.logger.info(f"Watching directory: {self.config.input_path}")
        self.logger.info("Press Ctrl+C to stop")
        
        processed_files = set()
        
        try:
            while True:
                # Find all XML files in input directory
                xml_files = list(self.config.input_path.glob('*.xml'))
                
                for xml_file in xml_files:
                    if xml_file in processed_files:
                        continue
                    
                    self.logger.info(f"New file detected: {xml_file.name}")
                    exit_code = self.process_file(xml_file)
                    
                    if exit_code == EXIT_SUCCESS:
                        processed_files.add(xml_file)
                    
                    # Small delay between files
                    time.sleep(1)
                
                # Wait before checking again
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Watch mode interrupted by user")
            return EXIT_SUCCESS
        except Exception as e:
            self.logger.error(f"Watch mode error: {e}", exc_info=True)
            return EXIT_CONFIG_ERROR


def cmd_process(args, client: NutanixAPIClient) -> int:
    """Handle the 'process' command."""
    if args.watch:
        return client.watch_directory()
    elif args.input:
        input_file = Path(args.input)
        return client.process_file(input_file)
    else:
        print("Error: Either --input or --watch must be specified", file=sys.stderr)
        return EXIT_CONFIG_ERROR


def cmd_cleanup(args, client: NutanixAPIClient) -> int:
    """Handle the 'cleanup' command."""
    logger = get_logger()
    
    days = args.older_than
    dry_run = args.dry_run
    
    logger.info(f"Archive cleanup: deleting files older than {days} days")
    if dry_run:
        logger.info("DRY RUN MODE - No files will be deleted")
    
    files_deleted, size_freed = client.archiver.cleanup_old_archives(days, dry_run)
    
    if dry_run:
        print(f"\nDry run complete: {files_deleted} files would be deleted")
    else:
        print(f"\nCleanup complete:")
        print(f"  Files deleted: {files_deleted}")
        print(f"  Space freed: {size_freed / 1024 / 1024:.2f} MB")
    
    return EXIT_SUCCESS


def cmd_validate(args, client: NutanixAPIClient) -> int:
    """Handle the 'validate' command."""
    logger = get_logger()
    
    print("Validating configuration...")
    print(f"✓ Configuration loaded successfully")
    print(f"✓ Environment: {client.config.environment}")
    print(f"✓ API URL: {client.config.api_url}")
    print(f"✓ Private key: {client.config.jwt_private_key_path}")
    print(f"✓ Input directory: {client.config.input_path}")
    print(f"✓ Output directory: {client.config.output_path}")
    print(f"✓ Archive directories configured")
    
    # Test JWT generation
    try:
        print("\nTesting JWT generation...")
        token = client.jwt_handler.generate_token()
        print(f"✓ JWT token generated successfully")
        print(f"  Token preview: {token[:50]}...")
    except Exception as e:
        print(f"✗ JWT generation failed: {e}")
        return EXIT_AUTH_ERROR
    
    print("\n✓ All validations passed")
    return EXIT_SUCCESS


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Nutanix API Client - Unified XML processing and API communication',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process a single file
  %(prog)s process --input order.xml
  
  # Watch directory for new files
  %(prog)s process --watch
  
  # Clean up old archives
  %(prog)s cleanup --older-than 30
  
  # Validate configuration
  %(prog)s validate
        '''
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration file (default: config/config.yaml)',
        default=None
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process XML files')
    process_group = process_parser.add_mutually_exclusive_group(required=True)
    process_group.add_argument(
        '--input', '-i',
        help='Input XML file to process'
    )
    process_group.add_argument(
        '--watch',
        action='store_true',
        help='Watch input directory for new files'
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old archive files')
    cleanup_parser.add_argument(
        '--older-than',
        type=int,
        default=30,
        help='Delete files older than N days (default: 30)'
    )
    cleanup_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without deleting'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return EXIT_CONFIG_ERROR
    
    # Initialize client
    try:
        client = NutanixAPIClient(args.config)
    except SystemExit as e:
        return e.code
    
    # Execute command
    if args.command == 'process':
        return cmd_process(args, client)
    elif args.command == 'cleanup':
        return cmd_cleanup(args, client)
    elif args.command == 'validate':
        return cmd_validate(args, client)
    else:
        parser.print_help()
        return EXIT_CONFIG_ERROR


if __name__ == '__main__':
    sys.exit(main())
