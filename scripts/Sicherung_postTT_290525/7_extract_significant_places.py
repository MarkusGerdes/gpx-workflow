#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7_extract_significant_places.py
-------------------------------
Analyzes the track data CSV containing location information (output of step 4)
to extract significant places (cities/towns/villages) visited along the route.
Calculates the number of track points and the approximate distance spent
within each place. Filters out irrelevant place names.
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np

def extract_places(input_csv_path: str, output_csv_path: str):
    """Extracts and summarizes significant places from track data."""
    print(f"[Info] Extracting significant places from: {input_csv_path}")

    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        df = pd.read_csv(input_csv_path)
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            # Leere Output-Datei erstellen
            pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"]).to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere Ortszusammenfassungs-CSV gespeichert: {output_csv_path}")
            sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # --- Spalten prüfen ---
    # Wir brauchen 'City' aus Schritt 4.
    # 'Distanz (km)' aus der *vollen* Route wäre ideal für die Streckenberechnung,
    # aber die Input-CSV hier basiert auf den *optimierten* Punkten.
    # Daher können wir die Strecke im Ort nur *annähernd* schätzen.
    # Wir benötigen eine Distanzspalte. Wenn sie nicht da ist, können wir die Strecke nicht berechnen.
    required_cols = ["City"]
    if not all(col in df.columns for col in required_cols):
        print(f"❌ Fehler: Fehlende Spalten in {input_csv_path}. Benötigt: {required_cols}")
        sys.exit(1)

    # Optionale Distanzspalte prüfen
    has_distance = 'Distanz (km)' in df.columns or 'Strecke Delta (km)' in df.columns
    distance_col = None
    if 'Distanz (km)' in df.columns:
        distance_col = 'Distanz (km)'
    elif 'Strecke Delta (km)' in df.columns:
        # Wenn nur Delta da ist, berechne kumulative Distanz neu (annähernd!)
        print("[Warnung] 'Distanz (km)' fehlt, berechne Annäherung aus 'Strecke Delta (km)'.")
        df['Distanz_approx_km'] = df['Strecke Delta (km)'].cumsum()
        distance_col = 'Distanz_approx_km'
        has_distance = True
    else:
        print("[Warnung] Keine Distanzspalte gefunden. 'Strecke im Ort (km)' wird nicht berechnet.")


    # --- Orte filtern und analysieren ---
    # Ignoriere unsinnige oder fehlerhafte Ortsnamen
    # Konvertiere alle Einträge in der 'City'-Spalte sicherheitshalber zu Strings
    df['City'] = df['City'].astype(str)
    ignore_places = ["Unbekannter Ort", "Fehler", "Keine PLZ", "", "nan", "None"]
    df_filtered = df[~df["City"].isin(ignore_places)].copy() # copy() um SettingWithCopyWarning zu vermeiden

    if df_filtered.empty:
        print("[Warnung] Keine signifikanten Orte nach Filterung gefunden.")
        pd.DataFrame(columns=["Ort", "Vorkommen", "Strecke im Ort (km)"]).to_csv(output_csv_path, index=False, encoding='utf-8')
        print(f"[OK] Leere Ortszusammenfassungs-CSV gespeichert: {output_csv_path}")
        sys.exit(0)

    # Gruppieren nach Stadt
    grouped = df_filtered.groupby("City")

    results = []
    for city, group in grouped:
        count = len(group)
        dist_in_place = 0.0

        if has_distance:
            # Berechne Distanz im Ort: Max(Distanz) - Min(Distanz) innerhalb der Gruppe
            # Dies ist eine Annäherung, da die Punkte vereinfacht sind!
            min_dist = group[distance_col].min()
            max_dist = group[distance_col].max()
            dist_in_place = max_dist - min_dist
        else:
            dist_in_place = np.nan # Markiere als nicht berechenbar

        results.append({
            "Ort": city,
            "Vorkommen": count,
            "Strecke im Ort (km)": dist_in_place
        })

    # --- Ergebnisse speichern ---
    result_df = pd.DataFrame(results)
    # Sortieren, z.B. nach Anzahl Vorkommen oder Strecke (falls berechnet)
    sort_by_col = "Strecke im Ort (km)" if has_distance else "Vorkommen"
    result_df = result_df.sort_values(by=sort_by_col, ascending=False, na_position='last')

    try:
        result_df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.2f')
        print(f"[OK] Ortszusammenfassung gespeichert ({len(result_df)} Orte): {output_csv_path}")
    except Exception as e:
        print(f"[Fehler] Konnte Ortszusammenfassungs-CSV nicht schreiben: {output_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract significant places from geocoded track data.")
    parser.add_argument("--input-csv", required=True, help="Path to the input CSV file with location data (output of step 4).")
    parser.add_argument("--output-csv", required=True, help="Path to save the output CSV file with places summary.")
    args = parser.parse_args()

    extract_places(args.input_csv, args.output_csv)