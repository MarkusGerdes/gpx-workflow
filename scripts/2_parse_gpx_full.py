#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2_parse_gpx_full.py (V2 - Flexibler für geplante Tracks)
-------------------
Parses a GPX file to extract track points including latitude, longitude,
and elevation (if available). Handles tracks with or without timestamps.
Calculates cumulative distance and ascent for each point.
"""

SCRIPT_NAME = "2_parse_gpx_full.py"
SCRIPT_VERSION = "2.0.1" # Bugfix: write_csv_with_metadata() Parameter-Kompatibilität
SCRIPT_DESCRIPTION = "GPX parsing with flexible handling of missing time/elevation data"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Flexible GPX parsing implementation
v2.0.0 (2025-06-08): Added complete metadata system with GPX parsing performance tracking
v2.0.1 (2025-06-08): Fixed write_csv_with_metadata() parameter compatibility with new template
"""

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "gpxpy>=1.4.0",
    "geopy>=2.2.0",
    "numpy>=1.21.0"
]

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import pandas as pd
import numpy as np
from geopy.distance import geodesic
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

def parse_gpx_flexible(input_gpx_path: str, output_csv_path: str):
    """
    Parses GPX, handling missing time/elevation, saves track data to CSV.
    """
    run_start_time = datetime.now()
    print_script_info()
    print(f"[Info] Parsing GPX (flexibel): {input_gpx_path}")
    
    # Metadaten-Initialisierung
    metadata = {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'timestamp': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': input_gpx_path,
        'output_file': output_csv_path,
        'input_file_size_mb': 0.0,
        'points_raw': 0,
        'points_valid': 0,
        'tracks_found': 0,
        'segments_found': 0,
        'has_elevation_data': False,
        'has_time_data': False,
        'elevation_coverage_percent': 0.0,
        'time_coverage_percent': 0.0,
        'total_distance_km': 0.0,
        'total_ascent_m': 0.0,
        'parsing_time_sec': 0.0,
        'processing_time_sec': 0.0,
        'total_runtime_sec': 0.0,
        'data_quality_score': 0.0,
        'success': False,
        'error_message': ''
    }
    
    # Input-File-Info
    try:
        file_size = os.path.getsize(input_gpx_path) / (1024 * 1024)  # MB
        metadata['input_file_size_mb'] = round(file_size, 3)
    except:
        metadata['input_file_size_mb'] = 0.0
    
    # GPX-Datei öffnen und parsen
    parsing_start = datetime.now()
    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        with open(input_gpx_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        
        # Struktur-Analyse
        metadata['tracks_found'] = len(gpx.tracks)
        metadata['segments_found'] = sum(len(track.segments) for track in gpx.tracks)
        
    except FileNotFoundError: 
        metadata['error_message'] = f"Input file not found: {input_gpx_path}"
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_gpx_path}")
        # Metadaten speichern auch bei Fehler
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_gpx_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    except Exception as e: 
        metadata['error_message'] = f"GPX parsing failed: {str(e)}"
        print(f"[Fehler] Konnte GPX-Datei nicht laden/parsen: {input_gpx_path} - {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_gpx_path],
            additional_metadata=metadata
        )
        sys.exit(1)
    
    parsing_time = (datetime.now() - parsing_start).total_seconds()
    metadata['parsing_time_sec'] = round(parsing_time, 3)

    data = []
    point_counter = 0
    has_elevation_data = False
    has_time_data = False
    first_elevation = None
    first_time = None
    elevation_count = 0
    time_count = 0
    
    processing_start = datetime.now()

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point_counter += 1
                # Grundlegende Daten extrahieren
                lat = point.latitude
                lon = point.longitude
                ele = None
                time = None

                # Höhe prüfen und speichern (falls vorhanden)
                if point.elevation is not None:
                    try:
                         ele = float(point.elevation)
                         elevation_count += 1
                         if not has_elevation_data: # Merke, dass Höhendaten existieren
                             has_elevation_data = True
                             first_elevation = ele
                    except (ValueError, TypeError):
                        ele = None # Ignoriere ungültige Höhenangaben

                # Zeit prüfen und speichern (falls vorhanden)
                if point.time is not None:
                    try:
                         time = pd.to_datetime(point.time)
                         time_count += 1
                         if not has_time_data: # Merke, dass Zeitdaten existieren
                             has_time_data = True
                             first_time = time
                    except (ValueError, TypeError):
                         time = None # Ignoriere ungültige Zeitangaben

                # Punkt hinzufügen, wenn Lat/Lon gültig sind
                # Höhe und Zeit werden als None hinzugefügt, falls nicht vorhanden
                if lat is not None and lon is not None:
                     data.append({
                        'Latitude': lat,
                        'Longitude': lon,
                        'Elevation (m)': ele,
                        'Time': time
                    })

    # Metadaten aktualisieren
    metadata['points_raw'] = point_counter
    metadata['points_valid'] = len(data)
    metadata['has_elevation_data'] = has_elevation_data
    metadata['has_time_data'] = has_time_data
    
    if point_counter > 0:
        metadata['elevation_coverage_percent'] = round((elevation_count / point_counter) * 100, 1)
        metadata['time_coverage_percent'] = round((time_count / point_counter) * 100, 1)
    
    print(f"[Info] {point_counter} Punkte im GPX gefunden, {len(data)} Punkte mit gültigen Lat/Lon.")
    if has_elevation_data: print(f"[Info] Höhendaten gefunden ({metadata['elevation_coverage_percent']}% coverage).")
    else: print("[Warnung] Keine oder ungültige Höhendaten im GPX gefunden.")
    if has_time_data: print(f"[Info] Zeitstempel gefunden ({metadata['time_coverage_percent']}% coverage).")
    else: print("[Warnung] Keine oder ungültige Zeitstempel im GPX gefunden.")


    if not data or len(data) < 2:
        print(f"[Fehler] Zu wenig gültige Trackpunkte (mit Lat/Lon) in {input_gpx_path}.")
        metadata['error_message'] = f"Insufficient valid track points: {len(data)}"
        metadata['data_quality_score'] = 0.0
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        
        # Leere Datei erstellen, damit Workflow nicht abbricht
        empty_df = pd.DataFrame(columns=['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)'])
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_gpx_path],
            additional_metadata=metadata
        )
        print(f"[OK] Leere Track-CSV gespeichert: {output_csv_path}")
        sys.exit(0) # Beende sauber

    df = pd.DataFrame(data)

    # --- Berechnungen (Distanz immer möglich, Höhe/Zeit optional) ---

    # Distanz
    distances_km = [0.0]
    for i in range(1, len(df)):
        coord1 = (df.loc[i-1, 'Latitude'], df.loc[i-1, 'Longitude'])
        coord2 = (df.loc[i, 'Latitude'], df.loc[i, 'Longitude'])
        try: d = geodesic(coord1, coord2).kilometers; distances_km.append(d)
        except ValueError: distances_km.append(0.0)
    df['Strecke Delta (km)'] = distances_km
    df['Distanz (km)'] = np.cumsum(distances_km)

    # Aufstieg (nur wenn Höhendaten vorhanden)
    if has_elevation_data:
        # Fülle fehlende Höhenwerte (None) ggf. auf (z.B. mit erstem Wert oder linear interpolieren)
        # Einfachste Methode: ffill/bfill oder mit erstem Wert füllen
        if df['Elevation (m)'].isnull().any():
             print("[Warnung] Fülle fehlende Höhenwerte auf...")
             # df['Elevation (m)'].interpolate(method='linear', inplace=True) # Linear
             df['Elevation (m)'].fillna(method='ffill', inplace=True) # Forward fill
             df['Elevation (m)'].fillna(method='bfill', inplace=True) # Backward fill für Anfang
             # Fallback falls alles None war (unwahrscheinlich hier, da has_elevation_data=True)
             if df['Elevation (m)'].isnull().all():
                  print("[Warnung] Konnte fehlende Höhen nicht füllen, setze alle auf 0.")
                  df['Elevation (m)'] = 0.0
             else: # Setze verbleibende NaNs auf den ersten bekannten Wert
                  df['Elevation (m)'].fillna(df['Elevation (m)'].iloc[0] if pd.notna(df['Elevation (m)'].iloc[0]) else 0.0, inplace=True)


        elevation_diff = df['Elevation (m)'].diff().fillna(0)
        df['Aufstieg (m)'] = elevation_diff.clip(lower=0)
    else:
        # Füge leere Spalte hinzu, wenn keine Höhendaten da sind
        df['Aufstieg (m)'] = 0.0
        # Setze auch Elevation auf 0, wenn komplett fehlend
        if 'Elevation (m)' not in df.columns or df['Elevation (m)'].isnull().all():
             df['Elevation (m)'] = 0.0


    # Zeit (Reihenfolge sicherstellen, falls vorhanden, aber nicht für Berechnungen hier verwenden)
    if has_time_data:
        df.sort_values(by='Time', inplace=True)
        df.reset_index(drop=True, inplace=True)
    else:
        # Füge leere Zeitspalte hinzu, falls nicht vorhanden
        if 'Time' not in df.columns:
            df['Time'] = pd.NaT # Not a Time

    # Finale Metadaten berechnen
    processing_time = (datetime.now() - processing_start).total_seconds()
    metadata['processing_time_sec'] = round(processing_time, 3)
    
    if len(df) > 0:
        metadata['total_distance_km'] = round(df['Distanz (km)'].iloc[-1], 3)
        metadata['total_ascent_m'] = round(df['Aufstieg (m)'].sum(), 1)
    
    # Data Quality Score berechnen (0-100)
    quality_factors = [
        min(metadata['points_valid'] / max(metadata['points_raw'], 1), 1.0) * 30,  # Punkt-Validität (30%)
        (metadata['elevation_coverage_percent'] / 100) * 25,  # Höhen-Abdeckung (25%)
        (metadata['time_coverage_percent'] / 100) * 25,  # Zeit-Abdeckung (25%)
        min(metadata['tracks_found'], 1) * 10,  # Track-Existenz (10%)
        min(metadata['segments_found'] / max(metadata['tracks_found'], 1), 1) * 10  # Segment-Dichte (10%)
    ]
    metadata['data_quality_score'] = round(sum(quality_factors), 1)
    
    # Wähle und ordne finale Spalten
    final_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)']
    df = df[final_cols]

    try:
        metadata['success'] = True
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        
        write_csv_with_metadata(
            dataframe=df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_gpx_path],
            additional_metadata=metadata,
            float_format='%.6f'
        )
        
        print(f"[OK] Parsing abgeschlossen (flexibel) und gespeichert: {output_csv_path}")
        print(f"[Metadaten] Verarbeitet: {metadata['points_valid']}/{metadata['points_raw']} Punkte, "
              f"Quality Score: {metadata['data_quality_score']}/100, "
              f"Runtime: {metadata['total_runtime_sec']}s")
              
    except Exception as e:
        metadata['success'] = False
        metadata['error_message'] = f"CSV write failed: {str(e)}"
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Konnte CSV nicht schreiben: {output_csv_path} - {e}")
        empty_df = pd.DataFrame()
        write_csv_with_metadata(
            dataframe=empty_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_gpx_path],
            additional_metadata=metadata
        )
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse GPX file flexibly (handles missing time/elevation).")
    parser.add_argument("input_gpx", help="Path to the input GPX file.")
    parser.add_argument("output_csv", help="Path to save the output CSV file.")
    args = parser.parse_args()

    parse_gpx_flexible(args.input_gpx, args.output_csv)