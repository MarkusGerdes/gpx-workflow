# --- START OF FILE 4_reverse_geocode.py ---

SCRIPT_NAME = "4_reverse_geocode.py"
SCRIPT_VERSION = "1.1.3" # Einführung einer Versionskontrolle, lauffaehiges Script, Meta Daten

import sys
import os
import pandas as pd
from geopy.geocoders import Nominatim
from tqdm import tqdm
from time import sleep
from geopy.distance import geodesic
import argparse
from datetime import datetime

def main():
    run_start_time = datetime.now()
    
    parser = argparse.ArgumentParser(description="Reverse geocode coordinates from a simplified track CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to the input simplified track CSV (Lat/Lon/original_index from 2b).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV with location data.")
    parser.add_argument("--sampling-dist", type=float, default=0.5, help="Min distance [km] between geocoding queries.")
    args = parser.parse_args()
    input_csv_path = args.input_csv # Umbenannt für Klarheit innerhalb der Funktion
    output_csv_path = args.output_csv # Umbenannt für Klarheit
    sampling_distance_km = args.sampling_dist

    # Metadaten-Sammlung
    metadata_lines = [
        f"# Processed by: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Processing Timestamp: {run_start_time.isoformat()}",
        f"# Input CSV: {os.path.basename(input_csv_path)}",
        f"# Sampling Distance: {sampling_distance_km} km",
    ]
    api_metadata = {
        "api_provider": "Nominatim (OpenStreetMap data)",
        "api_endpoint_used_implicitly_by_geopy": "https://nominatim.openstreetmap.org/reverse (oder ähnlich)",
        "api_query_start_time": None,
        "api_query_end_time": None,
        "api_total_queries_attempted": 0, # Gesamtzahl der Punkte, für die ein Geocoding versucht wurde
        "api_successful_queries": 0,
        "api_failed_queries_after_retries": 0,
        "api_data_source_info": "OpenStreetMap data. OSM data is typically a few minutes to hours behind the live database. Check Nominatim status for details.",
        "user_agent_for_api": "gpx_workflow_v2_4" # Wie im Skript verwendet
    }

    # Sicherstellen, dass das Ausgabeverzeichnis existiert
    output_dir = os.path.dirname(output_csv_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Geolocator initialisieren
    geolocator = Nominatim(user_agent="gpx_workflow_v2_4", timeout=10) # Eindeutiger User-Agent

    # --- Input-Daten laden ---
    try:
        df = pd.read_csv(input_csv_path)
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            cols_out_empty = ['Latitude', 'Longitude', 'original_index', 'Street', 'City', 'PostalCode']
            pd.DataFrame(columns=cols_out_empty).to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere Output-CSV gespeichert: {output_csv_path}")
            sys.exit(0) # Sauberes Beenden
    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # Spalten prüfen
    required_columns = ["Latitude", "Longitude", "original_index"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Fehler: Fehlende Spalten in {input_csv_path}: {', '.join(missing_columns)}")
        sys.exit(1)

    # Konvertiere 'original_index' zu Integer (nullable integer)
    if 'original_index' in df.columns:
        df['original_index'] = pd.to_numeric(df['original_index'], errors='coerce').astype('Int64')

    # Listen für neue Spalten vorbereiten
    streets = []
    cities = []
    postal_codes = []

    last_geocoded_coord = None
    print(f"\nStarte Reverse Geocoding (Sampling: >= {sampling_distance_km} km)...")

    last_street = 'Unbekannte Straße' # Fallback-Werte
    last_city = 'Unbekannter Ort'
    last_postal = 'Keine PLZ'

    # ... (vor der Geocoding-Schleife)
    actual_api_queries_made = 0 # Zähler initialisieren
    successful_api_queries = 0
    failed_api_queries_after_retries = 0
    
    api_metadata["api_query_start_time"] = datetime.now().isoformat() # Startzeit hier setzen    

    # --- Geocoding-Schleife ---
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Geokodierung", unit="Punkt"):
        current_coord = (row['Latitude'], row['Longitude'])
        do_geocode = True
        # dist = 0.0 # Nicht unbedingt nötig hier zu initialisieren

        if last_geocoded_coord is not None:
            try:
                dist = geodesic(last_geocoded_coord, current_coord).kilometers
                if dist < sampling_distance_km:
                    do_geocode = False
            except ValueError: # Kann bei ungültigen Koordinaten auftreten
                print(f"[Warnung] Ungültige Koordinaten bei Index {df.index.get_loc(idx)} ({current_coord}). Geocoding wird versucht.")
                do_geocode = True # Versuche es trotzdem

        current_street_val = last_street
        current_city_val = last_city
        current_postal_val = last_postal

        if do_geocode:
            attempts = 0
            max_attempts = 3
            success = False
            while attempts < max_attempts and not success:
                try:
                    location = geolocator.reverse(current_coord, language='de', timeout=15)
                    success = True

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

                        last_street = current_street_val
                        last_city = current_city_val
                        last_postal = current_postal_val
                        last_geocoded_coord = current_coord
                    else:
                        # Behalte die letzten *gültigen* Werte, wenn keine Adresse gefunden wurde
                        # current_street_val, current_city_val, current_postal_val sind bereits mit last_... initialisiert
                        if location is None:
                            print(f"[Info] Keine Adresse gefunden für {current_coord} (API gab None zurück).")
                        else:
                             print(f"[Warnung] Keine verwertbare Adresse in API-Antwort für {current_coord}.")


                    sleep(1.1) # Nominatim-Policy

                except Exception as e:
                    attempts += 1
                    wait_time = 2 * attempts # Simple exponential backoff for retries
                    print(f"[Fehler] Geocoding-Fehler für {current_coord} (Versuch {attempts}/{max_attempts}): {e}. Warte {wait_time}s...")
                    sleep(wait_time)
                    if attempts == max_attempts:
                        print(f"[Fehler] Geocoding für {current_coord} nach {max_attempts} Versuchen fehlgeschlagen. Verwende Fallback-Werte.")
                        # Fallback-Werte sind bereits in current_street_val etc.

        streets.append(current_street_val)
        cities.append(current_city_val)
        postal_codes.append(current_postal_val)

    api_metadata["api_query_end_time"] = datetime.now().isoformat()
    api_metadata["api_total_queries_attempted"] = actual_api_queries_made
    api_metadata["api_successful_queries"] = successful_api_queries
    api_metadata["api_failed_queries_after_retries"] = failed_api_queries_after_retries    
    
    # Füge API Metadaten zu den Hauptmetadaten hinzu
    if actual_api_queries_made > 0 : # Nur wenn API genutzt wurde
        metadata_lines.append("# API_USED: YES (Nominatim)")
        for key, value in api_metadata.items():
            if value is not None:
                 metadata_lines.append(f"# API_METADATA_{key.upper()}: {value}")
    else:
        metadata_lines.append("# API_USED: NO (Sampling-Distanz nicht erreicht für API Calls)")

    # --- Neue Spalten dem DataFrame hinzufügen NACH der Schleife ---
    df["Street"] = streets
    df["City"] = cities
    df["PostalCode"] = postal_codes

    # --- Ergebnis speichern ---
    # Stelle sicher, dass alle gewünschten Spalten im finalen DataFrame sind
    final_output_columns = ['Latitude', 'Longitude', 'original_index', 'Street', 'City', 'PostalCode']
    # Wähle nur Spalten aus, die auch wirklich in df existieren (Sicherheitsmaßnahme)
    df_to_save = df[[col for col in final_output_columns if col in df.columns]]

    try:
        # Schreibe Metadaten-Header
        with open(output_csv_path, 'w', encoding='utf-8') as f:
            for line in metadata_lines:
                f.write(line + "\n")
        # Hänge DataFrame an
        df_to_save.to_csv(output_csv_path, mode='a', index=False, encoding='utf-8', float_format='%.6f', header=True)
        print(f"\n[OK] Reverse Geocoding abgeschlossen und Metadaten gespeichert: {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte Output-CSV nicht schreiben: {output_csv_path} - {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    run_end_time = datetime.now()
    print(f"[{run_end_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} finished. Duration: {run_end_time - run_start_time}")


if __name__ == "__main__":
    # Argparse ist bereits in main()
    main()