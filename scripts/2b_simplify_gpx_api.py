#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2b_simplify_gpx_api.py
----------------------
Simplifies track points from a full track CSV using Ramer-Douglas-Peucker (RDP).
Optimizes track data for API calls while preserving route accuracy.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "2b_simplify_gpx_api.py"
SCRIPT_VERSION = "2.0.0" # v2.0.0 (2025-06-08): Vollständiges Performance-Tracking System für RDP-Track-Simplification
SCRIPT_DESCRIPTION = "Track simplification using RDP algorithm for optimized API calls"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic RDP simplification
v1.1.0 (2025-06-07): Standardized header, improved error handling and index tracking
v1.1.1 (2025-06-08): Fixed CSV reading to handle metadata headers with comment='#'
v2.0.0 (2025-06-08): Vollständiges Performance-Tracking System für RDP-Track-Simplification
- 30+ Performance-Metriken für umfassende RDP-Algorithm-Analyse
- Point-Reduction-Efficiency + Coordinate-Precision-Tracking
- Input-Data-Quality + Simplification-Algorithm-Performance
- Index-Mapping-Performance + Error-Handling-Metriken
- Output-Quality-Assessment + Processing-Time-Breakdown
- Compatible mit universellem v2.0.0 Metadaten-Template-System
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "api_simplification"
INPUT_FILE_PATTERN = "*_track_data_full.csv"
OUTPUT_FILE_PATTERN = "*_track_data_simplified.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "numpy>=1.20.0",
    "rdp>=0.8.0"
]

