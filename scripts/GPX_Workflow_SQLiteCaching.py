#!/usr/bin/env python3
"""
SQLite-basiertes Geocoding Cache System
Ersetzt das ursprüngliche 4_reverse_geocode.py mit SQLite-Cache
"""

SCRIPT_NAME = "GPX_Workflow_SQLiteCaching.py"
SCRIPT_VERSION = "1.0.0"  # Korrigierte Version für echten Workflow

import sys
import os
import pandas as pd
from geopy.geocoders import Nominatim
from tqdm import tqdm
from time import sleep
from geopy.distance import geodesic
import argparse
from datetime import datetime
import logging

# SQLite Cache System imports
import sqlite3
import json
import hashlib
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path
from SQLiteGeocodingCache import SQLiteGeocodingCache


@dataclass
class GeocodingResult:
    """Datenklasse für Geocoding-Ergebnisse"""
    latitude: float
    longitude: float
    street: str
    city: str
    postal_code: str
    country: Optional[str] = None
    raw_address: Optional[Dict] = None
    api_provider: str = "Nominatim"
    query_date: Optional[str] = None


def setup_logging(verbose: bool = False):
    """Konfiguriert Logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('geocoding.log'),
            logging.StreamHandler()
        ]
    )


def main():
    run_start_time = datetime.now()
    
    parser = argparse.ArgumentParser(description="Reverse geocode coordinates with SQLite caching.")
    parser.add_argument("--input-csv", required=True, help="Path to the input simplified track CSV.")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV with location data.")
    parser.add_argument("--sampling-dist", type=float, default=0.5, help="Min distance [km] between geocoding queries.")
    parser.add_argument("--cache-db", default="geocoding_cache.db", help="Path to SQLite cache database.")
    parser.add_argument("--cache-tolerance", type=float, default=0.1, help="Cache search tolerance in km.")
    parser.add_argument("--force-api", action="store_true", help="Force API calls, ignore cache.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    input_csv_path = args.input_csv
    output_csv_path = args.output_csv
    sampling_distance_km = args.sampling_dist
    cache_db_path = args.cache_db
    cache_tolerance_km = args.cache_tolerance
    force_api = args.force_api

    logger.info(f"Starting {SCRIPT_NAME} v{SCRIPT_VERSION}")
    logger.info(f"Cache database: {cache_db_path}")
    logger.info(f"Cache tolerance: {cache_tolerance_km} km")
    logger.info(f"Sampling distance: {sampling_distance_km} km")

    # SQLite Cache initialisieren
    cache = SQLiteGeocodingCache(cache_db_path)
    
    # Metadaten sammeln
    metadata_lines = [
        f"# Processed by: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Processing Timestamp: {run_start_time.isoformat()}",
        f"# Input CSV: {os.path.basename(input_csv_path)}",
        f"# Sampling Distance: {sampling_distance_km} km",
        f"# Cache Database: {cache_db_path}",
        f"# Cache Tolerance: {cache_tolerance_km} km",
    ]

    # Cache-Statistiken vor Start
    initial_stats = cache.get_cache_statistics()
    logger.info(f"Initial cache stats: {initial_stats}")

    # API-Metadaten
    api_metadata = {
        "api_provider": "Nominatim (OpenStreetMap data)",
        "api_query_start_time": None,
        "api_query_end_time": None,
        "api_total_queries_attempted": 0,
        "api_successful_queries": 0,
        "api_failed_queries_after_retries": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "user_agent_for_api": "gpx_workflow_v2_sqlite"
    }

    # Ausgabeverzeichnis erstellen
    output_dir = os.path.dirname(output_csv_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Geolocator initialisieren
    geolocator = Nominatim(user_agent="gpx_workflow_v2_sqlite", timeout=10)

    # Input-Daten laden
    try:
        df = pd.read_csv(input_csv_path)
        if df.empty:
            logger.warning(f"Input CSV is empty: {input_csv_path}")
            empty_cols = ['Latitude', 'Longitude', 'original_index', 'Street', 'City', 'PostalCode']
            pd.DataFrame(columns=empty_cols).to_csv(output_csv_path, index=False, encoding='utf-8')
            logger.info(f"Empty output CSV saved: {output_csv_path}")
            return
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading input CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # Spalten prüfen
    required_columns = ["Latitude", "Longitude", "original_index"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing columns in {input_csv_path}: {', '.join(missing_columns)}")
        sys.exit(1)

    # original_index konvertieren
    if 'original_index' in df.columns:
        df['original_index'] = pd.to_numeric(df['original_index'], errors='coerce').astype('Int64')

    # GPX Track im Cache erstellen
    track_name = os.path.splitext(os.path.basename(input_csv_path))[0]
    track_id = cache.create_gpx_track(
        filename=os.path.basename(input_csv_path),
        track_name=track_name,
        total_points=len(df),
        sampling_distance=sampling_distance_km,
        script_version=SCRIPT_VERSION
    )

    # Listen für neue Spalten
    streets = []
    cities = []
    postal_codes = []

    last_geocoded_coord = None
    last_street = 'Unbekannte Straße'
    last_city = 'Unbekannter Ort'
    last_postal = 'Keine PLZ'

    api_metadata["api_query_start_time"] = datetime.now().isoformat()

    print(f"\nStarte Reverse Geocoding mit SQLite-Cache (Sampling: >= {sampling_distance_km} km)...")

    # Hauptschleife
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Geokodierung", unit="Punkt"):
        current_coord = (row['Latitude'], row['Longitude'])
        do_geocode = True

        # Sampling-Distanz prüfen
        if last_geocoded_coord is not None:
            try:
                dist = geodesic(last_geocoded_coord, current_coord).kilometers
                if dist < sampling_distance_km:
                    do_geocode = False
            except ValueError:
                logger.warning(f"Invalid coordinates at index {idx}: {current_coord}")
                do_geocode = True

        current_street_val = last_street
        current_city_val = last_city
        current_postal_val = last_postal
        geocoding_cache_id = None

        if do_geocode:
            # Erst im Cache suchen (außer force_api ist gesetzt)
            cached_result = None
            if not force_api:
                cached_result = cache.find_cached_geocoding(
                    current_coord[0], current_coord[1], 
                    tolerance_km=cache_tolerance_km
                )

            if cached_result:
                # Cache-Hit
                api_metadata["cache_hits"] += 1
                current_street_val = cached_result.street
                current_city_val = cached_result.city
                current_postal_val = cached_result.postal_code
                
                # Bei Cache-Hit: Keine neue DB-Referenz nötig
                geocoding_cache_id = None
                
                logger.debug(f"Cache hit for {current_coord}: {cached_result.city}")
                
                last_street = current_street_val
                last_city = current_city_val
                last_postal = current_postal_val
                last_geocoded_coord = current_coord

            else:
                # Cache-Miss - API-Call nötig
                api_metadata["cache_misses"] += 1
                api_metadata["api_total_queries_attempted"] += 1
                
                attempts = 0
                max_attempts = 3
                success = False
                
                while attempts < max_attempts and not success:
                    try:
                        location = geolocator.reverse(current_coord, language='de', timeout=15)
                        success = True
                        api_metadata["api_successful_queries"] += 1

                        if location and location.raw and 'address' in location.raw:
                            address = location.raw['address']
                            city_options = [
                                address.get('city'), address.get('town'),
                                address.get('village'), address.get('hamlet'),
                                address.get('suburb'), address.get('county')
                            ]
                            current_city_val = next((c for c in city_options if c), 'Unbekannter Ort')
                            current_street_val = address.get('road', 'Unbekannte Straße')
                            current_postal_val = address.get('postcode', 'Keine PLZ')

                            # Ergebnis im Cache speichern
                            result = GeocodingResult(
                                latitude=current_coord[0],
                                longitude=current_coord[1],
                                street=current_street_val,
                                city=current_city_val,
                                postal_code=current_postal_val,
                                country=address.get('country'),
                                raw_address=address,
                                api_provider="Nominatim",
                                query_date=datetime.now().isoformat()
                            )
                            geocoding_cache_id = cache.cache_geocoding_result(result)

                            last_street = current_street_val
                            last_city = current_city_val
                            last_postal = current_postal_val
                            last_geocoded_coord = current_coord
                            
                            logger.debug(f"API success for {current_coord}: {current_city_val}")
                        else:
                            logger.info(f"No address found for {current_coord}")

                        sleep(1.1)  # Nominatim Rate Limit

                    except Exception as e:
                        attempts += 1
                        wait_time = 2 * attempts
                        logger.error(f"Geocoding error for {current_coord} (attempt {attempts}/{max_attempts}): {e}")
                        if attempts < max_attempts:
                            logger.info(f"Waiting {wait_time}s before retry...")
                            sleep(wait_time)
                        else:
                            api_metadata["api_failed_queries_after_retries"] += 1
                            logger.error(f"Geocoding failed after {max_attempts} attempts for {current_coord}")

        # Track-Point in Datenbank speichern
        cache.add_track_point(
            track_id=track_id,
            latitude=current_coord[0],
            longitude=current_coord[1],
            original_index=row.get('original_index'),
            geocoding_cache_id=geocoding_cache_id
        )

        # Listen für CSV-Output füllen
        streets.append(current_street_val)
        cities.append(current_city_val)
        postal_codes.append(current_postal_val)

    api_metadata["api_query_end_time"] = datetime.now().isoformat()

    # Cache-Statistiken nach Verarbeitung
    final_stats = cache.get_cache_statistics()
    logger.info(f"Final cache stats: {final_stats}")

    # Metadaten ergänzen
    if api_metadata["api_total_queries_attempted"] > 0:
        metadata_lines.append("# API_USED: YES (Nominatim)")
        for key, value in api_metadata.items():
            if value is not None:
                metadata_lines.append(f"# API_METADATA_{key.upper()}: {value}")
    else:
        metadata_lines.append("# API_USED: NO (Only cache hits)")

    metadata_lines.append(f"# CACHE_HITS: {api_metadata['cache_hits']}")
    metadata_lines.append(f"# CACHE_MISSES: {api_metadata['cache_misses']}")
    metadata_lines.append(f"# CACHE_HIT_RATE: {api_metadata['cache_hits'] / (api_metadata['cache_hits'] + api_metadata['cache_misses']) * 100:.1f}%" if (api_metadata['cache_hits'] + api_metadata['cache_misses']) > 0 else "# CACHE_HIT_RATE: N/A")

    # DataFrame für CSV-Output erweitern
    df["Street"] = streets
    df["City"] = cities
    df["PostalCode"] = postal_codes

    # Finalen DataFrame vorbereiten
    final_output_columns = ['Latitude', 'Longitude', 'original_index', 'Street', 'City', 'PostalCode']
    df_to_save = df[[col for col in final_output_columns if col in df.columns]]

    # CSV-Output schreiben
    try:
        # Metadaten-Header schreiben
        with open(output_csv_path, 'w', encoding='utf-8') as f:
            for line in metadata_lines:
                f.write(line + "\n")
        
        # DataFrame anhängen
        df_to_save.to_csv(output_csv_path, mode='a', index=False, encoding='utf-8', 
                         float_format='%.6f', header=True)
        
        logger.info(f"Reverse Geocoding completed. Output saved: {output_csv_path}")
        
        # Track-Metadaten aktualisieren
        cache.connection.execute("""
            UPDATE gpx_tracks SET geocoded_points = ? WHERE id = ?
        """, (api_metadata['cache_hits'] + api_metadata['api_successful_queries'], track_id))
        cache.connection.commit()
        
    except Exception as e:
        logger.error(f"Could not write output CSV: {output_csv_path} - {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    run_end_time = datetime.now()
    duration = run_end_time - run_start_time
    
    # Zusammenfassung
    print(f"\n{'='*60}")
    print(f"GEOCODING SUMMARY")
    print(f"{'='*60}")
    print(f"Script: {SCRIPT_NAME} v{SCRIPT_VERSION}")
    print(f"Duration: {duration}")
    print(f"Total points processed: {len(df)}")
    print(f"Cache hits: {api_metadata['cache_hits']}")
    print(f"Cache misses (API calls): {api_metadata['cache_misses']}")
    print(f"API success rate: {api_metadata['api_successful_queries']}/{api_metadata['api_total_queries_attempted']}")
    if (api_metadata['cache_hits'] + api_metadata['cache_misses']) > 0:
        hit_rate = api_metadata['cache_hits'] / (api_metadata['cache_hits'] + api_metadata['cache_misses']) * 100
        print(f"Cache hit rate: {hit_rate:.1f}%")
    print(f"SQLite database: {cache_db_path}")
    print(f"Output CSV: {output_csv_path}")
    print(f"{'='*60}")
    
    logger.info(f"Script finished. Duration: {duration}")
    
    # Cache schließen
    cache.close()


if __name__ == "__main__":
    main()