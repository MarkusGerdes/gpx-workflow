#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5c_merge_filter_pois.py (V2 - Mit Höhenanreicherung vom Track)
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
from shapely.geometry import Point, LineString # Optional, wenn nicht schon von KDTree abgedeckt
import numpy as np
from scipy.spatial import KDTree # Für schnelle Nächste-Nachbar-Suche
from geopy.distance import distance as geopy_distance # Für präzise Distanz

# Korrekter tqdm Import:
try:
    from tqdm import tqdm
    print("[INFO 5c] tqdm für Fortschrittsbalken geladen.", file=sys.stderr)
except ImportError:
    print("[WARNUNG 5c] tqdm nicht gefunden (pip install tqdm), Fortschrittsbalken wird nicht angezeigt.", file=sys.stderr)
    def tqdm(iterable, *args, **kwargs): # Dummy-Funktion als Fallback
        print(f"Iteriere über {kwargs.get('desc', 'iterable')} (tqdm nicht verfügbar)...", file=sys.stderr)
        return iterable

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
        'Dist_POI_to_Track_m': -1.0
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
    print("[Info 5c] Merging, enriching (elevation from track), and filtering POIs...")

    # --- 1. Lade Service POIs (aus 5a) ---
    service_df = pd.DataFrame()
    if service_csv_path and os.path.exists(service_csv_path):
        try:
            service_df = pd.read_csv(service_csv_path)
            # Stelle sicher, dass Elevation_OSM existiert, fülle mit NaN falls nicht
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
                        "Elevation_OSM": elem.get("Elevation_OSM"), # Name aus 5b
                        # "tags": elem.get("tags") # Bei Bedarf
                    })
            print(f"[Info 5c] Peak/Viewpoint POIs geladen: {len(peak_data_list)}")
        except Exception as e:
            print(f"[Warnung 5c] Fehler beim Laden Peak/Viewpoint JSON '{peak_json_path}': {e}", file=sys.stderr)
    else:
        print(f"[Warnung 5c] Peak/Viewpoint JSON nicht gefunden oder nicht angegeben: {peak_json_path}", file=sys.stderr)

    peak_df = pd.DataFrame(peak_data_list)
    if not peak_df.empty:
        if 'Elevation_OSM' not in peak_df.columns: # Fallback
            peak_df['Elevation_OSM'] = np.nan
        peak_df['Elevation_OSM'] = pd.to_numeric(peak_df['Elevation_OSM'], errors='coerce')


    # --- 3. Kombiniere POIs ---
    all_pois_df = pd.concat([service_df, peak_df], ignore_index=True)
    if all_pois_df.empty:
        print("[Warnung 5c] Keine POIs zum Verarbeiten vorhanden.")
        # Header für leere Datei
        empty_cols = ["Name", "Typ", "Adresse", "Latitude", "Longitude", 
                      "Elevation_OSM", "Elevation_Track_m", "Dist_POI_to_Track_m", 
                      "Nearest_Track_Dist_km"]
        pd.DataFrame(columns=empty_cols).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK 5c] Leere relevante POI CSV gespeichert: {output_csv_path}")
        return

    all_pois_df.drop_duplicates(subset=['Latitude', 'Longitude', 'Name', 'Typ'], inplace=True, keep='first')
    all_pois_df.reset_index(drop=True, inplace=True)
    all_pois_df.dropna(subset=['Latitude', 'Longitude'], inplace=True) # POIs ohne Koordinaten sind nutzlos
    if all_pois_df.empty: # Erneute Prüfung
        print("[Warnung 5c] Keine POIs mit gültigen Koordinaten nach Deduplizierung.")
        # ... (leere CSV speichern) ...
        return
    print(f"[Info 5c] Gesamt POIs nach Deduplizierung: {len(all_pois_df)}")


    # --- 4. Lade Full Track für Höhen-Lookup und Distanzberechnung ---
    full_track_df = pd.DataFrame()
    track_kdtree = None
    if full_track_csv_path and os.path.exists(full_track_csv_path):
        try:
            full_track_df = pd.read_csv(full_track_csv_path)
            # Benötigt: 'Latitude', 'Longitude', 'Elevation (m)', 'Distanz (km)'
            required_track_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Distanz (km)']
            if not all(col in full_track_df.columns for col in required_track_cols):
                raise ValueError(f"Full track CSV '{full_track_csv_path}' fehlt Spalten: {required_track_cols}")
            
            full_track_df.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)
            if not full_track_df.empty:
                # KDTree erwartet Daten als (lat, lon) Paare
                track_coords_for_kdtree = full_track_df[['Latitude', 'Longitude']].values
                track_kdtree = KDTree(track_coords_for_kdtree)
                print(f"[Info 5c] Volle Route für Lookup geladen ({len(full_track_df)} Punkte) und KDTree erstellt.")
            else:
                print(f"[Warnung 5c] Volle Route ist nach Bereinigung leer. Höhenanreicherung nicht möglich.", file=sys.stderr)
        except Exception as e:
            print(f"[Fehler 5c] Laden/Verarbeiten Track CSV '{full_track_csv_path}': {e}", file=sys.stderr)
            # Fahre fort ohne Höhenanreicherung vom Track, wenn KDTree nicht erstellt werden konnte
            track_kdtree = None 
            full_track_df = pd.DataFrame() # Leeren, um Fehler unten zu vermeiden
    else:
        print(f"[Warnung 5c] Volle Track CSV nicht gefunden: {full_track_csv_path}. Höhenanreicherung vom Track nicht möglich.", file=sys.stderr)


    # --- 5. Anreicherung und Filterung ---
    print("[Info 5c] Anreicherung der POIs mit nächstgelegenen Track-Informationen...")
    
    enriched_poi_details_list = []
    # Verwende tqdm für den Fortschrittsbalken
    for idx, poi_row in tqdm(all_pois_df.iterrows(), total=len(all_pois_df), desc="Enriching POIs"):
        nearest_track_info = pd.Series(dtype=object) # Leere Series als Default
        if track_kdtree is not None and not full_track_df.empty:
             nearest_track_info = find_nearest_track_point_details(
                track_kdtree,
                full_track_df, # Der DataFrame zum Nachschlagen der Details
                poi_row['Latitude'],
                poi_row['Longitude']
            )
        
        # Kombiniere poi_row mit nearest_track_info
        # pd.concat ist hier nützlich, da beide Series sind
        combined_info = pd.concat([poi_row, nearest_track_info])
        enriched_poi_details_list.append(combined_info)

    if not enriched_poi_details_list:
        print(f"[Warnung 5c] Keine POIs nach Anreicherung übrig.", file=sys.stderr)
        # ... (leere CSV speichern) ...
        return
        
    enriched_df = pd.DataFrame(enriched_poi_details_list)

    # Finale Höhenspalte erstellen:
    # Priorität 1: Elevation_OSM (wenn es eine valide Zahl ist)
    # Priorität 2: Nearest_Track_Ele_m
    # Priorität 3: NaN
    enriched_df['Elevation_final_m'] = pd.to_numeric(enriched_df['Elevation_OSM'], errors='coerce')
    enriched_df['Elevation_final_m'] = enriched_df['Elevation_final_m'].fillna(
        pd.to_numeric(enriched_df.get('Nearest_Track_Ele_m', pd.NA), errors='coerce') # .get für den Fall, dass Spalte fehlt
    )
    
    # Umbenennen und Auswählen der finalen Spalten für den Filter
    # Dist_POI_to_Track_m ist bereits in enriched_df, wenn Anreicherung erfolgreich war
    # Entfernung_m wird durch Dist_POI_to_Track_m ersetzt/erzeugt
    if 'Dist_POI_to_Track_m' not in enriched_df.columns: # Fallback, falls Anreicherung fehlschlug
        enriched_df['Dist_POI_to_Track_m'] = -1.0
    
    # Ersetze die alte 'Elevation'-Logik mit der neuen 'Elevation_final_m'
    # und stelle sicher, dass die Spalte für is_poi_relevant 'Elevation' heißt
    enriched_df.rename(columns={'Elevation_final_m': 'Elevation', # Für is_poi_relevant
                                'Dist_POI_to_Track_m': 'Entfernung_m'}, inplace=True)


    # --- Filterung (Logik aus deinem `is_poi_relevant` anwenden) ---
    # Die `is_poi_relevant` Funktion benötigt `track_line_shapely`.
    # Wir können die Distanz `Entfernung_m` direkt verwenden, die wir schon berechnet haben.
    
    relevant_mask = []
    print("[Info 5c] Filtere POIs nach Relevanz...")
    for _, poi_series in tqdm(enriched_df.iterrows(), total=len(enriched_df), desc="Filtering POIs"):
        # `is_poi_relevant` muss angepasst werden, um `poi_series['Entfernung_m']` zu verwenden
        # statt die Distanz neu zu berechnen.
        # Für dieses Beispiel vereinfache ich den Filter hier direkt:
        
        is_relevant_flag = False
        poi_type_f = poi_series.get("Typ", "").lower()
        
        # --- KORREKTUR HIER ---
        raw_distance_val = poi_series.get("Entfernung_m", float('inf'))
        distance_m_f_numeric = pd.to_numeric(raw_distance_val, errors='coerce')
        if pd.isna(distance_m_f_numeric): # Prüfe, ob die Konvertierung zu NaN geführt hat
            distance_m_f = float('inf')
        else:
            distance_m_f = distance_m_f_numeric
        # --- ENDE KORREKTUR ---
        
        elevation_f = pd.to_numeric(poi_series.get("Elevation"), errors='coerce') # Bereits Elevation_final_m
        name_f = poi_series.get("Name", "")

        if poi_type_f == "peak":
            if not name_f: is_relevant_flag = False
            else:
                if pd.notna(elevation_f):
                    for rule in filter_config.get('peak_relevance_filter', []):
                        if distance_m_f <= rule.get('max_dist_km', 0) * 1000 and elevation_f >= rule.get('min_elev_m', 0):
                            is_relevant_flag = True; break
                else: is_relevant_flag = False # Peaks ohne Höhe sind weniger relevant
        elif poi_type_f == "viewpoint":
            is_relevant_flag = distance_m_f <= filter_config.get('max_dist_viewpoint_km', 2.0) * 1000
        else: # Service POIs
            is_relevant_flag = distance_m_f <= filter_config.get('max_dist_service_km', 0.5) * 1000
        
        relevant_mask.append(is_relevant_flag)

    relevant_pois_df = enriched_df[relevant_mask].copy()
    print(f"[Info 5c] Relevante POIs nach Filterung: {len(relevant_pois_df)}")

    # --- 6. Speichere gefilterte und angereicherte POIs ---
    # Wähle finale Spalten aus
    output_cols = ["Name", "Typ", "Adresse", "Latitude", "Longitude", 
                   "Elevation_OSM", # Originale OSM Höhe (kann NaN sein)
                   "Elevation",     # Finale verwendete Höhe (aus OSM oder vom Track)
                   "Entfernung_m",  # Distanz POI zum nächsten Trackpunkt
                   "Nearest_Track_Dist_km" # Kumulative Distanz des nächsten Trackpunkts
                   # Optional: 'Nearest_Track_Idx', 'Nearest_Track_Lat', 'Nearest_Track_Lon'
                  ]
    
    # Stelle sicher, dass alle Output-Spalten existieren, fülle mit NaN falls nicht
    for col in output_cols:
        if col not in relevant_pois_df.columns:
            relevant_pois_df[col] = np.nan # oder pd.NA für konsistente Pandas Missing Values

    relevant_pois_df = relevant_pois_df[output_cols]

    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        relevant_pois_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK 5c] {len(relevant_pois_df)} relevante und angereicherte POIs gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler 5c] Konnte relevante POI CSV nicht schreiben '{output_csv_path}': {e}", file=sys.stderr)
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