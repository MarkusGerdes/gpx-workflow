#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8c_enrich_filter_places.py
--------------------------
Reads sorted places with center coordinates (output of 8b) and the
full track data (output of 2c).
Calculates the nearest point on the full track for each place center.
Calculates the geodetic distance between the place center and the nearest track point.
Retrieves the distance along the track and elevation of that nearest point.
Filters places based on relevance criteria (max distance to track, min occurrences).
Saves the enriched and filtered list of relevant places.

Requires: pandas, numpy, scipy, geopy
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from scipy.spatial import KDTree
from geopy.distance import distance as geopy_distance
from typing import Optional, Tuple, List, Dict

# NEU: tqdm importieren (mit Fallback)
try:
    from tqdm import tqdm
except ImportError:
    print("[Warnung] tqdm nicht gefunden (pip install tqdm), Fortschrittsbalken wird nicht angezeigt.")
    def tqdm(iterable, *args, **kwargs): # Dummy-Funktion
        return iterable

# --- Helper Function: Nearest Neighbor ---
def find_nearest_track_point_kdtree(track_lat_lon: np.ndarray, place_lat: float, place_lon: float) -> Tuple[int, float]:
    """
    Finds index and approximate geodetic distance (meters) of the nearest track point.
    Returns (index, distance_meters) or (-1, -1.0).
    """
    if track_lat_lon is None or track_lat_lon.shape[0] == 0: return -1, -1.0
    try:
        # KDTree uses Euclidean distance on lat/lon - good for finding the index quickly
        tree = KDTree(track_lat_lon)
        _, index = tree.query([place_lat, place_lon]) # We only need the index from KDTree

        # Calculate precise geodetic distance using the found index
        nearest_track_point_coords = (track_lat_lon[index, 0], track_lat_lon[index, 1])
        place_coords = (place_lat, place_lon)
        distance_m = geopy_distance(place_coords, nearest_track_point_coords).meters
        return index, distance_m
    except ValueError as e: # Handle potential errors in geopy_distance
        print(f"[Warnung] Geodätische Distanzberechnung fehlgeschlagen für ({place_lat},{place_lon}): {e}. Gebe Index, -1.0 zurück.")
        # We might still have a valid index from KDTree query before geopy failed
        try:
             tree = KDTree(track_lat_lon); _, index = tree.query([place_lat, place_lon]); return index, -1.0
        except: return -1, -1.0 # Fallback if everything fails
    except Exception as e:
        print(f"[Warnung] KDTree Fehler oder anderer Fehler: {e}")
        return -1, -1.0


