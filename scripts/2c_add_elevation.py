#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2c_add_elevation.py
-------------------
Reads track data CSV (output of step 2).
Checks if elevation data is missing or invalid (e.g., all zeros or NaN).
If needed, fetches elevation data for track coordinates from the
Open Topo Data API (https://www.opentopodata.org/).
Recalculates ascent based on the new elevation data.
Saves the updated track data to a new CSV file.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "2c_add_elevation.py"
SCRIPT_VERSION = "2.1.0"
SCRIPT_DESCRIPTION = "Elevation data validation and enrichment with integrated metadata system"
LAST_UPDATED = "2025-06-15"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.1.0 (pre-2025): Enhanced API integration with batch processing and retry logic
v2.0.0 (2025-06-08): Vollständiges Performance-Tracking System für Elevation-API-Integration
v2.1.0 (2025-06-15): Integrated unified metadata system with CSV_METADATA_TEMPLATE
- Removed custom metadata header generation
- Integrated with standardized CSV_METADATA_TEMPLATE system
- Streamlined API performance tracking and metadata collection
- Maintained full OpenTopoData API functionality
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "elevation_api"
INPUT_FILE_PATTERN = "*_track_data_full.csv"
OUTPUT_FILE_PATTERN = "*_track_data_full_with_elevation.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "requests>=2.25.0",
    "numpy>=1.20.0",
    "tqdm>=4.60.0"
]

# === IMPORTS ===
import sys
import os
import argparse
import pandas as pd
import numpy as np
import requests
import time
import math
import csv
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)



# --- Konfiguration ---
OPENTOPO_API_URL = "https://api.opentopodata.org/v1/lookup"
BATCH_SIZE = 100      # Max locations per API request (API limit is 100)
REQUEST_TIMEOUT = 30  # Timeout for API request
SLEEP_BETWEEN_REQUESTS = 1.1 # Be nice to the API (max 1 req/sec)
RETRY_DELAY = 5       # Wait time between retries
MAX_RETRIES = 3       # Max retries per batch

