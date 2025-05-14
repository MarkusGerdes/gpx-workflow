#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8b_geocode_places.py
--------------------
Reads a CSV file with a sorted list of place names (output of step 8).
Performs forward geocoding for each place name using Nominatim to find
its coordinates (latitude, longitude). Handles API rate limits and errors.
Saves the results (place name, latitude, longitude) to a new CSV file.
"""

import sys
import os
import argparse
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderQuotaExceeded
import time
from tqdm import tqdm # Für Fortschrittsanzeige

# --- Konstanten ---
NOMINATIM_USER_AGENT = "gpx_workflow_v2_place_geocoder" # Eigener User Agent
REQUEST_TIMEOUT = 15  # Timeout für Geocoding-Anfragen
SLEEP_BETWEEN_REQUESTS = 1.1 # Nominatim Policy: max 1 req/sec
RETRY_DELAY = 5       # Wartezeit zwischen Wiederholungsversuchen
MAX_RETRIES = 3       # Maximale Wiederholungsversuche pro Ort

def geocode_places(input_csv_path: str, output_csv_path: str, context: str = None):
    """
    Performs forward geocoding for places listed in the input CSV.

    Args:
        input_csv_path: Path to the sorted places CSV (needs 'Ort' column).
        output_csv_path: Path to save the output CSV with coordinates.
        context: Optional context string (e.g., ", Country Name") to add
                 to the query for better results.
    """
    print(f"[Info] Geocoding places from: {input_csv_path}")

    # --- Lade Input-CSV ---
    try:
        places_df = pd.read_csv(input_csv_path)
        if places_df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            pd.DataFrame(columns=["Ort", "Latitude_Center", "Longitude_Center"]).to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere Geocoding-Ergebnis-CSV gespeichert: {output_csv_path}")
            sys.exit(0)

        # Prüfe auf 'Ort'-Spalte
        if "Ort" not in places_df.columns:
             if "City" in places_df.columns:
                 print("[Warnung] Spalte 'Ort' fehlt, verwende stattdessen 'City'.")
                 places_df.rename(columns={"City": "Ort"}, inplace=True)
             else:
                 raise ValueError("Input CSV muss Spalte 'Ort' oder 'City' enthalten.")

        # Entferne Duplikate, um unnötige API-Abfragen zu vermeiden
        unique_places = places_df['Ort'].astype(str).str.strip().unique()
        # Entferne leere oder irrelevante Namen direkt
        unique_places = [p for p in unique_places if p and p not in ["Unbekannter Ort", "Fehler", "nan", "None"]]
        print(f"[Info] {len(unique_places)} eindeutige Orte zum Geocodieren gefunden.")
        if not unique_places:
             print("[Warnung] Keine gültigen Ortsnamen zum Geocodieren gefunden.")
             pd.DataFrame(columns=["Ort", "Latitude_Center", "Longitude_Center"]).to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere Geocoding-Ergebnis-CSV gespeichert: {output_csv_path}")
             sys.exit(0)


    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # --- Initialisiere Geocoder ---
    geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT)

    # --- Geocoding durchführen ---
    results = []
    print("[Info] Starte Forward Geocoding (beachte API Limits!)...")
    for place_name in tqdm(unique_places, desc="Geocoding Places"):
        lat, lon = None, None
        full_query = f"{place_name}{context if context else ''}" # Füge Kontext hinzu, falls vorhanden

        for attempt in range(MAX_RETRIES):
            location = None # Reset location für jeden Versuch
            try:
                # print(f"DEBUG: Querying '{full_query}' (Attempt {attempt+1})") # Optional Debug
                location = geolocator.geocode(full_query, timeout=REQUEST_TIMEOUT)
                if location:
                    lat = location.latitude
                    lon = location.longitude
                    print(f"  -> Gefunden: {place_name} -> ({lat:.4f}, {lon:.4f})")
                    break # Erfolg, nächste Stadt
                else:
                    # Kein Ergebnis, aber kein Fehler -> nächster Versuch (oder Ende)
                    if attempt == MAX_RETRIES - 1:
                        print(f"  -> !! Nicht gefunden: {place_name} (nach {MAX_RETRIES} Versuchen)")
                # Wichtig: Warte nach JEDER Anfrage, auch wenn kein Ergebnis
                time.sleep(SLEEP_BETWEEN_REQUESTS)

            except GeocoderTimedOut:
                print(f"  -> !! Timeout für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            except GeocoderQuotaExceeded:
                 print(f"  -> !! Quota überschritten für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}). Warte länger...")
                 time.sleep(RETRY_DELAY * 5) # Länger warten bei Quota-Problem
            except GeocoderServiceError as e:
                 print(f"  -> !! Service Fehler für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")
                 time.sleep(RETRY_DELAY)
            except Exception as e:
                 print(f"  -> !! Unerwarteter Fehler für {place_name} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")
                 time.sleep(RETRY_DELAY)

            # Wenn wir hier sind und keinen Erfolg hatten, versuchen wir es erneut (nach Wartezeit)

        # Speichere Ergebnis (auch wenn Lat/Lon None sind)
        results.append({
            "Ort": place_name,
            "Latitude_Center": lat,
            "Longitude_Center": lon
        })

    # --- Ergebnisse speichern ---
    result_df = pd.DataFrame(results)

    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Füge Originaldaten wieder hinzu (optional, aber kann nützlich sein)
        # Merge mit dem ursprünglichen DataFrame, um Spalten wie 'Vorkommen' etc. zu behalten
        # Stelle sicher, dass 'Ort' in beiden DFs als String behandelt wird
        places_df['Ort'] = places_df['Ort'].astype(str)
        result_df['Ort'] = result_df['Ort'].astype(str)
        final_df = pd.merge(places_df, result_df, on="Ort", how="left")

        final_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.6f')
        print(f"\n[OK] Geocoding-Ergebnisse gespeichert ({len(final_df)} Einträge): {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte Geocoding-Ergebnis-CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forward geocode place names from a CSV file.")
    parser.add_argument("--input-csv", required=True, help="Path to the sorted places CSV file (output of step 8).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with coordinates.")
    parser.add_argument("--context", default="", help="Optional context (e.g., ', Country') to add to geocoding query.")
    args = parser.parse_args()

    geocode_places(args.input_csv, args.output_csv, args.context)