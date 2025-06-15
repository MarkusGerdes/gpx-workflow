#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4b_fetch_surface_grouped.py
---------------------------
Reads optimized track data with location info (output of step 4).
Groups consecutive points by Street and City.
Selects a representative point for each group.
Queries Overpass API only for these representative points to get surface data.
Assigns the found surface data back to ALL points of the corresponding group
in the *full* track data CSV.

Requires: pandas, requests, overpy, tqdm, geopy
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
import requests
import overpy
import time
import math
from tqdm import tqdm
from geopy.distance import geodesic
from typing import Optional, List, Dict, Any, Tuple

# Optional: Shapely (für find_closest_way, falls benötigt)
try:
    from shapely.geometry import Point, LineString
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

# --- Konfiguration (wie in altem 4b, aber SAMPLING entfällt) ---
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_REQUESTS = 1.1
RETRY_DELAY = 3
MAX_RETRIES = 4
QUERY_RADIUS_M = 80 # Radius um den repräsentativen Punkt
RELEVANT_HIGHWAY_TYPES = ["primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "track", "cycleway", "path", "bridleway", "footway"]
HIGHWAY_QUERY_FILTER_VALUE = "|".join(RELEVANT_HIGHWAY_TYPES) 
HIGHWAY_TO_SURFACE_INFERENCE = { "motorway": "paved", "trunk": "paved", "primary": "paved", "secondary": "paved", "tertiary": "paved", "unclassified": "paved", "residential": "paved", "living_street": "paved", "service": "paved", "cycleway": "paved", "track": "unpaved", "path": "unpaved", "bridleway": "unpaved", "footway": "paved" }
DEFAULT_SURFACE = "unknown"

# --- Helper Funktionen (infer_surface, get_way_tags, find_closest_way wie in altem 4b) ---
def infer_surface(tags: dict) -> str:
    highway = tags.get("highway"); tracktype = tags.get("tracktype")
    if not highway: return DEFAULT_SURFACE
    if highway == "track":
        if tracktype in ["grade1", "grade2"]: return "compacted"
        elif tracktype in ["grade3", "grade4", "grade5"]: return "ground"
        else: return "unpaved"
    return HIGHWAY_TO_SURFACE_INFERENCE.get(highway, DEFAULT_SURFACE)

def get_way_tags(way: overpy.Way) -> dict:
    tags = way.tags; surface = tags.get("surface", None)
    if surface is None: surface = infer_surface(tags)
    return {"surface": surface, "tracktype": tags.get("tracktype"), "highway": tags.get("highway"), "smoothness": tags.get("smoothness"), "osm_way_id": way.id}

def find_closest_way(ways: List[overpy.Way], point_lat: float, point_lon: float) -> Optional[overpy.Way]:
    if not ways: return None
    if not SHAPELY_AVAILABLE: return ways[0]
    try:
        query_point = Point(point_lon, point_lat); min_dist = float('inf'); closest_way = None
        for way in ways:
            if not way.nodes: continue
            way_coords = [(node.lon, node.lat) for node in way.nodes]
            if len(way_coords) < 2: continue
            try: way_line = LineString(way_coords); dist = way_line.distance(query_point)
            except Exception: continue # Ignore ways causing Shapely errors
            if dist < min_dist: min_dist = dist; closest_way = way
        return closest_way
    except Exception as e: print(f"[Warnung] Shapely Fehler: {e}"); return ways[0]


# --- Hauptfunktion ---
def fetch_surface_grouped(track_loc_csv: str, output_csv_path: str, query_radius: int):
    """Fetches surface data by querying representative points of street/city blocks."""
    print(f"[Info] Fetching grouped Surface Data for: {track_loc_csv}")
    print(f"  Query Radius: {query_radius}m")

    # --- Lade optimierten Track mit Location ---
    try:
        df_loc = pd.read_csv(track_loc_csv, dtype=str, keep_default_na=False)
        if not all(col in df_loc.columns for col in ["Latitude", "Longitude", "Street", "City"]):
             raise ValueError("Input CSV needs 'Latitude', 'Longitude', 'Street', 'City'.")
        if df_loc.empty:
             print("[Warnung] Input CSV leer.")
             # --- KORREKTE EINRÜCKUNG ---
             pd.DataFrame(columns=['Latitude', 'Longitude', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']).to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere Surface-CSV gespeichert: {output_csv_path}")
             sys.exit(0)
             # --------------------------

        df_loc['Latitude'] = pd.to_numeric(df_loc['Latitude'], errors='coerce')
        df_loc['Longitude'] = pd.to_numeric(df_loc['Longitude'], errors='coerce')
        df_loc.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        if df_loc.empty:
             print("[Warnung] Keine gültigen Koordinaten im Input.")
             # --- KORREKTE EINRÜCKUNG ---
             pd.DataFrame(columns=['Latitude', 'Longitude', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']).to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere Surface-CSV gespeichert (keine validen Coords): {output_csv_path}")
             sys.exit(0)

    except FileNotFoundError: print(f"[Fehler] Input nicht gefunden: {track_loc_csv}"); sys.exit(1)
    except Exception as e: print(f"[Fehler] Lesen Input CSV fehlgeschlagen: {e}"); sys.exit(1)

    # --- Gruppiere nach aufeinanderfolgenden Straßen/Orts-Blöcken ---
    print("[Info] Gruppiere Punkte nach Straßen-/Ortsblöcken...")
    # Erstelle eine ID für jeden Blockwechsel
    df_loc['block_id'] = (df_loc[['Street', 'City']] != df_loc[['Street', 'City']].shift()).any(axis=1).cumsum()

    representative_points = []
    # Für jede Block-ID, wähle den mittleren Punkt
    for block_id, group in df_loc.groupby('block_id'):
        middle_index = group.index[len(group) // 2]
        rep_point = group.loc[middle_index]
        representative_points.append({
            'block_id': block_id,
            'latitude': rep_point['Latitude'],
            'longitude': rep_point['Longitude'],
            'street': rep_point['Street'], # Behalte Infos für Debugging
            'city': rep_point['City']
        })

    print(f"[Info] {len(representative_points)} repräsentative Punkte ausgewählt für {df_loc['block_id'].nunique()} Blöcke.")

    # --- Overpass API Setup ---
    api = overpy.Overpass()
    surface_results_by_block = {} # Dictionary: block_id -> tags_dict
    api_errors = 0

    # --- Iteriere NUR durch repräsentative Punkte ---
    for point_info in tqdm(representative_points, desc="Querying Surface Data"):
        block_id = point_info['block_id']
        lat = point_info['latitude']
        lon = point_info['longitude']

        # --- Baue Overpass Query für diesen Punkt ---
        query = f"""
        [out:json][timeout:{REQUEST_TIMEOUT}];
        ( way(around:{query_radius},{lat:.7f},{lon:.7f})["highway"~"{HIGHWAY_QUERY_FILTER_VALUE}"]; );
        out body; >; out skel qt;
        """

        # --- Führe Query mit Retries aus ---
        success = False
        for attempt in range(MAX_RETRIES):
            try:
                result = api.query(query)
                success = True
                closest_way = find_closest_way(result.ways, lat, lon)
                if closest_way:
                    way_tags = get_way_tags(closest_way)
                    surface_results_by_block[block_id] = way_tags # Speichere Ergebnis für Block-ID
                break
            # --- Fehlerbehandlung (wie vorher) ---
            except overpy.exception.OverpassTooManyRequests: wait_time = RETRY_DELAY * (attempt + 1); print(f"-> Rate Limit Block {block_id}, Warte {wait_time}s..."); time.sleep(wait_time)
            except overpy.exception.OverpassGatewayTimeout: wait_time = RETRY_DELAY * (attempt + 1); print(f"-> Timeout Block {block_id}, Warte {wait_time}s..."); time.sleep(wait_time)
            except Exception as e: print(f"-> Fehler Overpass Query Block {block_id} (Versuch {attempt+1}): {e}"); time.sleep(RETRY_DELAY)

        if not success: print(f"-> FEHLER Abfrage Block {block_id} nach {MAX_RETRIES} Versuchen."); api_errors += 1
        time.sleep(SLEEP_BETWEEN_REQUESTS) # Pause nach jeder Abfrage

    print(f"\n[Info] Overpass-Abfragen abgeschlossen. {len(surface_results_by_block)} Blöcke mit Daten ({api_errors} Fehler).")

    # --- Ordne Ergebnisse allen Punkten im ursprünglichen DataFrame zu ---
    print("[Info] Weise Oberflächenwerte den ursprünglichen Punkten zu...")
    # Erstelle leere Spalten
    for col in ['Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']:
        df_loc[col] = None

    # Fülle die Spalten basierend auf den Ergebnissen pro Block
    for block_id, tags in surface_results_by_block.items():
        # Finde alle Zeilen mit dieser block_id
        mask = df_loc['block_id'] == block_id
        df_loc.loc[mask, 'Surface'] = tags.get('surface')
        df_loc.loc[mask, 'Tracktype'] = tags.get('tracktype')
        df_loc.loc[mask, 'Highway'] = tags.get('highway')
        df_loc.loc[mask, 'Smoothness'] = tags.get('smoothness')
        df_loc.loc[mask, 'OSM_Way_ID'] = tags.get('osm_way_id')

    # Setze Default für Blöcke ohne Ergebnis
    df_loc['Surface'].fillna(DEFAULT_SURFACE, inplace=True)

    # --- Speichere finale CSV ---
    try:
        output_dir = os.path.dirname(output_csv_path); os.makedirs(output_dir, exist_ok=True)
        # Wähle relevante Spalten für den Output (diesmal für die *optimierte* Route)
        # Optional: Distanz hinzufügen, wenn in Input vorhanden oder hier berechnet
        final_cols = ['Latitude', 'Longitude', 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']
        # Füge optional Distanz hinzu, falls vorhanden
        # if 'Distanz_km_approx' in df_loc.columns: final_cols.insert(2, 'Distanz_km_approx')

        # Stelle sicher, dass alle finalen Spalten existieren
        for col in final_cols:
            if col not in df_loc.columns: df_loc[col] = None

        df_final = df_loc[final_cols]
        df_final.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK] Gruppierte Oberflächendaten gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte finale Surface-CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch grouped surface data for a track using Overpass API.")
    parser.add_argument("--input-csv", required=True, help="Path to optimized track CSV with location (4...).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output surface data CSV (4b...).")
    parser.add_argument("--radius", type=int, default=QUERY_RADIUS_M, help="Query radius [m].")
    # Sampling-Argument wird nicht mehr benötigt
    args = parser.parse_args()

    fetch_surface_grouped(args.input_csv, args.output_csv, args.radius)