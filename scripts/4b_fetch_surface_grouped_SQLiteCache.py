#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4b_fetch_surface_grouped_SQLiteCache.py
--------------------------------------
Fetches surface/tracktype data for GPS coordinates using SQLite caching.
Uses Overpass API to query OSM data with significant performance improvements.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "4b_fetch_surface_grouped_SQLiteCache.py"
SCRIPT_VERSION = "3.0.1"  # Fixed version
SCRIPT_DESCRIPTION = "SQLite-cached surface data fetching with Overpass API integration and standardized metadata"
LAST_UPDATED = "2025-06-08"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v2.0.0 (pre-2025): SQLite cache integration for performance optimization
v2.1.0 (2025-06-07): Standardized header, improved error handling and logging
v3.0.0 (2025-06-07): Implemented full standardized metadata system with processing history
v3.0.1 (2025-06-08): Fixed import issues and restored missing functionality
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "surface_analysis"
INPUT_FILE_PATTERN = "*_track_simplified.csv"
OUTPUT_FILE_PATTERN = "*_surface_data.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "requests>=2.25.0",
    "overpy>=0.6.0",
    "tqdm>=4.60.0",
    "shapely>=1.7.0"
]

import sys
import os
import argparse
import pandas as pd
import numpy as np
import requests
import overpy
import time
from tqdm import tqdm
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging
from pathlib import Path

# SQLite Cache System imports
try:
    from SQLiteSurfaceCache import SQLiteSurfaceCache, SurfaceResult
    SQLITE_CACHE_AVAILABLE = True
    print("[INFO] SQLite Cache System verfügbar.")
except ImportError:
    SQLITE_CACHE_AVAILABLE = False
    print("[WARNUNG] SQLite Cache System nicht verfügbar. Fallback-Modus aktiviert.")

# Import Metadaten-System (mit Fallback)
try:
    sys.path.append(str(Path(__file__).parent.parent / "project_management"))
    from CSV_METADATA_TEMPLATE import write_csv_with_metadata
    METADATA_SYSTEM_AVAILABLE = True
    print("[INFO] Metadaten-System verfügbar.")
except ImportError:
    METADATA_SYSTEM_AVAILABLE = False
    print("[WARNUNG] Metadaten-System nicht verfügbar. Standard CSV-Export wird verwendet.")

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

try:
    from shapely.geometry import Point, LineString
    SHAPELY_AVAILABLE = True
    print("[INFO] Shapely ist verfügbar.")
except ImportError:
    SHAPELY_AVAILABLE = False
    print("[WARNUNG] Shapely ist nicht verfügbar. Die Auswahl des nächsten Weges wird weniger präzise sein.")

# --- Konfiguration ---
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_REQUESTS = 1.1
RETRY_DELAY = 5
MAX_RETRIES = 3
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

