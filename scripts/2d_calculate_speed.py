#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2d_calculate_speed.py
---------------------
Calculates point-to-point speed based on time and distance deltas
from the full track data. Adds speed columns to the CSV with
detailed algorithm performance tracking and optimization metrics.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "2d_calculate_speed.py"
SCRIPT_VERSION = "2.1.0"
SCRIPT_DESCRIPTION = "Speed calculation with integrated metadata system"
LAST_UPDATED = "2025-06-15"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.1.0 (pre-2025): Enhanced datetime parsing and error handling
v1.2.0 (2025-06-07): Standardized header, improved debug logging and speed calculation
v2.0.0 (2025-06-07): Enhanced metadata system with algorithm performance tracking and calculation optimization metrics
v2.1.0 (2025-06-15): Integrated unified metadata system with CSV_METADATA_TEMPLATE
- Removed custom metadata header generation
- Integrated with standardized CSV_METADATA_TEMPLATE system
- Streamlined performance tracking and metadata collection
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "speed_calculation"
INPUT_FILE_PATTERN = "*_track_data_full_with_elevation.csv"
OUTPUT_FILE_PATTERN = "*_track_data_full_with_speed.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "numpy>=1.20.0"
]

# === ALGORITHM CONFIGURATION ===
DEFAULT_ROLLING_WINDOW = 0
MAX_SPEED_THRESHOLD_KMH = 100  # Unrealistic speeds above this are clipped
TIME_PARSING_FORMATS = ["ISO8601", "mixed", "auto"]
SMOOTHING_METHODS = ["rolling_mean", "none"]

# === PERFORMANCE TRACKING ===
TRACK_ALGORITHM_PERFORMANCE = True
TRACK_CALCULATION_STAGES = True
TRACK_DATA_QUALITY_METRICS = True

import pandas as pd
import numpy as np
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

# === PERFORMANCE TRACKING GLOBALS ===
calculation_stats = {
    'start_time': None,
    'data_points_processed': 0,
    'time_parsing_method': None,
    'time_parsing_duration': 0,
    'speed_calculation_duration': 0,
    'smoothing_duration': 0,
    'data_quality_issues': 0,
    'extreme_speeds_clipped': 0,
    'zero_time_deltas': 0,
    'processing_stages': {}
}

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print(f"Max Speed Threshold: {MAX_SPEED_THRESHOLD_KMH} km/h")
    print(f"Algorithm Tracking: {TRACK_ALGORITHM_PERFORMANCE}")
    print("=" * 50)

def log_stage(stage_name: str, duration: float = None, details: dict = None):
    """Log processing stage for performance tracking."""
    calculation_stats['processing_stages'][stage_name] = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'details': details or {}
    }



