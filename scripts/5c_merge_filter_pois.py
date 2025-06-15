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

# === SCRIPT METADATA ===
SCRIPT_NAME = "5c_merge_filter_pois.py"
SCRIPT_VERSION = "2.0.1" # Enhanced POI-Processing-Performance-Tracking + Template-System-Kompatibilität
SCRIPT_DESCRIPTION = "POI merging, elevation enrichment and relevance filtering with standardized metadata"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.1.0 (pre-2025): Enhanced POI processing with track proximity calculation
v1.2.0 (2025-06-07): Standardized header, improved elevation API integration and error handling
v2.0.0 (2025-06-07): Implemented full standardized metadata system with processing history
v2.0.1 (2025-06-08): Enhanced POI-Processing-Performance-Tracking + Template-System-Kompatibilität
- KDTree-Performance-Tracking für Spatial-Indexing und Nearest-Neighbor-Search
- POI-Merging-Algorithm-Performance mit Deduplication-Metriken
- Elevation-API-Integration-Performance (OpenTopoData) mit Batch-Processing-Stats
- POI-Filtering-Efficiency-Metriken für Type-Based und Distance-Based-Filtering
- Multi-Source-Data-Integration-Analysis (Service, Peak, Track-Elevation)
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "poi_filtering"
INPUT_FILE_PATTERN = "*_service_pois.csv"
OUTPUT_FILE_PATTERN = "*_relevant_pois.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "requests>=2.25.0",
    "shapely>=1.7.0",
    "numpy>=1.20.0",
    "scipy>=1.7.0",
    "geopy>=2.2.0",
    "tqdm>=4.60.0"
]

import sys
import os
import argparse
import pandas as pd
import json
import requests # Für HTTP-Anfragen
import time     # Um Rate-Limits der API zu respektieren
from shapely.geometry import Point, LineString # Optional, wenn nicht schon von KDTree abgedeckt
import numpy as np
from scipy.spatial import KDTree # Für schnelle Nächste-Nachbar-Suche
from geopy.distance import distance as geopy_distance # Für präzise Distanz
from datetime import datetime
from pathlib import Path

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

# Korrekter tqdm Import:
try:
    from tqdm import tqdm
    print("[INFO 5c] tqdm für Fortschrittsbalken geladen.", file=sys.stderr)
except ImportError:
    print("[WARNUNG 5c] tqdm nicht gefunden (pip install tqdm), Fortschrittsbalken wird nicht angezeigt.", file=sys.stderr)
    def tqdm(iterable, *args, **kwargs): # Dummy-Funktion als Fallback
        print(f"Iteriere über {kwargs.get('desc', 'iterable')} (tqdm nicht verfügbar)...", file=sys.stderr)
        return iterable

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

# Helper function for distance conversion (approximate)
def degrees_to_meters(degrees):
    """Rough conversion from degrees to meters at mid-latitudes."""
    return degrees * 111000 # More accurate would need latitude

