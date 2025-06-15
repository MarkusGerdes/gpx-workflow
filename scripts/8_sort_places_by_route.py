#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8_sort_places_by_route.py
-------------------------
Sorts the significant places (output of step 7) based on their first
appearance along the optimized route (output of step 4).
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "8_sort_places_by_route.py"
SCRIPT_VERSION = "2.0.1" # Bugfix: write_csv_with_metadata() Parameter-Kompatibilität
SCRIPT_DESCRIPTION = "Advanced route-based place sorting with algorithm performance tracking and route-sequence analysis"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic route-based sorting functionality
v1.1.0 (2025-06-07): Standardized header, improved sorting logic and error handling
v2.0.0 (2025-06-08): Erweiterte Metadaten + Sorting-Algorithm-Performance-Tracking
- Route-Sequence-Analysis und Sorting-Algorithm-Performance-Metriken
- Place-Position-Tracking entlang der Route mit Index-Mapping
- Input-Data-Correlation-Analysis zwischen Track und Places
- Sorting-Efficiency und Route-Coverage-Qualitäts-Metriken
- Geographic-Sequence-Validation und Order-Consistency-Checks
v2.0.1 (2025-06-08): Fixed write_csv_with_metadata() parameter compatibility with new template
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "place_sorting"
INPUT_FILE_PATTERN = "*_significant_places.csv"
OUTPUT_FILE_PATTERN = "*_places_sorted.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0"
]

import sys
import os
import argparse
import pandas as pd
import csv
import time
from datetime import datetime
from pathlib import Path

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



