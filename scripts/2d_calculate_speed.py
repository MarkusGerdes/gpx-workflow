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
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Speed calculation from time and distance deltas with smoothing options and performance tracking"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.1.0 (pre-2025): Enhanced datetime parsing and error handling
v1.2.0 (2025-06-07): Standardized header, improved debug logging and speed calculation
v2.0.0 (2025-06-07): Enhanced metadata system with algorithm performance tracking and calculation optimization metrics
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

def save_performance_metadata_to_csv_header(df: pd.DataFrame, output_csv_path: str, metadata: dict):
    """Save speed calculation performance metadata as CSV header comments."""
    if not TRACK_ALGORITHM_PERFORMANCE:
        return df
    
    # Calculate total processing time
    total_time = time.time() - calculation_stats['start_time'] if calculation_stats['start_time'] else 0
    
    # Calculate performance metrics
    points_per_second = round(calculation_stats['data_points_processed'] / max(total_time, 0.001), 1)
    data_quality_score = round((1 - calculation_stats['data_quality_issues'] / max(calculation_stats['data_points_processed'], 1)) * 100, 1)
    
    # Create metadata header as comments
    metadata_lines = [
        "# Speed Calculation Performance Metadata",
        f"# Script: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Description: {SCRIPT_DESCRIPTION}",
        f"# Category: Speed Calculation + Time Delta Analysis + Smoothing",
        "#",
        f"# Processing Performance:",
        f"# - Total Processing Time: {total_time:.3f} seconds",
        f"# - Data Points Processed: {calculation_stats['data_points_processed']}",
        f"# - Processing Rate: {points_per_second} points/second",
        f"# - Data Quality Score: {data_quality_score}%",
        "#",
        f"# Algorithm Details:",
        f"# - Time Parsing Method: {calculation_stats['time_parsing_method']}",
        f"# - Speed Calculation Duration: {calculation_stats['speed_calculation_duration']:.3f}s",
        f"# - Smoothing Duration: {calculation_stats['smoothing_duration']:.3f}s",
        f"# - Rolling Window Size: {metadata.get('rolling_window', 0)}",
        f"# - Max Speed Threshold: {MAX_SPEED_THRESHOLD_KMH} km/h",
        "#",
        f"# Data Quality Issues:",
        f"# - Zero Time Deltas: {calculation_stats['zero_time_deltas']}",
        f"# - Extreme Speeds Clipped: {calculation_stats['extreme_speeds_clipped']}",
        f"# - Total Quality Issues: {calculation_stats['data_quality_issues']}",
        "#",
        f"# Speed Statistics:",
        f"# - Min Speed: {metadata.get('min_speed', 0)} km/h",
        f"# - Max Speed: {metadata.get('max_speed', 0)} km/h",
        f"# - Average Speed: {metadata.get('avg_speed', 0)} km/h",
        f"# - Speed Variance: {metadata.get('speed_variance', 0)}",
        "#",
        f"# Input Analysis:",
        f"# - Input File: {metadata.get('input_file', '')}",
        f"# - Required Columns Present: {metadata.get('required_columns_present', False)}",
        f"# - Input Columns: {len(metadata.get('input_columns', []))}",
        "#"
    ]
    
    # Write CSV with metadata header
    try:
        with open(output_csv_path, 'w', encoding='utf-8') as f:
            # Write metadata as comments
            for line in metadata_lines:
                f.write(line + '\n')
            
            # Write CSV data
            df.to_csv(f, index=False, float_format='%.3f')
            
        print(f"[Metadata] Speed calculation metadata embedded in CSV header: {output_csv_path}")
        
    except Exception as e:
        print(f"[Error] Could not write CSV with metadata header: {e}")
        # Fallback: save without metadata
        df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.3f')
    
    return df

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
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            save_performance_metadata_to_csv_header(df, output_csv_path, metadata)
            print(f"[OK] Leere Geschwindigkeits-CSV gespeichert: {output_csv_path}")
            sys.exit(0)

        calculation_stats['data_points_processed'] = len(df)
        metadata['input_columns'] = list(df.columns)
        
        # Debug: Prüfe Spalten und Datentypen
        print(f"[Debug] Verfügbare Spalten: {list(df.columns)}")
        print(f"[Debug] Datenpunkte: {len(df)}")
        
        if 'Time' not in df.columns or 'Strecke Delta (km)' not in df.columns:
            print("[Fehler] Benötigte Spalten 'Time' oder 'Strecke Delta (km)' nicht im Input CSV gefunden.")
            print(f"[Debug] Vorhandene Spalten: {list(df.columns)}")
            save_performance_metadata_to_csv_header(df, output_csv_path, metadata)
            print(f"[Warnung] Input wurde nach Output kopiert, da Geschwindigkeitsberechnung nicht möglich: {output_csv_path}")
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
        
        # Save CSV with embedded metadata
        save_performance_metadata_to_csv_header(df, output_csv_path, metadata)
        print(f"[OK] CSV mit Geschwindigkeitsdaten gespeichert: {output_csv_path}")
        print(f"[Info] Zeilen verarbeitet: {len(df)}")

    except Exception as e:
        print(f"[Fehler] Konnte Output-CSV nicht schreiben: {output_csv_path} - {e}")
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
