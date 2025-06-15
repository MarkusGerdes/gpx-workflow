#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8_sort_places_by_route.py
-------------------------
Sorts the significant places (output of step 7) based on their first
appearance along the optimized route (output of step 4).
"""

SCRIPT_NAME = "8_sort_places_by_route.py"
SCRIPT_VERSION = "1.0.0" # Einführung einer Versionskontrolle, lauffaehiges Script

import sys
import os
import argparse
import pandas as pd

def sort_places(track_csv_path: str, places_csv_path: str, output_csv_path: str):
    """Sorts places based on route order."""
    print(f"[Info] Sorting places from '{places_csv_path}' based on route '{track_csv_path}'")

    # --- Lade Input-Dateien ---
    try:
        # Route mit Ortsinformation (aus Schritt 4)
        track_df = pd.read_csv(track_csv_path, comment='#')
        if track_df.empty:
            print(f"[Warnung] Track CSV ist leer: {track_csv_path}")
            # Wenn der Track leer ist, können wir nicht sortieren. Leere Output speichern.
            pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"]).to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere sortierte Orts-CSV gespeichert, da Track leer: {output_csv_path}")
            sys.exit(0)

        # Unsortierte Ortsliste (aus Schritt 7)
        places_df = pd.read_csv(places_csv_path, comment='#')
        if places_df.empty:
             print(f"[Warnung] Places CSV ist leer: {places_csv_path}")
             # Wenn keine Orte da sind, leere Output speichern.
             places_df.to_csv(output_csv_path, index=False, encoding='utf-8')
             print(f"[OK] Leere sortierte Orts-CSV gespeichert, da keine Orte gefunden: {output_csv_path}")
             sys.exit(0)

    except FileNotFoundError as e:
        print(f"[Fehler] Eingabedatei nicht gefunden: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-Dateien: {e}")
        sys.exit(1)

    # --- Spalten prüfen ---
    if "City" not in track_df.columns:
        print(f"Fehler: Spalte 'City' fehlt in Track-Datei: {track_csv_path}")
        sys.exit(1)
    if "Ort" not in places_df.columns:
        # Versuche Fallback, falls Spalte 'City' heißt
        if "City" in places_df.columns:
             print("[Warnung] Spalte 'Ort' fehlt in Places-Datei, verwende stattdessen 'City'.")
             places_df.rename(columns={"City": "Ort"}, inplace=True)
        else:
             print(f"Fehler: Spalte 'Ort' (oder 'City') fehlt in Places-Datei: {places_csv_path}")
             sys.exit(1)

    # --- Sortierlogik ---
    # Konvertiere 'City' im Track sicherheitshalber zu Strings
    track_df['City'] = track_df['City'].astype(str)
    # Entferne irrelevante Einträge und Duplikate, behalte die Reihenfolge bei
    ordered_cities_on_route = track_df.drop_duplicates(subset=['City'], keep='first')['City'].tolist()

    # Filtere irrelevante Orte aus der Liste, die wir sortieren wollen
    ignore_places = ["Unbekannter Ort", "Fehler", "Keine PLZ", "", "nan", "None"]
    ordered_cities_on_route = [city for city in ordered_cities_on_route if city not in ignore_places]

    # Funktion zum Ermitteln des ersten Index (Position) im Track
    def get_sort_key(place_name):
        try:
            # Finde den Index des ersten Vorkommens des Ortes in der geordneten Liste
            return ordered_cities_on_route.index(str(place_name)) # Konvertiere place_name zu str
        except ValueError:
            # Wenn der Ort aus der Place-Liste nicht im Track vorkommt (sollte nicht passieren, aber sicher ist sicher)
            # oder nach Filterung entfernt wurde, weise einen hohen Index zu (ans Ende).
            return float('inf')

    # Wende die Sortierfunktion an, um einen Sortierindex zu erstellen
    # Stelle sicher, dass 'Ort' auch ein String ist für den Vergleich in get_sort_key
    places_df['sort_index'] = places_df['Ort'].astype(str).apply(get_sort_key)

    # Sortiere den DataFrame basierend auf dem neuen Index
    sorted_places_df = places_df.sort_values("sort_index")

    # Entferne die Hilfsspalte 'sort_index'
    sorted_places_df = sorted_places_df.drop(columns="sort_index")

    # --- Speichern ---
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        sorted_places_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.2f')
        print(f"[OK] Sortierte Orte gespeichert ({len(sorted_places_df)} Einträge): {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte sortierte Orts-CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sort significant places based on their order along the route.")
    parser.add_argument("--track-csv", required=True, help="Path to the track CSV file with location data (output of step 4).")
    parser.add_argument("--places-csv", required=True, help="Path to the unsorted places summary CSV file (output of step 7).")
    parser.add_argument("--output-csv", required=True, help="Path to save the sorted places CSV file.")
    args = parser.parse_args()

    sort_places(args.track_csv, args.places_csv, args.output_csv)