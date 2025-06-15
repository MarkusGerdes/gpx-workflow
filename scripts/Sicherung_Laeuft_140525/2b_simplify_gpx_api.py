#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2b_simplify_gpx_api.py
----------------------
Simplifies the track points from a GPX file using the Ramer-Douglas-Peucker (RDP)
algorithm or other methods, intended for reducing the number of points for
API calls (like geocoding or POI queries). Saves only Latitude and Longitude.
"""

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import pandas as pd
from simplification.cutil import simplify_coords # RDP implementation

def simplify_gpx_for_api(input_gpx_path: str, output_csv_path: str, method: str, epsilon: float):
    """
    Simplifies GPX track points and saves Lat/Lon to CSV.

    Args:
        input_gpx_path: Path to the input GPX file.
        output_csv_path: Path to save the simplified output CSV file.
        method: Simplification method ('rdp').
        epsilon: Epsilon value for RDP (in degrees).
    """
    print(f"[Info] Simplifying GPX for API use: {input_gpx_path}")
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

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Use (longitude, latitude) order as often expected by simplification/geometry libs (x, y)
                points.append([point.longitude, point.latitude])

    if len(points) < 2:
        print(f"[Warnung] Weniger als 2 Punkte in {input_gpx_path}. Vereinfachung nicht möglich. Leere CSV wird erstellt.")
        # Create an empty DataFrame and save it
        simplified_df = pd.DataFrame(columns=['Latitude', 'Longitude'])
        try:
            simplified_df.to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere CSV gespeichert: {output_csv_path}")
        except Exception as e:
            print(f"[Fehler] Konnte leere CSV nicht schreiben: {output_csv_path} - {e}")
            sys.exit(1)
        return # Exit function after saving empty file

    print(f"[Info] Original number of points: {len(points)}")

    simplified_points = []
    if method.lower() == 'rdp':
        if epsilon <= 0:
             print(f"[Warnung] Epsilon für RDP muss positiv sein (ist {epsilon}). Verwende alle Punkte.")
             simplified_points = points # Keep all points if epsilon is invalid
        else:
            try:
                simplified_points = simplify_coords(points, epsilon)
                print(f"[Info] Simplified number of points (RDP, epsilon={epsilon}): {len(simplified_points)}")
            except Exception as e:
                print(f"[Fehler] Fehler während RDP-Vereinfachung: {e}. Verwende Originalpunkte.")
                simplified_points = points # Fallback to original points on error
    # TODO: Hier könnte die Logik für 'winkel' oder andere Methoden eingefügt werden
    # elif method.lower() == 'winkel':
    #     # Implementiere hier deinen Winkel-basierten Ansatz
    #     print("[Info] Winkel-basierte Vereinfachung noch nicht implementiert.")
    #     simplified_points = points # Fallback
    else:
        print(f"[Warnung] Unbekannte Vereinfachungsmethode '{method}'. Verwende Originalpunkte.")
        simplified_points = points # Fallback to original points if method unknown

    # --- Wichtig: Start- und Endpunkt immer behalten! ---
    # RDP behält sie normalerweise, aber zur Sicherheit:
    if simplified_points: # Check if list is not empty
      start_point_orig = [points[0][0], points[0][1]]
      end_point_orig = [points[-1][0], points[-1][1]]
      start_point_simp = [simplified_points[0][0], simplified_points[0][1]]
      end_point_simp = [simplified_points[-1][0], simplified_points[-1][1]]

      final_points = []
      if start_point_orig != start_point_simp:
          final_points.append(start_point_orig)
      final_points.extend(simplified_points)
      if end_point_orig != end_point_simp and start_point_orig != end_point_orig : # Avoid adding end if it's same as start
         # Check if end point is already the last point after RDP (it should be)
         # We only need to add it if RDP somehow removed it and it's different from start
         if not np.allclose(final_points[-1], end_point_orig):
             final_points.append(end_point_orig)
      simplified_points = final_points
      # Entferne Duplikate, falls durch das Hinzufügen welche entstanden sind
      seen = set()
      simplified_points_unique = []
      for p in simplified_points:
          p_tuple = tuple(p)
          if p_tuple not in seen:
              simplified_points_unique.append(p)
              seen.add(p_tuple)
      simplified_points = simplified_points_unique


    if not simplified_points:
         print(f"[Warnung] Vereinfachung führte zu keinen Punkten. Leere CSV wird erstellt.")
         simplified_df = pd.DataFrame(columns=['Latitude', 'Longitude'])
    else:
        # Konvertiere zurück zu DataFrame mit Latitude, Longitude
        simplified_df = pd.DataFrame(simplified_points, columns=['Longitude', 'Latitude'])
        # Stelle die ursprüngliche Spaltenreihenfolge sicher
        simplified_df = simplified_df[['Latitude', 'Longitude']]


    try:
        simplified_df.to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Vereinfachte API-Trackdaten gespeichert: {output_csv_path} ({len(simplified_df)} Punkte)")
    except Exception as e:
        print(f"[Fehler] Konnte vereinfachte CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simplify GPX track points for API usage.")
    parser.add_argument("--input", required=True, help="Path to the input GPX file.")
    parser.add_argument("--output", required=True, help="Path to save the simplified CSV output file.")
    parser.add_argument("--method", default="rdp", help="Simplification method (e.g., 'rdp').")
    parser.add_argument("--epsilon", type=float, default=0.0001, help="Epsilon value for RDP simplification (in degrees).")
    # Hier könnten Argumente für andere Methoden hinzugefügt werden
    args = parser.parse_args()

    simplify_gpx_for_api(args.input, args.output, args.method, args.epsilon)