# === IMPORTS ===
import sys
import os
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import time
import csv
from rdp import rdp # pip install rdp

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def write_csv_with_metadata(filepath: str, data_dict: dict, script_info: dict):
    """Universal metadata CSV writer compatible with v2.0.0 template system."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header-Kommentare im v2.0.0 Standard-Format
            writer.writerow(['# RDP Track Simplification Performance Metadata'])
            writer.writerow([f'# Script: {script_info["name"]} v{script_info["version"]}'])
            writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([f'# Description: {script_info["description"]}'])
            writer.writerow(['# Category: RDP Algorithm + Track Simplification + Point Reduction'])
            writer.writerow(['#'])
            
            # Standard v2.0.0 CSV-Header
            writer.writerow(['Metric', 'Value', 'Unit', 'Category', 'Description'])
            
            # Flache Struktur für alle Metriken
            for category, metrics in data_dict.items():
                if isinstance(metrics, dict):
                    for metric_name, metric_value in metrics.items():
                        # Unit-Bestimmung
                        if 'time' in metric_name.lower():
                            unit = 'seconds'
                        elif 'ratio' in metric_name.lower() or 'efficiency' in metric_name.lower():
                            unit = 'ratio'
                        elif 'count' in metric_name.lower() or metric_name.endswith('_points'):
                            unit = 'count'
                        elif 'percentage' in metric_name.lower() or 'reduction' in metric_name.lower():
                            unit = 'percent'
                        elif 'size' in metric_name.lower() and 'mb' in metric_name.lower():
                            unit = 'MB'
                        elif 'precision' in metric_name.lower():
                            unit = 'decimal_places'
                        else:
                            unit = 'value'
                            
                        # Description-Generierung
                        desc_map = {
                            'input_loading_time': 'Time spent loading and parsing input CSV file',
                            'rdp_algorithm_time': 'Time spent executing RDP simplification algorithm',
                            'index_mapping_time': 'Time spent mapping simplified points to original indices',
                            'output_writing_time': 'Time spent writing simplified CSV to disk',
                            'total_processing_time': 'Total end-to-end track simplification time',
                            'original_points_count': 'Number of points in input track before simplification',
                            'simplified_points_count': 'Number of points after RDP simplification',
                            'start_end_forced_points': 'Number of start/end points force-added to output',
                            'final_output_points': 'Final number of points in output CSV',
                            'point_reduction_ratio': 'Ratio of points removed (simplified/original)',
                            'point_reduction_percentage': 'Percentage of points removed from original track',
                            'coordinate_precision_used': 'Decimal places used for coordinate rounding in merge',
                            'successful_index_mappings': 'Number of simplified points successfully mapped to original indices',
                            'failed_index_mappings': 'Number of simplified points that could not be mapped',
                            'epsilon_value_used': 'RDP epsilon parameter used for simplification',
                            'input_file_size_mb': 'Size of input CSV file in megabytes',
                            'output_file_size_mb': 'Size of output CSV file in megabytes',
                            'compression_efficiency': 'File size reduction ratio (output/input)',
                            'data_quality_score': 'Quality assessment of simplification result',
                            'algorithm_efficiency': 'RDP algorithm execution efficiency score'
                        }
                        description = desc_map.get(metric_name, f'{category.replace("_", " ").title()} metric')
                        
                        writer.writerow([
                            metric_name,
                            metric_value,
                            unit,
                            category.replace('_', ' ').title(),
                            description
                        ])
                else:
                    # Handle non-dict values
                    unit = 'seconds' if 'time' in category.lower() else 'value'
                    description = f'General {category.replace("_", " ")} metric'
                    writer.writerow([category, metrics, unit, 'General', description])
                    
        print(f"[Info] RDP simplification metadata saved: {filepath}")
        
    except Exception as e:
        print(f"[Warning] Could not save metadata CSV: {e}")

def save_metadata_csv(output_path: str, metadata: dict):
    """Save metadata CSV next to output file."""
    # Generiere Metadaten-Pfad basierend auf Output-Pfad
    output_path_obj = Path(output_path)
    metadata_filename = f"{output_path_obj.stem}_rdp_metadata.csv"
    metadata_path = output_path_obj.parent / metadata_filename
    
    script_info = {
        'name': SCRIPT_NAME,
        'version': SCRIPT_VERSION,
        'description': SCRIPT_DESCRIPTION
    }
    
    write_csv_with_metadata(str(metadata_path), metadata, script_info)

def simplify_track_with_indexing(input_full_track_csv: str, output_simplified_csv: str, epsilon: float):
    print(f"[Info] Simplifying track from CSV with indexing: {input_full_track_csv}")
    print(f"  Epsilon: {epsilon}")
    
    # === PERFORMANCE-TRACKING INITIALISIERUNG ===
    start_total_time = time.time()
    
    performance_data = {
        'processing_phases': {
            'input_loading_time': None,
            'rdp_algorithm_time': None,
            'index_mapping_time': None,
            'output_writing_time': None,
            'total_processing_time': None
        },
        'input_analysis': {
            'input_file_size_mb': 0,
            'input_data_rows': 0,
            'input_columns_count': 0,
            'coordinate_data_quality': 0
        },
        'rdp_algorithm': {
            'original_points_count': 0,
            'simplified_points_count': 0,
            'epsilon_value_used': epsilon,
            'algorithm_efficiency': 0
        },
        'data_quality': {
            'point_reduction_ratio': 0,
            'point_reduction_percentage': 0,
            'start_end_forced_points': 0,
            'final_output_points': 0,
            'coordinate_precision_used': 6,
            'data_quality_score': 0
        },
        'index_mapping': {
            'successful_index_mappings': 0,
            'failed_index_mappings': 0,
            'mapping_accuracy_percentage': 0
        },
        'output_generation': {
            'output_file_size_mb': 0,
            'compression_efficiency': 0
        },
        'error_handling': {
            'processing_error': None,
            'file_not_found': False,
            'empty_result': False,
            'index_mapping_failed': False
        }
    }
    
    precision = 6  # Koordinaten-Präzision für Merge
    performance_data['data_quality']['coordinate_precision_used'] = precision
    
    try:
        output_dir = os.path.dirname(output_simplified_csv)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # === INPUT LOADING PHASE ===
        input_loading_start = time.time()
        
        # Analysiere Input-Datei
        if os.path.exists(input_full_track_csv):
            input_file_size = os.path.getsize(input_full_track_csv)
            performance_data['input_analysis']['input_file_size_mb'] = round(input_file_size / (1024 * 1024), 3)

        # CSV mit Metadaten-Header laden (Skip Header-Zeilen mit #)
        df_full = pd.read_csv(input_full_track_csv, comment='#')
        
        performance_data['input_analysis']['input_data_rows'] = len(df_full)
        performance_data['input_analysis']['input_columns_count'] = len(df_full.columns)
        performance_data['processing_phases']['input_loading_time'] = time.time() - input_loading_start

        if df_full.empty or len(df_full) < 2:
            print(f"[Warnung] Input CSV '{input_full_track_csv}' ist leer oder hat < 2 Punkte. Keine Vereinfachung, kopiere relevante Spalten.")
            cols_to_output = ['Latitude', 'Longitude']
            if not df_full.empty:
                df_full['original_index'] = df_full.index
                if 'original_index' not in cols_to_output : cols_to_output.append('original_index')
            
            # Sicherstellen, dass nur existierende Spalten ausgewählt werden
            df_to_save = pd.DataFrame(columns=cols_to_output) # Leeren DF mit den richtigen Spalten erstellen
            if not df_full.empty:
                 df_to_save = df_full[[col for col in cols_to_output if col in df_full.columns]]

            df_to_save.to_csv(output_simplified_csv, index=False, float_format='%.6f')
            print(f"[OK] Vereinfachte Daten (ggf. leer/unverändert) gespeichert: {output_simplified_csv}")
            
            # Metadaten für leeren Fall
            performance_data['data_quality']['final_output_points'] = len(df_to_save)
            performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
            save_metadata_csv(output_simplified_csv, performance_data)
            return

        # === RDP ALGORITHM PHASE ===
        rdp_algorithm_start = time.time()
        
        # Vorbereitung für RDP: Numpy-Array mit (Longitude, Latitude)
        points_for_rdp_np = df_full[['Longitude', 'Latitude']].values
        performance_data['rdp_algorithm']['original_points_count'] = len(points_for_rdp_np)

        # RDP anwenden
        print(f"[Info] Original number of points: {len(points_for_rdp_np)}")
        simplified_points_np = rdp(points_for_rdp_np, epsilon=epsilon)
        performance_data['rdp_algorithm']['simplified_points_count'] = len(simplified_points_np)
        
        performance_data['processing_phases']['rdp_algorithm_time'] = time.time() - rdp_algorithm_start
        print(f"[Info] Number of points after RDP: {len(simplified_points_np)}")

        # === INDEX MAPPING PHASE ===
        index_mapping_start = time.time()

        if len(simplified_points_np) == 0 and len(points_for_rdp_np) > 0:
             print("[Warnung] RDP resultierte in 0 Punkten. Verwende stattdessen Start- und Endpunkt.")
             # Fallback: Nur Start- und Endpunkt des Originals verwenden
             indices_to_keep = [0, len(df_full) - 1] if len(df_full) > 1 else [0]
             indices_to_keep = list(set(indices_to_keep)) # Eindeutig machen
             df_simplified_with_index = df_full.iloc[indices_to_keep].copy()
             df_simplified_with_index['original_index'] = df_simplified_with_index.index
             performance_data['index_mapping']['successful_index_mappings'] = len(df_simplified_with_index)
             performance_data['index_mapping']['failed_index_mappings'] = 0
        elif len(simplified_points_np) < 2 and len(points_for_rdp_np) >=2 :
             print("[Warnung] RDP resultierte in weniger als 2 Punkten. Füge Original-Start/Endpunkte hinzu.")
             # Erstelle DataFrame aus den wenigen RDP-Punkten
             df_rdp_temp = pd.DataFrame(simplified_points_np, columns=['Longitude', 'Latitude'])
             # Füge Start- und Endpunkte des Originals hinzu
             start_point_orig_coords = df_full.iloc[[0]][['Longitude', 'Latitude']]
             end_point_orig_coords = df_full.iloc[[-1]][['Longitude', 'Latitude']]
             
             df_combined = pd.concat([start_point_orig_coords, df_rdp_temp, end_point_orig_coords], ignore_index=True)
             df_combined.drop_duplicates(subset=['Longitude', 'Latitude'], keep='first', inplace=True)
             
             # Jetzt Indizes für diese Punkte finden
             df_full_indexed = df_full.copy()
             df_full_indexed['original_index'] = df_full_indexed.index
             df_simplified_with_index = pd.merge(
                 df_combined.round(decimals=6), # Runde für Merge
                 df_full_indexed[['Longitude', 'Latitude', 'original_index']].round(decimals=6),
                 on=['Longitude', 'Latitude'],
                 how='left'
             ).drop_duplicates(subset=['Longitude', 'Latitude'], keep='first')
            
             # Count successful mappings
             successful_mappings = (~df_simplified_with_index['original_index'].isnull()).sum()
             performance_data['index_mapping']['successful_index_mappings'] = successful_mappings
             performance_data['index_mapping']['failed_index_mappings'] = len(df_simplified_with_index) - successful_mappings
            
        else:
            # === STANDARD RDP PROCESSING ===
            # Erstelle DataFrame aus simplifizierten Punkten
            df_simplified_coords = pd.DataFrame(simplified_points_np, columns=['Longitude_s', 'Latitude_s'])
            
            # Index-Mapping vorbereiten
            df_full_indexed = df_full.copy()
            df_full_indexed['original_index'] = df_full_indexed.index
            
            # Koordinaten runden für robusteren Merge
            df_simplified_coords_rounded = df_simplified_coords.round({'Longitude_s': precision, 'Latitude_s': precision})
            df_full_indexed_rounded = df_full_indexed.round({'Longitude': precision, 'Latitude': precision})
            
            # Umbenennen für Merge
            df_simplified_coords_rounded.rename(columns={'Longitude_s': 'Longitude', 'Latitude_s': 'Latitude'}, inplace=True)
            
            # Index-Mapping durchführen
            df_simplified_with_index = pd.merge(
                df_simplified_coords_rounded,
                df_full_indexed_rounded[['Longitude', 'Latitude', 'original_index']],
                on=['Longitude', 'Latitude'],
                how='left'
            )
            
            # Präzise Koordinaten wiederherstellen
            if 'original_index' in df_simplified_with_index.columns and not df_simplified_with_index['original_index'].isnull().all():
                df_simplified_with_index.drop_duplicates(subset=['Longitude', 'Latitude'], keep='first', inplace=True)
                
                valid_indices_df = df_simplified_with_index.dropna(subset=['original_index']).copy()
                valid_indices_df['original_index'] = valid_indices_df['original_index'].astype(int)
                
                # Erstelle finalen DataFrame mit präzisen Werten
                final_simplified_df = df_full.iloc[valid_indices_df['original_index'].values][['Latitude', 'Longitude']].copy()
                final_simplified_df['original_index'] = valid_indices_df['original_index'].values
                df_simplified_with_index = final_simplified_df.reset_index(drop=True)
                
                performance_data['index_mapping']['successful_index_mappings'] = len(valid_indices_df)
                performance_data['index_mapping']['failed_index_mappings'] = len(df_simplified_coords) - len(valid_indices_df)
            else:
                print("[Warnung] Originalindizes konnten nicht zugeordnet werden. Verwende gerundete Koordinaten.")
                performance_data['error_handling']['index_mapping_failed'] = True
                df_simplified_with_index = df_simplified_coords_rounded[['Latitude', 'Longitude']].copy()
                performance_data['index_mapping']['successful_index_mappings'] = 0
                performance_data['index_mapping']['failed_index_mappings'] = len(df_simplified_coords)
        
        performance_data['processing_phases']['index_mapping_time'] = time.time() - index_mapping_start
        
        # === START/END POINTS ENFORCEMENT ===
        start_end_processing_start = time.time()
        
        if not df_full.empty:
            start_orig_data = df_full.iloc[[0]].copy()
            start_orig_data['original_index'] = start_orig_data.index[0]
            
            end_orig_data = df_full.iloc[[-1]].copy()
            end_orig_data['original_index'] = end_orig_data.index[0]
            
            # Füge Start/End-Punkte hinzu
            df_simplified_with_index = pd.concat([
                start_orig_data[['Latitude', 'Longitude', 'original_index']],
                df_simplified_with_index,
                end_orig_data[['Latitude', 'Longitude', 'original_index']]
            ], ignore_index=True)
            
            if 'original_index' in df_simplified_with_index.columns:
                df_simplified_with_index.drop_duplicates(subset=['original_index'], keep='first', inplace=True)
                df_simplified_with_index.sort_values(by='original_index', inplace=True)
            else:
                df_simplified_with_index.drop_duplicates(subset=['Latitude', 'Longitude'], keep='first', inplace=True)
                
            df_simplified_with_index.reset_index(drop=True, inplace=True)
            performance_data['data_quality']['start_end_forced_points'] = 2
        
        # === OUTPUT PREPARATION ===
        if df_simplified_with_index.empty:
            print("[Warnung] Simplification führte zu leerem DataFrame.")
            performance_data['error_handling']['empty_result'] = True
            df_to_save = pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index'])
        else:
            output_cols = ['Latitude', 'Longitude']
            if 'original_index' in df_simplified_with_index.columns:
                output_cols.append('original_index')
                df_simplified_with_index['original_index'] = pd.to_numeric(
                    df_simplified_with_index['original_index'], errors='coerce'
                ).astype('Int64')
            
            df_to_save = df_simplified_with_index[output_cols].copy()
        
        performance_data['data_quality']['final_output_points'] = len(df_to_save)
        
        # === OUTPUT WRITING PHASE ===
        output_writing_start = time.time()
        
        df_to_save.to_csv(output_simplified_csv, index=False, encoding='utf-8', float_format='%.6f')
        
        performance_data['processing_phases']['output_writing_time'] = time.time() - output_writing_start
        
        # Analysiere Output-Datei
        if os.path.exists(output_simplified_csv):
            output_file_size = os.path.getsize(output_simplified_csv)
            performance_data['output_generation']['output_file_size_mb'] = round(output_file_size / (1024 * 1024), 3)
            
            # Kompressionseffizienz
            if performance_data['input_analysis']['input_file_size_mb'] > 0:
                performance_data['output_generation']['compression_efficiency'] = round(
                    performance_data['output_generation']['output_file_size_mb'] / 
                    performance_data['input_analysis']['input_file_size_mb'], 3
                )
        
        # === FINALES PERFORMANCE-TRACKING ===
        total_processing_time = time.time() - start_total_time
        performance_data['processing_phases']['total_processing_time'] = total_processing_time
        
        # Berechne Reduktions-Metriken
        if performance_data['rdp_algorithm']['original_points_count'] > 0:
            performance_data['data_quality']['point_reduction_ratio'] = round(
                performance_data['data_quality']['final_output_points'] / performance_data['rdp_algorithm']['original_points_count'], 3
            )
            performance_data['data_quality']['point_reduction_percentage'] = round(
                (1 - performance_data['data_quality']['point_reduction_ratio']) * 100, 1
            )
        
        # Index-Mapping-Accuracy
        if performance_data['data_quality']['final_output_points'] > 0:
            performance_data['index_mapping']['mapping_accuracy_percentage'] = round(
                (performance_data['index_mapping']['successful_index_mappings'] / performance_data['data_quality']['final_output_points']) * 100, 1
            )
        
        # Qualitätsbewertung
        if performance_data['data_quality']['final_output_points'] >= 2:
            quality_score = min(100, (
                50 + # Basis-Score für erfolgreiche Verarbeitung
                25 * (performance_data['index_mapping']['successful_index_mappings'] / max(1, performance_data['rdp_algorithm']['simplified_points_count'])) + # Index-Mapping-Erfolg
                25 * (performance_data['data_quality']['point_reduction_ratio']) # Punkt-Reduktion (weniger ist besser für API)
            ))
        else:
            quality_score = 10  # Niedrige Bewertung für unbrauchbare Ergebnisse
            
        performance_data['data_quality']['data_quality_score'] = round(quality_score, 1)
        
        # Algorithm-Effizienz (Punkte pro Sekunde)
        if performance_data['processing_phases']['rdp_algorithm_time'] > 0:
            performance_data['rdp_algorithm']['algorithm_efficiency'] = round(
                performance_data['rdp_algorithm']['original_points_count'] / performance_data['processing_phases']['rdp_algorithm_time'], 1
            )
        
        print(f"[Info] Endgültige Anzahl simplifizierter Punkte: {len(df_to_save)}")
        print(f"[Performance] Total processing time: {total_processing_time:.3f} seconds")
        print(f"[Performance] Point reduction: {performance_data['data_quality']['point_reduction_percentage']:.1f}%")
        print(f"[Performance] Quality score: {performance_data['data_quality']['data_quality_score']}/100")
        print(f"[OK] Vereinfachte API-Trackdaten mit Indizes gespeichert: {output_simplified_csv}")
        
        # Speichere Metadaten
        save_metadata_csv(output_simplified_csv, performance_data)
        
    except FileNotFoundError:
        performance_data['error_handling']['file_not_found'] = True
        performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_full_track_csv}")
        pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index']).to_csv(output_simplified_csv, index=False)
        save_metadata_csv(output_simplified_csv, performance_data)
        sys.exit(1)
    except Exception as e:
        performance_data['error_handling']['processing_error'] = str(e)
        performance_data['processing_phases']['total_processing_time'] = time.time() - start_total_time
        print(f"[Fehler] Fehler bei der Vereinfachung: {input_full_track_csv} - {e}")
        pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index']).to_csv(output_simplified_csv, index=False)
        save_metadata_csv(output_simplified_csv, performance_data)
        sys.exit(1)

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Simplify track points from full CSV and keep original indices.")
    parser.add_argument("--input-csv", required=True, help="Path to the input full track data CSV (output of 2_parse_gpx_full.py).")
    parser.add_argument("--output", required=True, help="Path to save the simplified CSV (Lat, Lon, original_index).")
    parser.add_argument("--epsilon", type=float, default=0.0001, help="Epsilon value for RDP simplification (in degrees).")
    args = parser.parse_args()

    simplify_track_with_indexing(args.input_csv, args.output, args.epsilon)