def setup_logging(verbose: bool = False):
    """Konfiguriert Logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('surface_processing.log'),
            logging.StreamHandler()
        ]
    )

# --- Helper Funktionen ---
def infer_surface(tags: dict) -> str:
    highway = tags.get("highway")
    tracktype = tags.get("tracktype")
    
    if not highway: 
        return DEFAULT_SURFACE
    if highway == "track":
        if tracktype in ["grade1", "grade2"]: 
            return "compacted"
        elif tracktype in ["grade3", "grade4", "grade5"]: 
            return "ground"
        else: 
            return "unpaved"
    return HIGHWAY_TO_SURFACE_INFERENCE.get(highway, DEFAULT_SURFACE)

def get_way_tags(way: overpy.Way) -> dict:
    tags = way.tags
    surface = tags.get("surface")
    if surface is None:
        surface = infer_surface(tags)
    
    return {
        "surface": surface,
        "tracktype": tags.get("tracktype"),
        "highway": tags.get("highway"),
        "smoothness": tags.get("smoothness"),
        "osm_way_id": way.id
    }

def find_closest_way(ways: list[overpy.Way], point_lat: float, point_lon: float) -> Optional[overpy.Way]:
    if not ways: 
        return None
    if not SHAPELY_AVAILABLE:
        return ways[0]
    
    try:
        query_point = Point(point_lon, point_lat)
        min_dist = float('inf')
        closest_way = None
        
        for way in ways:
            if not way.nodes or len(way.nodes) < 2:
                continue
            way_coords = [(node.lon, node.lat) for node in way.nodes]
            try:
                way_line = LineString(way_coords)
                dist = way_line.distance(query_point)
                if dist < min_dist:
                    min_dist = dist
                    closest_way = way
            except Exception:
                continue
        return closest_way
    except Exception as e:
        print(f"[Warnung] Shapely Fehler in find_closest_way: {e}")
        return ways[0]

# --- Fallback Cache Klasse für den Fall, dass SQLite Cache nicht verfügbar ist ---
class FallbackCache:
    """Einfacher In-Memory Cache als Fallback"""
    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0
    
    def find_cached_surface(self, lat, lon, radius, tolerance_km=0.1):
        # Vereinfachter Cache-Lookup
        return None  # Immer Cache-Miss für Fallback
    
    def cache_surface_result(self, result):
        return None
    
    def get_cache_statistics(self):
        return {'cache_hits': self.hits, 'cache_misses': self.misses}
    
    def create_surface_track(self, **kwargs):
        return 1
    
    def add_surface_track_point(self, **kwargs):
        pass
    
    def close(self):
        pass

# --- Hauptfunktion mit SQLite Cache ---
def fetch_surface_data_with_sqlite_cache(
    input_track_loc_idx_csv: str,
    full_track_ref_csv_path: str,
    output_surface_csv_path: str,
    query_radius_m: int,
    dist_col_in_ref: str,
    cache_db_path: str = "surface_cache.db",
    cache_tolerance_km: float = 0.1,
    force_api: bool = False,
    verbose: bool = False
):
    run_start_time = datetime.now()
    
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    print_script_info()
    
    logger.info(f"Starting {SCRIPT_NAME} v{SCRIPT_VERSION}")
    logger.info(f"Surface cache database: {cache_db_path}")
    logger.info(f"Cache tolerance: {cache_tolerance_km} km")
    logger.info(f"Query radius: {query_radius_m} m")
    
    # SQLite Cache initialisieren (mit Fallback)
    if SQLITE_CACHE_AVAILABLE:
        try:
            cache = SQLiteSurfaceCache(cache_db_path)
        except Exception as e:
            logger.warning(f"SQLite Cache konnte nicht initialisiert werden: {e}")
            cache = FallbackCache()
    else:
        cache = FallbackCache()
    
    # Cache-Statistiken vor Start
    initial_stats = cache.get_cache_statistics()
    logger.info(f"Initial cache stats: {initial_stats}")
    
    print(f"[Info] Fetching grouped Surface Data for: {input_track_loc_idx_csv}")
    print(f"  Reference track for distance: {full_track_ref_csv_path}")
    print(f"  Query Radius: {query_radius_m}m")
    print(f"  Cache Database: {cache_db_path}")

    # --- Lade Input-Datei ---
    try:
        dtypes_input = {'Latitude': float, 'Longitude': float, 'original_index': 'Int64', 'Street': str, 'City': str}
        df_loc = pd.read_csv(input_track_loc_idx_csv, dtype=dtypes_input, keep_default_na=False, comment='#')

        required_cols = ["Latitude", "Longitude", "original_index", "Street", "City"]
        if not all(col in df_loc.columns for col in required_cols):
            raise ValueError(f"Input CSV fehlt Spalten. Benötigt: {required_cols}")
        
        if 'Street' in df_loc.columns:
            df_loc['Street'] = df_loc['Street'].replace('', 'StraßeUnbekanntFürBlock')
        if 'City' in df_loc.columns:
            df_loc['City'] = df_loc['City'].replace('', 'OrtUnbekanntFürBlock')

        if df_loc.empty:
            logger.warning("Input CSV ist leer.")
            empty_cols = ['Latitude', 'Longitude', 'original_index', dist_col_in_ref, 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']
            pd.DataFrame(columns=empty_cols).to_csv(output_surface_csv_path, index=False)
            return
        
        df_loc['Latitude'] = pd.to_numeric(df_loc['Latitude'], errors='coerce')
        df_loc['Longitude'] = pd.to_numeric(df_loc['Longitude'], errors='coerce')
        df_loc.dropna(subset=['Latitude', 'Longitude'], inplace=True)

        if df_loc.empty:
            logger.warning("Keine gültigen Koordinaten nach Bereinigung.")
            empty_cols = ['Latitude', 'Longitude', 'original_index', dist_col_in_ref, 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']
            pd.DataFrame(columns=empty_cols).to_csv(output_surface_csv_path, index=False)
            return

    except Exception as e:
        logger.error(f"Fehler beim Lesen der Input-CSV: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Lade Referenz-Track-Datei ---
    df_full_track_ref = pd.DataFrame()
    if full_track_ref_csv_path and os.path.exists(full_track_ref_csv_path):
        try:
            df_full_track_ref = pd.read_csv(full_track_ref_csv_path, comment='#')
            if dist_col_in_ref not in df_full_track_ref.columns:
                logger.warning(f"Spalte '{dist_col_in_ref}' nicht in Referenz-Track gefunden.")
                df_full_track_ref = pd.DataFrame()
        except Exception as e:
            logger.warning(f"Fehler beim Lesen der Referenz-Track-Datei: {e}")
            df_full_track_ref = pd.DataFrame()

    # --- Gruppiere nach Straßen/Orts-Blöcken ---
    logger.info("Gruppiere Punkte nach Straßen-/Ortsblöcken...")
    cols_for_block_id = []
    if 'Street' in df_loc.columns:
        cols_for_block_id.append('Street')
    if 'City' in df_loc.columns:
        cols_for_block_id.append('City')

    if len(cols_for_block_id) > 0:
        df_loc['temp_group_key'] = list(zip(*(df_loc[col] for col in cols_for_block_id)))
        is_new_block = df_loc['temp_group_key'].ne(df_loc['temp_group_key'].shift())
        if not df_loc.empty:
            is_new_block.iloc[0] = True 
        df_loc['block_id'] = is_new_block.cumsum()
        df_loc.drop(columns=['temp_group_key'], inplace=True)
    else:
        df_loc['block_id'] = 1

    # --- Repräsentative Punkte auswählen ---
    representative_points_data = []
    for block_id_val, group_df in df_loc.groupby('block_id'):
        if group_df.empty: 
            continue
        rep_point_series = group_df.iloc[0]
        representative_points_data.append({
            'block_id': block_id_val,
            'latitude': rep_point_series['Latitude'],
            'longitude': rep_point_series['Longitude'],
        })

    logger.info(f"{len(representative_points_data)} repräsentative Punkte für {df_loc['block_id'].nunique()} Blöcke ausgewählt.")

    # --- Surface Track in DB erstellen ---
    track_name = os.path.splitext(os.path.basename(input_track_loc_idx_csv))[0]
    track_id = cache.create_surface_track(
        filename=os.path.basename(input_track_loc_idx_csv),
        track_name=track_name,
        total_blocks=len(representative_points_data),
        query_radius_m=query_radius_m,
        script_version=SCRIPT_VERSION
    )

    # --- Surface-Abfragen mit SQLite Cache ---
    api = overpy.Overpass()
    surface_data_for_blocks = {}
    api_query_errors = 0

    logger.info("Starte Surface-Abfragen mit SQLite-Cache...")

    for point_data in tqdm(representative_points_data, desc="Surface Queries (SQLite Cache)"):
        current_block_id = point_data['block_id']
        lat_query = point_data['latitude']
        lon_query = point_data['longitude']
        surface_cache_id = None

        # Cache prüfen (außer force_api ist gesetzt)
        cached_result = None
        if not force_api:
            cached_result = cache.find_cached_surface(
                lat_query, lon_query, query_radius_m, 
                tolerance_km=cache_tolerance_km
            )

        if cached_result:
            # Cache-Hit
            surface_data_for_blocks[current_block_id] = {
                "surface": cached_result.surface,
                "tracktype": cached_result.tracktype,
                "highway": cached_result.highway,
                "smoothness": cached_result.smoothness,
                "osm_way_id": cached_result.osm_way_id
            }
            logger.debug(f"Cache hit for block {current_block_id}: {cached_result.surface}")

        else:
            # Cache-Miss - API-Call nötig
            overpass_query_str = f"""
            [out:json][timeout:{REQUEST_TIMEOUT}];
            ( way(around:{query_radius_m},{lat_query:.7f},{lon_query:.7f})["highway"~"{HIGHWAY_QUERY_FILTER_VALUE}"]; );
            out body; >; out skel qt;
            """

            query_successful = False
            for attempt_num in range(MAX_RETRIES):
                try:
                    api_result = api.query(overpass_query_str)
                    query_successful = True

                    if not api_result.ways:
                        result_dict = {"surface": DEFAULT_SURFACE, "highway": "none_found_in_radius"}
                    else:
                        selected_way = find_closest_way(api_result.ways, lat_query, lon_query)
                        if selected_way:
                            result_dict = get_way_tags(selected_way)
                        else:
                            result_dict = {"surface": DEFAULT_SURFACE, "highway": "none_selected_from_candidates"}

                    # Ergebnis im Cache speichern (wenn verfügbar)
                    if SQLITE_CACHE_AVAILABLE:
                        try:
                            surface_result = SurfaceResult(
                                latitude=lat_query,
                                longitude=lon_query,
                                surface=result_dict.get("surface", DEFAULT_SURFACE),
                                highway=result_dict.get("highway"),
                                tracktype=result_dict.get("tracktype"),
                                smoothness=result_dict.get("smoothness"),
                                osm_way_id=result_dict.get("osm_way_id"),
                                query_radius_m=query_radius_m,
                                api_provider="Overpass",
                                query_date=datetime.now().isoformat()
                            )
                            surface_cache_id = cache.cache_surface_result(surface_result)
                        except Exception as e:
                            logger.warning(f"Cache speichern fehlgeschlagen: {e}")
                    
                    surface_data_for_blocks[current_block_id] = result_dict
                    
                    logger.debug(f"API success for block {current_block_id}: {result_dict.get('surface')}")
                    
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                    break

                except overpy.exception.OverpassTooManyRequests:
                    wait = RETRY_DELAY * (attempt_num + 2)
                    logger.warning(f"Rate Limit für Block {current_block_id} (Versuch {attempt_num + 1}/{MAX_RETRIES}). Warte {wait}s...")
                    time.sleep(wait)
                except Exception as e:
                    logger.error(f"Fehler bei Block {current_block_id} (Versuch {attempt_num + 1}/{MAX_RETRIES}): {e}")
                    time.sleep(RETRY_DELAY)

            if not query_successful:
                api_query_errors += 1
                surface_data_for_blocks[current_block_id] = {"surface": DEFAULT_SURFACE, "highway": "api_query_failed"}

        # Track-Point in Datenbank speichern
        try:
            cache.add_surface_track_point(
                track_id=track_id,
                block_id=current_block_id,
                latitude=lat_query,
                longitude=lon_query,
                surface_cache_id=surface_cache_id
            )
        except Exception as e:
            logger.debug(f"Track-Point speichern fehlgeschlagen: {e}")

    # Cache-Statistiken nach Verarbeitung
    final_stats = cache.get_cache_statistics()
    logger.info(f"Final cache stats: {final_stats}")

    # --- Ergebnisse den Punkten zuweisen ---
    logger.info("Weise Surface-Werte den ursprünglichen Punkten zu...")
    for col_name in ['Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID']:
        df_loc[col_name] = pd.NA

    for block_id_val, tags_dict in surface_data_for_blocks.items():
        block_mask = df_loc['block_id'] == block_id_val
        df_loc.loc[block_mask, 'Surface'] = tags_dict.get('surface', DEFAULT_SURFACE)
        df_loc.loc[block_mask, 'Tracktype'] = tags_dict.get('tracktype')
        df_loc.loc[block_mask, 'Highway'] = tags_dict.get('highway')
        df_loc.loc[block_mask, 'Smoothness'] = tags_dict.get('smoothness')
        df_loc.loc[block_mask, 'OSM_Way_ID'] = tags_dict.get('osm_way_id')

    df_loc['Surface'].fillna(DEFAULT_SURFACE, inplace=True)

    # --- Distanz vom Original-Track hinzufügen ---
    logger.info("Beginne Hinzufügen von Distanz/Höhe...")
    df_loc[dist_col_in_ref] = pd.NA
    df_loc['Elevation (m)'] = pd.NA

    if not df_full_track_ref.empty and 'original_index' in df_loc.columns:
        df_loc_indexed_for_merge = df_loc.dropna(subset=['original_index']).copy()
        if not df_loc_indexed_for_merge.empty:
            df_loc_indexed_for_merge['original_index'] = df_loc_indexed_for_merge['original_index'].astype(int)

            cols_to_merge_from_ref = []
            if dist_col_in_ref in df_full_track_ref.columns:
                cols_to_merge_from_ref.append(dist_col_in_ref)
            if 'Elevation (m)' in df_full_track_ref.columns:
                cols_to_merge_from_ref.append('Elevation (m)')

            if cols_to_merge_from_ref:
                df_ref_for_merge = df_full_track_ref[cols_to_merge_from_ref].copy()
                df_ref_for_merge['original_index'] = df_full_track_ref.index

                merged_df = pd.merge(
                    df_loc_indexed_for_merge,
                    df_ref_for_merge,
                    on='original_index',
                    how='left',
                    suffixes=('', '_ref')
                )

                # Iteriere über merged_df und aktualisiere df_loc
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
                
                logger.info("Distanz und Höhe vom Original-Track verarbeitet.")

    # --- Finale CSV mit vollständigen Metadaten speichern ---
    try:
        output_dir_final = os.path.dirname(output_surface_csv_path)
        if output_dir_final: 
            os.makedirs(output_dir_final, exist_ok=True)

        final_output_cols = [
            'Latitude', 'Longitude', 'original_index', dist_col_in_ref, 
            'Elevation (m)', 'Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness', 'OSM_Way_ID'
        ]

        for col_name in final_output_cols:
            if col_name not in df_loc.columns:
                df_loc[col_name] = pd.NA
        
        df_final_output = df_loc[final_output_cols]
        
        # Verwende Metadaten-System wenn verfügbar, sonst Standard-CSV
        if METADATA_SYSTEM_AVAILABLE:
            # Sammle Metadaten für standardisierten Header
            processing_parameters = {
                'query_radius_m': query_radius_m,
                'cache_tolerance_km': cache_tolerance_km,
                'force_api': force_api,
                'total_blocks_processed': len(representative_points_data),
                'highway_filter': HIGHWAY_QUERY_FILTER_VALUE,
                'request_timeout': REQUEST_TIMEOUT,
                'max_retries': MAX_RETRIES,
                'default_surface': DEFAULT_SURFACE
            }
            
            # API-Metadaten zusammenstellen
            api_metadata_clean = {
                'provider': 'Overpass API',
                'endpoint': OVERPASS_API_URL,
                'data_source': 'OpenStreetMap',
                'total_api_calls': final_stats.get('cache_misses', 0),
                'cache_hits': final_stats.get('cache_hits', 0),
                'api_errors': api_query_errors,
                'success_rate': f"{((final_stats.get('cache_misses', 0) - api_query_errors) / max(final_stats.get('cache_misses', 1), 1) * 100):.1f}%",
                'cache_hit_rate': f"{(final_stats.get('cache_hits', 0) / max((final_stats.get('cache_hits', 0) + final_stats.get('cache_misses', 0)), 1) * 100):.1f}%"
            }
            
            additional_metadata = {
                'cache_database': cache_db_path,
                'processing_duration_seconds': (datetime.now() - run_start_time).total_seconds(),
                'track_blocks_count': df_loc['block_id'].nunique(),
                'surface_types_found': df_final_output['Surface'].nunique(),
                'data_quality': 'high' if api_query_errors == 0 else 'medium',
                'shapely_available': SHAPELY_AVAILABLE,
                'sqlite_cache_available': SQLITE_CACHE_AVAILABLE
            }
            
            # Input-Dateien auflisten
            input_files = [input_track_loc_idx_csv]
            if full_track_ref_csv_path and os.path.exists(full_track_ref_csv_path):
                input_files.append(full_track_ref_csv_path)
            
            # CSV mit vollständigen Metadaten schreiben
            try:
                write_csv_with_metadata(
                    dataframe=df_final_output,
                    output_path=output_surface_csv_path,
                    script_name=SCRIPT_NAME,
                    script_version=SCRIPT_VERSION,
                    input_files=input_files,
                    processing_parameters=processing_parameters,
                    api_metadata=api_metadata_clean,
                    additional_metadata=additional_metadata,
                    float_format='%.6f'
                )
            except Exception as e:
                logger.warning(f"Metadaten-Export fehlgeschlagen: {e}. Verwende Standard-CSV.")
                df_final_output.to_csv(output_surface_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        else:
            # Standard CSV-Export ohne Metadaten
            df_final_output.to_csv(output_surface_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        
        logger.info(f"Surface-Daten gespeichert: {output_surface_csv_path} ({len(df_final_output)} Zeilen)")

        # Track-Metadaten aktualisieren (wenn SQLite verfügbar)
        if SQLITE_CACHE_AVAILABLE:
            try:
                cache.connection.execute("""
                    UPDATE gpx_surface_tracks SET 
                    cached_blocks = ?, api_calls = ? 
                    WHERE id = ?
                """, (
                    final_stats.get('cache_hits', 0), 
                    final_stats.get('cache_misses', 0), 
                    track_id
                ))
                cache.connection.commit()
            except Exception as e:
                logger.debug(f"Track-Metadaten Update fehlgeschlagen: {e}")

    except Exception as e:
        logger.error(f"Fehler beim Schreiben der Output-CSV: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    run_end_time = datetime.now()
    duration = run_end_time - run_start_time
    
    # Zusammenfassung
    print(f"\n{'='*60}")
    print(f"SURFACE DATA PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f"Script: {SCRIPT_NAME} v{SCRIPT_VERSION}")
    print(f"Duration: {duration}")
    print(f"Total blocks processed: {len(representative_points_data)}")
    print(f"Cache hits: {final_stats.get('cache_hits', 0)}")
    print(f"Cache misses (API calls): {final_stats.get('cache_misses', 0)}")
    if (final_stats.get('cache_hits', 0) + final_stats.get('cache_misses', 0)) > 0:
        hit_rate = final_stats.get('cache_hits', 0) / (final_stats.get('cache_hits', 0) + final_stats.get('cache_misses', 0)) * 100
        print(f"Cache hit rate: {hit_rate:.1f}%")
    print(f"API errors: {api_query_errors}")
    print(f"SQLite database: {cache_db_path}")
    print(f"Output CSV: {output_surface_csv_path}")
    print(f"{'='*60}")
    
    logger.info(f"Script finished. Duration: {duration}")
    
    # Cache schließen
    cache.close()


# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch grouped surface data with SQLite caching.")
    parser.add_argument("--input-csv", required=True, help="Path to optimized track CSV with location and original_index.")
    parser.add_argument("--full-track-ref-csv", required=True, help="Path to the full track CSV for referencing original distance.")
    parser.add_argument("--output-csv", required=True, help="Path to save the output surface data CSV.")
    parser.add_argument("--radius", type=int, required=True, help="Query radius [m].")
    parser.add_argument("--dist-col-ref", required=True, help="Name of distance column in reference CSV.")
    parser.add_argument("--cache-db", default="surface_cache.db", help="Path to SQLite cache database.")
    parser.add_argument("--cache-tolerance", type=float, default=0.1, help="Cache search tolerance in km.")
    parser.add_argument("--force-api", action="store_true", help="Force API calls, ignore cache.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    
    args = parser.parse_args()

    fetch_surface_data_with_sqlite_cache(
        args.input_csv,
        args.full_track_ref_csv,
        args.output_csv,
        args.radius,
        args.dist_col_ref,
        args.cache_db,
        args.cache_tolerance,
        args.force_api,
        args.verbose
    )