#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2_parse_gpx_full.py (V2 - Flexibler für geplante Tracks)
-------------------
Parses a GPX file to extract track points including latitude, longitude,
and elevation (if available). Handles tracks with or without timestamps.
Calculates cumulative distance and ascent for each point.
"""

SCRIPT_NAME = "2_parse_gpx_full.py "
SCRIPT_VERSION = "1.0.0" # Einführung einer Versionskontrolle, lauffaehiges Script

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import pandas as pd
import numpy as np
from geopy.distance import geodesic

def parse_gpx_flexible(input_gpx_path: str, output_csv_path: str):
    """
    Parses GPX, handling missing time/elevation, saves track data to CSV.
    """
    print(f"[Info] Parsing GPX (flexibel): {input_gpx_path}")
    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        with open(input_gpx_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
    # ... (Fehlerbehandlung für Datei öffnen/parsen wie vorher) ...
    except FileNotFoundError: print(f"[Fehler] Eingabedatei nicht gefunden: {input_gpx_path}"); sys.exit(1)
    except Exception as e: print(f"[Fehler] Konnte GPX-Datei nicht laden/parsen: {input_gpx_path} - {e}"); sys.exit(1)

    data = []
    point_counter = 0
    has_elevation_data = False
    has_time_data = False
    first_elevation = None
    first_time = None

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
                         if not has_elevation_data: # Merke, dass Höhendaten existieren
                             has_elevation_data = True
                             first_elevation = ele
                    except (ValueError, TypeError):
                        ele = None # Ignoriere ungültige Höhenangaben

                # Zeit prüfen und speichern (falls vorhanden)
                if point.time is not None:
                    try:
                         time = pd.to_datetime(point.time)
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

    print(f"[Info] {point_counter} Punkte im GPX gefunden, {len(data)} Punkte mit gültigen Lat/Lon.")
    if has_elevation_data: print("[Info] Höhendaten gefunden.")
    else: print("[Warnung] Keine oder ungültige Höhendaten im GPX gefunden.")
    if has_time_data: print("[Info] Zeitstempel gefunden.")
    else: print("[Warnung] Keine oder ungültige Zeitstempel im GPX gefunden.")


    if not data or len(data) < 2:
        print(f"[Fehler] Zu wenig gültige Trackpunkte (mit Lat/Lon) in {input_gpx_path}.")
        # Leere Datei erstellen, damit Workflow nicht abbricht
        pd.DataFrame(columns=['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)']).to_csv(output_csv_path, index=False, encoding='utf-8')
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

    # Wähle und ordne finale Spalten
    final_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)']
    df = df[final_cols]

    try:
        df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK] Parsing abgeschlossen (flexibel) und gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse GPX file flexibly (handles missing time/elevation).")
    parser.add_argument("input_gpx", help="Path to the input GPX file.")
    parser.add_argument("output_csv", help="Path to save the output CSV file.")
    args = parser.parse_args()

    parse_gpx_flexible(args.input_gpx, args.output_csv)