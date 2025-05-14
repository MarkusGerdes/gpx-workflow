#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5a_fetch_service_pois.py
------------------------
Fetches service-related Points of Interest (shops, drinking water, etc.)
from the Overpass API based on points from a simplified track CSV.
"""

import sys
import os
import argparse
import pandas as pd
import overpy
from tqdm import tqdm
import time
from geopy.distance import geodesic # For sampling distance calculation

def fetch_service_pois(input_csv_path: str, output_csv_path: str, radius_m: int, sampling_km: float):
    """Fetches service POIs using Overpass API."""
    print(f"[Info] Fetching Service POIs for: {input_csv_path}")
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        df = pd.read_csv(input_csv_path)
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

    api = overpy.Overpass()
    poi_list = []
    last_query_coord = None
    processed_points_count = 0

    print(f"[Info] Searching with radius {radius_m}m, sampling every {sampling_km}km...")

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

                        poi_list.append({
                            "Name": poi_name,
                            "Typ": poi_type,
                            "Adresse": full_address,
                            "Latitude": float(node.lat),
                            "Longitude": float(node.lon)
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
                 print(f" Konnte Daten für Punkt {idx} nach {max_attempts} Versuchen nicht abrufen.")


    # Create DataFrame, drop duplicates, and save
    if poi_list:
        pois_df = pd.DataFrame(poi_list)
        pois_df = pois_df.drop_duplicates(subset=["Latitude", "Longitude"]) # Basic duplicate check
        pois_df.to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"\n[OK] {len(pois_df)} eindeutige Service POIs gefunden (von {processed_points_count} abgefragten Punkten) und gespeichert: {output_csv_path}")
    else:
        print("\n[Info] Keine Service POIs gefunden.")
        # Save empty file
        pd.DataFrame(columns=["Name", "Typ", "Adresse", "Latitude", "Longitude"]).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Leere Service POI CSV gespeichert: {output_csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch service-related POIs along a simplified GPX track.")
    parser.add_argument("--input", required=True, help="Path to the input simplified track CSV file (needs Latitude, Longitude).")
    parser.add_argument("--output", required=True, help="Path to save the raw service POIs CSV file.")
    parser.add_argument("--radius", type=int, default=500, help="Search radius around track points in meters.")
    parser.add_argument("--sampling", type=float, default=0.5, help="Minimum distance [km] between query points along the track.")
    args = parser.parse_args()

    fetch_service_pois(args.input, args.output, args.radius, args.sampling)