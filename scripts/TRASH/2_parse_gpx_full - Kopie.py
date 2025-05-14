#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2_parse_gpx_full.py
-------------------
Parses a GPX file to extract track points including latitude, longitude,
elevation, and crucially, timestamps. Calculates cumulative distance and
ascent for each point based on the full track data.
"""

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import pandas as pd
import numpy as np
from geopy.distance import geodesic # Using geodesic for potentially better accuracy

def parse_gpx_full(input_gpx_path: str, output_csv_path: str):
    """
    Parses the full GPX file and saves track data to CSV.

    Args:
        input_gpx_path: Path to the input GPX file.
        output_csv_path: Path to save the output CSV file.
    """
    print(f"[Info] Parsing GPX: {input_gpx_path}")
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(input_gpx_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_gpx_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Konnte GPX-Datei nicht laden oder parsen: {input_gpx_path} - {e}")
        sys.exit(1)

    data = []
    point_counter = 0
    # Iteriere durch alle Tracks und Segmente
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point_counter += 1
                if point.elevation is not None and point.time is not None:
                    data.append({
                        'Latitude': point.latitude,
                        'Longitude': point.longitude,
                        'Elevation (m)': float(point.elevation),
                        'Time': pd.to_datetime(point.time) # Make sure time is datetime object
                    })
                # Optional: Fallback, falls Zeit oder Höhe fehlen? Aktuell übersprungen.

    print(f"[Info] {point_counter} Punkte im GPX gefunden, {len(data)} Punkte mit Zeit und Höhe.")

    if not data or len(data) < 2:
        print(f"[Fehler] Zu wenig gültige Trackpunkte (mit Zeit & Höhe) in {input_gpx_path}.")
        # Create empty file to avoid downstream errors? Or exit? Let's exit for now.
        sys.exit(1)

    df = pd.DataFrame(data)
    df.sort_values(by='Time', inplace=True) # Ensure chronological order
    df.reset_index(drop=True, inplace=True)

    # Berechnungen: Distanz (geodesic) und Aufstieg
    # Use geodesic distance for potentially better accuracy over varying latitudes
    distances_km = [0.0]
    for i in range(1, len(df)):
        coord1 = (df.loc[i-1, 'Latitude'], df.loc[i-1, 'Longitude'])
        coord2 = (df.loc[i, 'Latitude'], df.loc[i, 'Longitude'])
        # Handle potential errors during distance calculation
        try:
            d = geodesic(coord1, coord2).kilometers
            distances_km.append(d)
        except ValueError:
             print(f"[Warnung] Ungültige Koordinaten bei Index {i}, setze Distanzdelta zu 0.")
             distances_km.append(0.0) # Append 0 if coords are invalid

    df['Strecke Delta (km)'] = distances_km
    df['Distanz (km)'] = np.cumsum(distances_km)

    # Calculate ascent based on elevation difference
    elevation_diff = df['Elevation (m)'].diff().fillna(0)
    df['Aufstieg (m)'] = elevation_diff.clip(lower=0) # Only positive differences count as ascent

    try:
        df.to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Parsing abgeschlossen und gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a GPX file to extract full track data including timestamps.")
    parser.add_argument("input_gpx", help="Path to the input GPX file.")
    parser.add_argument("output_csv", help="Path to save the output CSV file.")
    args = parser.parse_args()

    parse_gpx_full(args.input_gpx, args.output_csv)