def sort_places(track_csv_path: str, places_csv_path: str, output_csv_path: str, basename: str = None):
    """Sorts places based on route order with performance tracking."""
    run_start_time = datetime.now()
    print_script_info()
    print(f"[Info] Sorting places from '{places_csv_path}' based on route '{track_csv_path}'")
    
    # Metadaten-Initialisierung
    metadata = {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'timestamp': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'track_file': track_csv_path,
        'places_file': places_csv_path,
        'output_file': output_csv_path,
        'track_file_size_mb': 0.0,
        'places_file_size_mb': 0.0,
        'track_total_points': 0,
        'track_columns_count': 0,
        'places_total_count': 0,
        'places_columns_count': 0,
        'total_cities_on_route': 0,
        'unique_cities_before_filtering': 0,
        'filtered_cities_count': 0,
        'unique_cities_after_filtering': 0,
        'route_filter_efficiency_percent': 0.0,
        'places_found_on_route': 0,
        'places_not_found_on_route': 0,
        'route_coverage_percent': 0.0,
        'input_analysis_time_sec': 0.0,
        'algorithm_processing_time_sec': 0.0,
        'sorting_time_sec': 0.0,
        'output_generation_time_sec': 0.0,
        'total_runtime_sec': 0.0,
        'sorting_efficiency_places_per_sec': 0.0,
        'success': False,
        'error_message': ''
    }
    
    print(f"[Performance] Place sorting started at {run_start_time.strftime('%H:%M:%S')}")

    # --- Lade Input-Dateien ---
    # === INPUT FILE ANALYSIS ===
    input_analysis_start = time.time()
    
    try:
        # Route mit Ortsinformation (aus Schritt 4)
        if os.path.exists(track_csv_path):
            track_file_size = os.path.getsize(track_csv_path) / (1024 * 1024)  # MB
            metadata['track_file_size_mb'] = round(track_file_size, 3)
        
        track_df = pd.read_csv(track_csv_path, comment='#')
        metadata['track_total_points'] = len(track_df)
        metadata['track_columns_count'] = len(track_df.columns)
        
        if track_df.empty:
            metadata['error_message'] = 'Track CSV is empty'
            metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
            print(f"[Warnung] Track CSV ist leer: {track_csv_path}")
            
            # Wenn der Track leer ist, können wir nicht sortieren. Leere Output speichern.
            empty_df = pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"])
            write_csv_with_metadata(
                dataframe=empty_df,
                output_path=output_csv_path,
                script_name=SCRIPT_NAME,
                script_version=SCRIPT_VERSION,
                input_files=[track_csv_path, places_csv_path],
                additional_metadata=metadata
            )
            print(f"[OK] Leere sortierte Orts-CSV gespeichert, da Track leer: {output_csv_path}")
            return

        # Unsortierte Ortsliste (aus Schritt 7)
        if os.path.exists(places_csv_path):
            places_file_size = os.path.getsize(places_csv_path) / (1024 * 1024)  # MB
            metadata['places_file_size_mb'] = round(places_file_size, 3)
        
        places_df = pd.read_csv(places_csv_path, comment='#')
        metadata['places_total_count'] = len(places_df)
        metadata['places_columns_count'] = len(places_df.columns)
        metadata['input_analysis_time_sec'] = round(time.time() - input_analysis_start, 3)
        
        if places_df.empty:
             metadata['error_message'] = 'Places CSV is empty'
             metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
             print(f"[Warnung] Places CSV ist leer: {places_csv_path}")
             
             # Wenn keine Orte da sind, leere Output speichern.
             write_csv_with_metadata(
                 dataframe=places_df,
                 output_path=output_csv_path,
                 script_name=SCRIPT_NAME,
                 script_version=SCRIPT_VERSION,
                 input_files=[track_csv_path, places_csv_path],
                 additional_metadata=metadata
             )
             print(f"[OK] Leere sortierte Orts-CSV gespeichert, da keine Orte gefunden: {output_csv_path}")
             return

    except FileNotFoundError as e:
        metadata['error_message'] = f'Input file not found: {str(e)}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Eingabedatei nicht gefunden: {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[track_csv_path, places_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    except Exception as e:
        metadata['error_message'] = f'CSV read error: {str(e)}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Fehler beim Lesen der Input-Dateien: {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[track_csv_path, places_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)

    # --- Spalten prüfen ---
    if "City" not in track_df.columns:
        print(f"Fehler: Spalte 'City' fehlt in Track-Datei: {track_csv_path}")
        sys.exit(1)
    if "Ort" not in places_df.columns:
        # Versuche Fallback, falls Spalte 'City' heißt
        if "City" in places_df.columns:
             print("[Warnung] Spalte 'Ort' fehlt in Places-Datei, verwende stattdessen 'City'.")
             places_df.rename(columns={"City": "Ort"}, inplace=True)
        else:
             print(f"Fehler: Spalte 'Ort' (oder 'City') fehlt in Places-Datei: {places_csv_path}")
             sys.exit(1)

    # --- Sortierlogik ---
    # === ROUTE-SEQUENCE-ANALYSIS ===
    algorithm_start = time.time()
    
    # Konvertiere 'City' im Track sicherheitshalber zu Strings
    track_df['City'] = track_df['City'].astype(str)
    # Entferne irrelevante Einträge und Duplikate, behalte die Reihenfolge bei
    ordered_cities_on_route = track_df.drop_duplicates(subset=['City'], keep='first')['City'].tolist()
    
    # Route-Sequence-Metriken
    metadata['total_cities_on_route'] = len(ordered_cities_on_route)
    metadata['unique_cities_before_filtering'] = len(set(ordered_cities_on_route))
    
    # Filtere irrelevante Orte aus der Liste, die wir sortieren wollen
    ignore_places = ["Unbekannter Ort", "Fehler", "Keine PLZ", "", "nan", "None"]
    ordered_cities_on_route = [city for city in ordered_cities_on_route if city not in ignore_places]
    
    # Filtering-Efficiency
    metadata['filtered_cities_count'] = len(ordered_cities_on_route)
    metadata['unique_cities_after_filtering'] = len(set(ordered_cities_on_route))
    filter_efficiency = (len(ordered_cities_on_route) / metadata['total_cities_on_route']) * 100 if metadata['total_cities_on_route'] > 0 else 0
    metadata['route_filter_efficiency_percent'] = round(filter_efficiency, 2)

    # === SORTING-ALGORITHMUS-PERFORMANCE ===
    sorting_start = time.time()
    
    # Funktion zum Ermitteln des ersten Index (Position) im Track
    def get_sort_key(place_name):
        try:
            # Finde den Index des ersten Vorkommens des Ortes in der geordneten Liste
            index = ordered_cities_on_route.index(str(place_name)) # Konvertiere place_name zu str
            return index
        except ValueError:
            # Wenn der Ort aus der Place-Liste nicht im Track vorkommt (sollte nicht passieren, aber sicher ist sicher)
            # oder nach Filterung entfernt wurde, weise einen hohen Index zu (ans Ende).
            return float('inf')

    # Wende die Sortierfunktion an, um einen Sortierindex zu erstellen
    # Stelle sicher, dass 'Ort' auch ein String ist für den Vergleich in get_sort_key
    places_df['sort_index'] = places_df['Ort'].astype(str).apply(get_sort_key)
    
    # Sortier-Quality-Metriken
    places_found_on_route = len(places_df[places_df['sort_index'] != float('inf')])
    places_not_found_on_route = len(places_df[places_df['sort_index'] == float('inf')])
    
    metadata['places_found_on_route'] = places_found_on_route
    metadata['places_not_found_on_route'] = places_not_found_on_route
    metadata['route_coverage_percent'] = round((places_found_on_route / len(places_df)) * 100, 2) if len(places_df) > 0 else 0
    metadata['sorting_time_sec'] = round(time.time() - sorting_start, 3)

    # Sortiere den DataFrame basierend auf dem neuen Index
    sorted_places_df = places_df.sort_values("sort_index")

    # Entferne die Hilfsspalte 'sort_index'
    sorted_places_df = sorted_places_df.drop(columns="sort_index")
    
    # Algorithmus-Performance-Abschluss
    metadata['algorithm_processing_time_sec'] = round(time.time() - algorithm_start, 3)

    # === OUTPUT GENERATION MIT PERFORMANCE-TRACKING ===
    output_generation_start = time.time()
    
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        metadata['output_generation_time_sec'] = round(time.time() - output_generation_start, 3)
        metadata['success'] = True
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        metadata['sorting_efficiency_places_per_sec'] = round(len(places_df) / metadata['total_runtime_sec'], 1) if metadata['total_runtime_sec'] > 0 else 0
        
        write_csv_with_metadata(
            dataframe=sorted_places_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[track_csv_path, places_csv_path],
            additional_metadata=metadata,
            float_format='%.2f'
        )
        
        print(f"[OK] Sortierte Orte gespeichert ({len(sorted_places_df)} Einträge): {output_csv_path}")
        print(f"[Performance] Sorted {len(sorted_places_df)} places based on route sequence")
        print(f"[Metadaten] Route Coverage: {metadata['route_coverage_percent']}%, "
              f"Filter Efficiency: {metadata['route_filter_efficiency_percent']}%, "
              f"Runtime: {metadata['total_runtime_sec']}s")
        
    except Exception as e:
        metadata['success'] = False
        metadata['error_message'] = f'Output write error: {str(e)}'
        metadata['output_generation_time_sec'] = round(time.time() - output_generation_start, 3)
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Konnte sortierte Orts-CSV nicht schreiben: {output_csv_path} - {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[track_csv_path, places_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    


if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Sort significant places based on their order along the route.")
    parser.add_argument("--track-csv", required=True, help="Path to the track CSV file with location data (output of step 4).")
    parser.add_argument("--places-csv", required=True, help="Path to the unsorted places summary CSV file (output of step 7).")
    parser.add_argument("--output-csv", required=True, help="Path to save the sorted places CSV file.")
    parser.add_argument("--basename", help="Basename for metadata files (optional).")
    args = parser.parse_args()

    sort_places(args.track_csv, args.places_csv, args.output_csv, args.basename)