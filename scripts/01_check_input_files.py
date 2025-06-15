#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_check_input_files.py
------------------------------------
Validates input files for the GPX workflow pipeline.
Checks file existence, readability, and expected column structure.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "01_check_input_files.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Input validation for GPX workflow pipeline with comprehensive performance tracking"
LAST_UPDATED = "2025-06-09"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Original version as 'check_input_files.py'
v1.1.0 (2025-06-07): Standardized header, renamed to 01_, improved error handling
v2.0.0 (2025-06-09): Enhanced metadata system with validation performance tracking embedded in CSV headers
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "input_validation"
INPUT_FILE_PATTERN = "*.csv"
OUTPUT_FILE_PATTERN = "validation_report.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0"
]

# === PERFORMANCE TRACKING ===
TRACK_VALIDATION_PERFORMANCE = True
TRACK_FILE_ANALYSIS = True
TRACK_DATA_QUALITY_METRICS = True

# === IMPORTS ===
import pandas as pd
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# === PERFORMANCE TRACKING GLOBALS ===
validation_stats = {
    'start_time': None,
    'files_checked': 0,
    'files_passed': 0,
    'files_failed': 0,
    'total_data_points': 0,
    'total_file_size_mb': 0,
    'validation_duration': 0,
    'file_read_duration': 0,
    'column_check_duration': 0,
    'data_quality_issues': 0,
    'processing_stages': {}
}

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print(f"Validation Tracking: {TRACK_VALIDATION_PERFORMANCE}")
    print("=" * 50)

def log_stage(stage_name: str, duration: float = None, details: dict = None):
    """Log processing stage for performance tracking."""
    validation_stats['processing_stages'][stage_name] = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'details': details or {}
    }

def save_validation_metadata_to_csv_header(results_df: pd.DataFrame, output_csv_path: str, metadata: dict):
    """Save validation performance metadata as CSV header comments."""
    if not TRACK_VALIDATION_PERFORMANCE:
        return results_df
    
    # Calculate total processing time
    total_time = time.time() - validation_stats['start_time'] if validation_stats['start_time'] else 0
    
    # Calculate performance metrics
    validation_efficiency = round(validation_stats['files_checked'] / max(total_time, 0.001), 1)
    validation_success_rate = round((validation_stats['files_passed'] / max(validation_stats['files_checked'], 1)) * 100, 1)
    
    # Create metadata header as comments
    metadata_lines = [
        "# Input Validation Performance Metadata",
        f"# Script: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Description: {SCRIPT_DESCRIPTION}",
        f"# Category: Input Validation + File Structure Analysis + Data Quality Check",
        "#",
        f"# Validation Performance:",
        f"# - Total Processing Time: {total_time:.3f} seconds",
        f"# - Files Checked: {validation_stats['files_checked']}",
        f"# - Files Passed: {validation_stats['files_passed']}",
        f"# - Files Failed: {validation_stats['files_failed']}",
        f"# - Validation Efficiency: {validation_efficiency} files/second",
        f"# - Success Rate: {validation_success_rate}%",
        "#",
        f"# Data Analysis:",
        f"# - Total Data Points: {validation_stats['total_data_points']}",
        f"# - Total File Size: {validation_stats['total_file_size_mb']:.2f} MB",
        f"# - Average File Size: {validation_stats['total_file_size_mb']/max(validation_stats['files_checked'], 1):.2f} MB",
        f"# - File Read Duration: {validation_stats['file_read_duration']:.3f}s",
        f"# - Column Check Duration: {validation_stats['column_check_duration']:.3f}s",
        "#",
        f"# Data Quality:",
        f"# - Quality Issues Found: {validation_stats['data_quality_issues']}",
        f"# - Data Quality Score: {max(0, 100 - validation_stats['data_quality_issues']*10)}%",
        "#",
        f"# Validation Config:",
        f"# - Config Compatibility: {CONFIG_COMPATIBILITY}",
        f"# - Pattern Checked: {INPUT_FILE_PATTERN}",
        f"# - Python Version Required: {PYTHON_VERSION_MIN}",
        "#"
    ]
    
    # Write CSV with metadata header
    try:
        with open(output_csv_path, 'w', encoding='utf-8') as f:
            # Write metadata as comments
            for line in metadata_lines:
                f.write(line + '\n')
            
            # Write CSV data
            results_df.to_csv(f, index=False)
            
        print(f"[Metadata] Validation metadata embedded in CSV header: {output_csv_path}")
        
    except Exception as e:
        print(f"[Error] Could not write CSV with metadata header: {e}")
        # Fallback: save without metadata
        results_df.to_csv(output_csv_path, index=False, encoding='utf-8')
    
    return results_df

