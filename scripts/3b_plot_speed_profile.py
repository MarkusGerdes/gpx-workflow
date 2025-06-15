#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3b_plot_speed_profile.py
------------------------
Generates a detailed 3-segment speed profile plot with pause detection
and elevation overlay. Includes comprehensive pause analysis and statistics.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "3b_plot_speed_profile.py"
SCRIPT_VERSION = "2.3.0" # Vollständiges Metadaten-System + Speed-Profile-Performance-Tracking
SCRIPT_DESCRIPTION = "3-segment speed profile with pause detection and elevation overlay"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v2.1.0 (pre-2025): Fixed all_pauses error, enhanced pause detection
v2.2.0 (2025-06-07): Standardized header, improved pause categorization and visualization
v2.3.0 (2025-06-08): Vollständiges Metadaten-System + Speed-Profile-Performance-Tracking
- Visualization-Algorithm-Performance-Tracking für Multi-Segment-Analysis
- Pause-Detection-Algorithm-Performance mit Speed und Time-Based-Detection
- Plot-Generation-Performance-Metriken für Matplotlib-Rendering und DPI-Optimization
- Data-Quality-Analysis für Speed-Outlier-Detection und Data-Smoothing
- Segment-Analysis-Performance mit Statistical-Computing-Metriken
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "speed_profile"
INPUT_FILE_PATTERN = "*_track_data_full_with_speed.csv"
OUTPUT_FILE_PATTERN = "*_speed_profile.png"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "matplotlib>=3.3.0",
    "numpy>=1.20.0"
]

# === IMPORTS ===
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime

