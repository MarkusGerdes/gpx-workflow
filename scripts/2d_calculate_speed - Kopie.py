#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2d_calculate_speed.py
---------------------
Calculates point-to-point speed based on time and distance deltas
from the full track data. Adds speed columns to the CSV.
"""

SCRIPT_NAME = "2d_calculate_speed.py"
SCRIPT_VERSION = "1.0.0"

import pandas as pd
import numpy as np
import argparse
import os
import sys

def calculate_speed(input_csv_path: str, output_csv_path: str, rolling_window: int = 0):
    print(f"[Info] Calculating speed for: {input_csv_path}")
    try:
        df = pd.read_csv(input_csv_path, parse_dates=['Time'], comment='#') # Time direkt parsen
        if df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
            df.to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[OK] Leere Geschwindigkeits-CSV gespeichert: {output_csv_path}")
            sys.exit(0)

        if 'Time' not in df.columns or 'Strecke Delta (km)' not in df.columns:
            print("[Fehler] Benötigte Spalten 'Time' oder 'Strecke Delta (km)' nicht im Input CSV gefunden.")
            # Eventuell leere Spalten hinzufügen und mit NaNs füllen, oder abbrechen
            # Fürs Erste: Kopiere Input nach Output, wenn Spalten fehlen und gib Warnung aus
            df.to_csv(output_csv_path, index=False, encoding='utf-8')
            print(f"[Warnung] Input wurde nach Output kopiert, da Geschwindigkeitsberechnung nicht möglich: {output_csv_path}")
            sys.exit(0) # Oder sys.exit(1) wenn es ein harter Fehler sein soll

        # Zeitdifferenz berechnen
        # df['Time'] ist bereits datetime durch parse_dates
        df['TimeDelta (s)'] = df['Time'].diff().dt.total_seconds()
        # Erster Wert von diff() ist NaT, total_seconds() wird NaN. Fülle mit 0 für den ersten Punkt.
        df['TimeDelta (s)'] = df['TimeDelta (s)'].fillna(0)

        # Geschwindigkeit (km/h)
        # Vermeide Division durch Null und handle NaNs
        # Strecke Delta (km) / (TimeDelta (s) / 3600)
        df['Geschwindigkeit (km/h)'] = np.where(
            df['TimeDelta (s)'] > 0,
            df['Strecke Delta (km)'] / (df['TimeDelta (s)'] / 3600.0),
            0 # Geschwindigkeit ist 0, wenn keine Zeit vergangen ist oder Strecke 0 ist
        )
        # Korrigiere extreme Werte (optional, aber oft sinnvoll)
        df['Geschwindigkeit (km/h)'] = df['Geschwindigkeit (km/h)'].clip(upper=100) # z.B. Max 100 km/h

        # Geglättete Geschwindigkeit (optional)
        if rolling_window > 1 and 'Geschwindigkeit (km/h)' in df.columns:
            df[f'Geschwindigkeit geglättet (km/h, W{rolling_window})'] = df['Geschwindigkeit (km/h)'].rolling(window=rolling_window, center=True, min_periods=1).mean()
        elif rolling_window > 1:
            print(f"[Warnung] Geglättete Geschwindigkeit nicht berechnet, da Roh-Geschwindigkeit nicht vorhanden.")


        output_dir = os.path.dirname(output_csv_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        df.to_csv(output_csv_path, index=False, encoding='utf-8', float_format='%.3f')
        print(f"[OK] CSV mit Geschwindigkeitsdaten gespeichert: {output_csv_path}")

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler bei der Geschwindigkeitsberechnung: {input_csv_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate speed from track data.")
    parser.add_argument("input_csv", help="Path to the input track CSV (from 2c).")
    parser.add_argument("output_csv", help="Path to save the output CSV with speed data.")
    parser.add_argument("--rolling-window", type=int, default=0, help="Window size for rolling mean of speed (0 to disable).")
    args = parser.parse_args()

    calculate_speed(args.input_csv, args.output_csv, args.rolling_window)