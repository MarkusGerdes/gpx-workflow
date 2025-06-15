#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7_extract_significant_places.py
-------------------------------
Analyzes the track data CSV containing location information (output of step 4)
to extract significant places (cities/towns/villages) visited along the route.
Calculates the number of track points and the approximate distance spent
within each place. Filters out irrelevant place names.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "7_extract_significant_places.py"
SCRIPT_VERSION = "2.0.1" # Bugfix: write_csv_with_metadata() Parameter-Kompatibilität
SCRIPT_DESCRIPTION = "Advanced place extraction with algorithm performance tracking and place-quality metrics"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic place extraction functionality
v1.1.0 (2025-06-07): Standardized header, improved distance calculation and error handling
v2.0.0 (2025-06-08): Erweiterte Metadaten + Place-Extraction-Algorithm-Performance-Tracking
- Algorithmus-Performance-Tracking für Place-Extraction und Distanz-Berechnung
- Place-Quality-Metriken (Coverage, Diversity, Filtering-Efficiency)
- Input-Data-Analysis und Track-Point-Statistiken
- Distance-Calculation-Performance mit verschiedenen Methoden
- Detaillierte Place-Categories und Geographic-Distribution-Analysis
v2.0.1 (2025-06-08): Fixed write_csv_with_metadata() parameter compatibility with new template
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "place_extraction"
INPUT_FILE_PATTERN = "*_geocoded.csv"
OUTPUT_FILE_PATTERN = "*_significant_places.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "numpy>=1.20.0"
]

import sys
import os
import argparse
import pandas as pd
import numpy as np
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