def save_metadata_as_text_header(output_png_path: str, metadata: dict):
    """Save speed profile visualization metadata as text file with the PNG."""
    # Create text metadata file path (parallel to PNG)
    metadata_txt_path = output_png_path.replace('.png', '_metadata.txt')
    
    try:
        with open(metadata_txt_path, 'w', encoding='utf-8') as f:
            f.write("# Speed Profile Visualization Performance Metadata\n")
            f.write(f"# Script: {metadata['script_name']} v{metadata['script_version']}\n")
            f.write(f"# Generated: {metadata['timestamp']}\n")
            f.write(f"# Description: {SCRIPT_DESCRIPTION}\n")
            f.write(f"# Category: Visualization + Pause Detection + Multi-Segment Analysis\n")
            f.write("#\n")
            f.write(f"# Input Analysis:\n")
            f.write(f"# - Input File: {metadata['input_file']}\n")
            f.write(f"# - Input File Size: {metadata['input_file_size_mb']} MB\n")
            f.write(f"# - Data Points: {metadata['input_data_points']}\n")
            f.write(f"# - Columns: {metadata['input_columns_count']}\n")
            f.write(f"# - Has Elevation: {metadata['has_elevation_data']}\n")
            f.write(f"# - Has Time Data: {metadata['has_time_data']}\n")
            f.write("#\n")
            f.write(f"# Speed Analysis:\n")
            f.write(f"# - Speed Column Used: {metadata['speed_column_used']}\n")
            f.write(f"# - Smoothing Applied: {metadata['smoothing_applied']}\n")
            f.write(f"# - Total Distance: {metadata['total_distance_km']} km\n")
            f.write(f"# - Overall Avg Speed: {metadata['overall_avg_speed_kmh']} km/h\n")
            f.write(f"# - Overall Max Speed: {metadata['overall_max_speed_kmh']} km/h\n")
            f.write(f"# - Moving Avg Speed: {metadata['moving_avg_speed_kmh']} km/h\n")
            f.write("#\n")
            f.write(f"# Pause Detection:\n")
            f.write(f"# - Detection Method: {metadata['pause_detection_method']}\n")
            f.write(f"# - Speed-Based Pauses: {metadata['speed_based_pauses']}\n")
            f.write(f"# - Time-Based Pauses: {metadata['time_based_pauses']}\n")
            f.write(f"# - Total Pauses: {metadata['total_pauses_detected']}\n")
            f.write(f"# - Total Pause Time: {metadata['total_pause_time_sec']} seconds\n")
            f.write(f"# - Average Pause Duration: {metadata['avg_pause_duration_sec']} seconds\n")
            f.write(f"# - Pause Detection Time: {metadata['pause_detection_time_sec']} seconds\n")
            f.write("#\n")
            f.write(f"# Data Quality:\n")
            f.write(f"# - Outliers Detected: {metadata['outliers_detected']}\n")
            f.write(f"# - Outliers Filtered: {metadata['outliers_filtered_percent']}%\n")
            f.write(f"# - Data Quality Score: {metadata['data_quality_score']}/100\n")
            f.write("#\n")
            f.write(f"# Plot Generation:\n")
            f.write(f"# - Segments: {metadata['segment_count']}\n")
            f.write(f"# - Plot DPI: {metadata['plot_dpi']}\n")
            f.write(f"# - Plot Dimensions: {metadata['plot_width_px']}x{metadata['plot_height_px']} px\n")
            f.write(f"# - Plot File Size: {metadata['plot_file_size_kb']} KB\n")
            f.write(f"# - Matplotlib Backend: {metadata['matplotlib_backend']}\n")
            f.write("#\n")
            f.write(f"# Performance Metrics:\n")
            f.write(f"# - Data Analysis Time: {metadata['data_analysis_time_sec']} seconds\n")
            f.write(f"# - Segment Processing Time: {metadata['segment_processing_time_sec']} seconds\n")
            f.write(f"# - Plot Generation Time: {metadata['plot_generation_time_sec']} seconds\n")
            f.write(f"# - Plot Save Time: {metadata['plot_save_time_sec']} seconds\n")
            f.write(f"# - Total Runtime: {metadata['total_runtime_sec']} seconds\n")
            f.write(f"# - Visualization Efficiency: {metadata['visualization_efficiency_points_per_sec']} points/sec\n")
            f.write("#\n")
            f.write(f"# Result:\n")
            f.write(f"# - Success: {metadata['success']}\n")
            if metadata['error_message']:
                f.write(f"# - Error: {metadata['error_message']}\n")
            f.write(f"# - Output File: {metadata['output_file']}\n")
            
        print(f"[Metadata] Speed profile metadata saved to: {metadata_txt_path}")
        
    except Exception as e:
        print(f"[Warning] Could not save metadata text file: {e}")

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def plot_speed_profile(input_csv_path: str, output_png_path: str, smooth_window_name: str = ""):
    """Generates 3-segment speed profile plot with comprehensive performance tracking."""
    run_start_time = datetime.now()
    print_script_info()
    print(f"[Info] Generating 3-segment speed profile plot for: {input_csv_path}")
    
    # Metadaten-Initialisierung
    metadata = {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'timestamp': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': input_csv_path,
        'output_file': output_png_path,
        'input_file_size_mb': 0.0,
        'input_data_points': 0,
        'input_columns_count': 0,
        'speed_column_used': '',
        'has_elevation_data': False,
        'has_time_data': False,
        'smoothing_applied': False,
        'outliers_detected': 0,
        'outliers_filtered_percent': 0.0,
        'pause_detection_method': '',
        'speed_based_pauses': 0,
        'time_based_pauses': 0,
        'combined_pauses': 0,
        'total_pauses_detected': 0,
        'avg_pause_duration_sec': 0.0,
        'total_pause_time_sec': 0.0,
        'pause_detection_time_sec': 0.0,
        'data_analysis_time_sec': 0.0,
        'segment_processing_time_sec': 0.0,
        'plot_generation_time_sec': 0.0,
        'plot_save_time_sec': 0.0,
        'total_distance_km': 0.0,
        'overall_avg_speed_kmh': 0.0,
        'overall_max_speed_kmh': 0.0,
        'moving_avg_speed_kmh': 0.0,
        'segment_count': 3,
        'plot_dpi': 150,
        'plot_width_px': 0,
        'plot_height_px': 0,
        'plot_file_size_kb': 0.0,
        'matplotlib_backend': '',
        'data_quality_score': 0.0,
        'visualization_efficiency_points_per_sec': 0.0,
        'total_runtime_sec': 0.0,
        'success': False,
        'error_message': ''
    }
    try:
        # Input-File-Analysis
        if os.path.exists(input_csv_path):
            file_size = os.path.getsize(input_csv_path) / (1024 * 1024)  # MB
            metadata['input_file_size_mb'] = round(file_size, 3)
            
        data_analysis_start = time.time()
        df = pd.read_csv(input_csv_path, comment='#')
        
        # Input-Daten-Statistiken
        metadata['input_data_points'] = len(df)
        metadata['input_columns_count'] = len(df.columns)
        metadata['has_elevation_data'] = 'Elevation (m)' in df.columns
        metadata['has_time_data'] = 'Time' in df.columns or 'Timestamp' in df.columns
        metadata['matplotlib_backend'] = plt.get_backend()
        
        if df.empty:
            metadata['error_message'] = 'Input CSV is empty'
            metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            
            # Erstelle leere PNG und Metadaten
            Path(output_png_path).touch()
            
            # Speichere Metadaten als Textdatei
            save_metadata_as_text_header(output_png_path, metadata)
            
            print(f"[OK] Leere PNG für Geschwindigkeitsprofil erstellt: {output_png_path}")
            return

        required_cols = ['Distanz (km)', 'Geschwindigkeit (km/h)']
        if not all(col in df.columns for col in required_cols):
            metadata['error_message'] = f'Missing required columns: {required_cols}'
            metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
            print(f"[Fehler] Benötigte Spalten {required_cols} nicht im Input CSV gefunden.")
            
            # Erstelle leere PNG und Metadaten
            Path(output_png_path).touch()
            
            # Speichere Metadaten als Textdatei
            save_metadata_as_text_header(output_png_path, metadata)
            
            print(f"[OK] Leere PNG (fehlende Spalten) erstellt: {output_png_path}")
            return

        # Entscheide, welche Geschwindigkeitsspalte verwendet wird
        speed_col_to_plot = 'Geschwindigkeit (km/h)'
        speed_col_label = 'Geschwindigkeit (km/h)'
        metadata['speed_column_used'] = speed_col_to_plot
        metadata['smoothing_applied'] = False
        
        if smooth_window_name and smooth_window_name in df.columns:
            speed_col_to_plot = smooth_window_name
            window_size = smooth_window_name.split("W")[-1].split(")")[0] if "W" in smooth_window_name else "?"
            speed_col_label = f'Geschwindigkeit geglättet (W{window_size})'
            metadata['speed_column_used'] = speed_col_to_plot
            metadata['smoothing_applied'] = True
            print(f"[Info] Verwende geglättete Geschwindigkeitsspalte: {speed_col_to_plot}")
        elif smooth_window_name:
            print(f"[Warnung] Geglättete Geschwindigkeitsspalte '{smooth_window_name}' nicht gefunden. Verwende Rohdaten.")
        
        # Grundlegende Datenstatistiken
        metadata['total_distance_km'] = round(df['Distanz (km)'].max(), 2)
        metadata['overall_avg_speed_kmh'] = round(df[speed_col_to_plot].mean(), 2)
        metadata['overall_max_speed_kmh'] = round(df[speed_col_to_plot].max(), 2)

        # PAUSENERKENNUNG auf ROHDATEN
        pause_detection_start = time.time()
        df_raw = df.copy()
        
        # === KONFIGURATION PAUSENERKENNUNG ===
        pause_threshold_speed = 2.0        # km/h - Geschwindigkeit unter der als "Pause" gilt
        min_pause_points = 3               # Mindestanzahl GPS-Punkte für gültige Pause
        min_pause_duration = 10            # Sekunden - Mindestdauer für relevante Pausen
        gap_threshold_multiplier = 5       # Faktor für Zeitlücken-Erkennung (5x normales Intervall)
        min_gap_duration = 60              # Sekunden - Mindest-Zeitlücke
        duplicate_tolerance_km = 0.1       # km - Toleranz für Duplikat-Erkennung (100m)
        
        metadata['pause_detection_method'] = 'speed_and_time_based'
        
        speed_pause_mask = df_raw[speed_col_to_plot] <= pause_threshold_speed
        
        # === ZEIT-BASIERTE PAUSEN ERKENNEN ===
        time_based_pauses = []
        time_col = None
        avg_interval_seconds = 5  # Fallback GPS-Intervall wenn keine Zeitstempel
        
        if 'Time' in df_raw.columns or 'Timestamp' in df_raw.columns:
            time_col = 'Time' if 'Time' in df_raw.columns else 'Timestamp'
            try:
                df_raw[time_col] = pd.to_datetime(df_raw[time_col])
                time_diffs = df_raw[time_col].diff().dt.total_seconds()
                median_interval = time_diffs.median()
                
                # Zeitlücken-Schwellwert: Größer als Mindest-Gap UND 5x normales Intervall
                gap_threshold = max(min_gap_duration, median_interval * gap_threshold_multiplier)
                large_gaps = time_diffs > gap_threshold
                
                print(f"[Info] Normales GPS-Intervall: {median_interval:.1f}s, Erkenne Lücken > {gap_threshold:.0f}s")
                
                for i, is_gap in enumerate(large_gaps):
                    if is_gap and i > 0:
                        gap_duration = time_diffs.iloc[i]
                        gap_km = df_raw.iloc[i-1]['Distanz (km)']
                        
                        # Filter: Nur Zeitlücken >= Mindestdauer
                        if gap_duration >= min_pause_duration:
                            time_based_pauses.append((i-1, i, gap_km, gap_duration, 'Zeitlücke'))
                            print(f"[Info] Zeitlücke gefunden bei {gap_km:.1f} km: {gap_duration:.0f}s")
                        else:
                            print(f"[Debug] Kurze Zeitlücke ignoriert bei {gap_km:.1f} km: {gap_duration:.0f}s")
            except Exception as e:
                print(f"[Info] Zeitstempel-Verarbeitung fehlgeschlagen: {e}")
                time_col = None
        else:
            print("[Info] Keine Zeitstempel gefunden, verwende geschätzte Intervalle")
        
        # === GESCHWINDIGKEITS-BASIERTE PAUSEN SAMMELN ===
        pause_blocks = []
        in_pause = False
        pause_start = None
        
        for i, is_pause in enumerate(speed_pause_mask):
            if is_pause and not in_pause:
                pause_start = i
                in_pause = True
            elif not is_pause and in_pause:
                if i - pause_start >= min_pause_points:
                    # Berechne Pausendauer
                    if time_col and not df_raw.iloc[pause_start:i][time_col].isna().any():
                        duration_seconds = (df_raw.iloc[i-1][time_col] - df_raw.iloc[pause_start][time_col]).total_seconds()
                    else:
                        duration_seconds = (i - pause_start) * avg_interval_seconds
                    
                    # Filter: Nur Pausen >= Mindestdauer
                    if duration_seconds >= min_pause_duration:
                        pause_km = df_raw.iloc[pause_start]['Distanz (km)']
                        pause_blocks.append((pause_start, i-1, pause_km, duration_seconds, 'Geschwindigkeit'))
                        print(f"[Debug] Geschwindigkeits-Pause bei {pause_km:.1f} km: {duration_seconds:.0f}s")
                    else:
                        print(f"[Debug] Kurze Geschwindigkeits-Pause ignoriert: {duration_seconds:.0f}s")
                in_pause = False
                
        # Letzte Pause falls am Ende
        if in_pause and len(df_raw) - pause_start >= min_pause_points:
            if time_col and not df_raw.iloc[pause_start:][time_col].isna().any():
                duration_seconds = (df_raw.iloc[-1][time_col] - df_raw.iloc[pause_start][time_col]).total_seconds()
            else:
                duration_seconds = (len(df_raw) - pause_start) * avg_interval_seconds
            
            # Filter: Nur Pausen >= Mindestdauer
            if duration_seconds >= min_pause_duration:
                pause_km = df_raw.iloc[pause_start]['Distanz (km)']
                pause_blocks.append((pause_start, len(df_raw)-1, pause_km, duration_seconds, 'Geschwindigkeit'))
                print(f"[Debug] End-Pause bei {pause_km:.1f} km: {duration_seconds:.0f}s")
            else:
                print(f"[Debug] Kurze End-Pause ignoriert: {duration_seconds:.0f}s")
        
        # ALLE PAUSEN KOMBINIEREN - HIER IST DER FIX!
        all_pauses = pause_blocks + time_based_pauses
        all_pauses.sort(key=lambda x: x[2])  # Sortiere nach km-Position
        
        # Pause-Detection-Performance-Metriken
        metadata['pause_detection_time_sec'] = round(time.time() - pause_detection_start, 3)
        metadata['speed_based_pauses'] = len(pause_blocks)
        metadata['time_based_pauses'] = len(time_based_pauses)
        metadata['total_pauses_detected'] = len(all_pauses)
        
        if all_pauses:
            total_pause_time = sum(p[3] for p in all_pauses)
            metadata['total_pause_time_sec'] = round(total_pause_time, 1)
            metadata['avg_pause_duration_sec'] = round(total_pause_time / len(all_pauses), 1)
        
        print(f"[Info] {len(pause_blocks)} Geschwindigkeits-Pausen + {len(time_based_pauses)} Zeit-Lücken = {len(all_pauses)} gesamt")

        # === DATEN FÜR VISUALISIERUNG BEREINIGEN ===
        data_cleaning_start = time.time()
        df_clean = df.copy()
        max_realistic_speed = 80  # km/h - Maximalgeschwindigkeit für Plausibilitätsprüfung
        outlier_mask = df_clean[speed_col_to_plot] > max_realistic_speed
        metadata['outliers_detected'] = int(outlier_mask.sum())
        metadata['outliers_filtered_percent'] = round((outlier_mask.sum() / len(df_clean)) * 100, 2) if len(df_clean) > 0 else 0
        
        if outlier_mask.sum() > 0:
            print(f"[Info] Entferne {outlier_mask.sum()} unrealistische Geschwindigkeitswerte (>{max_realistic_speed} km/h)")
            df_clean.loc[outlier_mask, speed_col_to_plot] = np.nan
            df_clean[speed_col_to_plot] = df_clean[speed_col_to_plot].interpolate()
        
        # Moving-Speed-Statistik (ohne Pausen)
        moving_mask = df_clean[speed_col_to_plot] > pause_threshold_speed
        if moving_mask.sum() > 0:
            metadata['moving_avg_speed_kmh'] = round(df_clean.loc[moving_mask, speed_col_to_plot].mean(), 2)
        
        metadata['data_analysis_time_sec'] = round(time.time() - data_analysis_start, 3)

        # === PLOT-SETUP ===
        plot_generation_start = time.time()
        total_distance = df_clean['Distanz (km)'].max()
        num_segments = 3  # Anzahl der Segment-Plots
        segment_size = total_distance / num_segments
        print(f"[Info] Gesamtdistanz: {total_distance:.1f} km, Segmentgröße: {segment_size:.1f} km")

        max_speed_overall = df_clean[speed_col_to_plot].max()
        y_axis_buffer = 1.05  # 5% Puffer über Maximum
        y_max = max_speed_overall * y_axis_buffer

        fig, axes = plt.subplots(num_segments, 1, figsize=(14, 12), sharex=False)
        segment_stats = []
        
        # Segment-Processing-Performance
        segment_processing_start = time.time()
        
        for i in range(num_segments):
            start_km = i * segment_size
            end_km = (i + 1) * segment_size
            
            # Daten für dieses Segment filtern
            segment_mask = (df_clean['Distanz (km)'] >= start_km) & (df_clean['Distanz (km)'] <= end_km)
            segment_df = df_clean[segment_mask].copy()
            
            if segment_df.empty:
                print(f"[Warnung] Segment {i+1} ist leer")
                continue
            
            # Statistiken für dieses Segment berechnen
            avg_speed = segment_df[speed_col_to_plot].mean()
            max_speed_segment = segment_df[speed_col_to_plot].max()
            segment_stats.append((i+1, start_km, end_km, avg_speed, max_speed_segment))
            
            # === GESCHWINDIGKEIT PLOTTEN ===
            color_speed = 'tab:red'  # Farbe für Geschwindigkeitslinie
            axes[i].plot(segment_df['Distanz (km)'], segment_df[speed_col_to_plot], 
                        color=color_speed, alpha=0.8, linewidth=1.5, label='Geschwindigkeit')
            
            # === PAUSEN MARKIEREN - NUR ZEITANGABEN MIT FARBEN ===
            segment_pause_count = 0
            segment_time_gaps = 0
            segment_combined = 0
            
            # Sammle alle Pausen in diesem Segment für optimale Höhenverteilung
            segment_pauses = [p for p in all_pauses if start_km <= p[2] <= end_km]
            
            if len(segment_pauses) > 0:
                # === HÖHENVERTEILUNG MIT MAXIMALEM ABSTAND ===
                min_height = 0.75    # 75% der Y-Achse - untere Grenze für Markierungen
                max_height = 0.95    # 95% der Y-Achse - obere Grenze für Markierungen
                if len(segment_pauses) == 1:
                    heights = [max_height]
                else:
                    # Verteile gleichmäßig über verfügbaren Bereich für maximalen Abstand
                    height_range = max_height - min_height
                    heights = [min_height + (i * height_range / (len(segment_pauses) - 1)) 
                              for i in range(len(segment_pauses))]
                    # Alterniere zwischen oben und unten für bessere Verteilung
                    heights = [heights[i] if i % 2 == 0 else heights[-(i//2+1)] for i in range(len(heights))]
            
            for idx, (pause_start_idx, pause_end_idx, pause_km, duration_seconds, pause_type) in enumerate(segment_pauses):
                # === ZEITFORMAT BESTIMMEN ===
                if duration_seconds < 60:
                    time_str = f"{int(duration_seconds)}s"
                elif duration_seconds < 3600:
                    time_str = f"{int(duration_seconds/60)}m"
                else:
                    time_str = f"{duration_seconds/3600:.1f}h"
                
                # === FARBE BASIEREND AUF PAUSENTYP ===
                if '+' in pause_type:  # Kombinierte Pause (Geschwindigkeit + Zeitlücke)
                    color = 'purple'
                    segment_combined += 1
                elif pause_type == 'Geschwindigkeit':
                    color = 'red'      # Geschwindigkeits-Pausen (≤ 2 km/h)
                    segment_pause_count += 1
                else:  # Zeitlücke
                    color = 'orange'   # Zeit-Lücken (GPS-Ausfälle, Tunnel)
                    segment_time_gaps += 1
                
                # Verwende optimierte Höhe für maximalen Abstand
                y_position = y_max * heights[idx]
                
                # === NUR ZEITANGABE MIT FARBE - KEIN SYMBOL, KOMPAKTE BOX ===
                pause_fontsize = 9           # Schriftgröße für Zeitangaben
                pause_box_padding = 0.1      # Padding um Zeitangabe
                pause_box_alpha = 0.8       # Transparenz der Box
                
                axes[i].text(pause_km, y_position, time_str,
                           fontsize=pause_fontsize, color=color, ha='center', va='center', 
                           weight='bold', 
                           bbox=dict(boxstyle="round,pad=0.1", facecolor='white', 
                                   alpha=pause_box_alpha, edgecolor=color, linewidth=1))
                
                # Vertikale Linie zur besseren Orientierung
                pause_line_alpha = 0.6      # Transparenz der vertikalen Linie
                axes[i].axvline(x=pause_km, color=color, linestyle=':', linewidth=1, alpha=pause_line_alpha)
            
            # === LEGENDE MIT FARBKODIERUNG FÜR PAUSENTYPEN ===
            legend_elements = []
            legend_marker_size = 8  # Größe der Marker in der Legende
            
            if segment_pause_count > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', 
                                                markersize=legend_marker_size, label=f'Geschwindigkeits-Pausen ({segment_pause_count}x)', linestyle='None'))
            if segment_time_gaps > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', 
                                                markersize=legend_marker_size, label=f'Zeit-Lücken ({segment_time_gaps}x)', linestyle='None'))
            if segment_combined > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='purple', 
                                                markersize=legend_marker_size, label=f'Kombinierte Pausen ({segment_combined}x)', linestyle='None'))
            
            # === DURCHSCHNITTSGESCHWINDIGKEIT (NUR FAHRBEREICHE) ===
            moving_mask = segment_df[speed_col_to_plot] > pause_threshold_speed
            if moving_mask.sum() > 0:
                avg_speed_moving = segment_df.loc[moving_mask, speed_col_to_plot].mean()
                legend_elements.append(plt.Line2D([0], [0], color='darkred', linestyle='--', 
                                                label=f'Ø Fahrt {avg_speed_moving:.1f} km/h'))
                axes[i].axhline(y=avg_speed_moving, color='darkred', linestyle='--', alpha=0.7)
            else:
                legend_elements.append(plt.Line2D([0], [0], color='darkred', linestyle='--', 
                                                label=f'Ø {avg_speed:.1f} km/h'))
                axes[i].axhline(y=avg_speed, color='darkred', linestyle='--', alpha=0.7)
            
            # Geschwindigkeitslinie für Legende
            legend_elements.insert(0, plt.Line2D([0], [0], color=color_speed, linewidth=1.5, 
                                               label='Geschwindigkeit', alpha=0.8))
            
            # Höhenprofil (optional)
            if 'Elevation (m)' in df_clean.columns:
                ax2 = axes[i].twinx()
                color_elevation = 'tab:blue'
                
                # Berechne Höhen-Range für dieses Segment
                segment_min_elevation = segment_df['Elevation (m)'].min()
                segment_max_elevation = segment_df['Elevation (m)'].max()
                elevation_range = segment_max_elevation - segment_min_elevation
                
                # Puffer für bessere Darstellung
                elevation_buffer = max(10, elevation_range * 0.1)  # Mindestens 10m Puffer
                y_min_elevation = segment_min_elevation - elevation_buffer
                y_max_elevation = segment_max_elevation + elevation_buffer
                
                ax2.plot(segment_df['Distanz (km)'], segment_df['Elevation (m)'], 
                        color=color_elevation, alpha=0.3, linewidth=1.0, linestyle='-')
                ax2.fill_between(segment_df['Distanz (km)'], segment_df['Elevation (m)'], 
                                color=color_elevation, alpha=0.1)
                
                # CRITICAL: Set proper Y-axis limits for elevation
                ax2.set_ylim(y_min_elevation, y_max_elevation)
                
                ax2.set_ylabel('Höhe (m)', color=color_elevation, fontsize=10)
                ax2.tick_params(axis='y', labelcolor=color_elevation, labelsize=9)
                
                print(f"[Debug] Segment {i+1} Elevation: {segment_min_elevation:.0f}-{segment_max_elevation:.0f}m")
            
            # Achsen konfigurieren
            axes[i].set_title(f'Segment {i+1}: {start_km:.0f}-{end_km:.0f} km ' + 
                             f'(Ø {avg_speed:.1f} km/h, Max {max_speed_segment:.1f} km/h)', 
                             fontsize=12, fontweight='bold')
            axes[i].set_ylabel(speed_col_label, color=color_speed, fontsize=10)
            axes[i].tick_params(axis='y', labelcolor=color_speed, labelsize=9)
            axes[i].grid(True, which='major', linestyle=':', linewidth=0.5, color='gray', alpha=0.7)
            axes[i].legend(handles=legend_elements, loc='upper right', fontsize=9)
            axes[i].set_ylim(0, y_max)
            
            if i == 2:
                axes[i].set_xlabel('Distanz (km)', fontsize=11)
            axes[i].set_xlim(start_km, end_km)

        # === TITEL UND GESAMTSTATISTIKEN ===
        basename = os.path.basename(output_png_path).replace("_speed_profile.png", "")
        fig.suptitle(f'Geschwindigkeitsprofil (3-Segment Analyse) - {basename}', 
                    fontsize=14, fontweight='bold', y=0.98)

        # Berechne Gesamtstatistiken
        overall_avg = df_clean[speed_col_to_plot].mean()
        overall_max = df_clean[speed_col_to_plot].max()
        speed_pauses = len([p for p in all_pauses if p[4] == 'Geschwindigkeit'])
        time_gaps = len([p for p in all_pauses if p[4] == 'Zeitlücke'])
        combined_pauses = len([p for p in all_pauses if '+' in p[4]])
        
        # Erstelle Statistik-Text basierend auf verfügbaren Pausentypen
        if combined_pauses > 0:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P + {time_gaps}T + {combined_pauses}P+T'
        elif time_gaps > 0:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P + {time_gaps}T'
        else:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P'
        
        # Layout-Parameter
        top_margin = 0.94      # Oberer Rand für Titel
        bottom_margin = 0.08   # Unterer Rand für Statistiken
        stats_fontsize = 10    # Schriftgröße für Statistiken
        
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=stats_fontsize, style='italic')

        plt.tight_layout()
        plt.subplots_adjust(top=top_margin, bottom=bottom_margin)

        # === SPEICHERN ===
        plot_save_start = time.time()
        output_dir = os.path.dirname(output_png_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        plot_dpi = 150  # DPI für gespeicherte Grafik
        metadata['plot_dpi'] = plot_dpi
        
        plt.savefig(output_png_path, dpi=plot_dpi, bbox_inches='tight')
        
        # Plot-Performance-Metriken
        metadata['segment_processing_time_sec'] = round(time.time() - segment_processing_start, 3)
        metadata['plot_generation_time_sec'] = round(time.time() - plot_generation_start, 3)
        metadata['plot_save_time_sec'] = round(time.time() - plot_save_start, 3)
        
        # File-Size-Analysis
        if os.path.exists(output_png_path):
            plot_file_size = os.path.getsize(output_png_path) / 1024  # KB
            metadata['plot_file_size_kb'] = round(plot_file_size, 1)
            
        # Plot-Dimensions (approximated from DPI and figure size)
        metadata['plot_width_px'] = int(14 * plot_dpi)  # 14 inches * DPI
        metadata['plot_height_px'] = int(12 * plot_dpi)  # 12 inches * DPI
        
        plt.close(fig)
        
        # === AUSGABE DER SEGMENT-STATISTIKEN ===
        print(f"[Info] Segment-Statistiken:")
        for seg_num, start, end, avg, max_seg in segment_stats:
            print(f"  Segment {seg_num} ({start:.0f}-{end:.0f} km): Ø {avg:.1f} km/h, Max {max_seg:.1f} km/h")
        
        # === FINALE METADATEN UND SPEICHERUNG ===
        metadata['success'] = True
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        metadata['visualization_efficiency_points_per_sec'] = round(metadata['input_data_points'] / metadata['total_runtime_sec'], 1) if metadata['total_runtime_sec'] > 0 else 0
        
        # Data-Quality-Score berechnen (0-100)
        quality_factors = [
            min(metadata['input_data_points'] / 1000, 1.0) * 20,  # Datenpunkte-Qualität (20%)
            (1 - metadata['outliers_filtered_percent'] / 100) * 25,  # Outlier-Bereinigung (25%)
            min(metadata['total_pauses_detected'], 1) * 15,  # Pause-Detection-Success (15%)
            (1 if metadata['has_elevation_data'] else 0.5) * 20,  # Elevation-Data-Availability (20%)
            (1 if metadata['has_time_data'] else 0.5) * 20  # Time-Data-Availability (20%)
        ]
        metadata['data_quality_score'] = round(sum(quality_factors), 1)
        
        # Speichere Metadaten als Textdatei
        save_metadata_as_text_header(output_png_path, metadata)
        
        print(f"[OK] 3-Segment Geschwindigkeitsprofil gespeichert: {output_png_path}")
        print(f"[Metadaten] Quality Score: {metadata['data_quality_score']}/100, "
              f"Pauses: {metadata['total_pauses_detected']}, "
              f"Runtime: {metadata['total_runtime_sec']}s")

    except FileNotFoundError:
        metadata['success'] = False
        metadata['error_message'] = f'Input file not found: {input_csv_path}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        
        # Speichere Error-Metadaten
        save_metadata_as_text_header(output_png_path.replace('.png', '_error.png'), metadata)
        sys.exit(1)
    except Exception as e:
        metadata['success'] = False
        metadata['error_message'] = f'Plot generation error: {str(e)}'
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[Fehler] Fehler beim Erstellen des Geschwindigkeitsprofils: {input_csv_path} - {e}")
        
        # Speichere Error-Metadaten
        try:
            save_metadata_as_text_header(output_png_path.replace('.png', '_error.png'), metadata)
        except:
            pass
            
        try:
            Path(output_png_path).touch()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Plot 3-segment speed profile from track data.")
    parser.add_argument("input_csv", help="Path to input CSV with speed data (from 2d).")
    parser.add_argument("output_png", help="Path to save the output PNG plot.")
    parser.add_argument("--smooth-col-name", default="", help="Name of the smoothed speed column to use (e.g., 'Geschwindigkeit geglättet (km/h, W5)'). Optional.")
    args = parser.parse_args()
    
    plot_speed_profile(args.input_csv, args.output_png, args.smooth_col_name)
