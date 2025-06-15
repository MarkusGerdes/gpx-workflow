#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8b_geocode_places.py
--------------------
Reads a CSV file with a sorted list of place names (output of step 8).
Performs forward geocoding for each place name using Nominatim to find
its coordinates (latitude, longitude). Handles API rate limits and errors.
Saves the results with detailed performance tracking and metadata.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "8b_geocode_places.py"
SCRIPT_VERSION = "2.0.1"
SCRIPT_DESCRIPTION = "Forward geocoding of place names with Nominatim API, rate limiting and performance tracking"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic forward geocoding functionality
v1.1.0 (2025-06-07): Standardized header, improved error handling and retry logic
v2.0.0 (2025-06-07): Enhanced metadata system with comprehensive API performance tracking and success rate monitoring
v2.0.1 (2025-06-08): Fixed CSV reading to handle metadata headers with comment='#'
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "place_geocoding"
INPUT_FILE_PATTERN = "*_significant_places.csv"
OUTPUT_FILE_PATTERN = "*_places_geocoded.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "geopy>=2.2.0",
    "tqdm>=4.60.0"
]

# === API CONFIGURATION ===
API_SERVICE = "Nominatim"
API_USER_AGENT = "gpx_workflow_v2_place_geocoder"
API_TIMEOUT = 15
RATE_LIMIT_DELAY = 1.1  # Nominatim Policy: max 1 req/sec
RETRY_DELAY = 5
MAX_RETRIES = 3

# === PERFORMANCE TRACKING ===
TRACK_API_PERFORMANCE = True
TRACK_GEOCODING_SUCCESS_RATE = True
TRACK_RETRY_PATTERNS = True

import sys
import os
import argparse
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderQuotaExceeded
import time
from tqdm import tqdm
from datetime import datetime

# === PERFORMANCE TRACKING GLOBALS ===
geocoding_stats = {
    'start_time': None,
    'places_processed': 0,
    'places_successful': 0,
    'places_failed': 0,
    'api_requests_total': 0,
    'api_timeouts': 0,
    'api_quota_exceeded': 0,
    'api_service_errors': 0,
    'total_retry_attempts': 0,
    'context_queries': 0,
    'processing_stages': {}
}

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print(f"API Service: {API_SERVICE}")
    print(f"Rate Limit: {RATE_LIMIT_DELAY}s between requests")
    print(f"Performance Tracking: {TRACK_API_PERFORMANCE}")
    print("=" * 50)

def log_stage(stage_name: str, duration: float = None, details: dict = None):
    """Log processing stage for performance tracking."""
    geocoding_stats['processing_stages'][stage_name] = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'details': details or {}
    }

def save_performance_metadata(output_csv_path: str, metadata: dict):
    """Save geocoding performance metadata to CSV file."""
    if not TRACK_API_PERFORMANCE:
        return
    
    # Create metadata CSV path
    base_path = output_csv_path.replace('.csv', '_metadata.csv')
    
    # Calculate total processing time
    total_time = time.time() - geocoding_stats['start_time'] if geocoding_stats['start_time'] else 0
    
    # Calculate success rates
    success_rate = round(geocoding_stats['places_successful'] / max(geocoding_stats['places_processed'], 1) * 100, 1)
    avg_time_per_place = round(total_time / max(geocoding_stats['places_processed'], 1), 2)
    retry_rate = round(geocoding_stats['total_retry_attempts'] / max(geocoding_stats['api_requests_total'], 1) * 100, 1)
    
    # Prepare metadata row
    metadata_row = {
        'timestamp': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'input_file': metadata.get('input_file', ''),
        'output_file': os.path.basename(output_csv_path),
        'processing_time_seconds': round(total_time, 2),
        'places_total': geocoding_stats['places_processed'],
        'places_geocoded_successfully': geocoding_stats['places_successful'],
        'places_failed': geocoding_stats['places_failed'],
        'geocoding_success_rate': success_rate,
        'avg_time_per_place_seconds': avg_time_per_place,
        'api_requests_total': geocoding_stats['api_requests_total'],
        'api_timeouts': geocoding_stats['api_timeouts'],
        'api_quota_exceeded': geocoding_stats['api_quota_exceeded'],
        'api_service_errors': geocoding_stats['api_service_errors'],
        'retry_attempts_total': geocoding_stats['total_retry_attempts'],
        'retry_rate_percent': retry_rate,
        'rate_limit_delay_seconds': RATE_LIMIT_DELAY,
        'max_retries_per_place': MAX_RETRIES,
        'context_added': metadata.get('context_added', False),
        'context_queries': geocoding_stats['context_queries'],
        'unique_places_input': metadata.get('unique_places', 0),
        'duplicate_places_skipped': metadata.get('duplicates_skipped', 0),
        'invalid_places_filtered': metadata.get('invalid_places', 0),
        'nominatim_user_agent': API_USER_AGENT,
        'api_timeout_seconds': API_TIMEOUT
    }
    
    # Convert to DataFrame and save
    df = pd.DataFrame([metadata_row])
    df.to_csv(base_path, index=False, encoding='utf-8', float_format='%.3f')
    print(f"[Metadata] Geocoding performance data saved: {base_path}")