def extract_places(input_csv_path: str, output_csv_path: str, basename: str = None):
    """Extracts and summarizes significant places from track data with performance tracking."""
    run_start_time = datetime.now()
    print_script_info()
    print(f"[Info] Extracting significant places from: {input_csv_path}")
    
    # Metadaten-Initialisierung
    metadata = {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'timestamp': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': input_csv_path,
        'output_file': output_csv_path,
        'input_file_size_mb': 0.0,
        'input_track_points': 0,
        'input_columns_count': 0,
        'original_unique_places': 0,
        'points_after_filtering': 0,
        'filter_efficiency_percent': 0.0,
        'places_filtered_out': 0,
        'unique_places_after_filtering': 0,
        'final_places_count': 0,
        'place_diversity_score': 0.0,
        'extraction_efficiency_percent': 0.0,
        'total_distance_calculated_km': 0.0,
        'places_with_distance_calculation': 0,
        'average_distance_per_place_km': 0.0,
        'has_distance_column': False,
        'distance_column_used': '',
        'input_analysis_time_sec': 0.0,
        'algorithm_processing_time_sec': 0.0,
        'distance_calculation_time_sec': 0.0,
        'output_generation_time_sec': 0.0,
        'total_runtime_sec': 0.0,
        'processing_efficiency_points_per_sec': 0.0,
        'success': False,
        'error_message': ''
    }
    
    print(f"[Performance] Place extraction started at {run_start_time.strftime('%H:%M:%S')}")

    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # === INPUT FILE ANALYSIS ===
        input_analysis_start = time.time()
        if os.path.exists(input_csv_path):
            file_size = os.path.getsize(input_csv_path) / (1024 * 1024)  # MB
            metadata['input_file_size_mb'] = round(file_size, 3)
        
        df = pd.read_csv(input_csv_path, comment='#')
        
        # Input-Daten-Statistiken
        metadata['input_track_points'] = len(df)
        metadata['input_columns_count'] = len(df.columns)
        metadata['input_analysis_time_sec'] = round(time.time() - input_analysis_start, 3)
        
        if df.empty:
            metadata['error_message'] = 'Input CSV is empty'
            metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            
            # Leere Output-Datei erstellen
            empty_df = pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"])
            write_csv_with_metadata(
                dataframe=empty_df,
                output_path=output_csv_path,
                script_name=SCRIPT_NAME,
                script_version=SCRIPT_VERSION,
                input_files=[input_csv_path],
                additional_metadata=metadata
            )
            print(f"[OK] Leere Ortszusammenfassungs-CSV gespeichert: {output_csv_path}")
            return

    except FileNotFoundError:
        metadata['error_message'] = f'Input file not found: {input_csv_path}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    except Exception as e:
        metadata['error_message'] = f'CSV read error: {str(e)}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)

    # --- Spalten prüfen ---
    # Wir brauchen 'City' aus Schritt 4.
    # 'Distanz (km)' aus der *vollen* Route wäre ideal für die Streckenberechnung,
    # aber die Input-CSV hier basiert auf den *optimierten* Punkten.
    # Daher können wir die Strecke im Ort nur *annähernd* schätzen.
    # Wir benötigen eine Distanzspalte. Wenn sie nicht da ist, können wir die Strecke nicht berechnen.
    required_cols = ["City"]
    if not all(col in df.columns for col in required_cols):
        print(f"❌ Fehler: Fehlende Spalten in {input_csv_path}. Benötigt: {required_cols}")
        sys.exit(1)

    # Optionale Distanzspalte prüfen
    has_distance = 'Distanz (km)' in df.columns or 'Strecke Delta (km)' in df.columns
    distance_col = None
    if 'Distanz (km)' in df.columns:
        distance_col = 'Distanz (km)'
        metadata['distance_column_used'] = 'Distanz (km)'
    elif 'Strecke Delta (km)' in df.columns:
        # Wenn nur Delta da ist, berechne kumulative Distanz neu (annähernd!)
        print("[Warnung] 'Distanz (km)' fehlt, berechne Annäherung aus 'Strecke Delta (km)'.")
        df['Distanz_approx_km'] = df['Strecke Delta (km)'].cumsum()
        distance_col = 'Distanz_approx_km'
        metadata['distance_column_used'] = 'Strecke Delta (km) (approximated)'
        has_distance = True
    else:
        print("[Warnung] Keine Distanzspalte gefunden. 'Strecke im Ort (km)' wird nicht berechnet.")
        metadata['distance_column_used'] = 'none'
    
    metadata['has_distance_column'] = has_distance


    # --- Orte filtern und analysieren ---
    # === ALGORITHMUS-PERFORMANCE-TRACKING ===
    algorithm_start = time.time()
    
    # Ignoriere unsinnige oder fehlerhafte Ortsnamen
    # Konvertiere alle Einträge in der 'City'-Spalte sicherheitshalber zu Strings
    df['City'] = df['City'].astype(str)
    
    # Analyse der ursprünglichen Daten
    original_unique_places = df['City'].nunique()
    metadata['original_unique_places'] = original_unique_places
    
    ignore_places = ["Unbekannter Ort", "Fehler", "Keine PLZ", "", "nan", "None"]
    df_filtered = df[~df["City"].isin(ignore_places)].copy() # copy() um SettingWithCopyWarning zu vermeiden
    
    # Filtering-Efficiency-Metriken
    filtered_points = len(df_filtered)
    filter_efficiency = (filtered_points / len(df)) * 100 if len(df) > 0 else 0
    metadata['points_after_filtering'] = filtered_points
    metadata['filter_efficiency_percent'] = round(filter_efficiency, 2)
    metadata['places_filtered_out'] = len(df) - filtered_points

    if df_filtered.empty:
        metadata['error_message'] = 'No significant places found after filtering'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print("[Warnung] Keine signifikanten Orte nach Filterung gefunden.")
        
        empty_df = pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"])
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            additional_metadata=metadata
        )
        print(f"[OK] Leere Ortszusammenfassungs-CSV gespeichert: {output_csv_path}")
        return

    # === PLACE-GROUPING-ALGORITHMUS ===
    grouping_start = time.time()
    grouped = df_filtered.groupby("City")
    unique_places_after_filtering = df_filtered['City'].nunique()
    metadata['unique_places_after_filtering'] = unique_places_after_filtering
    metadata['place_diversity_score'] = round((unique_places_after_filtering / filtered_points) * 100, 2) if filtered_points > 0 else 0

    results = []
    distance_calculation_start = time.time()
    total_distance_calculated = 0
    places_with_distance = 0
    
    for city, group in grouped:
        count = len(group)
        dist_in_place = 0.0

        if has_distance:
            # === DISTANZ-BERECHNUNG-ALGORITHMUS ===
            distance_calc_start = time.time()
            # Berechne Distanz im Ort: Max(Distanz) - Min(Distanz) innerhalb der Gruppe
            # Dies ist eine Annäherung, da die Punkte vereinfacht sind!
            min_dist = group[distance_col].min()
            max_dist = group[distance_col].max()
            dist_in_place = max_dist - min_dist
            
            if dist_in_place > 0:
                total_distance_calculated += dist_in_place
                places_with_distance += 1
                
            # Individual distance calculation times not tracked in unified system
        else:
            dist_in_place = np.nan # Markiere als nicht berechenbar

        results.append({
            "Ort": city,
            "Vorkommen": count,
            "Strecke im Ort (km)": dist_in_place
        })
    
    # Distance-Calculation-Performance-Metriken
    metadata['distance_calculation_time_sec'] = round(time.time() - distance_calculation_start, 3)
    metadata['total_distance_calculated_km'] = round(total_distance_calculated, 2)
    metadata['places_with_distance_calculation'] = places_with_distance
    metadata['average_distance_per_place_km'] = round(total_distance_calculated / places_with_distance, 2) if places_with_distance > 0 else 0

    # --- Ergebnisse speichern ---
    output_generation_start = time.time()
    result_df = pd.DataFrame(results)
    
    # Algorithmus-Performance-Abschluss
    metadata['algorithm_processing_time_sec'] = round(time.time() - algorithm_start, 3)
    
    # Sortieren, z.B. nach Anzahl Vorkommen oder Strecke (falls berechnet)
    sort_by_col = "Strecke im Ort (km)" if has_distance else "Vorkommen"
    result_df = result_df.sort_values(by=sort_by_col, ascending=False, na_position='last')
    
    # Output-Quality-Metriken
    metadata['final_places_count'] = len(result_df)
    metadata['extraction_efficiency_percent'] = round((len(result_df) / original_unique_places) * 100, 2) if original_unique_places > 0 else 0

    try:
        metadata['output_generation_time_sec'] = round(time.time() - output_generation_start, 3)
        metadata['success'] = True
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        metadata['processing_efficiency_points_per_sec'] = round(metadata['input_track_points'] / metadata['total_runtime_sec'], 1) if metadata['total_runtime_sec'] > 0 else 0
        
        write_csv_with_metadata(
            dataframe=result_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            additional_metadata=metadata,
            float_format='%.2f'
        )
        
        print(f"[OK] Ortszusammenfassung gespeichert ({len(result_df)} Orte): {output_csv_path}")
        print(f"[Performance] Extracted {len(result_df)} unique places from {metadata['input_track_points']} track points")
        print(f"[Metadaten] Quality Score: {metadata['place_diversity_score']}/100, "
              f"Filter Efficiency: {metadata['filter_efficiency_percent']}%, "
              f"Runtime: {metadata['total_runtime_sec']}s")
        
    except Exception as e:
        metadata['success'] = False
        metadata['error_message'] = f'Output write error: {str(e)}'
        metadata['output_generation_time_sec'] = round(time.time() - output_generation_start, 3)
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Konnte Ortszusammenfassungs-CSV nicht schreiben: {output_csv_path} - {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    


if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Extract significant places from geocoded track data.")
    parser.add_argument("--input-csv", required=True, help="Path to the input CSV file with location data (output of step 4).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with places summary.")
    parser.add_argument("--basename", help="Basename for metadata files (optional).")
    args = parser.parse_args()

    extract_places(args.input_csv, args.output_csv, args.basename)