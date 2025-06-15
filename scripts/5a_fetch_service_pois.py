#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5a_fetch_service_pois.py
------------------------
Fetches service-related Points of Interest (shops, drinking water, etc.)
from the Overpass API based on points from a simplified track CSV.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "5a_fetch_service_pois.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Service POI fetching from Overpass API with sampling, error handling and standardized metadata"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic POI fetching functionality
v1.1.0 (2025-06-07): Standardized header, improved error handling and elevation parsing
v2.0.0 (2025-06-07): Implemented full standardized metadata system with processing history
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "service_pois"
INPUT_FILE_PATTERN = "*_track_simplified.csv"
OUTPUT_FILE_PATTERN = "*_service_pois.csv"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "overpy>=0.6.0",
    "tqdm>=4.60.0",
    "geopy>=2.2.0"
]

import sys
import os
import argparse
import pandas as pd
import overpy
from tqdm import tqdm
import time
from datetime import datetime
from pathlib import Path
from geopy.distance import geodesic # For sampling distance calculation

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def fetch_service_pois(input_csv_path: str, output_csv_path: str, radius_m: int, sampling_km: float):
    """Fetches service POIs using Overpass API."""
    run_start_time = datetime.now()
    print(f"[{run_start_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} started.")
    print(f"[Info] Fetching Service POIs for: {input_csv_path}")
    print(f"[Info] Using radius: {radius_m}m, sampling: {sampling_km}km")
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        df = pd.read_csv(input_csv_path, comment='#')
        if not all(col in df.columns for col in ["Latitude", "Longitude"]):
             raise ValueError("Input CSV must contain 'Latitude' and 'Longitude' columns.")
        if df.empty:
             print("[Warnung] Input CSV ist leer. Es werden keine POIs gesucht.")
             # Create empty output file
             pd.DataFrame(columns=["Name", "Typ", "Adresse", "Latitude", "Longitude"]).to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere Service POI CSV gespeichert: {output_csv_path}")
             return

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # Metadaten sammeln
    api_metadata = {
        "api_provider": "Overpass API (OpenStreetMap data)",
        "api_endpoint": "https://overpass-api.de/api/interpreter",
        "api_query_start_time": None,
        "api_query_end_time": None,
        "api_total_queries_attempted": 0,
        "api_successful_queries": 0,
        "api_failed_queries_after_retries": 0,
        "poi_types_searched": ["supermarket", "bicycle", "bakery", "drinking_water", "restaurant", "cafe"]
    }

    api = overpy.Overpass()
    poi_list = []
    last_query_coord = None
    processed_points_count = 0

    print(f"[Info] Searching with radius {radius_m}m, sampling every {sampling_km}km...")
    api_metadata["api_query_start_time"] = datetime.now().isoformat()

    # Define the Overpass query for service POIs
    service_query_template = """
    [out:json][timeout:60];
    (
      node(around:{radius_val},{lat_val},{lon_val})["shop"="supermarket"];
      node(around:{radius_val},{lat_val},{lon_val})["shop"="bicycle"];
      node(around:{radius_val},{lat_val},{lon_val})["shop"="bakery"];
      node(around:{radius_val},{lat_val},{lon_val})["amenity"="drinking_water"];
      node(around:{radius_val},{lat_val},{lon_val})["amenity"="restaurant"];
      node(around:{radius_val},{lat_val},{lon_val})["amenity"="cafe"];
    );
    out body;
    >;
    out skel qt;
    """

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Service POI Query"):
        lat = row["Latitude"]
        lon = row["Longitude"]
        current_coord = (lat, lon)

        # Check sampling distance
        do_query = False
        if last_query_coord is None:
            do_query = True
        else:
            distance = geodesic(last_query_coord, current_coord).kilometers
            if distance >= sampling_km:
                do_query = True

        if do_query:
            processed_points_count += 1
            api_metadata["api_total_queries_attempted"] += 1
            # --- KORREKTUR: Query HIER formatieren ---
            query = service_query_template.format(radius_val=radius_m, lat_val=lat, lon_val=lon)
            # ------------------------------------------

            attempts = 0
            max_attempts = 3
            success = False
            while attempts < max_attempts and not success:
                try:
                    # print(f"DEBUG Query:\n{query}") # Optional Debug
                    result = api.query(query) # Verwende die formatierte Query
                    success = True
                    api_metadata["api_successful_queries"] += 1

                    for node in result.nodes:
                        tags = node.tags
                        poi_type = tags.get('amenity', tags.get('shop', 'Unbekannt'))
                        poi_name = tags.get('name', poi_type.capitalize()) # Default name to type

                        # Construct address
                        street = tags.get('addr:street', '')
                        housenumber = tags.get('addr:housenumber', '')
                        postcode = tags.get('addr:postcode', '')
                        city = tags.get('addr:city', tags.get('addr:town', tags.get('addr:village', '')))
                        address_parts = [p for p in [street, housenumber, postcode, city] if p]
                        full_address = ", ".join(address_parts) if address_parts else "Adresse unbekannt"
                        
                        elevation_str = tags.get('ele')
                        elevation_val = None
                        if elevation_str is not None:
                            try:
                                elevation_val = float(elevation_str)
                            except ValueError:
                                print(f"[Warnung 5a] Ungültiger Höhenwert '{elevation_str}' für POI '{poi_name}'.", file=sys.stderr)
                                elevation_val = None # Oder pd.NA, aber None ist einfacher für pd.DataFrame

                        poi_list.append({
                            "Name": poi_name,
                            "Typ": poi_type,
                            "Adresse": full_address,
                            "Latitude": float(node.lat),
                            "Longitude": float(node.lon),
                            "Elevation_OSM": elevation_val                            
                        })

                    last_query_coord = current_coord
                    time.sleep(1) # Be nice to the API

                except overpy.exception.OverpassTooManyRequests:
                    wait_time = 5 * (attempts + 1)
                    print(f" Rate Limit erreicht bei Punkt {idx}. Warte {wait_time}s...")
                    time.sleep(wait_time)
                    attempts += 1
                except overpy.exception.OverpassGatewayTimeout:
                     wait_time = 5 * (attempts + 1)
                     print(f" Gateway Timeout bei Punkt {idx}. Warte {wait_time}s...")
                     time.sleep(wait_time)
                     attempts += 1
                except Exception as e:
                    print(f" Fehler bei Overpass Query (Punkt {idx}): {e}")
                    attempts += 1 # Count as attempt even on other errors
                    time.sleep(2) # Short sleep on other errors

            if not success:
                 api_metadata["api_failed_queries_after_retries"] += 1
                 print(f" Konnte Daten für Punkt {idx} nach {max_attempts} Versuchen nicht abrufen.")


    api_metadata["api_query_end_time"] = datetime.now().isoformat()

    # Create DataFrame, drop duplicates, and save with metadata
    if poi_list:
        pois_df = pd.DataFrame(poi_list)
        pois_df = pois_df.drop_duplicates(subset=["Latitude", "Longitude"])
        # Stelle sicher, dass die Spalte existiert, auch wenn alle Werte None sind
        if 'Elevation_OSM' not in pois_df.columns:
            pois_df['Elevation_OSM'] = None # Oder pd.NA
    else:
        print("\n[Info] Keine Service POIs gefunden.")
        # Create empty DataFrame with correct columns
        pois_df = pd.DataFrame(columns=["Name", "Typ", "Adresse", "Latitude", "Longitude", "Elevation_OSM"])

    # Prepare metadata for CSV
    processing_parameters = {
        'search_radius_m': radius_m,
        'sampling_distance_km': sampling_km,
        'total_track_points_processed': len(df),
        'sampled_query_points': processed_points_count,
        'max_retries_per_query': 3,
        'request_timeout_s': 60
    }
    
    additional_metadata = {
        'processing_duration_seconds': (datetime.now() - run_start_time).total_seconds(),
        'unique_pois_found': len(pois_df),
        'poi_types_found': list(pois_df['Typ'].unique()) if not pois_df.empty else [],
        'data_quality': 'high' if api_metadata['api_failed_queries_after_retries'] == 0 else 'medium'
    }
    
    try:
        # Save with full metadata
        write_csv_with_metadata(
            dataframe=pois_df,
            output_path=output_csv_path,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_csv_path],
            processing_parameters=processing_parameters,
            api_metadata=api_metadata,
            additional_metadata=additional_metadata,
            float_format='%.6f'
        )
        
        print(f"[OK] Service POI CSV mit Metadaten gespeichert: {output_csv_path} ({len(pois_df)} POIs)")
        
    except Exception as e:
        print(f"[Fehler] Konnte CSV mit Metadaten nicht schreiben: {output_csv_path} - {e}")
        # Fallback: einfache CSV
        pois_df.to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Fallback CSV gespeichert: {output_csv_path}")
        
    run_end_time = datetime.now()
    print(f"[{run_end_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} finished. Duration: {run_end_time - run_start_time}")
    
    # Performance summary
    if processed_points_count > 0:
        success_rate = (api_metadata['api_successful_queries'] / api_metadata['api_total_queries_attempted']) * 100
        print(f"[Summary] API Success Rate: {success_rate:.1f}% ({api_metadata['api_successful_queries']}/{api_metadata['api_total_queries_attempted']})")
        print(f"[Summary] POIs per Query: {len(pois_df) / processed_points_count:.1f} average")


if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Fetch service-related POIs along a simplified GPX track.")
    parser.add_argument("--input", required=True, help="Path to the input simplified track CSV file (needs Latitude, Longitude).")
    parser.add_argument("--output", required=True, help="Path to save the raw service POIs CSV file.")
    parser.add_argument("--radius", type=int, default=500, help="Search radius around track points in meters.")
    parser.add_argument("--sampling", type=float, default=0.5, help="Minimum distance [km] between query points along the track.")
    args = parser.parse_args()

    fetch_service_pois(args.input, args.output, args.radius, args.sampling)