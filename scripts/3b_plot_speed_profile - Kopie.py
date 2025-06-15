#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3b_plot_speed_profile.py
------------------------
Generates a plot of the speed profile over distance,
optionally including elevation. Now with 3-segment breakdown.
"""

SCRIPT_NAME = "3b_plot_speed_profile.py"
SCRIPT_VERSION = "2.1.0"  # Fixed all_pauses error

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import argparse
import os
import sys
from pathlib import Path

def plot_speed_profile(input_csv_path: str, output_png_path: str, smooth_window_name: str = ""):
    print(f"[Info] Generating 3-segment speed profile plot for: {input_csv_path}")
    try:
        df = pd.read_csv(input_csv_path, comment='#')
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            Path(output_png_path).touch()
            print(f"[OK] Leere PNG für Geschwindigkeitsprofil erstellt: {output_png_path}")
            sys.exit(0)

        required_cols = ['Distanz (km)', 'Geschwindigkeit (km/h)']
        if not all(col in df.columns for col in required_cols):
            print(f"[Fehler] Benötigte Spalten {required_cols} nicht im Input CSV gefunden.")
            Path(output_png_path).touch()
            print(f"[OK] Leere PNG (fehlende Spalten) erstellt: {output_png_path}")
            sys.exit(1)

        # Entscheide, welche Geschwindigkeitsspalte verwendet wird
        speed_col_to_plot = 'Geschwindigkeit (km/h)'
        speed_col_label = 'Geschwindigkeit (km/h)'
        if smooth_window_name and smooth_window_name in df.columns:
            speed_col_to_plot = smooth_window_name
            window_size = smooth_window_name.split("W")[-1].split(")")[0] if "W" in smooth_window_name else "?"
            speed_col_label = f'Geschwindigkeit geglättet (W{window_size})'
            print(f"[Info] Verwende geglättete Geschwindigkeitsspalte: {speed_col_to_plot}")
        elif smooth_window_name:
            print(f"[Warnung] Geglättete Geschwindigkeitsspalte '{smooth_window_name}' nicht gefunden. Verwende Rohdaten.")

        # PAUSENERKENNUNG auf ROHDATEN
        df_raw = df.copy()
        pause_threshold_speed = 2.0  # km/h
        min_pause_points = 3
        speed_pause_mask = df_raw[speed_col_to_plot] <= pause_threshold_speed
        
        # Zeit-basierte Pausen
        time_based_pauses = []
        time_col = None
        avg_interval_seconds = 5
        
        if 'Time' in df_raw.columns or 'Timestamp' in df_raw.columns:
            time_col = 'Time' if 'Time' in df_raw.columns else 'Timestamp'
            try:
                df_raw[time_col] = pd.to_datetime(df_raw[time_col])
                time_diffs = df_raw[time_col].diff().dt.total_seconds()
                median_interval = time_diffs.median()
                gap_threshold = max(60, median_interval * 5)
                large_gaps = time_diffs > gap_threshold
                
                print(f"[Info] Normales GPS-Intervall: {median_interval:.1f}s, Erkenne Lücken > {gap_threshold:.0f}s")
                
                for i, is_gap in enumerate(large_gaps):
                    if is_gap and i > 0:
                        gap_duration = time_diffs.iloc[i]
                        gap_km = df_raw.iloc[i-1]['Distanz (km)']
                        time_based_pauses.append((i-1, i, gap_km, gap_duration, 'Zeitlücke'))
                        print(f"[Info] Zeitlücke gefunden bei {gap_km:.1f} km: {gap_duration:.0f}s")
            except Exception as e:
                print(f"[Info] Zeitstempel-Verarbeitung fehlgeschlagen: {e}")
                time_col = None
        else:
            print("[Info] Keine Zeitstempel gefunden, verwende geschätzte Intervalle")
        
        # Geschwindigkeits-basierte Pausen sammeln
        pause_blocks = []
        in_pause = False
        pause_start = None
        
        for i, is_pause in enumerate(speed_pause_mask):
            if is_pause and not in_pause:
                pause_start = i
                in_pause = True
            elif not is_pause and in_pause:
                if i - pause_start >= min_pause_points:
                    if time_col and not df_raw.iloc[pause_start:i][time_col].isna().any():
                        duration_seconds = (df_raw.iloc[i-1][time_col] - df_raw.iloc[pause_start][time_col]).total_seconds()
                    else:
                        duration_seconds = (i - pause_start) * avg_interval_seconds
                    
                    pause_km = df_raw.iloc[pause_start]['Distanz (km)']
                    pause_blocks.append((pause_start, i-1, pause_km, duration_seconds, 'Geschwindigkeit'))
                in_pause = False
                
        # Letzte Pause falls am Ende
        if in_pause and len(df_raw) - pause_start >= min_pause_points:
            if time_col and not df_raw.iloc[pause_start:][time_col].isna().any():
                duration_seconds = (df_raw.iloc[-1][time_col] - df_raw.iloc[pause_start][time_col]).total_seconds()
            else:
                duration_seconds = (len(df_raw) - pause_start) * avg_interval_seconds
            pause_km = df_raw.iloc[pause_start]['Distanz (km)']
            pause_blocks.append((pause_start, len(df_raw)-1, pause_km, duration_seconds, 'Geschwindigkeit'))
        
        # ALLE PAUSEN KOMBINIEREN - HIER IST DER FIX!
        all_pauses = pause_blocks + time_based_pauses
        all_pauses.sort(key=lambda x: x[2])  # Sortiere nach km-Position
        
        print(f"[Info] {len(pause_blocks)} Geschwindigkeits-Pausen + {len(time_based_pauses)} Zeit-Lücken = {len(all_pauses)} gesamt")

        # Daten für Visualisierung bereinigen
        df_clean = df.copy()
        max_realistic_speed = 80
        outlier_mask = df_clean[speed_col_to_plot] > max_realistic_speed
        if outlier_mask.sum() > 0:
            print(f"[Info] Entferne {outlier_mask.sum()} unrealistische Geschwindigkeitswerte (>{max_realistic_speed} km/h)")
            df_clean.loc[outlier_mask, speed_col_to_plot] = np.nan
            df_clean[speed_col_to_plot] = df_clean[speed_col_to_plot].interpolate()

        # Plot-Setup
        total_distance = df_clean['Distanz (km)'].max()
        segment_size = total_distance / 3
        print(f"[Info] Gesamtdistanz: {total_distance:.1f} km, Segmentgröße: {segment_size:.1f} km")

        max_speed_overall = df_clean[speed_col_to_plot].max()
        y_max = max_speed_overall * 1.05

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
        segment_stats = []
        
        for i in range(3):
            start_km = i * segment_size
            end_km = (i + 1) * segment_size
            
            segment_mask = (df_clean['Distanz (km)'] >= start_km) & (df_clean['Distanz (km)'] <= end_km)
            segment_df = df_clean[segment_mask].copy()
            
            if segment_df.empty:
                print(f"[Warnung] Segment {i+1} ist leer")
                continue
            
            avg_speed = segment_df[speed_col_to_plot].mean()
            max_speed_segment = segment_df[speed_col_to_plot].max()
            segment_stats.append((i+1, start_km, end_km, avg_speed, max_speed_segment))
            
            # Geschwindigkeit plotten
            color_speed = 'tab:red'
            axes[i].plot(segment_df['Distanz (km)'], segment_df[speed_col_to_plot], 
                        color=color_speed, alpha=0.8, linewidth=1.5, label='Geschwindigkeit')
            
            # Pausen markieren - NUR Zeitangaben mit Farben
            segment_pause_count = 0
            segment_time_gaps = 0
            segment_combined = 0
            
            # Sammle alle Pausen in diesem Segment für optimale Höhenverteilung
            segment_pauses = [p for p in all_pauses if start_km <= p[2] <= end_km]
            
            if len(segment_pauses) > 0:
                # Berechne optimale Höhenverteilung mit maximalem Abstand
                min_height = 0.75
                max_height = 0.95
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
                if duration_seconds < 60:
                    time_str = f"{int(duration_seconds)}s"
                elif duration_seconds < 3600:
                    time_str = f"{int(duration_seconds/60)}m"
                else:
                    time_str = f"{duration_seconds/3600:.1f}h"
                
                # Bestimme nur Farbe basierend auf Typ
                if '+' in pause_type:  # Kombinierte Pause
                    color = 'purple'
                    segment_combined += 1
                elif pause_type == 'Geschwindigkeit':
                    color = 'red'
                    segment_pause_count += 1
                else:  # Zeitlücke
                    color = 'orange'
                    segment_time_gaps += 1
                
                # Verwende optimierte Höhe für maximalen Abstand
                y_position = y_max * heights[idx]
                
                # NUR Zeitangabe mit Farbe - kein Symbol, keine Box
                axes[i].text(pause_km, y_position, time_str,
                           fontsize=9, color=color, ha='center', va='center', 
                           weight='bold', 
                           bbox=dict(boxstyle="round,pad=0.1", facecolor='white', 
                                   alpha=0.8, edgecolor=color, linewidth=1))
                
                axes[i].axvline(x=pause_km, color=color, linestyle=':', linewidth=1, alpha=0.6)
            
            # Legende mit Farbkodierung für Pausentypen
            legend_elements = []
            if segment_pause_count > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', 
                                                markersize=8, label=f'Geschwindigkeits-Pausen ({segment_pause_count}x)', linestyle='None'))
            if segment_time_gaps > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', 
                                                markersize=8, label=f'Zeit-Lücken ({segment_time_gaps}x)', linestyle='None'))
            if segment_combined > 0:
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='purple', 
                                                markersize=8, label=f'Kombinierte Pausen ({segment_combined}x)', linestyle='None'))
            
            # Durchschnittsgeschwindigkeit
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
                ax2.plot(segment_df['Distanz (km)'], segment_df['Elevation (m)'], 
                        color=color_elevation, alpha=0.3, linewidth=1.0, linestyle='-')
                ax2.fill_between(segment_df['Distanz (km)'], segment_df['Elevation (m)'], 
                                color=color_elevation, alpha=0.1)
                ax2.set_ylabel('Höhe (m)', color=color_elevation, fontsize=10)
                ax2.tick_params(axis='y', labelcolor=color_elevation, labelsize=9)
            
            # Achsen konfigurieren
            axes[i].set_title(f'Segment {i+1}: {start_km:.0f}-{end_km:.0f} km ' + 
                             f'(Ø {avg_speed:.1f} km/h, Max {max_speed_segment:.1f} km/h)', 
                             fontsize=12, fontweight='bold')
            axes[i].set_ylabel(speed_col_label, color=color_speed, fontsize=10)
            axes[i].tick_params(axis='y', labelcolor=color_speed, labelsize=9)
            axes[i].grid(True, which='major', linestyle=':', linewidth=0.5, color='gray', alpha=0.7)
            axes[i].legend(loc='upper right', fontsize=9)
            axes[i].set_ylim(0, y_max)
            
            if i == 2:
                axes[i].set_xlabel('Distanz (km)', fontsize=11)
            axes[i].set_xlim(start_km, end_km)

        # Titel und Statistiken
        basename = os.path.basename(output_png_path).replace("_speed_profile.png", "")
        fig.suptitle(f'Geschwindigkeitsprofil (3-Segment Analyse) - {basename}', 
                    fontsize=14, fontweight='bold', y=0.98)

        overall_avg = df_clean[speed_col_to_plot].mean()
        overall_max = df_clean[speed_col_to_plot].max()
        speed_pauses = len([p for p in all_pauses if p[4] == 'Geschwindigkeit'])
        time_gaps = len([p for p in all_pauses if p[4] == 'Zeitlücke'])
        combined_pauses = len([p for p in all_pauses if '+' in p[4]])
        
        if combined_pauses > 0:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P + {time_gaps}T + {combined_pauses}P+T'
        elif time_gaps > 0:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P + {time_gaps}T'
        else:
            stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Geschwindigkeit: {overall_avg:.1f} km/h | Max: {overall_max:.1f} km/h | Pausen: {speed_pauses}P'
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, style='italic')

        plt.tight_layout()
        plt.subplots_adjust(top=0.94, bottom=0.08)

        # Speichern
        output_dir = os.path.dirname(output_png_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        plt.savefig(output_png_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # Statistiken ausgeben
        print(f"[Info] Segment-Statistiken:")
        for seg_num, start, end, avg, max_seg in segment_stats:
            print(f"  Segment {seg_num} ({start:.0f}-{end:.0f} km): Ø {avg:.1f} km/h, Max {max_seg:.1f} km/h")
        
        print(f"[OK] 3-Segment Geschwindigkeitsprofil gespeichert: {output_png_path}")

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Erstellen des Geschwindigkeitsprofils: {input_csv_path} - {e}")
        try:
            Path(output_png_path).touch()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot 3-segment speed profile from track data.")
    parser.add_argument("input_csv", help="Path to input CSV with speed data (from 2d).")
    parser.add_argument("output_png", help="Path to save the output PNG plot.")
    parser.add_argument("--smooth-col-name", default="", help="Name of the smoothed speed column to use (e.g., 'Geschwindigkeit geglättet (km/h, W5)'). Optional.")
    args = parser.parse_args()
    
    plot_speed_profile(args.input_csv, args.output_png, args.smooth_col_name)