def check_file(filepath, expected_columns=None, file_description=""):
    """
    Validates a CSV file for existence, readability and column structure.
    
    Args:
        filepath (str): Path to the CSV file
        expected_columns (list): List of expected column names
        file_description (str): Human-readable description of the file
    
    Returns:
        dict: Validation results with performance metrics
    """
    file_start_time = time.time()
    print(f"\n=== CHECKING: {file_description or filepath} ===")
    
    result = {
        'file_path': filepath,
        'file_description': file_description,
        'status': 'error',
        'file_size_mb': 0,
        'total_rows': 0,
        'total_columns': 0,
        'columns_found': [],
        'missing_columns': [],
        'extra_columns': [],
        'data_points': 0,
        'has_data': False,
        'read_duration': 0,
        'column_check_duration': 0,
        'quality_issues': []
    }
    
    validation_stats['files_checked'] += 1
    
    # Check file existence
    if not os.path.exists(filepath):
        print(f"✗ File not found: {filepath}")
        result['quality_issues'].append('file_not_found')
        validation_stats['data_quality_issues'] += 1
        validation_stats['files_failed'] += 1
        return result
    
    # Check file size
    file_size = os.path.getsize(filepath)
    file_size_mb = file_size / (1024 * 1024)
    result['file_size_mb'] = round(file_size_mb, 3)
    validation_stats['total_file_size_mb'] += file_size_mb
    print(f"✓ File found ({file_size:,} bytes, {file_size_mb:.2f} MB)")
    
    try:
        # Test reading the file
        read_start = time.time()
        df_sample = pd.read_csv(filepath, nrows=5, comment='#')  # Skip comment lines
        df_full = pd.read_csv(filepath, comment='#')
        read_duration = time.time() - read_start
        
        result['read_duration'] = round(read_duration, 3)
        validation_stats['file_read_duration'] += read_duration
        
        print(f"✓ File readable (read in {read_duration:.3f}s)")
        
        result['total_rows'] = len(df_full)
        result['total_columns'] = len(df_sample.columns)
        result['columns_found'] = list(df_sample.columns)
        result['data_points'] = len(df_full) * len(df_sample.columns)
        validation_stats['total_data_points'] += result['data_points']
        
        print(f"  Total rows: {result['total_rows']:,}")
        print(f"  Total columns: {result['total_columns']}")
        print(f"  Data points: {result['data_points']:,}")
        print(f"  Columns: {result['columns_found']}")
        
        # Show sample data
        if len(df_sample) > 0:
            print(f"\n  Sample data (first 3 rows):")
            print(df_sample.head(3).to_string())
        
        # Check expected columns
        column_check_start = time.time()
        if expected_columns:
            missing_cols = set(expected_columns) - set(df_sample.columns)
            extra_cols = set(df_sample.columns) - set(expected_columns)
            
            result['missing_columns'] = sorted(missing_cols)
            result['extra_columns'] = sorted(extra_cols)
            
            if missing_cols:
                print(f"  ✗ Missing required columns: {result['missing_columns']}")
                result['quality_issues'].append('missing_columns')
                validation_stats['data_quality_issues'] += len(missing_cols)
                validation_stats['files_failed'] += 1
                return result
            else:
                print(f"  ✓ All required columns present")
            
            if extra_cols:
                print(f"  ℹ Additional columns found: {result['extra_columns']}")
        
        column_check_duration = time.time() - column_check_start
        result['column_check_duration'] = round(column_check_duration, 3)
        validation_stats['column_check_duration'] += column_check_duration
        
        # Check for empty dataframe
        if len(df_full) == 0:
            print(f"  ✗ File is empty (no data rows)")
            result['quality_issues'].append('empty_file')
            validation_stats['data_quality_issues'] += 1
            validation_stats['files_failed'] += 1
            return result
        
        result['has_data'] = True
        result['status'] = 'ok'
        validation_stats['files_passed'] += 1
        
        # Log successful file processing
        log_stage(f"file_validation_{os.path.basename(filepath)}", time.time() - file_start_time, {
            'file_size_mb': result['file_size_mb'],
            'data_points': result['data_points'],
            'columns': result['total_columns']
        })
        
        return result
        
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        result['quality_issues'].append(f'read_error: {str(e)}')
        validation_stats['data_quality_issues'] += 1
        validation_stats['files_failed'] += 1
        return result

