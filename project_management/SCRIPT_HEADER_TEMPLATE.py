#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMPLATE_script_header.py
------------------------------------
This is the standardized header template for all GPX Workflow scripts.
Copy this header to all scripts and adapt the metadata.
"""

# === SCRIPT METADATA (MANDATORY) ===
SCRIPT_NAME = "XX_script_name.py"          # Exact filename
SCRIPT_VERSION = "1.0.0"                   # Semantic versioning: Major.Minor.Patch
SCRIPT_DESCRIPTION = "Brief description of what this script does"
LAST_UPDATED = "2025-06-07"                # ISO format: YYYY-MM-DD
AUTHOR = "Markus"                          # Author name
CONFIG_COMPATIBILITY = "2.1"               # Which config.yaml version is required

# === CHANGELOG (OPTIONAL BUT RECOMMENDED) ===
CHANGELOG = """
v1.0.0 (2025-06-07): Initial version with standardized header
v1.1.0 (TBD): [Future improvements planned]
"""

# === DEPENDENCIES & REQUIREMENTS (OPTIONAL) ===
PYTHON_VERSION_MIN = "3.8"                # Minimum Python version
REQUIRED_PACKAGES = [                      # Required pip packages
    "pandas>=1.3.0",
    "requests>=2.25.0",
    # Add other requirements as needed
]

# === SCRIPT CONFIGURATION (OPTIONAL) ===
DEFAULT_CONFIG_SECTION = "api_simplification"  # Which config.yaml section this script uses
INPUT_FILE_PATTERN = "*.gpx"              # Expected input file pattern
OUTPUT_FILE_PATTERN = "2_*_track_data_full.csv"  # Expected output file pattern

# === IMPORTS ===
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add other imports as needed for the specific script

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata - useful for debugging and logging."""
    print(f"=== {SCRIPT_NAME} ===")
    print(f"Version: {SCRIPT_VERSION}")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def check_config_compatibility(config_version):
    """Check if the loaded config.yaml version is compatible."""
    try:
        config_major = float(config_version.split('.')[0])
        required_major = float(CONFIG_COMPATIBILITY.split('.')[0])
        
        if config_major < required_major:
            print(f"[WARNING] Config version {config_version} may be incompatible.")
            print(f"[WARNING] This script requires config version {CONFIG_COMPATIBILITY} or higher.")
            return False
        return True
    except (ValueError, AttributeError):
        print(f"[WARNING] Could not parse config version: {config_version}")
        return False

def main():
    """Main function - adapt this for your specific script."""
    print_script_info()
    
    # Your script logic goes here
    print(f"[INFO] {SCRIPT_NAME} executed successfully")

if __name__ == "__main__":
    main()