def geocode_places(input_csv_path: str, output_csv_path: str, context: str = None):
    """
    Performs forward geocoding for places listed in the input CSV.

    Args:
        input_csv_path: Path to the sorted places CSV (needs 'Ort' column).
        output_csv_path: Path to save the output CSV with coordinates.
        context: Optional context string (e.g., ", Country Name") to add
                 to the query for better results.
    """
    geocoding_stats['start_time'] = time.time()
    print(f"[Info] Geocoding places from: {input_csv_path}")

    metadata = {
        'input_file': os.path.basename(input_csv_path),
        'context_added': bool(context),
        'unique_places': 0,
        'duplicates_skipped': 0,
        'invalid_places': 0
    }

    # --- Lade Input-CSV ---
    stage_start = time.time()
    try:
        # CSV mit Metadaten-Header laden (Skip Header-Zeilen mit #)
        places_df = pd.read_csv(input_csv_path, comment='#')
        if places_df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            pd.DataFrame(columns=["Ort", "Latitude_Center", "Longitude_Center"]).to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere Geocoding-Ergebnis-CSV gespeichert: {output_csv_path}")
            save_performance_metadata(output_csv_path, metadata)
            sys.exit(0)

        # Prüfe auf 'Ort'-Spalte
        if "Ort" not in places_df.columns:
             if "City" in places_df.columns:
                 print("[Warnung] Spalte 'Ort' fehlt, verwende stattdessen 'City'.")
                 places_df.rename(columns={"City": "Ort"}, inplace=True)
             else:
                 raise ValueError("Input CSV muss Spalte 'Ort' oder 'City' enthalten.")

        # Entferne Duplikate, um unnötige API-Abfragen zu vermeiden
        original_count = len(places_df)
        unique_places = places_df['Ort'].astype(str).str.strip().unique()
        metadata['duplicates_skipped'] = original_count - len(unique_places)
        
        # Entferne leere oder irrelevante Namen direkt
        valid_places = [p for p in unique_places if p and p not in ["Unbekannter Ort", "Fehler", "nan", "None"]]
        metadata['invalid_places'] = len(unique_places) - len(valid_places)
        metadata['unique_places'] = len(valid_places)
        
        print(f"[Info] {len(valid_places)} eindeutige Orte zum Geocodieren gefunden.")
        print(f"[Info] {metadata['duplicates_skipped']} Duplikate übersprungen, {metadata['invalid_places']} ungültige Einträge gefiltert.")
        
        if not valid_places:
             print("[Warnung] Keine gültigen Ortsnamen zum Geocodieren gefunden.")
             pd.DataFrame(columns=["Ort", "Latitude_Center", "Longitude_Center"]).to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere Geocoding-Ergebnis-CSV gespeichert: {output_csv_path}")
             save_performance_metadata(output_csv_path, metadata)
             sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    log_stage("csv_loading_and_filtering", time.time() - stage_start, {
        'original_places': original_count,
        'unique_places': len(valid_places),
        'duplicates_filtered': metadata['duplicates_skipped'],
        'invalid_filtered': metadata['invalid_places']
    })

    # --- Initialisiere Geocoder ---
    geolocator = Nominatim(user_agent=API_USER_AGENT)

    # --- Geocoding durchführen ---
    results = []
    print("[Info] Starte Forward Geocoding (beachte API Limits!)...")
    
    geocoding_start = time.time()
    for place_name in tqdm(valid_places, desc="Geocoding Places"):
        geocoding_stats['places_processed'] += 1
        lat, lon = None, None
        place_start_time = time.time()
        
        full_query = f"{place_name}{context if context else ''}"
        if context:
            geocoding_stats['context_queries'] += 1

        for attempt in range(MAX_RETRIES):
            geocoding_stats['api_requests_total'] += 1
            location = None
            
            try:
                location = geolocator.geocode(full_query, timeout=API_TIMEOUT)
                if location:
                    lat = location.latitude
                    lon = location.longitude
                    geocoding_stats['places_successful'] += 1
                    print(f"  -> Gefunden: {place_name} -> ({lat:.4f}, {lon:.4f})")
                    break
                else:
                    if attempt == MAX_RETRIES - 1:
                        geocoding_stats['places_failed'] += 1
                        print(f"  -> !! Nicht gefunden: {place_name} (nach {MAX_RETRIES} Versuchen)")
                
                # Warte nach JEDER Anfrage
                time.sleep(RATE_LIMIT_DELAY)

            except GeocoderTimedOut:
                geocoding_stats['api_timeouts'] += 1
                geocoding_stats['total_retry_attempts'] += 1
                print(f"  -> !! Timeout für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            except GeocoderQuotaExceeded:
                geocoding_stats['api_quota_exceeded'] += 1
                geocoding_stats['total_retry_attempts'] += 1
                print(f"  -> !! Quota überschritten für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}). Warte länger...")
                time.sleep(RETRY_DELAY * 5)
            except GeocoderServiceError as e:
                geocoding_stats['api_service_errors'] += 1
                geocoding_stats['total_retry_attempts'] += 1
                print(f"  -> !! Service Fehler für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                geocoding_stats['total_retry_attempts'] += 1
                print(f"  -> !! Unerwarteter Fehler für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

        # Speichere Ergebnis (auch wenn Lat/Lon None sind)
        results.append({
            "Ort": place_name,
            "Latitude_Center": lat,
            "Longitude_Center": lon
        })

    log_stage("geocoding_process", time.time() - geocoding_start, {
        'places_processed': geocoding_stats['places_processed'],
        'successful': geocoding_stats['places_successful'],
        'failed': geocoding_stats['places_failed']
    })

    # --- Ergebnisse speichern ---
    save_start = time.time()
    result_df = pd.DataFrame(results)

    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Füge Originaldaten wieder hinzu (optional, aber kann nützlich sein)
        places_df['Ort'] = places_df['Ort'].astype(str)
        result_df['Ort'] = result_df['Ort'].astype(str)
        final_df = pd.merge(places_df, result_df, on="Ort", how="left")

        final_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"\n[OK] Geocoding-Ergebnisse gespeichert ({len(final_df)} Einträge): {output_csv_path}")
        
        # Save performance metadata
        save_performance_metadata(output_csv_path, metadata)
        
    except Exception as e:
        print(f"[Fehler] Konnte Geocoding-Ergebnis-CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

    log_stage("results_saving", time.time() - save_start, {'output_rows': len(final_df)})

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Forward geocode place names from a CSV file.")
    parser.add_argument("--input-csv", required=True, help="Path to the sorted places CSV file (output of step 8).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with coordinates.")
    parser.add_argument("--context", default="", help="Optional context (e.g., ', Country') to add to geocoding query.")
    args = parser.parse_args()

    geocode_places(args.input_csv, args.output_csv, args.context)