def get_default_input_files():
    """
    Returns default input files configuration for validation.
    This could be loaded from config.yaml in the future.
    """
    return {
        "geocoded_optimized": {
            "pattern": "output/*_track_data_with_location_optimized.csv",
            "description": "Geocoded and API-optimized track data",
            "required_columns": ["Latitude", "Longitude", "original_index", "Street", "City"]
        },
        "elevation_data": {
            "pattern": "output/*_track_data_full_with_elevation.csv", 
            "description": "Full track data with elevation information",
            "required_columns": ["Distanz (km)", "Elevation (m)"]
        },
        "surface_data": {
            "pattern": "output/*_surface_data.csv",
            "description": "Surface type data from Overpass API",
            "required_columns": ["Surface", "original_index"]
        }
    }

def find_files_by_pattern(pattern):
    """Find files matching a pattern."""
    from glob import glob
    return glob(pattern)

def main():
    """Main validation function."""
    validation_stats['start_time'] = time.time()
    print_script_info()
    
    # Get input file configurations
    input_configs = get_default_input_files()
    
    validation_results = []
    all_ok = True
    
    print(f"\nStarting validation of {len(input_configs)} file types...")
    
    for config_name, config in input_configs.items():
        print(f"\n{'='*20} {config_name.upper().replace('_', ' ')} {'='*20}")
        
        # Find files matching pattern
        matching_files = find_files_by_pattern(config["pattern"])
        
        if not matching_files:
            print(f"✗ No files found matching pattern: {config['pattern']}")
            validation_results.append({
                'config_name': config_name,
                'file_path': config['pattern'],
                'file_description': config.get('description', ''),
                'status': 'not_found',
                'file_size_mb': 0,
                'total_rows': 0,
                'total_columns': 0,
                'data_points': 0,
                'has_data': False,
                'quality_issues': 'no_files_found'
            })
            all_ok = False
            continue
        
        print(f"Found {len(matching_files)} matching files:")
        
        for filepath in matching_files:
            file_result = check_file(
                filepath, 
                config.get("required_columns"), 
                config.get("description", "")
            )
            
            file_result['config_name'] = config_name
            validation_results.append(file_result)
            
            if file_result['status'] != 'ok':
                all_ok = False
    
    # Create results DataFrame
    results_df = pd.DataFrame(validation_results)
    
    # Summary
    print(f"\n{'='*50}")
    print("VALIDATION SUMMARY")
    print(f"{'='*50}")
    
    summary_by_config = {}
    for result in validation_results:
        config_name = result['config_name']
        if config_name not in summary_by_config:
            summary_by_config[config_name] = {'ok': 0, 'error': 0, 'not_found': 0}
        summary_by_config[config_name][result['status']] += 1
    
    for config_name, counts in summary_by_config.items():
        total_files = sum(counts.values())
        status_symbol = "✓" if counts['error'] == 0 and counts['not_found'] == 0 else "✗"
        print(f"{status_symbol} {config_name.upper().replace('_', ' ')}: {counts['ok']}/{total_files} files OK")
        
        # Show individual file results
        config_results = [r for r in validation_results if r['config_name'] == config_name]
        for result in config_results:
            if result['status'] == 'ok':
                file_symbol = "  ✓"
                details = f"({result['total_rows']:,} rows, {result['file_size_mb']:.2f} MB)"
            else:
                file_symbol = "  ✗"
                details = f"({result['status']})"
            
            filename = os.path.basename(result['file_path']) if result['status'] != 'not_found' else result['file_path']
            print(f"{file_symbol} {filename} {details}")
    
    # Save results to CSV with metadata
    output_csv_path = "validation_report.csv"
    metadata = {
        'total_configs': len(input_configs),
        'total_files_found': len([r for r in validation_results if r['status'] != 'not_found']),
        'overall_success': all_ok
    }
    
    save_validation_metadata_to_csv_header(results_df, output_csv_path, metadata)
    
    print(f"\n{'='*50}")
    print(f"[Performance] Validation completed in {time.time() - validation_stats['start_time']:.3f}s")
    print(f"[Performance] Files checked: {validation_stats['files_checked']}, Success rate: {validation_stats['files_passed']}/{validation_stats['files_checked']}")
    print(f"[Performance] Total data points analyzed: {validation_stats['total_data_points']:,}")
    print(f"[Results] Detailed validation report saved: {output_csv_path}")
    
    if all_ok:
        print("✓ ALL INPUT FILES VALIDATION PASSED")
        print("The GPX workflow pipeline should run successfully with these files.")
        return 0
    else:
        print("✗ INPUT FILE VALIDATION ISSUES FOUND")
        print("Please fix the issues before running the GPX workflow pipeline.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