# --- Helper Function: Nearest Neighbor (leicht angepasst) ---
def find_nearest_track_point_details(
    track_kdtree: KDTree,      # Vorberechneter KDTree der Trackpunkte
    track_df_for_lookup: pd.DataFrame, # Original Track DataFrame für Detail-Lookup
    poi_lat: float,
    poi_lon: float
) -> pd.Series: # Gibt eine Pandas Series mit Details des nächsten Punkts zurück oder eine leere Series
    """
    Finds details (index, lat, lon, elevation, track_distance_km) of the nearest track point
    and calculates geodetic distance (meters) from POI to this track point.
    """
    empty_result = pd.Series({
        'Nearest_Track_Idx': -1,
        'Nearest_Track_Lat': np.nan,
        'Nearest_Track_Lon': np.nan,
        'Nearest_Track_Ele_m': np.nan,
        'Nearest_Track_Dist_km': np.nan, # Kumulative Distanz entlang des Tracks
        'Dist_POI_to_Track_m': float('inf') 
    })
    if track_kdtree is None or track_df_for_lookup.empty:
        return empty_result

    try:
        # Finde Index des nächsten Nachbarn mit KDTree
        # KDTree erwartet (lat, lon) in derselben Reihenfolge wie beim Erstellen
        distance_deg, nearest_idx = track_kdtree.query([poi_lat, poi_lon])

        if nearest_idx < 0 or nearest_idx >= len(track_df_for_lookup):
             print(f"[Warnung 5c] KDTree gab ungültigen Index zurück: {nearest_idx} für ({poi_lat},{poi_lon})", file=sys.stderr)
             return empty_result

        nearest_track_point_data = track_df_for_lookup.iloc[nearest_idx]

        # Berechne präzise geodätische Distanz
        poi_coords = (poi_lat, poi_lon)
        track_point_coords = (nearest_track_point_data['Latitude'], nearest_track_point_data['Longitude'])
        dist_poi_to_track_m = geopy_distance(poi_coords, track_point_coords).meters

        return pd.Series({
            'Nearest_Track_Idx': nearest_idx,
            'Nearest_Track_Lat': nearest_track_point_data['Latitude'],
            'Nearest_Track_Lon': nearest_track_point_data['Longitude'],
            'Nearest_Track_Ele_m': nearest_track_point_data['Elevation (m)'], # Spaltenname aus 2c
            'Nearest_Track_Dist_km': nearest_track_point_data['Distanz (km)'], # Spaltenname aus 2c
            'Dist_POI_to_Track_m': dist_poi_to_track_m
        })

    except ValueError as e:
        print(f"[Warnung 5c] Geodätische Distanzberechnung fehlgeschlagen für POI ({poi_lat},{poi_lon}): {e}", file=sys.stderr)
        # Versuche, zumindest den Index zurückzugeben, falls vorhanden
        try:
            _, nearest_idx = track_kdtree.query([poi_lat, poi_lon])
            if 0 <= nearest_idx < len(track_df_for_lookup):
                 temp_res = empty_result.copy()
                 temp_res['Nearest_Track_Idx'] = nearest_idx
                 # Fülle andere Werte aus track_df_for_lookup, wenn möglich
                 nearest_track_point_data = track_df_for_lookup.iloc[nearest_idx]
                 temp_res['Nearest_Track_Lat'] = nearest_track_point_data['Latitude']
                 temp_res['Nearest_Track_Lon'] = nearest_track_point_data['Longitude']
                 temp_res['Nearest_Track_Ele_m'] = nearest_track_point_data['Elevation (m)']
                 temp_res['Nearest_Track_Dist_km'] = nearest_track_point_data['Distanz (km)']
                 return temp_res
        except: pass
        return empty_result
    except Exception as e:
        print(f"[Warnung 5c] KDTree Fehler oder anderer Fehler für POI ({poi_lat},{poi_lon}): {e}", file=sys.stderr)
        return empty_result

