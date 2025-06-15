#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2c_add_elevation.py
-------------------
Reads track data CSV (output of step 2).
Checks if elevation data is missing or invalid (e.g., all zeros or NaN).
If needed, fetches elevation data for track coordinates from the
Open Topo Data API (https://www.opentopodata.org/).
Recalculates ascent based on the new elevation data.
Saves the updated track data to a new CSV file.

Requires: pandas, requests, numpy
"""

SCRIPT_NAME = "2c_add_elevation.py"
SCRIPT_VERSION = "1.1.0" # Einführung einer Versionskontrolle, lauffaehiges Script

import sys
import os
import argparse
import pandas as pd
import numpy as np
import requests
import time
import math
from tqdm import tqdm
from datetime import datetime

# --- Konfiguration ---
OPENTOPO_API_URL = "https://api.opentopodata.org/v1/lookup"
BATCH_SIZE = 100      # Max locations per API request (API limit is 100)
REQUEST_TIMEOUT = 30  # Timeout for API request
SLEEP_BETWEEN_REQUESTS = 1.1 # Be nice to the API (max 1 req/sec)
RETRY_DELAY = 5       # Wait time between retries
MAX_RETRIES = 3       # Max retries per batch

def add_elevation(input_csv_path: str, output_csv_path: str, batch_size: int): # batch_size hier hinzufügen
    """Checks and adds elevation data using Open Topo Data API."""
    run_start_time = datetime.now()
    print(f"[{run_start_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} started.")
    print(f"[Info] Checking/Adding elevation for: {input_csv_path}")
    print(f"[Info] Using API Batch Size: {batch_size}")

    # Metadaten-Sammlung
    metadata_lines = [
        f"# Processed by: {SCRIPT_NAME} v{SCRIPT_VERSION}",
        f"# Processing Timestamp: {run_start_time.isoformat()}",
        f"# Input CSV: {os.path.basename(input_csv_path)}",
    ]
    api_metadata = {
        "api_provider": "OpenTopoData API (https://www.opentopodata.org/)",
        "api_endpoint": OPENTOPO_API_URL,
        "api_query_start_time": None,
        "api_query_end_time": None,
        "api_total_queries": 0,
        "api_successful_queries": 0,
        "api_failed_queries": 0,
        "api_data_source_info": "Primarily SRTM GL1 (Global 30m), ASTER GDEM, GMTED2010, ETOPO1. See API docs for details."
    }

    # --- Lade Input-CSV ---
    try:
        df = pd.read_csv(input_csv_path, parse_dates=['Time'], encoding='utf-8')
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            df.to_csv(output_csv_path, index=False, encoding='utf-8') # Save empty
            print(f"[OK] Leere Elevation-CSV gespeichert: {output_csv_path}")
            sys.exit(0)

        # Überprüfe notwendige Spalten
        if not all(col in df.columns for col in ['Latitude', 'Longitude']):
            raise ValueError("Input CSV benötigt 'Latitude' und 'Longitude'.")

        # Standardmäßig davon ausgehen, dass Höhe hinzugefügt werden muss
        needs_elevation_fetch = True
        if 'Elevation (m)' in df.columns and df['Elevation (m)'].notna().all():
            # Prüfen, ob die Werte sinnvoll sind (nicht alle gleich, nicht alle 0)
            unique_elevations = df['Elevation (m)'].nunique()
            if unique_elevations > 1:
                 # Wenn mehr als ein eindeutiger, nicht-NaN Wert existiert,
                 # gehen wir davon aus, dass die Daten valide sind.
                 # Eine Prüfung auf "alle 0" könnte hier noch sinnvoll sein.
                 min_el, max_el = df['Elevation (m)'].min(), df['Elevation (m)'].max()
                 if not (unique_elevations == 1 and min_el == 0.0): # Nicht alle 0
                      print("[Info] Vorhandene Höhendaten scheinen valide zu sein. Überspringe API-Abfrage.")
                      needs_elevation_fetch = False

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # --- API-Abfrage, falls nötig ---
    if needs_elevation_fetch:
        print("[Info] Höhendaten fehlen oder sind ungültig. Versuche Abfrage von Open Topo Data API...")
        coordinates = list(zip(df['Latitude'], df['Longitude']))
        num_points = len(coordinates)
        # --- Verwende übergebenen Parameter ---
        num_batches = math.ceil(num_points / batch_size)
        # ------------------------------------
        fetched_elevations = [None] * num_points # Liste für Ergebnisse

        api_errors = 0
        with tqdm(total=num_batches, desc="Fetching Elevation Batches") as pbar:
            for i in range(num_batches):
                # --- Verwende übergebenen Parameter ---
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, num_points)
                # ------------------------------------
                batch_coords = coordinates[start_idx:end_idx]

                # Erstelle Location-String für API
                locations_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in batch_coords])
                api_url_batch = f"{OPENTOPO_API_URL}?locations={locations_str}"

                # Führe API-Abfrage mit Retries durch
                success = False
                for attempt in range(MAX_RETRIES):
                    try:
                        response = requests.get(api_url_batch, timeout=REQUEST_TIMEOUT)
                        response.raise_for_status() # Fehler bei 4xx/5xx
                        data = response.json()

                        if data.get('status') == 'OK':
                            results = data.get('results', [])
                            if len(results) == len(batch_coords):
                                for j, res in enumerate(results):
                                     # Speichere Höhe oder None, falls nicht gefunden
                                     fetched_elevations[start_idx + j] = res.get('elevation')
                                success = True
                                break # Erfolg für diesen Batch
                            else:
                                print(f"[Warnung] API gab unerwartete Anzahl Ergebnisse für Batch {i+1} zurück.")
                                # Hier könnten komplexere Fehlerbehandlungen nötig sein
                        else:
                            print(f"[Warnung] API-Status nicht OK für Batch {i+1}: {data.get('status')}")
                            # Versuche es erneut nach kurzer Pause

                    except requests.exceptions.Timeout:
                         print(f"  -> Timeout Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
                    except requests.exceptions.HTTPError as e:
                         print(f"  -> HTTP Fehler {e.response.status_code} Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
                         if e.response.status_code == 429: # Too many requests
                              time.sleep(RETRY_DELAY * 2) # Länger warten
                    except requests.exceptions.RequestException as e:
                         print(f"  -> Request Fehler Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")
                    except Exception as e:
                         print(f"  -> Unerwarteter Fehler Batch {i+1} (Versuch {attempt+1}/{MAX_RETRIES}): {e}. Warte {RETRY_DELAY}s...")

                    # Warte vor dem nächsten Versuch
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)

                if not success:
                     print(f" Fehler: Konnte Batch {i+1} nach {MAX_RETRIES} Versuchen nicht abrufen.")
                     api_errors += 1
                     # Setze Höhen für diesen Batch auf None oder 0? Besser None lassen.

                # Pause zwischen den Batches
                if i < num_batches - 1:
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                pbar.update(1) # Aktualisiere Fortschrittsbalken

        api_metadata["api_query_end_time"] = datetime.now().isoformat()
        api_metadata["api_failed_queries"] = api_errors
        
        # Füge API Metadaten zu den Hauptmetadaten hinzu
        for key, value in api_metadata.items():
            if value is not None: # Nur vorhandene Metadaten hinzufügen
                 metadata_lines.append(f"# API_METADATA_{key.upper()}: {value}")

        # --- Aktualisiere DataFrame ---
        print("[Info] Aktualisiere DataFrame mit abgerufenen Höhen...")
        # Konvertiere None zu NaN für Pandas und float
        df['Elevation_API'] = [float(e) if e is not None else np.nan for e in fetched_elevations]

        # Fülle verbleibende NaNs (falls API-Aufrufe fehlschlugen oder API None lieferte)
        if df['Elevation_API'].isnull().any():
            num_null_before = df['Elevation_API'].isnull().sum()
            print(f"[Warnung] {num_null_before} Höhenwerte konnten nicht von API abgerufen werden. Fülle Lücken...")
            # Optionen: Interpolieren oder ffill/bfill
            df['Elevation_API'].interpolate(method='linear', limit_direction='both', inplace=True)
            # Fallback: Mit 0 füllen, wenn alles NaN ist
            if df['Elevation_API'].isnull().all():
                 df['Elevation_API'] = 0.0
            num_null_after = df['Elevation_API'].isnull().sum()
            if num_null_after > 0:
                print(f"[Warnung] {num_null_after} Höhenwerte konnten nicht gefüllt werden. Setze auf 0.")
                df['Elevation_API'].fillna(0.0, inplace=True)


        # Überschreibe die ursprüngliche Elevation-Spalte
        df['Elevation (m)'] = df['Elevation_API']
        df.drop(columns=['Elevation_API'], inplace=True)

        # --- Berechne Aufstieg NEU ---
        print("[Info] Berechne 'Aufstieg (m)' neu basierend auf API-Höhen...")
        elevation_diff = df['Elevation (m)'].diff().fillna(0)
        df['Aufstieg (m)'] = elevation_diff.clip(lower=0)

    else:
        # Wenn keine API-Abfrage nötig war, stelle sicher, dass 'Aufstieg (m)' trotzdem existiert
        if 'Aufstieg (m)' not in df.columns:
            print("[Info] Berechne 'Aufstieg (m)' aus vorhandenen Höhendaten...")
            elevation_diff = df['Elevation (m)'].diff().fillna(0)
            df['Aufstieg (m)'] = elevation_diff.clip(lower=0)


    # --- Speichere finale CSV mit Metadaten-Header ---
    try:
        output_dir = os.path.dirname(output_csv_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        
        final_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Time', 'Strecke Delta (km)', 'Distanz (km)', 'Aufstieg (m)']
        for col in final_cols:
            if col not in df.columns:
                 if col == 'Time': df[col] = pd.NaT
                 else: df[col] = 0.0 if col != 'Elevation (m)' else np.nan # Für Elevation NaN lassen, wenn nicht da
        
        # Stelle sicher, dass 'Elevation (m)' existiert, bevor es ausgewählt wird, oder fülle mit NaN
        if 'Elevation (m)' not in df.columns:
            df['Elevation (m)'] = np.nan # Oder 0.0, je nach gewünschtem Verhalten

        df_final = df[final_cols]

        # Schreibe Metadaten-Header
        with open(output_csv_path, 'w', encoding='utf-8') as f:
            for line in metadata_lines:
                f.write(line + "\n")
        
        # Hänge DataFrame an die Datei an
        df_final.to_csv(output_csv_path, mode='a', index=False, encoding='utf-8', float_format='%.6f', header=True) # header=True hier wichtig!
        print(f"[OK] Trackdaten mit Höhen und Metadaten gespeichert: {output_csv_path}")

    except Exception as e:
        print(f"[Fehler] Konnte finale CSV nicht schreiben: {output_csv_path} - {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    run_end_time = datetime.now()
    print(f"[{run_end_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} finished. Duration: {run_end_time - run_start_time}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and add elevation data to track CSV using Open Topo Data API.")
    parser.add_argument("--input-csv", required=True, help="Path to the input track data CSV file (output of step 2).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with potentially added elevation.")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of locations per API request batch.")
    args = parser.parse_args()

    add_elevation(args.input_csv, args.output_csv, args.batch_size)