def calculate_speed(input_csv_path: str, output_csv_path: str, rolling_window: int = 0):
    calculation_stats['start_time'] = time.time()
    print(f"[Info] Calculating speed for: {input_csv_path}")
    
    metadata = {
        'input_file': os.path.basename(input_csv_path),
        'rolling_window': rolling_window,
        'smoothing_enabled': rolling_window > 1
    }
    
    # --- CSV Loading Stage ---
    stage_start = time.time()
    try:
        # Erstmal ohne parse_dates laden, um den Datentyp zu prüfen
        df = pd.read_csv(input_csv_path, comment='#')
        
        if df.empty:
            print(f"[Warning] Input CSV is empty: {input_csv_path}")
            # Create empty CSV with metadata
            write_csv_with_metadata(
                dataframe=df,
                output_path=output_csv_path,
                script_name=SCRIPT_NAME,
                script_version=SCRIPT_VERSION,
                input_files=[input_csv_path],
                processing_parameters={'error': 'empty_input'},
                additional_metadata={'processing_error': 'Input CSV is empty', 'data_points_processed': 0}
            )
            print(f"[OK] Empty speed CSV with metadata saved: {output_csv_path}")
            sys.exit(0)

        calculation_stats['data_points_processed'] = len(df)
        metadata['input_columns'] = list(df.columns)
        
        # Debug: Prüfe Spalten und Datentypen
        print(f"[Debug] Verfügbare Spalten: {list(df.columns)}")
        print(f"[Debug] Datenpunkte: {len(df)}")
        
        if 'Time' not in df.columns or 'Strecke Delta (km)' not in df.columns:
            print("[Error] Required columns 'Time' or 'Strecke Delta (km)' not found in input CSV.")
            print(f"[Debug] Available columns: {list(df.columns)}")
            # Create CSV with error metadata
            write_csv_with_metadata(
                dataframe=df,
                output_path=output_csv_path,
                script_name=SCRIPT_NAME,
                script_version=SCRIPT_VERSION,
                input_files=[input_csv_path],
                processing_parameters={'error': 'missing_columns'},
                additional_metadata={'processing_error': 'Required columns missing', 'available_columns': list(df.columns)}
            )
            print(f"[Warning] Input copied to output as speed calculation not possible: {output_csv_path}")
            sys.exit(0)

        metadata['required_columns_present'] = True

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Laden der CSV: {input_csv_path} - {e}")
        sys.exit(1)

    log_stage("csv_loading", time.time() - stage_start, {
        'rows_loaded': len(df),
        'columns_detected': len(df.columns),
        'required_columns_present': metadata['required_columns_present']
    })

    # --- Time Parsing Stage ---
    time_parse_start = time.time()
    print(f"[Debug] Time Spalte Datentyp vor Konvertierung: {df['Time'].dtype}")
    print(f"[Debug] Erste 3 Time-Werte: {df['Time'].head(3).tolist()}")
    
    # Versuche verschiedene Datetime-Parsing-Methoden
    parsing_success = False
    for method in TIME_PARSING_FORMATS:
        try:
            if method == "ISO8601":
                df['Time'] = pd.to_datetime(df['Time'], format='ISO8601')
                calculation_stats['time_parsing_method'] = "ISO8601"
                print("[Debug] Time-Konvertierung mit ISO8601 Format erfolgreich")
                parsing_success = True
                break
            elif method == "mixed":
                df['Time'] = pd.to_datetime(df['Time'], format='mixed')
                calculation_stats['time_parsing_method'] = "mixed"
                print("[Debug] Time-Konvertierung mit mixed Format erfolgreich")
                parsing_success = True
                break
            elif method == "auto":
                df['Time'] = pd.to_datetime(df['Time'])
                calculation_stats['time_parsing_method'] = "auto"
                print("[Debug] Time-Konvertierung mit automatischem Parsing erfolgreich")
                parsing_success = True
                break
        except Exception as e:
            continue
    
    if not parsing_success:
        print(f"[Fehler] Konnte Time-Spalte mit keiner Methode konvertieren")
        print(f"[Debug] Beispiel Time-Werte: {df['Time'].head(5).tolist()}")
        sys.exit(1)
    
    calculation_stats['time_parsing_duration'] = time.time() - time_parse_start
    print(f"[Debug] Time Spalte Datentyp nach Konvertierung: {df['Time'].dtype}")

    log_stage("time_parsing", calculation_stats['time_parsing_duration'], {
        'parsing_method': calculation_stats['time_parsing_method'],
        'success': parsing_success
    })

    # --- Speed Calculation Stage ---
    speed_calc_start = time.time()
    
    # Zeitdifferenz berechnen
    df['TimeDelta (s)'] = df['Time'].diff().dt.total_seconds()
    df['TimeDelta (s)'] = df['TimeDelta (s)'].fillna(0)

    # Count zero time deltas (data quality issue)
    calculation_stats['zero_time_deltas'] = (df['TimeDelta (s)'] == 0).sum()
    calculation_stats['data_quality_issues'] += calculation_stats['zero_time_deltas']

    print(f"[Debug] TimeDelta berechnet. Min: {df['TimeDelta (s)'].min()}, Max: {df['TimeDelta (s)'].max()}")
    print(f"[Debug] Zero time deltas (data quality issue): {calculation_stats['zero_time_deltas']}")

    # Debug: Prüfe Strecke Delta Spalte
    print(f"[Debug] Strecke Delta Datentyp: {df['Strecke Delta (km)'].dtype}")
    print(f"[Debug] Strecke Delta Min/Max: {df['Strecke Delta (km)'].min()}/{df['Strecke Delta (km)'].max()}")

    # Geschwindigkeit (km/h)
    df['Geschwindigkeit (km/h)'] = np.where(
        df['TimeDelta (s)'] > 0,
        df['Strecke Delta (km)'] / (df['TimeDelta (s)'] / 3600.0),
        0
    )
    
    # Count extreme speeds before clipping
    extreme_speeds_mask = df['Geschwindigkeit (km/h)'] > MAX_SPEED_THRESHOLD_KMH
    calculation_stats['extreme_speeds_clipped'] = extreme_speeds_mask.sum()
    calculation_stats['data_quality_issues'] += calculation_stats['extreme_speeds_clipped']
    
    # Korrigiere extreme Werte
    df['Geschwindigkeit (km/h)'] = df['Geschwindigkeit (km/h)'].clip(upper=MAX_SPEED_THRESHOLD_KMH)
    
    # Calculate speed statistics
    speed_stats = df['Geschwindigkeit (km/h)'].describe()
    metadata['min_speed'] = round(speed_stats['min'], 2)
    metadata['max_speed'] = round(speed_stats['max'], 2)
    metadata['avg_speed'] = round(speed_stats['mean'], 2)
    metadata['speed_variance'] = round(df['Geschwindigkeit (km/h)'].var(), 2)
    
    calculation_stats['speed_calculation_duration'] = time.time() - speed_calc_start
    
    print(f"[Debug] Geschwindigkeit berechnet. Min: {metadata['min_speed']}, Max: {metadata['max_speed']}, Avg: {metadata['avg_speed']}")
    print(f"[Debug] Extreme speeds clipped: {calculation_stats['extreme_speeds_clipped']}")

    log_stage("speed_calculation", calculation_stats['speed_calculation_duration'], {
        'min_speed': metadata['min_speed'],
        'max_speed': metadata['max_speed'],
        'avg_speed': metadata['avg_speed'],
        'extreme_speeds_clipped': calculation_stats['extreme_speeds_clipped']
    })

    # --- Smoothing Stage (optional) ---
    smoothing_start = time.time()
    if rolling_window > 1:
        df[f'Geschwindigkeit geglättet (km/h, W{rolling_window})'] = df['Geschwindigkeit (km/h)'].rolling(
            window=rolling_window, center=True, min_periods=1
        ).mean()
        print(f"[Debug] Geglättete Geschwindigkeit mit Fenster {rolling_window} berechnet")
        
        # Calculate smoothing effectiveness
        original_variance = df['Geschwindigkeit (km/h)'].var()
        smoothed_variance = df[f'Geschwindigkeit geglättet (km/h, W{rolling_window})'].var()
        smoothing_effectiveness = round((1 - smoothed_variance / original_variance) * 100, 1) if original_variance > 0 else 0
        
        log_stage("smoothing_applied", calculation_stats['smoothing_duration'], {
            'rolling_window': rolling_window,
            'variance_reduction_percent': smoothing_effectiveness
        })
    else:
        log_stage("smoothing_skipped", 0, {'reason': 'rolling_window <= 1'})
    
    calculation_stats['smoothing_duration'] = time.time() - smoothing_start

    # --- Output Stage ---
    output_start = time.time()
    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Calculate total processing time
        total_time = time.time() - calculation_stats['start_time'] if calculation_stats['start_time'] else 0
        
        # Calculate performance metrics
        points_per_second = round(calculation_stats['data_points_processed'] / max(total_time, 0.001), 1)
        data_quality_score = round((1 - calculation_stats['data_quality_issues'] / max(calculation_stats['data_points_processed'], 1)) * 100, 1)
        
        # Prepare processing parameters
        processing_parameters = {
            'rolling_window_size': rolling_window,
            'max_speed_threshold_kmh': MAX_SPEED_THRESHOLD_KMH,
            'time_parsing_method': calculation_stats['time_parsing_method'],
            'smoothing_enabled': rolling_window > 1
        }
        
        # Prepare additional metadata
        additional_metadata = {
            'total_processing_time_sec': round(total_time, 3),
            'data_points_processed': calculation_stats['data_points_processed'],
            'processing_rate_points_per_sec': points_per_second,
            'data_quality_score': data_quality_score,
            'speed_calculation_duration_sec': round(calculation_stats['speed_calculation_duration'], 3),
            'smoothing_duration_sec': round(calculation_stats['smoothing_duration'], 3),
            'zero_time_deltas_count': calculation_stats['zero_time_deltas'],
            'extreme_speeds_clipped_count': calculation_stats['extreme_speeds_clipped'],
            'total_quality_issues': calculation_stats['data_quality_issues'],
            'min_speed_kmh': metadata['min_speed'],
            'max_speed_kmh': metadata['max_speed'],
            'avg_speed_kmh': metadata['avg_speed'],
            'speed_variance': metadata['speed_variance'],
            'required_columns_present': metadata['required_columns_present'],
            'input_columns_count': len(metadata['input_columns']),
            'algorithm_performance_tracking': TRACK_ALGORITHM_PERFORMANCE
        }
        
        # Save CSV with integrated metadata
        write_csv_with_metadata(
            dataframe=df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters=processing_parameters,
            api_metadata=None,
            additional_metadata=additional_metadata,
            float_format='%.3f'
        )
        
        print(f"[OK] CSV with speed data and metadata saved: {output_csv_path}")
        print(f"[Info] Rows processed: {len(df)}")
        print(f"[Performance] Processing time: {total_time:.3f}s, Quality score: {data_quality_score}%")

    except Exception as e:
        print(f"[Error] Could not write output CSV: {output_csv_path} - {e}")
        sys.exit(1)

    log_stage("output_saving", time.time() - output_start, {
        'output_rows': len(df),
        'output_columns': len(df.columns)
    })

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Calculate speed from track data.")
    parser.add_argument("input_csv", help="Path to the input track CSV (from 2c).")
    parser.add_argument("output_csv", help="Path to save the output CSV with speed data.")
    parser.add_argument("--rolling-window", type=int, default=0, help="Window size for rolling mean of speed (0 to disable).")
    args = parser.parse_args()

    calculate_speed(args.input_csv, args.output_csv, args.rolling_window)