# --- Main Function ---
# --- Main Function ---
def enrich_filter_places(
    places_coords_csv: str,
    full_track_csv: str,
    output_csv: str,
    # --- Änderung: Nimm die Werte als Argumente ---
    max_dist_meters_arg: Optional[float] = None,
    min_occurrences_arg: Optional[int] = None
    ):
    """Enriches places with track proximity data and filters them."""
    print(f"[Info] Enriching and filtering places...")
    print(f"  Input Places (8b): {places_coords_csv}")
    print(f"  Input Track (2c): {full_track_csv}")

    # --- Lade Inputs ---
    try:
        places_df = pd.read_csv(places_coords_csv, dtype={'Ort': str}) # Lese Ort als String
        if places_df.empty: print(f"[Warnung] Places CSV ist leer: {places_coords_csv}"); # Save empty and exit
        track_df = pd.read_csv(full_track_csv, dtype={'Elevation (m)': float, 'Distanz (km)': float})
        if track_df.empty: print(f"[Warnung] Track CSV ist leer: {full_track_csv}"); # Save empty and exit

        # Handle empty cases cleanly
        if places_df.empty or track_df.empty:
            output_cols = ["Ort", "Vorkommen", "Strecke im Ort (km)",
                           "Latitude_Center", "Longitude_Center",
                           "Nächster_Punkt_Index", "Nächster_Punkt_Distanz_km",
                           "Nächster_Punkt_Hoehe_m", "Distanz_Center_zu_Route_m"]
            pd.DataFrame(columns=output_cols).to_csv(output_csv, index=False, encoding='utf-8')
            print(f"[OK] Leere angereicherte Orts-CSV gespeichert: {output_csv}")
            sys.exit(0)

        # Prüfe notwendige Spalten
        req_place_cols = ['Ort', 'Latitude_Center', 'Longitude_Center']
        req_track_cols = ['Latitude', 'Longitude', 'Distanz (km)', 'Elevation (m)']
        if not all(c in places_df.columns for c in req_place_cols): raise ValueError(f"Places CSV fehlt Spalten: {req_place_cols}")
        if not all(c in track_df.columns for c in req_track_cols): raise ValueError(f"Track CSV fehlt Spalten: {req_track_cols}")

        # Entferne Orte ohne Koordinaten vor der Verarbeitung
        places_df.dropna(subset=['Latitude_Center', 'Longitude_Center'], inplace=True)
        if places_df.empty:
            print("[Warnung] Keine Orte mit gültigen Zentrumskoordinaten.")
            output_cols = ["Ort", "Vorkommen", "Strecke im Ort (km)", "Latitude_Center", "Longitude_Center", "Nächster_Punkt_Index", "Nächster_Punkt_Distanz_km", "Nächster_Punkt_Hoehe_m", "Distanz_Center_zu_Route_m"]
            pd.DataFrame(columns=output_cols).to_csv(output_csv, index=False, encoding='utf-8')
            print(f"[OK] Leere CSV (keine Coords): {output_csv}")
            sys.exit(0)



    except FileNotFoundError as e: print(f"[Fehler] Eingabedatei nicht gefunden: {e}"); sys.exit(1)
    except Exception as e: print(f"[Fehler] Fehler beim Laden der Input-Dateien: {e}"); sys.exit(1)

    # --- Bereite KDTree vor ---
    track_coords_latlon = track_df[['Latitude', 'Longitude']].values

    # --- Anreicherung ---
    print("[Info] Berechne Distanzen und nächste Punkte...")
    results = []
    for _, place_row in tqdm(places_df.iterrows(), total=len(places_df), desc="Enriching Places"):
        place_lat = place_row['Latitude_Center']
        place_lon = place_row['Longitude_Center']

        nearest_idx, distance_m = find_nearest_track_point_kdtree(track_coords_latlon, place_lat, place_lon)

        if nearest_idx != -1:
            nearest_point_data = track_df.iloc[nearest_idx]
            results.append({
                "Ort": place_row['Ort'],
                "Vorkommen": place_row.get('Vorkommen'), # Behalte alte Infos
                "Strecke im Ort (km)": place_row.get('Strecke im Ort (km)'), # Behalte alte Infos
                "Latitude_Center": place_lat,
                "Longitude_Center": place_lon,
                "Nächster_Punkt_Index": nearest_idx,
                "Nächster_Punkt_Distanz_km": nearest_point_data.get('Distanz (km)'),
                "Nächster_Punkt_Hoehe_m": nearest_point_data.get('Elevation (m)'),
                "Distanz_Center_zu_Route_m": distance_m if distance_m >= 0 else np.nan # Speichere Distanz, NaN bei Fehler
            })
        else:
             # Ort kann nicht zugeordnet werden, füge ihn ggf. ohne Distanz hinzu oder überspringe
             print(f"[Warnung] Kein nächster Punkt für '{place_row['Ort']}' gefunden.")
             results.append({
                "Ort": place_row['Ort'], "Vorkommen": place_row.get('Vorkommen'),
                "Strecke im Ort (km)": place_row.get('Strecke im Ort (km)'),
                "Latitude_Center": place_lat, "Longitude_Center": place_lon,
                 # Setze Distanz/Höhen-Werte auf NaN
                "Nächster_Punkt_Index": -1, "Nächster_Punkt_Distanz_km": np.nan,
                "Nächster_Punkt_Hoehe_m": np.nan, "Distanz_Center_zu_Route_m": np.nan })


    enriched_df = pd.DataFrame(results)

    # --- Filterung ---
    print("[Info] Filtere Orte nach Relevanz...")
    filtered_df = enriched_df.copy()
    initial_count = len(filtered_df)

    # 1. Filter: Maximale Distanz zum Track
    # --- Änderung: Prüfe, ob der Wert valide ist (nicht None oder < 0) ---
    if max_dist_meters_arg is not None and max_dist_meters_arg >= 0 and 'Distanz_Center_zu_Route_m' in filtered_df.columns:
        # Entferne zuerst NaNs in der Distanzspalte, damit der Vergleich funktioniert
        filtered_df.dropna(subset=['Distanz_Center_zu_Route_m'], inplace=True)
        filtered_df = filtered_df[filtered_df['Distanz_Center_zu_Route_m'] <= max_dist_meters_arg]
        print(f"  -> Nach Distanzfilter ({max_dist_meters_arg}m): {len(filtered_df)} Orte übrig.")
    else:
         print("  -> Distanzfilter nicht angewendet (Parameter nicht gesetzt oder ungültig).")


    # 2. Filter: Mindestanzahl Vorkommen (aus Schritt 7)
    # --- Änderung: Prüfe, ob der Wert valide ist (nicht None oder < 0) ---
    if min_occurrences_arg is not None and min_occurrences_arg >= 0 and 'Vorkommen' in filtered_df.columns:
         # Stelle sicher, dass Vorkommen numerisch ist
         filtered_df['Vorkommen'] = pd.to_numeric(filtered_df['Vorkommen'], errors='coerce').fillna(0).astype(int)
         filtered_df = filtered_df[filtered_df['Vorkommen'] >= min_occurrences_arg]
         print(f"  -> Nach Vorkommenfilter (>={min_occurrences_arg}): {len(filtered_df)} Orte übrig.")
    else:
         print("  -> Vorkommenfilter nicht angewendet (Parameter nicht gesetzt oder ungültig).")

    # Weitere Filter (z.B. Mindeststrecke im Ort) könnten hier hinzugefügt werden

    final_count = len(filtered_df)
    print(f"[Info] Filterung abgeschlossen. {final_count} von {initial_count} Orten als relevant eingestuft.")

    # --- Speichern ---
    try:
        output_dir = os.path.dirname(output_csv); os.makedirs(output_dir, exist_ok=True)
        # Wähle und ordne finale Spalten
        final_cols = ["Ort", "Vorkommen", "Strecke im Ort (km)",
                      "Latitude_Center", "Longitude_Center",
                      "Nächster_Punkt_Index", "Nächster_Punkt_Distanz_km",
                      "Nächster_Punkt_Hoehe_m", "Distanz_Center_zu_Route_m"]
        # Stelle sicher, dass alle Spalten existieren
        for col in final_cols:
            if col not in filtered_df.columns: filtered_df[col] = np.nan # Füge fehlende als NaN hinzu
        filtered_df = filtered_df[final_cols] # Wähle und ordne an

        filtered_df.to_csv(output_csv, index=False, encoding='utf-8', float_format='%.3f')
        print(f"[OK] Angereicherte und gefilterte Orte gespeichert: {output_csv}")
    except Exception as e:
        print(f"[Fehler] Konnte finale Orts-CSV nicht schreiben: {output_csv} - {e}")
        sys.exit(1)

# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich and filter places based on proximity.")
    parser.add_argument("--places-coords-csv", required=True)
    parser.add_argument("--full-track-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    # --- Änderung: Argumente optional machen, Typ prüfen ---
    # Verwende einen Default-Wert (z.B. -1), den das Skript als "nicht gesetzt" interpretiert
    parser.add_argument("--max-dist", type=float, default=-1.0, help="Max distance [m] (negative value or omit to disable).")
    parser.add_argument("--min-occ", type=int, default=-1, help="Min occurrences (negative value or omit to disable).")
    # ---------------------------------------------------------
    args = parser.parse_args()

    enrich_filter_places(
        args.places_coords_csv,
        args.full_track_csv,
        args.output_csv,
        # --- Übergabe der Werte an die Funktion ---
        args.max_dist if args.max_dist >= 0 else None,
        args.min_occ if args.min_occ >= 0 else None
    )