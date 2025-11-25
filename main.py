#!/usr/bin/env python3
"""
Nutanix API Client - Entry Point
A unified system for JWT generation, XML transformation, and API communication.

Author: FReptar0
"""

import sys

# Add package directory to path for proper imports
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from nutanix_client.cli import main

if __name__ == '__main__':
    sys.exit(main())
