#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4b_fetch_surface_grouped.py (V2 - mit original_index und Distanz-Referenz)
---------------------------
Reads optimized track data with location and original_index (output of step 4).
Groups consecutive points by Street and City.
Selects a representative point for each group.
Queries Overpass API for these representative points to get surface data.
Assigns the found surface data back to ALL points of the corresponding group.
Adds 'Distanz_km_orig_track' by merging with a full track reference CSV using original_index.
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
import requests # Wird hier nicht direkt verwendet, aber oft in Zusammenhang mit APIs
import overpy
import time
# import math # Nicht mehr direkt verwendet
from tqdm import tqdm
from typing import Optional, List, Dict, Any, Tuple # Optional hier hinzufügen
# from geopy.distance import geodesic # Nicht mehr direkt verwendet, da Gruppierung auf Street/City basiert

try:
    from shapely.geometry import Point, LineString
    SHAPELY_AVAILABLE = True
    print("[INFO] Shapely ist verfügbar.")
except ImportError:
    SHAPELY_AVAILABLE = False
    print("[WARNUNG] Shapely ist nicht verfügbar. Die Auswahl des nächsten Weges wird weniger präzise sein.")


# --- Konfiguration ---
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter" # Standard Overpass API
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_REQUESTS = 1.1 # Gemäß Nominatim/Overpass Richtlinien
RETRY_DELAY = 5 # Erhöht von 3 auf 5
MAX_RETRIES = 3 # Reduziert von 4 auf 3, um Endlosläufe bei persistenten Fehlern zu vermeiden
# QUERY_RADIUS_M wird als Parameter übergeben
RELEVANT_HIGHWAY_TYPES = ["primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "track", "cycleway", "path", "bridleway", "footway"]
HIGHWAY_QUERY_FILTER_VALUE = "|".join(RELEVANT_HIGHWAY_TYPES)
HIGHWAY_TO_SURFACE_INFERENCE = {
    "motorway": "paved", "trunk": "paved", "primary": "paved",
    "secondary": "paved", "tertiary": "paved", "unclassified": "paved",
    "residential": "paved", "living_street": "paved", "service": "paved",
    "cycleway": "paved", "track": "unpaved", "path": "unpaved",
    "bridleway": "unpaved", "footway": "paved"
}
DEFAULT_SURFACE = "unknown"
DEFAULT_DIST_COL_NAME_IN_REF = 'Distanz (km)' # Name der Distanzspalte in der Referenzdatei

# --- Helper Funktionen ---
def infer_surface(tags: dict) -> str:
    highway = tags.get("highway")
    tracktype = tags.get("tracktype")
    # surface_tag = tags.get("surface") # Direkt vorhanden?
    # if surface_tag: return surface_tag # Wenn explizit, dann nehmen

    if not highway: return DEFAULT_SURFACE
    if highway == "track":
        if tracktype in ["grade1", "grade2"]: return "compacted"
        elif tracktype in ["grade3", "grade4", "grade5"]: return "ground"
        else: return "unpaved" # Fallback für track ohne spezifischen tracktype
    return HIGHWAY_TO_SURFACE_INFERENCE.get(highway, DEFAULT_SURFACE)

def get_way_tags(way: overpy.Way) -> dict:
    tags = way.tags
    surface = tags.get("surface") # Erst direkten Surface-Tag prüfen
    if surface is None: # Nur wenn kein direkter Surface-Tag da ist, inferieren
        surface = infer_surface(tags)
    
    # Sicherstellen, dass auch 'paved' oder 'unpaved' aus Inferenz kommt, wenn surface explizit war
    # z.B. highway=residential (infer: paved) aber surface=gravel -> gravel nehmen
    # Die aktuelle Inferenz überschreibt nicht, wenn surface schon da ist. Das ist gut.

    return {
        "surface": surface,
        "tracktype": tags.get("tracktype"),
        "highway": tags.get("highway"),
        "smoothness": tags.get("smoothness"),
        "osm_way_id": way.id
    }

def find_closest_way(ways: list[overpy.Way], point_lat: float, point_lon: float) -> Optional[overpy.Way]:
    if not ways: return None
    if not SHAPELY_AVAILABLE:
        # print("  [Debug find_closest_way] Shapely nicht verfügbar, nehme ersten Weg.")
        return ways[0]
    try:
        query_point = Point(point_lon, point_lat)
        min_dist = float('inf')
        closest_way = None
        for way in ways:
            if not way.nodes or len(way.nodes) < 2: # Weg braucht mindestens 2 Knoten für eine Linie
                # print(f"  [Debug find_closest_way] Weg {way.id} hat < 2 Knoten.")
                continue
            way_coords = [(node.lon, node.lat) for node in way.nodes]
            try:
                way_line = LineString(way_coords)
                dist = way_line.distance(query_point)
                if dist < min_dist:
                    min_dist = dist
                    closest_way = way
            except Exception as shapely_err: # Fehler bei Erstellung LineString oder Distanz
                # print(f"  [Debug find_closest_way] Shapely Fehler bei Weg {way.id}: {shapely_err}")
                continue # Ignoriere diesen Weg
        # if closest_way:
        #    print(f"  [Debug find_closest_way] Nächster Weg ID {closest_way.id} mit Distanz {min_dist:.5f} (Grad).")
        # else:
        #    print("  [Debug find_closest_way] Kein nächster Weg gefunden via Shapely.")
        return closest_way
    except Exception as e:
        print(f"[Warnung] Allgemeiner Shapely Fehler in find_closest_way: {e}")
        return ways[0] # Fallback zum ersten Weg bei unerwartetem Fehler


# --- Hauptfunktion ---
def fetch_surface_data(
    input_track_loc_idx_csv: str,
    full_track_ref_csv_path: str,
    output_surface_csv_path: str,
    query_radius_m: int,
    dist_col_in_ref: str # Parameter direkt von argparse
):
    print(f"[Info] Fetching grouped Surface Data for: {input_track_loc_idx_csv}")
    print(f"  Reference track for distance: {full_track_ref_csv_path}")
    print(f"  Query Radius: {query_radius_m}m")

    # --- Lade Input-Datei (Output von Schritt 4) ---
    try:
        # Definiere dtypes für wichtigen Spalten
        # original_index sollte als Int64 gelesen werden, um NaNs korrekt zu behandeln, falls welche da sind
        # Obwohl es von 4_reverse_geocode.py als Int64 kommen sollte
        dtypes_input = {'Latitude': float, 'Longitude': float, 'original_index': 'Int64', 'Street': str, 'City': str}
        df_loc = pd.read_csv(input_track_loc_idx_csv, dtype=dtypes_input, keep_default_na=False)

        required_cols = ["Latitude", "Longitude", "original_index", "Street", "City"]
        if not all(col in df_loc.columns for col in required_cols):
            raise ValueError(f"Input CSV '{input_track_loc_idx_csv}' fehlt Spalten. Benötigt: {required_cols}")
        
        # Ersetze leere Strings in Street/City durch einen expliziten Wert für die Gruppierung,
        # um zu vermeiden, dass leere Strings unterschiedliche Blöcke erzeugen, wenn sie nicht NaN sind.
        if 'Street' in df_loc.columns: # Sicherstellen, dass die Spalte existiert
            df_loc['Street'] = df_loc['Street'].replace('', 'StraßeUnbekanntFürBlock')
        if 'City' in df_loc.columns: # Sicherstellen, dass die Spalte existiert
            df_loc['City'] = df_loc['City'].replace('', 'OrtUnbekanntFürBlock')

        if df_loc.empty:
            print("[Warnung] Input CSV ist leer.")
            empty_cols = ['Latitude', 'Longitude', 'original_index', dist_col_in_ref, 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']
            pd.DataFrame(columns=empty_cols).to_csv(output_surface_csv_path, index=False)
            sys.exit(0)
        
        # Konvertiere Koordinaten sicher zu numerisch, falls nicht schon durch dtype geschehen
        df_loc['Latitude'] = pd.to_numeric(df_loc['Latitude'], errors='coerce')
        df_loc['Longitude'] = pd.to_numeric(df_loc['Longitude'], errors='coerce')
        df_loc.dropna(subset=['Latitude', 'Longitude'], inplace=True) # Entferne Zeilen ohne gültige Koordinaten

        if df_loc.empty: # Erneute Prüfung nach dropna
            print("[Warnung] Keine gültigen Koordinaten im Input nach Bereinigung.")
            empty_cols = ['Latitude', 'Longitude', 'original_index', dist_col_in_ref, 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']
            pd.DataFrame(columns=empty_cols).to_csv(output_surface_csv_path, index=False)
            sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Input-Datei nicht gefunden: {input_track_loc_idx_csv}")
        sys.exit(1)
    except ValueError as ve:
        print(f"[Fehler] Problem mit Input CSV Spalten: {ve}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Lesen der Input-CSV '{input_track_loc_idx_csv}' fehlgeschlagen: {e}")
        sys.exit(1)

    # --- Lade Referenz-Track-Datei (Output von Schritt 2c) ---
    df_full_track_ref = pd.DataFrame() # Initialisiere als leerer DataFrame
    if full_track_ref_csv_path and os.path.exists(full_track_ref_csv_path):
        try:
            df_full_track_ref = pd.read_csv(full_track_ref_csv_path)
            if dist_col_in_ref not in df_full_track_ref.columns:
                print(f"[Warnung] Spalte '{dist_col_in_ref}' nicht in Referenz-Track '{full_track_ref_csv_path}' gefunden. Distanz wird nicht hinzugefügt.")
                df_full_track_ref = pd.DataFrame() # Leeren, um Merge-Fehler zu vermeiden
            elif df_full_track_ref.empty:
                print(f"[Warnung] Referenz-Track-Datei '{full_track_ref_csv_path}' ist leer.")
        except Exception as e:
            print(f"[Warnung] Fehler beim Lesen der Referenz-Track-Datei '{full_track_ref_csv_path}': {e}. Distanz wird nicht hinzugefügt.")
            df_full_track_ref = pd.DataFrame()
    else:
        print(f"[Warnung] Referenz-Track-Datei '{full_track_ref_csv_path}' nicht gefunden oder nicht angegeben. Distanz wird nicht hinzugefügt.")


    # --- Gruppiere nach aufeinanderfolgenden Straßen/Orts-Blöcken ---
    print("[Info] Gruppiere Punkte nach Straßen-/Ortsblöcken...")
    cols_for_block_id = []
    if 'Street' in df_loc.columns:
        cols_for_block_id.append('Street')
    else:
        print("[Warnung] Spalte 'Street' nicht in df_loc für block_id Berechnung gefunden.")
    if 'City' in df_loc.columns:
        cols_for_block_id.append('City')
    else:
        print("[Warnung] Spalte 'City' nicht in df_loc für block_id Berechnung gefunden.")

    if len(cols_for_block_id) > 0: # Nur wenn mindestens eine Spalte da ist
        # Erzeuge eine temporäre Spalte mit Tupeln der zu vergleichenden Werte
        # Dies macht den Vergleich einfacher und vermeidet Probleme mit dem Shift auf mehreren Spalten
        df_loc['temp_group_key'] = list(zip(*(df_loc[col] for col in cols_for_block_id)))
    
        # Vergleiche die aktuelle Zeile mit der vorherigen (geshifteten) Zeile
        # .ne() ist "not equal". fill_value für shift ist hier nicht so kritisch,
        # da die erste Zeile sowieso einen neuen Block startet (da der Vergleich mit NaN/NaT ungleich ist).
        # Wichtig ist, dass die erste Zeile als Blockanfang erkannt wird.
        is_new_block = df_loc['temp_group_key'].ne(df_loc['temp_group_key'].shift())
    
        # Die allererste Zeile ist immer ein neuer Block
        if not df_loc.empty:
            is_new_block.iloc[0] = True 
        
        df_loc['block_id'] = is_new_block.cumsum()
        df_loc.drop(columns=['temp_group_key'], inplace=True) # Temporäre Spalte entfernen
    else:
        print("[Warnung] Keine Spalten für block_id Berechnung vorhanden. Setze block_id auf 1 für alle.")
        df_loc['block_id'] = 1 # Fallback    

    representative_points_data = []
    for block_id_val, group_df in df_loc.groupby('block_id'):
        if group_df.empty: continue
        # Nimm den ersten Punkt des Blocks als repräsentativ (einfacher als Mitte bei komplexen Indizes nach potentiellem dropna)
        # Wichtig: .iloc[0] verwenden, da der Index von group_df der Originalindex aus df_loc ist.
        rep_point_series = group_df.iloc[0]
        representative_points_data.append({
            'block_id': block_id_val,
            'latitude': rep_point_series['Latitude'],
            'longitude': rep_point_series['Longitude'],
            # 'original_index_rep': rep_point_series['original_index'], # Index des Rep-Punktes
            # 'street_rep': rep_point_series['Street'], # Für Debugging
            # 'city_rep': rep_point_series['City']
        })

    print(f"[Info] {len(representative_points_data)} repräsentative Punkte für {df_loc['block_id'].nunique()} Blöcke ausgewählt.")

    # --- Overpass API Abfragen ---
    api = overpy.Overpass()
    surface_data_for_blocks = {} # block_id -> tags_dict
    api_query_errors = 0

    for point_data in tqdm(representative_points_data, desc="Overpass API Queries"):
        current_block_id = point_data['block_id']
        lat_query = point_data['latitude']
        lon_query = point_data['longitude']

        overpass_query_str = f"""
        [out:json][timeout:{REQUEST_TIMEOUT}];
        ( way(around:{query_radius_m},{lat_query:.7f},{lon_query:.7f})["highway"~"{HIGHWAY_QUERY_FILTER_VALUE}"]; );
        out body; >; out skel qt;
        """
        # print(f"\n[DEBUG] Block {current_block_id} Query für ({lat_query:.5f}, {lon_query:.5f}):\n{overpass_query_str[:150]}...") # Gekürzte Query

        query_successful = False
        for attempt_num in range(MAX_RETRIES):
            try:
                api_result = api.query(overpass_query_str)
                query_successful = True
                # print(f"  [DEBUG] Block {current_block_id}: Overpass gab {len(api_result.ways)} Wege zurück.")

                if not api_result.ways:
                    # print(f"  [DEBUG] Block {current_block_id}: Kein Weg im Radius {query_radius_m}m gefunden.")
                    surface_data_for_blocks[current_block_id] = {"surface": DEFAULT_SURFACE, "highway": "none_found_in_radius"}
                    break # Aus Retry-Schleife für diesen Block

                selected_way = find_closest_way(api_result.ways, lat_query, lon_query)

                if selected_way:
                    way_attribute_tags = get_way_tags(selected_way)
                    # print(f"  [DEBUG] Block {current_block_id}: Nächster Weg ID {selected_way.id}, Tags: {way_attribute_tags}")
                    surface_data_for_blocks[current_block_id] = way_attribute_tags
                else:
                    # print(f"  [DEBUG] Block {current_block_id}: Kein nächster Weg ausgewählt trotz {len(api_result.ways)} Kandidaten.")
                    surface_data_for_blocks[current_block_id] = {"surface": DEFAULT_SURFACE, "highway": "none_selected_from_candidates"}
                break # Aus Retry-Schleife

            except overpy.exception.OverpassTooManyRequests:
                wait = RETRY_DELAY * (attempt_num + 2) # Länger warten bei Rate Limit
                print(f"-> Rate Limit für Block {current_block_id} (Versuch {attempt_num + 1}/{MAX_RETRIES}). Warte {wait}s...")
                time.sleep(wait)
            except (overpy.exception.OverpassGatewayTimeout, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e_timeout:
                wait = RETRY_DELAY * (attempt_num + 1)
                print(f"-> Timeout/Netzwerkfehler für Block {current_block_id} (Versuch {attempt_num + 1}/{MAX_RETRIES}): {type(e_timeout).__name__}. Warte {wait}s...")
                time.sleep(wait)
            except Exception as e_general:
                print(f"-> Unerwarteter Fehler bei Overpass Query Block {current_block_id} (Versuch {attempt_num + 1}/{MAX_RETRIES}): {e_general}")
                # print(f"   Query war: {overpass_query_str}") # Bei Bedarf ausgeben
                time.sleep(RETRY_DELAY) # Kurze Pause auch hier

        if not query_successful:
            print(f"-> FEHLER: Abfrage für Block {current_block_id} nach {MAX_RETRIES} Versuchen fehlgeschlagen.")
            api_query_errors += 1
            surface_data_for_blocks[current_block_id] = {"surface": DEFAULT_SURFACE, "highway": "api_query_failed"}

        if len(representative_points_data) > 1 : # Nur schlafen, wenn es mehr als eine Anfrage gibt
             time.sleep(SLEEP_BETWEEN_REQUESTS)


    print(f"\n[Info] Overpass-Abfragen abgeschlossen. {len(surface_data_for_blocks) - api_query_errors} Blöcke mit potenziellen Daten ({api_query_errors} Fehler).")

    # --- Ergebnisse den Punkten im ursprünglichen df_loc zuweisen ---
    print("[Info] Weise Oberflächenwerte den ursprünglichen Punkten zu...")
    # Initialisiere Spalten mit pd.NA für bessere Handhabung fehlender Werte
    for col_name in ['Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']:
        df_loc[col_name] = pd.NA

    for block_id_val, tags_dict in surface_data_for_blocks.items():
        block_mask = df_loc['block_id'] == block_id_val
        df_loc.loc[block_mask, 'Surface'] = tags_dict.get('surface', DEFAULT_SURFACE) # Fallback hier auch
        df_loc.loc[block_mask, 'Tracktype'] = tags_dict.get('tracktype')
        df_loc.loc[block_mask, 'Highway'] = tags_dict.get('highway')
        df_loc.loc[block_mask, 'Smoothness'] = tags_dict.get('smoothness')
        df_loc.loc[block_mask, 'OSM_Way_ID'] = tags_dict.get('osm_way_id')

    # Fülle verbleibende NaNs in 'Surface' (sollte durch obiges Default abgedeckt sein)
    df_loc['Surface'].fillna(DEFAULT_SURFACE, inplace=True)

    # --- Distanz vom Original-Track hinzufügen ---
    print(f"[DEBUG 4b] Beginne Hinzufügen von Distanz/Höhe. df_loc Spalten: {df_loc.columns.tolist()}", file=sys.stderr)    
    df_loc[dist_col_in_ref] = pd.NA # Initialisiere Distanzspalte
    df_loc['Elevation (m)'] = pd.NA # Initialisiere Höhendaten-Spalte

    if not df_full_track_ref.empty and 'original_index' in df_loc.columns:
        df_loc_indexed_for_merge = df_loc.dropna(subset=['original_index']).copy()
        if not df_loc_indexed_for_merge.empty: # Nur weitermachen, wenn nach dropna noch was da ist
            df_loc_indexed_for_merge['original_index'] = df_loc_indexed_for_merge['original_index'].astype(int)

            cols_to_merge_from_ref = []
            if dist_col_in_ref in df_full_track_ref.columns:
                cols_to_merge_from_ref.append(dist_col_in_ref)
                print(f"[DEBUG 4b] '{dist_col_in_ref}' wird aus Referenz für Merge ausgewählt.")
            else:
                print(f"[Warnung 4b] Spalte '{dist_col_in_ref}' nicht in Referenz-Track. Distanz wird NICHT hinzugefügt.")

            if 'Elevation (m)' in df_full_track_ref.columns:
                cols_to_merge_from_ref.append('Elevation (m)')
                print(f"[DEBUG 4b] 'Elevation (m)' wird aus Referenz für Merge ausgewählt.")
            else:
                print(f"[Warnung 4b] Spalte 'Elevation (m)' nicht in Referenz-Track. Höhe wird NICHT hinzugefügt.")

            if not cols_to_merge_from_ref:
                 print(f"[Warnung 4b] Keine Spalten zum Mergen aus Referenzdatei ausgewählt.")
            else: # Dieser else-Block gehört zu 'if not cols_to_merge_from_ref:'
                df_ref_for_merge = df_full_track_ref[cols_to_merge_from_ref].copy()
                df_ref_for_merge['original_index'] = df_full_track_ref.index

                merged_df = pd.merge(
                    df_loc_indexed_for_merge,
                    df_ref_for_merge,
                    on='original_index',
                    how='left',
                    suffixes=('', '_ref')
                )
                print(f"[DEBUG 4b] Spalten nach Merge: {merged_df.columns.tolist()}", file=sys.stderr)

                # Iteriere über merged_df und aktualisiere df_loc
                # Dies stellt sicher, dass wir nur existierende Indizes in df_loc aktualisieren
                for _, row in merged_df.iterrows():
                    orig_idx = row['original_index']
                    
                    # Distanz
                    dist_val_from_merge = row.get(f"{dist_col_in_ref}_ref", row.get(dist_col_in_ref))
                    if pd.notna(dist_val_from_merge):
                        df_loc.loc[df_loc['original_index'] == orig_idx, dist_col_in_ref] = dist_val_from_merge

                    # Höhe
                    elev_val_from_merge = row.get("Elevation (m)_ref", row.get("Elevation (m)" if "Elevation (m)" in cols_to_merge_from_ref else None))
                    if pd.notna(elev_val_from_merge):
                        df_loc.loc[df_loc['original_index'] == orig_idx, 'Elevation (m)'] = elev_val_from_merge
                
                print(f"[Info 4b] '{dist_col_in_ref}' und 'Elevation (m)' vom Original-Track verarbeitet.")
        else: # Gehört zu if not df_loc_indexed_for_merge.empty
             print("[Warnung 4b] df_loc nach dropna von original_index leer. Kein Merge möglich.")
    else: # Gehört zu if not df_full_track_ref.empty and 'original_index' in df_loc.columns:
        print("[Info 4b] Distanz und Höhe vom Original-Track konnten nicht hinzugefügt werden (Referenz leer oder original_index fehlt in df_loc).")
  
    print(f"[DEBUG 4b] df_loc Spalten vor finalem Speichern: {df_loc.columns.tolist()}", file=sys.stderr)
    # --- Finale CSV speichern (dieser Block ist jetzt auf der Hauptebene der Funktion) ---
    try:
        output_dir_final = os.path.dirname(output_surface_csv_path)
        if output_dir_final: 
            os.makedirs(output_dir_final, exist_ok=True)

        final_output_cols = [
            'Latitude', 'Longitude', 'original_index', dist_col_in_ref, 
            'Elevation (m)',
            'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID'
        ]
        
        print(f"[DEBUG 4b] Finale Output Spalten definiert: {final_output_cols}", file=sys.stderr)

        for col_name in final_output_cols:
            if col_name not in df_loc.columns:
                print(f"[DEBUG 4b] Füge fehlende Spalte hinzu: {col_name}", file=sys.stderr)
                df_loc[col_name] = pd.NA
        
        df_final_output = df_loc[final_output_cols]
        print(f"[DEBUG 4b] df_final_output erstellt mit {len(df_final_output)} Zeilen.", file=sys.stderr)
        df_final_output.to_csv(output_surface_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK] Gruppierte Oberflächendaten gespeichert: {output_surface_csv_path} ({len(df_final_output)} Zeilen)")

    except Exception as e_write: # Dieses except gehört zum try direkt darüber
        print(f"[Fehler] Konnte finale Surface-CSV nicht schreiben: {output_surface_csv_path} - {e_write}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    print(f"[DEBUG 4b] Funktion fetch_surface_data beendet.", file=sys.stderr)


# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch grouped surface data and add original track distance.")
    parser.add_argument("--input-csv", required=True, help="Path to optimized track CSV with location and original_index (output of step 4).")
    parser.add_argument("--full-track-ref-csv", required=True, help="Path to the full track CSV (e.g., 2c_...) for referencing original distance.")
    parser.add_argument("--output-csv", required=True, help="Path to save the output surface data CSV.")
    parser.add_argument("--radius", type=int, required=True, help="Query radius [m].") # Mache es required oder gib Default
    
    # Neuer Parameter für den Namen der Distanzspalte
    parser.add_argument("--dist-col-ref", required=True, help="Name of distance column in reference CSV.")
    
    args = parser.parse_args()

    # QUERY_RADIUS_M Konstante wird nicht mehr benötigt, da args.radius verwendet wird
    # DEFAULT_DIST_COL_NAME_IN_REF wird nicht mehr benötigt, da args.dist_col_ref verwendet wird

    fetch_surface_data(
        args.input_csv,
        args.full_track_ref_csv,
        args.output_csv,
        args.radius,
        args.dist_col_ref # Übergabe des geparsten Arguments
    )