def get_elevation_from_api_batch(df, lat_col='Latitude', lon_col='Longitude',
                                 dataset='srtm90m', # oder andere wie 'aster30m', 'eudem25m' etc.
                                 batch_size=100, # OpenTopoData erlaubt bis zu 100 Punkte pro Anfrage
                                 delay_between_requests=1.1): # Wichtig, um API nicht zu überlasten (1 req/sec limit)
    """
    Ruft Höhen für eine Liste von Koordinaten von der OpenTopoData API ab.
    Fügt eine neue Spalte 'Elevation_API' zum DataFrame hinzu.
    df: Pandas DataFrame mit Lat/Lon-Spalten.
    lat_col: Name der Breitengrad-Spalte.
    lon_col: Name der Längengrad-Spalte.
    dataset: Das zu verwendende Höhenmodell (siehe OpenTopoData Doku).
    batch_size: Anzahl der Punkte pro API-Anfrage.
    delay_between_requests: Wartezeit zwischen Anfragen in Sekunden.
    """
    print(f"[Info 5c] Starte Höhenabfrage von OpenTopoData für {len(df)} Punkte (Dataset: {dataset})...")
    api_url = "https://api.opentopodata.org/v1/" + dataset
    all_api_elevations = [np.nan] * len(df) # Vorbelegen mit NaN

    # Iteriere über den DataFrame in Batches
    for i in tqdm(range(0, len(df), batch_size), desc="Abfrage Höhen-API"):
        batch_df = df.iloc[i:i + batch_size]
        
        # Erstelle die Location-Payload (lat,lon|lat,lon|...)
        locations_payload = "|".join([f"{row[lat_col]},{row[lon_col]}" for _, row in batch_df.iterrows() if pd.notna(row[lat_col]) and pd.notna(row[lon_col])])

        if not locations_payload: # Wenn alle Lat/Lon im Batch NaN sind
            continue

        try:
            response = requests.post(api_url, data={'locations': locations_payload})
            response.raise_for_status() # Löst einen Fehler bei HTTP-Fehlercodes aus
            results = response.json().get('results', [])

            # Ordne die Ergebnisse den richtigen Zeilen im Original-Batch zu
            # Dies ist wichtig, da die API nur für gültige Punkte Ergebnisse liefert
            # und die Reihenfolge beibehält.
            current_result_idx = 0
            for batch_idx, (_, original_row) in enumerate(batch_df.iterrows()):
                original_df_idx = original_row.name # Index im ursprünglichen DataFrame
                if pd.notna(original_row[lat_col]) and pd.notna(original_row[lon_col]):
                    if current_result_idx < len(results):
                        elevation_api = results[current_result_idx].get('elevation')
                        if elevation_api is not None:
                            all_api_elevations[original_df_idx] = float(elevation_api)
                        current_result_idx += 1
                    else:
                        # Sollte nicht passieren, wenn API korrekt antwortet
                        print(f"[Warnung 5c] API lieferte weniger Ergebnisse als erwartet für Batch ab Index {i}.", file=sys.stderr)
                        break 
        
        except requests.exceptions.RequestException as e:
            print(f"[Warnung 5c] Fehler bei API-Anfrage für Batch ab Index {i}: {e}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"[Warnung 5c] Fehler beim Parsen der API-Antwort für Batch ab Index {i}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[Warnung 5c] Unbekannter Fehler bei API-Abfrage für Batch ab Index {i}: {e}", file=sys.stderr)

        time.sleep(delay_between_requests) # Wichtig!

    df['Elevation_API'] = all_api_elevations
    print(f"[Info 5c] Höhenabfrage von API abgeschlossen. {df['Elevation_API'].notna().sum()} Höhenwerte erhalten.")
    return df

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
    run_start_time = datetime.now()
    print("[Info 5c] Merging, enriching (elevation from track), and filtering POIs...")

    # --- 1. Lade Service POIs (aus 5a) ---
    service_df = pd.DataFrame()
    if service_csv_path and os.path.exists(service_csv_path):
        try:
            service_df = pd.read_csv(service_csv_path, comment='#')
            if 'Elevation_OSM' not in service_df.columns:
                service_df['Elevation_OSM'] = np.nan
            service_df['Elevation_OSM'] = pd.to_numeric(service_df['Elevation_OSM'], errors='coerce')
            print(f"[Info 5c] Service POIs geladen: {len(service_df)}")
        except Exception as e:
            print(f"[Warnung 5c] Fehler beim Laden Service POI CSV '{service_csv_path}': {e}", file=sys.stderr)
    else:
        print(f"[Warnung 5c] Service POI Datei nicht gefunden oder nicht angegeben: {service_csv_path}", file=sys.stderr)

    # --- 2. Lade Peak/Viewpoint POIs (aus 5b) ---
    peak_data_list = []
    if peak_json_path and os.path.exists(peak_json_path):
        try:
            with open(peak_json_path, 'r', encoding='utf-8') as f:
                peak_json_data = json.load(f)
                for elem in peak_json_data.get("elements", []):
                    peak_data_list.append({
                        "Name": elem.get("name", elem.get("type", "Unbenannt").capitalize()),
                        "Typ": elem.get("type", "Unbekannt").lower(),
                        "Adresse": "N/A",
                        "Latitude": elem.get("latitude"),
                        "Longitude": elem.get("longitude"),
                        "Elevation_OSM": elem.get("Elevation_OSM"),
                    })
            print(f"[Info 5c] Peak/Viewpoint POIs geladen: {len(peak_data_list)}")
        except Exception as e:
            print(f"[Warnung 5c] Fehler beim Laden Peak/Viewpoint JSON '{peak_json_path}': {e}", file=sys.stderr)
    else:
        print(f"[Warnung 5c] Peak/Viewpoint JSON nicht gefunden oder nicht angegeben: {peak_json_path}", file=sys.stderr)

    peak_df = pd.DataFrame(peak_data_list)
    if not peak_df.empty:
        if 'Elevation_OSM' not in peak_df.columns:
            peak_df['Elevation_OSM'] = np.nan
        peak_df['Elevation_OSM'] = pd.to_numeric(peak_df['Elevation_OSM'], errors='coerce')

    # --- 3. Kombiniere POIs ---
    all_pois_df = pd.concat([service_df, peak_df], ignore_index=True)
    if all_pois_df.empty:
        print("[Warnung 5c] Keine POIs zum Verarbeiten vorhanden.")
        output_cols_empty = ["Name", "Typ", "Adresse", "Latitude", "Longitude",
                             "Elevation_OSM", "Elevation_API", "Elevation",
                             "Entfernung_m", "Nearest_Track_Dist_km"]
        pd.DataFrame(columns=output_cols_empty).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK 5c] Leere relevante POI CSV gespeichert: {output_csv_path}")
        return

    all_pois_df.drop_duplicates(subset=['Latitude', 'Longitude', 'Name', 'Typ'], inplace=True, keep='first')
    all_pois_df.reset_index(drop=True, inplace=True)
    all_pois_df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
    if all_pois_df.empty:
        print("[Warnung 5c] Keine POIs mit gültigen Koordinaten nach Deduplizierung.")
        output_cols_empty = ["Name", "Typ", "Adresse", "Latitude", "Longitude",
                             "Elevation_OSM", "Elevation_API", "Elevation",
                             "Entfernung_m", "Nearest_Track_Dist_km"]
        pd.DataFrame(columns=output_cols_empty).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK 5c] Leere relevante POI CSV gespeichert: {output_csv_path}")
        return
    print(f"[Info 5c] Gesamt POIs nach Deduplizierung: {len(all_pois_df)}")

    # --- 4. Lade Full Track für Höhen-Lookup und Distanzberechnung ---
    full_track_df = pd.DataFrame()
    track_kdtree = None
    if full_track_csv_path and os.path.exists(full_track_csv_path):
        try:
            full_track_df = pd.read_csv(full_track_csv_path, comment='#')
            required_track_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Distanz (km)']
            if not all(col in full_track_df.columns for col in required_track_cols):
                raise ValueError(f"Full track CSV '{full_track_csv_path}' fehlt Spalten: {required_track_cols}")
            
            full_track_df.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)
            if not full_track_df.empty:
                track_coords_for_kdtree = full_track_df[['Latitude', 'Longitude']].values
                track_kdtree = KDTree(track_coords_for_kdtree)
                print(f"[Info 5c] Volle Route für Lookup geladen ({len(full_track_df)} Punkte) und KDTree erstellt.")
            else:
                print(f"[Warnung 5c] Volle Route ist nach Bereinigung leer. Höhenanreicherung nicht möglich.", file=sys.stderr)
        except Exception as e:
            print(f"[Fehler 5c] Laden/Verarbeiten Track CSV '{full_track_csv_path}': {e}", file=sys.stderr)
            track_kdtree = None 
            full_track_df = pd.DataFrame()
    else:
        print(f"[Warnung 5c] Volle Track CSV nicht gefunden: {full_track_csv_path}. Höhenanreicherung vom Track nicht möglich.", file=sys.stderr)

    # --- 5. Anreicherung und Filterung ---
    print("[Info 5c] Anreicherung der POIs mit nächstgelegenen Track-Informationen...")
    
    enriched_poi_details_list = []
    for idx, poi_row in tqdm(all_pois_df.iterrows(), total=len(all_pois_df), desc="Enriching POIs"):
        nearest_track_info = pd.Series(dtype=object)
        if track_kdtree is not None and not full_track_df.empty:
             nearest_track_info = find_nearest_track_point_details(
                track_kdtree,
                full_track_df,
                poi_row['Latitude'],
                poi_row['Longitude']
            )
        combined_info = pd.concat([poi_row, nearest_track_info])
        enriched_poi_details_list.append(combined_info)

    if not enriched_poi_details_list:
        print(f"[Warnung 5c] Keine POIs nach Anreicherung übrig.", file=sys.stderr)
        output_cols_empty = ["Name", "Typ", "Adresse", "Latitude", "Longitude",
                             "Elevation_OSM", "Elevation_API", "Elevation",
                             "Entfernung_m", "Nearest_Track_Dist_km"]
        pd.DataFrame(columns=output_cols_empty).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK 5c] Leere relevante POI CSV gespeichert: {output_csv_path}")
        return
        
    enriched_df = pd.DataFrame(enriched_poi_details_list)
    
    # --- START DER KORRIGIERTEN HÖHENLOGIK UND API-ABFRAGE ---
    
    # Initialisiere Elevation_final_m mit OSM-Höhe, dann mit Track-Höhe
    enriched_df['Elevation_final_m'] = pd.to_numeric(enriched_df['Elevation_OSM'], errors='coerce')
    enriched_df['Elevation_final_m'] = enriched_df['Elevation_final_m'].fillna(
        pd.to_numeric(enriched_df.get('Nearest_Track_Ele_m', pd.NA), errors='coerce')
    )
    
    # Initialisiere die Spalte Elevation_API mit NaN
    enriched_df['Elevation_API'] = np.nan

    # Identifiziere POIs, für die wir eine Höhe von der API wollen 
    # (d.h. wo Elevation_final_m immer noch NaN ist)
    pois_needing_api_elevation_mask = enriched_df['Elevation_final_m'].isna() & \
                                      enriched_df['Latitude'].notna() & \
                                      enriched_df['Longitude'].notna()
    
    if pois_needing_api_elevation_mask.any():
        print(f"[Info 5c] {pois_needing_api_elevation_mask.sum()} POIs benötigen potenziell eine Höhenabfrage von der API.")
        df_to_query_api = enriched_df.loc[pois_needing_api_elevation_mask, ['Latitude', 'Longitude']].copy() # .loc und nur relevante Spalten
        
        # Stelle sicher, dass Latitude und Longitude numerisch sind
        df_to_query_api['Latitude'] = pd.to_numeric(df_to_query_api['Latitude'], errors='coerce')
        df_to_query_api['Longitude'] = pd.to_numeric(df_to_query_api['Longitude'], errors='coerce')
        df_to_query_api.dropna(subset=['Latitude', 'Longitude'], inplace=True) 
    
        if not df_to_query_api.empty:
            # API-Abfrage durchführen
            df_to_query_api = get_elevation_from_api_batch(df_to_query_api, lat_col='Latitude', lon_col='Longitude')
            
            # Füge die API-Höhen zurück in enriched_df für die entsprechenden Indizes
            if 'Elevation_API' in df_to_query_api.columns: # Sicherstellen, dass Spalte nach API-Call existiert
                enriched_df.loc[df_to_query_api.index, 'Elevation_API'] = df_to_query_api['Elevation_API']
        else:
            print("[Info 5c] Keine POIs mit gültigen Koordinaten für die API-Höhenabfrage übrig.")
    else:
        print("[Info 5c] Keine POIs benötigen eine API-Höhenabfrage basierend auf aktuellen Daten (OSM/Track-Höhe war ausreichend).")

    # Fülle Elevation_final_m nun mit API-Höhen, falls die vorherigen Quellen NaN waren und API eine Höhe lieferte
    enriched_df['Elevation_final_m'] = enriched_df['Elevation_final_m'].fillna(
        pd.to_numeric(enriched_df.get('Elevation_API', pd.NA), errors='coerce')
    )
    
    # Distanz-Spalte vorbereiten und Fallback
    if 'Dist_POI_to_Track_m' not in enriched_df.columns:
        enriched_df['Dist_POI_to_Track_m'] = float('inf') # Sollte durch find_nearest_track_point_details schon da sein
    # elif enriched_df['Dist_POI_to_Track_m'].isnull().any(): # Zusätzliche Sicherheit für NaN-Werte, die keine -1 waren
    #     enriched_df['Dist_POI_to_Track_m'].fillna(float('inf'), inplace=True)


    # Umbenennen der finalen Spalten für die Filterung
    enriched_df.rename(columns={'Elevation_final_m': 'Elevation',
                                'Dist_POI_to_Track_m': 'Entfernung_m'}, inplace=True)
    
    # --- ENDE DER KORRIGIERTEN HÖHENLOGIK UND API-ABFRAGE ---

    # --- Filterung (Logik aus deinem `is_poi_relevant` anwenden) ---
    relevant_mask = []
    print("[Info 5c] Filtere POIs nach Relevanz...")
    for _, poi_series in tqdm(enriched_df.iterrows(), total=len(enriched_df), desc="Filtering POIs"):
        is_relevant_flag = False 
        poi_type_f = poi_series.get("Typ", "").lower()
        
        raw_distance_val = poi_series.get("Entfernung_m", float('inf'))
        distance_m_f_scalar = pd.to_numeric(raw_distance_val, errors='coerce') 
        
        if pd.isna(distance_m_f_scalar): 
            distance_m_f = float('inf')
        else:
            distance_m_f = distance_m_f_scalar 
        
        elevation_f = pd.to_numeric(poi_series.get("Elevation"), errors='coerce') # Dies ist jetzt die finale Höhe
        name_f = poi_series.get("Name", "")
        
        if distance_m_f == float('inf'): 
            is_relevant_flag = False 
        else: 
            if poi_type_f == "peak":
                if not name_f:
                    is_relevant_flag = False
                else:
                    if pd.notna(elevation_f):
                        for rule in filter_config.get('peak_relevance_filter', []):
                            if distance_m_f <= rule.get('max_dist_km', 0) * 1000 and elevation_f >= rule.get('min_elev_m', 0):
                                is_relevant_flag = True
                                break 
                        # Wenn nach der Schleife is_relevant_flag immer noch False ist (weil keine Regel passte), bleibt es False.
                    else: 
                        is_relevant_flag = False
            elif poi_type_f == "viewpoint":
                is_relevant_flag = distance_m_f <= filter_config.get('max_dist_viewpoint_km', 2.0) * 1000
            else: # Service POIs
                is_relevant_flag = distance_m_f <= filter_config.get('max_dist_service_km', 0.5) * 1000
            
        relevant_mask.append(is_relevant_flag)

    if not relevant_mask: # Falls aus irgendeinem Grund die Maske leer ist (sollte nicht bei >0 POIs)
        print("[Warnung 5c] Relevanzmaske ist leer. Keine POIs als relevant befunden oder Fehler in der Schleife.", file=sys.stderr)
        relevant_pois_df = pd.DataFrame(columns=enriched_df.columns) # Leerer DataFrame mit Spalten
    elif len(relevant_mask) != len(enriched_df):
        print(f"[FEHLER 5c] Länge der Relevanzmaske ({len(relevant_mask)}) stimmt nicht mit Anzahl der POIs ({len(enriched_df)}) überein!", file=sys.stderr)
        # In diesem Fall ist ein schwerwiegender Fehler aufgetreten, ggf. abbrechen oder leeren DF
        relevant_pois_df = pd.DataFrame(columns=enriched_df.columns) 
    else:
        relevant_pois_df = enriched_df[relevant_mask].copy()
        
    print(f"[Info 5c] Relevante POIs nach Filterung: {len(relevant_pois_df)}")

    # --- 6. Speichere gefilterte und angereicherte POIs mit vollständigen Metadaten ---
    output_cols = ["Name", "Typ", "Adresse", "Latitude", "Longitude",
                   "Elevation_OSM",
                   "Elevation_API", 
                   "Elevation",     
                   "Entfernung_m",
                   "Nearest_Track_Dist_km"
                  ]
    
    for col in output_cols:
        if col not in relevant_pois_df.columns:
            relevant_pois_df[col] = np.nan 

    # Sicherstellen, dass die Reihenfolge der Spalten stimmt, auch wenn einige leer sind
    relevant_pois_df = relevant_pois_df.reindex(columns=output_cols)
    
    # Sammle Metadaten für standardisierten Header
    processing_parameters = {
        'max_dist_service_km': filter_config.get('max_dist_service_km', 0.5),
        'max_dist_viewpoint_km': filter_config.get('max_dist_viewpoint_km', 2.0),
        'peak_filter_rules_count': len(filter_config.get('peak_relevance_filter', [])),
        'total_input_pois': len(all_pois_df) if 'all_pois_df' in locals() else 0,
        'pois_after_deduplication': len(all_pois_df) if 'all_pois_df' in locals() else 0,
        'pois_needing_api_elevation': pois_needing_api_elevation_mask.sum() if 'pois_needing_api_elevation_mask' in locals() else 0,
        'final_relevant_pois': len(relevant_pois_df)
    }
    
    # API-Metadaten für Höhenabfrage
    api_metadata_pois = None
    if 'pois_needing_api_elevation_mask' in locals() and pois_needing_api_elevation_mask.any():
        api_calls_made = int(np.ceil(pois_needing_api_elevation_mask.sum() / 100))  # Geschätzt basierend auf Batch-Größe
        successful_elevations = relevant_pois_df['Elevation_API'].notna().sum()
        api_metadata_pois = {
            'provider': 'OpenTopoData API',
            'endpoint': 'api.opentopodata.org/v1/',
            'dataset': 'srtm90m',
            'estimated_api_calls': api_calls_made,
            'successful_elevations': int(successful_elevations),
            'batch_size': 100,
            'rate_limit_delay': 1.1
        }
    
    additional_metadata = {
        'processing_duration_seconds': (datetime.now() - run_start_time).total_seconds(),
        'kdtree_used': track_kdtree is not None,
        'elevation_sources_used': 'OSM, Track, API' if api_metadata_pois else 'OSM, Track',
        'poi_types_processed': list(all_pois_df['Typ'].unique()) if 'all_pois_df' in locals() else [],
        'data_quality': 'high' if len(relevant_pois_df) > 0 else 'low'
    }
    
    # Input-Dateien sammeln
    input_files = []
    if service_csv_path and os.path.exists(service_csv_path):
        input_files.append(service_csv_path)
    if peak_json_path and os.path.exists(peak_json_path):
        input_files.append(peak_json_path)
    if full_track_csv_path and os.path.exists(full_track_csv_path):
        input_files.append(full_track_csv_path)

    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        
        # CSV mit vollständigen Metadaten schreiben
        write_csv_with_metadata(
            dataframe=relevant_pois_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=input_files,
            processing_parameters=processing_parameters,
            api_metadata=api_metadata_pois,
            additional_metadata=additional_metadata,
            float_format='%.6f'
        )
        
        print(f"[OK 5c] {len(relevant_pois_df)} relevante und angereicherte POIs mit vollständigen Metadaten gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler 5c] Konnte relevante POI CSV nicht schreiben '{output_csv_path}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    print_script_info()
    
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