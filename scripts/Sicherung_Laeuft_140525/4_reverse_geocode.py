# --- START OF FILE 4_reverse_geocode.py --- (Original)

import sys
import os
import pandas as pd
from geopy.geocoders import Nominatim
from tqdm import tqdm
from time import sleep
from geopy.distance import geodesic
import argparse # <-- DIESE ZEILE HINZUFÜGEN

def main():
    # --- Anpassung nötig: Argument Parser ---
    # if len(sys.argv) != 3:
    #     print("Verwendung: python 4_reverse_geocode.py <input_csv> <output_csv>")
    #     sys.exit(1)
    # input_csv = sys.argv[1]
    # output_csv = sys.argv[2]
    # Stattdessen argparse verwenden:
    parser = argparse.ArgumentParser(description="Reverse geocode coordinates from a simplified track CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to the input simplified track CSV (Lat/Lon).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV with location data.")
    # Parameter aus Config übergeben
    parser.add_argument("--sampling-dist", type=float, default=0.5, help="Min distance [km] between geocoding queries.")
    args = parser.parse_args()
    input_csv = args.input_csv
    output_csv = args.output_csv
    sampling_distance_km = args.sampling_dist # Parameter verwenden

    # Sicherstellen, dass das Ausgabeverzeichnis existiert
    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Geolocator initialisieren
    geolocator = Nominatim(user_agent="gpx_workflow_v2", timeout=10) # User-Agent evtl. anpassen

    # --- Input-Daten laden ---
    try:
        df = pd.read_csv(input_csv)
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv}")
            # Leere Output-Datei erstellen und beenden
            df_out = pd.DataFrame(columns=['Latitude', 'Longitude', 'Street', 'City', 'PostalCode'])
            df_out.to_csv(output_csv, index=False, encoding='utf-8')
            print(f"[OK] Leere Output-CSV gespeichert: {output_csv}")
            sys.exit(0)
    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv}': {e}")
        sys.exit(1)


    required_columns = ["Latitude", "Longitude"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Fehler: Fehlende Spalten in {input_csv}: {', '.join(missing_columns)}")
        sys.exit(1)

    # Listen für neue Spalten vorbereiten
    streets = []
    cities = []
    postal_codes = []

    # Für Sampling: speichere zuletzt geokodierte Koordinaten
    last_geocoded_coord = None
    # sampling_distance_km = 0.5 # Wird jetzt als Parameter übergeben

    print(f"\nStarte Reverse Geocoding (Sampling: >= {sampling_distance_km} km)...")

    # Temporäre Variablen, um den letzten erfolgreichen Wert zu halten
    last_street = 'Unbekannte Straße'
    last_city = 'Unbekannter Ort'
    last_postal = 'Keine PLZ'

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Geokodierung", unit="Punkt"):
        current_coord = (row['Latitude'], row['Longitude'])
        do_geocode = True
        dist = 0.0 # Initialisiere dist

        if last_geocoded_coord is not None:
            # Prüfe den Abstand zum zuletzt geokodeten Punkt
            try:
                dist = geodesic(last_geocoded_coord, current_coord).kilometers
                if dist < sampling_distance_km:
                    do_geocode = False
            except ValueError:
                print(f"[Warnung] Ungültige Koordinaten bei Index {idx}. Geocoding wird versucht.")
                do_geocode = True # Versuche es trotzdem, falls Distanzberechnung fehlschlägt

        current_street = last_street # Standardmäßig letzte Werte übernehmen
        current_city = last_city
        current_postal = last_postal

        if do_geocode:
            attempts = 0
            max_attempts = 3
            success = False
            while attempts < max_attempts and not success:
                try:
                    # Nominatim erwartet (latitude, longitude)
                    location = geolocator.reverse(current_coord, language='de', timeout=15) # Timeout leicht erhöht
                    success = True # Anfrage erfolgreich

                    if location and location.raw and 'address' in location.raw:
                        address = location.raw['address']
                        # Fallback-Logik für Ortsnamen verbessert
                        city_options = [
                            address.get('city'),
                            address.get('town'),
                            address.get('village'),
                            address.get('hamlet'), # Kleinere Orte hinzufügen
                            address.get('suburb'), # Vororte hinzufügen
                            address.get('county') # Landkreis als letzter Fallback
                        ]
                        current_city = next((c for c in city_options if c), 'Unbekannter Ort') # Nimmt den ersten nicht-None Wert
                        current_street = address.get('road', 'Unbekannte Straße')
                        current_postal = address.get('postcode', 'Keine PLZ')

                        # Update der "letzten erfolgreichen" Werte
                        last_street = current_street
                        last_city = current_city
                        last_postal = current_postal
                        last_geocoded_coord = current_coord # Update des letzten *geokodierten* Punktes

                    else:
                        # Wenn keine Adresse gefunden wurde, behalte die letzten *gültigen* Werte
                        current_street = last_street
                        current_city = last_city
                        current_postal = last_postal
                        print(f"[Warnung] Keine Adresse gefunden für {current_coord}")

                    sleep(1.1)  # Schone den Server (Nominatim-Policy: max 1 req/sec)

                except Exception as e:
                    attempts += 1
                    wait_time = 2 * attempts
                    print(f"[Fehler] Geocoding-Fehler für {current_coord} (Versuch {attempts}/{max_attempts}): {e}. Warte {wait_time}s...")
                    sleep(wait_time)
                    if attempts == max_attempts:
                         print(f"[Fehler] Geocoding für {current_coord} nach {max_attempts} Versuchen fehlgeschlagen. Verwende letzte gültige Werte.")
                         # Behalte die letzten gültigen Werte
                         current_street = last_street
                         current_city = last_city
                         current_postal = last_postal

        # Füge die ermittelten oder übernommenen Werte hinzu
        streets.append(current_street)
        cities.append(current_city)
        postal_codes.append(current_postal)

    # Neue Spalten ergänzen
    df["Street"] = streets
    df["City"] = cities
    df["PostalCode"] = postal_codes

    # Ergebnis speichern
    try:
        df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"\n[OK] Reverse Geocoding abgeschlossen und gespeichert: {output_csv}")
    except Exception as e:
        print(f"[Fehler] Konnte Output-CSV nicht schreiben: {output_csv} - {e}")
        sys.exit(1)


if __name__ == "__main__":
    # -- main() wird jetzt direkt aufgerufen, Argumente werden oben geparsed --
    main()

# --- END OF FILE 4_reverse_geocode.py --- (Original)