def add_elevation(input_csv_path: str, output_csv_path: str, batch_size: int):
    """Checks and adds elevation data using Open Topo Data API."""
    # === PERFORMANCE-TRACKING INITIALISIERUNG ===
    run_start_time = datetime.now()
    performance_data = {
        'processing_phases': {},
        'input_analysis': {},
        'elevation_validation': {},
        'api_processing': {},
        'data_interpolation': {},
        'output_generation': {},
        'data_quality': {},
        'error_handling': {}
    }
    
    start_total_time = time.time()
    performance_data['api_processing']['batch_size_used'] = batch_size
    performance_data['api_processing']['network_timeout_seconds'] = REQUEST_TIMEOUT
    performance_data['api_processing']['max_retries_per_batch'] = MAX_RETRIES
    performance_data['api_processing']['sleep_between_requests'] = SLEEP_BETWEEN_REQUESTS
    
    print(f"[{run_start_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} started.")
    print(f"[Info] Checking/Adding elevation for: {input_csv_path}")
    print(f"[Info] Using API Batch Size: {batch_size}")

    # Metadaten-Sammlung für Original-Format (Header-Kommentare)
    metadata_lines = [
        f"# Processed by: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Processing Timestamp: {run_start_time.isoformat()}",
        f"# Input CSV: {os.path.basename(input_csv_path)}",
    ]
    api_metadata = {
        "api_provider": "OpenTopoData API (https://www.opentopodata.org/)",
        "api_endpoint": OPENTOPO_API_URL,
        "api_query_start_time": None,
        "api_query_end_time": None,
        "api_total_queries": 0,
        "api_successful_queries": 0,
        "api_failed_queries": 0,
        "api_data_source_info": "Primarily SRTM GL1 (Global 30m), ASTER GDEM, GMTED2010, ETOPO1"
    }

    # --- Lade Input-CSV ---
    try:
        input_loading_start = time.time()
        
        # Lade CSV - robuste Behandlung von Metadaten-Headern und Time-Spalte
        try:
            # Prüfe zunächst Header ohne parse_dates und mit comment-Handling
            header_df = pd.read_csv(input_csv_path, nrows=0, comment='#')
            
            if 'Time' in header_df.columns:
                # Time-Spalte existiert - parse sie mit comment-Handling
                df = pd.read_csv(input_csv_path, parse_dates=['Time'], encoding='utf-8', comment='#')
            else:
                # Time-Spalte existiert nicht - lade ohne parse_dates mit comment-Handling
                df = pd.read_csv(input_csv_path, encoding='utf-8', comment='#')
                # Füge eine dummy Time-Spalte hinzu
                df['Time'] = pd.NaT
        except Exception as csv_load_error:
            # Fallback: Versuche ohne comment-Parameter
            try:
                header_df = pd.read_csv(input_csv_path, nrows=0)
                
                if 'Time' in header_df.columns:
                    df = pd.read_csv(input_csv_path, parse_dates=['Time'], encoding='utf-8')
                else:
                    df = pd.read_csv(input_csv_path, encoding='utf-8')
                    df['Time'] = pd.NaT
            except Exception as final_error:
                raise final_error
        
        performance_data['processing_phases']['input_loading_time'] = time.time() - input_loading_start
        performance_data['data_quality']['original_points_count'] = len(df)
        performance_data['data_quality']['input_columns_count'] = len(df.columns) if not df.empty else 0
        
        if df.empty:
            performance_data['error_handling']['empty_input_data'] = True
            print(f"[Warning] Input CSV is empty: {input_csv_path}")
            
            # Save empty CSV with metadata
            write_csv_with_metadata(
                dataframe=df,
                output_path=output_csv_path,
                script_name=SCRIPT_NAME,
                script_version=SCRIPT_VERSION,
                input_files=[input_csv_path],
                processing_parameters={'error': 'empty_input'},
                additional_metadata={'processing_error': 'Input CSV is empty', 'data_points_processed': 0}
            )
            print(f"[OK] Empty elevation CSV with metadata saved: {output_csv_path}")
            return

        # Überprüfe notwendige Spalten
        required_columns = ['Latitude', 'Longitude']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            performance_data['error_handling']['missing_required_columns'] = missing_columns
            raise ValueError(f"Input CSV benötigt {required_columns}")

        # === ELEVATION VALIDATION PHASE (Original-Logik) ===
        elevation_validation_start = time.time()
        
        needs_elevation_fetch = True
        if 'Elevation (m)' in df.columns and df['Elevation (m)'].notna().all():
            unique_elevations = df['Elevation (m)'].nunique()
            if unique_elevations > 1:
                min_el, max_el = df['Elevation (m)'].min(), df['Elevation (m)'].max()
                if not (unique_elevations == 1 and min_el == 0.0):
                    print("[Info] Vorhandene Höhendaten scheinen valide zu sein. Überspringe API-Abfrage.")
                    needs_elevation_fetch = False
                    performance_data['elevation_validation']['existing_data_valid'] = True
                    performance_data['data_quality']['elevation_range_min'] = min_el
                    performance_data['data_quality']['elevation_range_max'] = max_el

        performance_data['processing_phases']['elevation_validation_time'] = time.time() - elevation_validation_start
        performance_data['elevation_validation']['needs_api_fetch'] = needs_elevation_fetch
        performance_data['data_quality']['points_needing_elevation'] = len(df) if needs_elevation_fetch else 0

    except FileNotFoundError:
        performance_data['error_handling']['file_not_found'] = True
        print(f"[Error] Input file not found: {input_csv_path}")
        performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
        
        # Create empty CSV with error metadata
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters={'error': 'file_not_found'},
            additional_metadata={'processing_error': 'Input file not found'}
        )
        sys.exit(1)
    except Exception as e:
        performance_data['error_handling']['csv_reading_error'] = str(e)
        print(f"[Error] Error reading input CSV '{input_csv_path}': {e}")
        performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
        
        # Create empty CSV with error metadata
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters={'error': 'csv_reading_failed'},
            additional_metadata={'processing_error': str(e)}
        )
        sys.exit(1)

    # --- API-Abfrage, falls nötig (Original-Implementierung) ---
    if needs_elevation_fetch:
        api_batch_processing_start = time.time()
        api_metadata["api_query_start_time"] = datetime.now().isoformat()
        
        print("[Info] Höhendaten fehlen oder sind ungültig. Versuche Abfrage von Open Topo Data API...")
        coordinates = list(zip(df['Latitude'], df['Longitude']))
        num_points = len(coordinates)
        num_batches = math.ceil(num_points / batch_size)
        fetched_elevations = [None] * num_points

        performance_data['api_processing']['api_batches_total'] = num_batches
        performance_data['api_processing']['api_provider_info'] = 'OpenTopoData API (https://www.opentopodata.org/)'
        performance_data['api_processing']['data_source_info'] = 'SRTM GL1, ASTER GDEM, GMTED2010, ETOPO1'
        
        api_errors = 0
        api_points_retrieved = 0
        api_points_failed = 0
        
        with tqdm(total=num_batches, desc="Fetching Elevation Batches") as pbar:
            for i in range(num_batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, num_points)
                batch_coords = coordinates[start_idx:end_idx]

                # Erstelle Location-String für API
                locations_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in batch_coords])
                api_url_batch = f"{OPENTOPO_API_URL}?locations={locations_str}"

                # Führe API-Abfrage mit Retries durch
                success = False
                for attempt in range(MAX_RETRIES):
                    try:
                        response = requests.get(api_url_batch, timeout=REQUEST_TIMEOUT)
                        response.raise_for_status()
                        data = response.json()

                        if data.get('status') == 'OK':
                            results = data.get('results', [])
                            if len(results) == len(batch_coords):
                                for j, res in enumerate(results):
                                    elevation = res.get('elevation')
                                    fetched_elevations[start_idx + j] = elevation
                                    if elevation is not None:
                                        api_points_retrieved += 1
                                    else:
                                        api_points_failed += 1
                                success = True
                                break
                            else:
                                print(f"[Warnung] API gab unerwartete Anzahl Ergebnisse für Batch {i+1} zurück.")
                        else:
                            print(f"[Warnung] API-Status nicht OK für Batch {i+1}: {data.get('status')}")

                    except requests.exceptions.Timeout:
                        print(f"  -> Timeout Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
                    except requests.exceptions.HTTPError as e:
                        print(f"  -> HTTP Fehler {e.response.status_code} Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}).")
                        if e.response.status_code == 429:
                            time.sleep(RETRY_DELAY * 2)
                    except requests.exceptions.RequestException as e:
                        print(f"  -> Request Fehler Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}): {e}")
                    except Exception as e:
                        print(f"  -> Unerwarteter Fehler Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}): {e}")

                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)

                if not success:
                    print(f"[Fehler] Konnte Batch {i+1} nach {MAX_RETRIES} Versuchen nicht abrufen.")
                    api_errors += 1
                    api_points_failed += len(batch_coords)

                # Pause zwischen den Batches
                if i < num_batches - 1:
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                pbar.update(1)

        api_metadata["api_query_end_time"] = datetime.now().isoformat()
        api_metadata["api_failed_queries"] = api_errors
        api_metadata["api_total_queries"] = num_batches
        api_metadata["api_successful_queries"] = num_batches - api_errors
        
        performance_data['processing_phases']['api_batch_processing_time'] = time.time() - api_batch_processing_start
        performance_data['api_processing']['api_batches_successful'] = num_batches - api_errors
        performance_data['api_processing']['api_batches_failed'] = api_errors
        performance_data['api_processing']['api_success_rate'] = round(((num_batches - api_errors) / max(1, num_batches)) * 100, 1)
        performance_data['api_processing']['api_points_retrieved'] = api_points_retrieved
        performance_data['api_processing']['api_points_failed'] = api_points_failed

        # Füge API Metadaten zu den Hauptmetadaten hinzu
        for key, value in api_metadata.items():
            if value is not None:
                metadata_lines.append(f"# API_METADATA_{key.upper()}: {value}")

        # --- Aktualisiere DataFrame (Original-Interpolation-Logik) ---
        data_interpolation_start = time.time()
        
        print("[Info] Aktualisiere DataFrame mit abgerufenen Höhen...")
        df['Elevation_API'] = [float(e) if e is not None else np.nan for e in fetched_elevations]

        interpolation_points_filled = 0
        if df['Elevation_API'].isnull().any():
            num_null_before = df['Elevation_API'].isnull().sum()
            print(f"[Warnung] {num_null_before} Höhenwerte konnten nicht von API abgerufen werden. Fülle Lücken...")
            
            # Original-Interpolation
            df['Elevation_API'].interpolate(method='linear', limit_direction='both', inplace=True)
            if df['Elevation_API'].isnull().all():
                df['Elevation_API'] = 0.0
            num_null_after = df['Elevation_API'].isnull().sum()
            if num_null_after > 0:
                print(f"[Warnung] {num_null_after} Höhenwerte konnten nicht gefüllt werden. Setze auf 0.")
                df['Elevation_API'].fillna(0.0, inplace=True)
            
            interpolation_points_filled = num_null_before - num_null_after

        performance_data['processing_phases']['data_interpolation_time'] = time.time() - data_interpolation_start
        performance_data['data_interpolation']['interpolation_points_filled'] = interpolation_points_filled

        # Überschreibe die ursprüngliche Elevation-Spalte
        df['Elevation (m)'] = df['Elevation_API']
        df.drop(columns=['Elevation_API'], inplace=True)

        # Berechne Aufstieg NEU
        print("[Info] Berechne 'Aufstieg (m)' neu basierend auf API-Höhen...")
        elevation_diff = df['Elevation (m)'].diff().fillna(0)
        df['Aufstieg (m)'] = elevation_diff.clip(lower=0)

    else:
        # Wenn keine API-Abfrage nötig war
        if 'Aufstieg (m)' not in df.columns:
            print("[Info] Berechne 'Aufstieg (m)' aus vorhandenen Höhendaten...")
            elevation_diff = df['Elevation (m)'].diff().fillna(0)
            df['Aufstieg (m)'] = elevation_diff.clip(lower=0)

    # --- Save final CSV with integrated metadata ---
    try:
        output_writing_start = time.time()
        
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        final_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)']
        for col in final_cols:
            if col not in df.columns:
                if col == 'Time':
                    df[col] = pd.NaT
                else:
                    df[col] = 0.0 if col != 'Elevation (m)' else np.nan

        if 'Elevation (m)' not in df.columns:
            df['Elevation (m)'] = np.nan

        df_final = df[final_cols]

        # === FINAL PERFORMANCE TRACKING ===
        total_processing_time = time.time() - start_total_time
        performance_data['processing_phases']['total_processing_time'] = total_processing_time

        # Quality assessment
        if not df_final['Elevation (m)'].isnull().all():
            performance_data['data_quality']['elevation_range_min'] = float(df_final['Elevation (m)'].min())
            performance_data['data_quality']['elevation_range_max'] = float(df_final['Elevation (m)'].max())
            performance_data['data_quality']['total_ascent_calculated'] = float(df_final['Aufstieg (m)'].sum())
            
            # Quality Score calculation
            quality_score = 100
            if needs_elevation_fetch:
                if performance_data['api_processing']['api_success_rate'] < 100:
                    quality_score -= (100 - performance_data['api_processing']['api_success_rate']) * 0.5
                if performance_data['data_interpolation'].get('interpolation_points_filled', 0) > 0:
                    interpolation_ratio = performance_data['data_interpolation']['interpolation_points_filled'] / len(df_final)
                    quality_score -= interpolation_ratio * 20
            
            performance_data['data_quality']['data_quality_score'] = round(max(0, quality_score), 1)
        else:
            performance_data['data_quality']['data_quality_score'] = 0

        # Prepare processing parameters
        processing_parameters = {
            'batch_size': batch_size,
            'request_timeout_sec': REQUEST_TIMEOUT,
            'max_retries_per_batch': MAX_RETRIES,
            'sleep_between_requests_sec': SLEEP_BETWEEN_REQUESTS,
            'api_provider': 'OpenTopoData',
            'needs_elevation_fetch': needs_elevation_fetch
        }
        
        # Prepare API metadata
        api_metadata_clean = {}
        if needs_elevation_fetch:
            api_metadata_clean = {
                'api_provider': 'OpenTopoData API (https://www.opentopodata.org/)',
                'api_endpoint': OPENTOPO_API_URL,
                'api_total_queries': performance_data['api_processing'].get('api_batches_total', 0),
                'api_successful_queries': performance_data['api_processing'].get('api_batches_successful', 0),
                'api_failed_queries': performance_data['api_processing'].get('api_batches_failed', 0),
                'api_success_rate_percent': performance_data['api_processing'].get('api_success_rate', 100),
                'data_source_info': 'SRTM GL1, ASTER GDEM, GMTED2010, ETOPO1'
            }
        
        # Prepare additional metadata
        additional_metadata = {
            'total_processing_time_sec': round(total_processing_time, 3),
            'original_points_count': performance_data['data_quality']['original_points_count'],
            'points_needing_elevation': performance_data['data_quality']['points_needing_elevation'],
            'data_quality_score': performance_data['data_quality']['data_quality_score'],
            'elevation_range_min_m': performance_data['data_quality'].get('elevation_range_min', 0),
            'elevation_range_max_m': performance_data['data_quality'].get('elevation_range_max', 0),
            'total_ascent_calculated_m': performance_data['data_quality'].get('total_ascent_calculated', 0),
            'input_loading_time_sec': round(performance_data['processing_phases']['input_loading_time'], 3),
            'elevation_validation_time_sec': round(performance_data['processing_phases']['elevation_validation_time'], 3),
            'existing_data_valid': performance_data['elevation_validation'].get('existing_data_valid', False)
        }
        
        # Add API-specific metadata if API was used
        if needs_elevation_fetch:
            additional_metadata.update({
                'api_batch_processing_time_sec': round(performance_data['processing_phases'].get('api_batch_processing_time', 0), 3),
                'data_interpolation_time_sec': round(performance_data['processing_phases'].get('data_interpolation_time', 0), 3),
                'api_points_retrieved': performance_data['api_processing'].get('api_points_retrieved', 0),
                'api_points_failed': performance_data['api_processing'].get('api_points_failed', 0),
                'interpolation_points_filled': performance_data['data_interpolation'].get('interpolation_points_filled', 0)
            })

        # Save CSV with integrated metadata
        write_csv_with_metadata(
            dataframe=df_final,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters=processing_parameters,
            api_metadata=api_metadata_clean if needs_elevation_fetch else None,
            additional_metadata=additional_metadata,
            float_format='%.6f'
        )
        
        performance_data['processing_phases']['output_writing_time'] = time.time() - output_writing_start
        
        if os.path.exists(output_csv_path):
            output_file_size = os.path.getsize(output_csv_path)
            performance_data['output_generation']['output_file_size_mb'] = round(output_file_size / (1024 * 1024), 3)
            performance_data['output_generation']['final_rows_count'] = len(df_final)
            performance_data['output_generation']['final_columns_count'] = len(df_final.columns)
        
        print(f"[OK] Track data with elevation and metadata saved: {output_csv_path}")
        print(f"[Performance] Processing time: {total_processing_time:.3f}s, Quality score: {performance_data['data_quality']['data_quality_score']}/100")

    except Exception as e:
        performance_data['error_handling']['output_writing_error'] = str(e)
        print(f"[Error] Could not write final CSV: {output_csv_path} - {e}")
        performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
        
        # Create empty CSV with error metadata
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters={'error': 'output_writing_failed'},
            additional_metadata={'processing_error': str(e)}
        )
        sys.exit(1)

    run_end_time = datetime.now()
    print(f"[{run_end_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} finished. Duration: {run_end_time - run_start_time}")

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Check and add elevation data to track CSV using Open Topo Data API.")
    parser.add_argument("--input-csv", required=True, help="Path to the input track data CSV file (output of step 2).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with potentially added elevation.")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of locations per API request batch.")
    args = parser.parse_args()

    add_elevation(args.input_csv, args.output_csv, args.batch_size)
