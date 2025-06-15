#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5c_merge_filter_pois.py
-----------------------
Merges POIs from service search and peak/viewpoint search.
Calculates the distance of each POI to the *full* GPX track.
Filters POIs based on type and relevance criteria (distance, elevation).
Saves the final list of relevant POIs to a CSV file.
"""

import sys
import os
import argparse
import pandas as pd
import json
from shapely.geometry import Point, LineString # Requires shapely
import numpy as np
from tqdm import tqdm # <--- DIESE ZEILE HINZUFÜGEN

# Helper function for distance conversion (approximate)
def degrees_to_meters(degrees):
    """Rough conversion from degrees to meters at mid-latitudes."""
    return degrees * 111000 # More accurate would need latitude

# Helper for relevance check (adapt from createMultipleMaps2.py logic)
def is_poi_relevant(poi_series, track_line_shapely, config):
    """
    Checks if a POI (as a Pandas Series) is relevant based on type,
    distance to track, and potentially elevation.
    """
    poi_type = poi_series.get("Typ", "").lower()
    lat = poi_series["Latitude"]
    lon = poi_series["Longitude"]
    name = poi_series.get("Name", "")
    elevation = poi_series.get("Elevation") # Can be NaN or string

    try:
        poi_point = Point(lon, lat)
        distance_deg = track_line_shapely.distance(poi_point)
        distance_m = degrees_to_meters(distance_deg) # Approximate distance in meters
    except Exception as e:
        print(f"[Warnung] Fehler bei Distanzberechnung für {name}: {e}")
        return False, 0 # Treat as irrelevant if distance fails

    relevant = False
    if poi_type == "peak":
        if not name: # Peaks without names are often less relevant
            relevant = False
        else:
            try:
                elev_m = float(elevation)
                 # Use filter criteria from config
                for rule in config.get('peak_relevance_filter', []):
                    if distance_m <= rule['max_dist_km'] * 1000 and elev_m >= rule['min_elev_m']:
                        relevant = True
                        break # Relevant if any rule matches
            except (ValueError, TypeError):
                relevant = False # Irrelevant if elevation is not a valid number

    elif poi_type == "viewpoint":
        relevant = distance_m <= config.get('max_dist_viewpoint_km', 2.0) * 1000

    else: # Service POIs (supermarket, drinking_water, etc.)
        relevant = distance_m <= config.get('max_dist_service_km', 0.5) * 1000

    return relevant, int(distance_m)


def merge_filter_pois(service_csv_path: str, peak_json_path: str, full_track_csv_path: str, output_csv_path: str, filter_config: dict):
    """Merges, filters, and saves relevant POIs."""
    print("[Info] Merging and filtering POIs...")

    # --- 1. Load Service POIs ---
    try:
        service_df = pd.read_csv(service_csv_path)
        # Standardize service POI columns
        if 'Elevation' not in service_df.columns:
            service_df['Elevation'] = pd.NA # Use pandas NA
        if 'Entfernung_m' not in service_df.columns:
             service_df['Entfernung_m'] = -1 # Placeholder
        print(f"[Info] Service POIs geladen: {len(service_df)} ")
    except FileNotFoundError:
        print(f"[Warnung] Service POI Datei nicht gefunden: {service_csv_path}. Überspringe.")
        service_df = pd.DataFrame(columns=["Name", "Typ", "Adresse", "Latitude", "Longitude", "Elevation", "Entfernung_m"])
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Service POI CSV '{service_csv_path}': {e}")
        sys.exit(1)

    # --- 2. Load Peak/Viewpoint POIs ---
    peak_data = []
    try:
        with open(peak_json_path, 'r', encoding='utf-8') as f:
            peak_json = json.load(f)
            for elem in peak_json.get("elements", []):
                 peak_data.append({
                     "Name": elem.get("name", elem.get("type", "Unbenannt").capitalize()),
                     "Typ": elem.get("type", "Unbekannt").lower(), # Ensure type is lowercase
                     "Adresse": "N/A", # No address usually for peaks/views
                     "Latitude": elem["latitude"],
                     "Longitude": elem["longitude"],
                     "Elevation": elem.get("elevation"), # Keep as string/None initially
                     "Entfernung_m": -1 # Placeholder
                 })
            print(f"[Info] Peak/Viewpoint POIs geladen: {len(peak_data)} ")
    except FileNotFoundError:
         print(f"[Warnung] Peak/Viewpoint JSON nicht gefunden: {peak_json_path}. Überspringe.")
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Peak/Viewpoint JSON '{peak_json_path}': {e}")
        sys.exit(1)

    peak_df = pd.DataFrame(peak_data)

    # --- 3. Combine POIs ---
    if peak_df.empty:
        all_pois_df = service_df
    elif service_df.empty:
        all_pois_df = peak_df
    else:
        all_pois_df = pd.concat([service_df, peak_df], ignore_index=True)

    if all_pois_df.empty:
        print("[Warnung] Keine POIs zum Filtern vorhanden.")
        # Save empty file
        pd.DataFrame(columns=["Name", "Typ", "Adresse", "Latitude", "Longitude", "Elevation", "Entfernung_m"]).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Leere relevante POI CSV gespeichert: {output_csv_path}")
        return

    # Drop duplicates *before* creating LineString if possible (reduces size)
    all_pois_df.drop_duplicates(subset=['Latitude', 'Longitude'], inplace=True, keep='first')
    # WICHTIG: Setze den Index zurück, damit er von 0 bis N-1 geht
    all_pois_df.reset_index(drop=True, inplace=True)
    print(f"[Info] Gesamt POIs nach Deduplizierung: {len(all_pois_df)}")

    # --- 4. Load Full Track and Create LineString ---
    # ... (Code zum Laden von full_track_df und Erstellen von track_line) ...
    try:
        full_track_df = pd.read_csv(full_track_csv_path)
        if not all(col in full_track_df.columns for col in ["Latitude", "Longitude"]): raise ValueError("Full track CSV needs 'Latitude' and 'Longitude'.")
        track_coords = list(zip(full_track_df['Longitude'], full_track_df['Latitude']))
        if len(track_coords) < 2: raise ValueError("Full track needs >= 2 points.")
        track_line = LineString(track_coords)
        print(f"[Info] Volle Route geladen ({len(track_coords)} Punkte).")
    except Exception as e: print(f"[Fehler] Laden/Verarbeiten Track CSV '{full_track_csv_path}': {e}"); sys.exit(1)


    # --- 5. Filter POIs ---
    # --- KORREKTUR: Ergebnisse sammeln statt Index verwenden ---
    relevance_results = [] # Liste für (is_relevant, distance_m) Tupel
    calculated_distances = [] # Liste für Distanzen

    print("[Info] Berechne Relevanz und Distanz für POIs...")
    for i, poi_row in tqdm(all_pois_df.iterrows(), total=len(all_pois_df), desc="Filtering POIs"):
        # Der Index 'i' von iterrows() wird jetzt NICHT mehr für relevant_mask verwendet!
        is_relevant, distance_m = is_poi_relevant(poi_row, track_line, filter_config)
        relevance_results.append(is_relevant)
        calculated_distances.append(distance_m if is_relevant else -1) # Speichere Distanz nur wenn relevant

    # Füge die Ergebnisse als neue Spalten hinzu
    all_pois_df['is_relevant'] = relevance_results
    all_pois_df['Entfernung_m'] = calculated_distances

    # Filtere den DataFrame basierend auf der neuen Spalte
    relevant_pois_df = all_pois_df[all_pois_df['is_relevant']].copy()

    # Entferne die temporäre Relevanzspalte
    relevant_pois_df.drop(columns=['is_relevant'], inplace=True)
    # -------------------------------------------------------------

    print(f"[Info] Relevante POIs nach Filterung: {len(relevant_pois_df)}")

    # --- 6. Save Filtered POIs ---
    # ... (Rest des Codes zum Speichern bleibt gleich) ...
    output_cols = ["Name", "Typ", "Adresse", "Latitude", "Longitude", "Elevation", "Entfernung_m"]
    for col in output_cols:
        if col not in relevant_pois_df.columns: relevant_pois_df[col] = pd.NA
    relevant_pois_df = relevant_pois_df[output_cols]
    try:
        output_dir = os.path.dirname(output_csv_path); os.makedirs(output_dir, exist_ok=True)
        relevant_pois_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK] {len(relevant_pois_df)} relevante POIs gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte relevante POI CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge, filter POIs by relevance to the full track.")
    parser.add_argument("--service-pois", required=True, help="Path to the raw service POIs CSV file.")
    parser.add_argument("--peak-pois", required=True, help="Path to the raw peak/viewpoint JSON file.")
    parser.add_argument("--full-track", required=True, help="Path to the full track data CSV file.")
    parser.add_argument("--output", required=True, help="Path to save the final relevant POIs CSV file.")
    # Add arguments for filter parameters (can be read from config in Snakemake)
    parser.add_argument("--max-dist-service-km", type=float, default=0.5)
    parser.add_argument("--max-dist-viewpoint-km", type=float, default=2.0)
    # Example how peak relevance filter *could* be passed (complex, better handle via config dict)
    # parser.add_argument('--peak-filter-rules', type=json.loads, default='[{"max_dist_km": 1, "min_elev_m": 100}]')

    args = parser.parse_args()

    # Create a simple config dict for filtering based on args (in real workflow, use config obj)
    filter_params = {
        'max_dist_service_km': args.max_dist_service_km,
        'max_dist_viewpoint_km': args.max_dist_viewpoint_km,
        # Example of manually adding peak rules here - better read from config file in practice
        'peak_relevance_filter': [
            { 'max_dist_km': 1, 'min_elev_m': 100 },
            { 'max_dist_km': 2, 'min_elev_m': 200 },
            { 'max_dist_km': 3, 'min_elev_m': 300 },
            { 'max_dist_km': 5, 'min_elev_m': 400 }
        ]
        # 'peak_relevance_filter': args.peak_filter_rules
    }


    merge_filter_pois(args.service_pois, args.peak_pois, args.full_track, args.output, filter_params)