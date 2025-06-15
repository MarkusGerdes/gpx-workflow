#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2b_simplify_gpx_api.py (V3 - Mit Original-Indizes)
----------------------
Simplifies track points from a full track CSV using Ramer-Douglas-Peucker (RDP).
Outputs Latitude, Longitude, and the original_index from the input CSV
for the simplified points.
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from rdp import rdp # pip install rdp

def simplify_track_with_indexing(input_full_track_csv: str, output_simplified_csv: str, epsilon: float):
    print(f"[Info] Simplifying track from CSV with indexing: {input_full_track_csv}")
    print(f"  Epsilon: {epsilon}")
    try:
        output_dir = os.path.dirname(output_simplified_csv)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        df_full = pd.read_csv(input_full_track_csv)

        if df_full.empty or len(df_full) < 2:
            print(f"[Warnung] Input CSV '{input_full_track_csv}' ist leer oder hat < 2 Punkte. Keine Vereinfachung, kopiere relevante Spalten.")
            cols_to_output = ['Latitude', 'Longitude']
            if not df_full.empty:
                df_full['original_index'] = df_full.index
                if 'original_index' not in cols_to_output : cols_to_output.append('original_index')
            
            # Sicherstellen, dass nur existierende Spalten ausgewählt werden
            df_to_save = pd.DataFrame(columns=cols_to_output) # Leeren DF mit den richtigen Spalten erstellen
            if not df_full.empty:
                 df_to_save = df_full[[col for col in cols_to_output if col in df_full.columns]]

            df_to_save.to_csv(output_simplified_csv, index=False, float_format='%.6f')
            print(f"[OK] Vereinfachte Daten (ggf. leer/unverändert) gespeichert: {output_simplified_csv}")
            return

        # Vorbereitung für RDP: Numpy-Array mit (Longitude, Latitude)
        points_for_rdp_np = df_full[['Longitude', 'Latitude']].values

        # RDP anwenden
        # Die rdp() Funktion gibt ein Numpy-Array der vereinfachten Punkte zurück
        print(f"[Info] Original number of points: {len(points_for_rdp_np)}")
        simplified_points_np = rdp(points_for_rdp_np, epsilon=epsilon)
        print(f"[Info] Number of points after RDP: {len(simplified_points_np)}")

        if len(simplified_points_np) == 0 and len(points_for_rdp_np) > 0:
             print("[Warnung] RDP resultierte in 0 Punkten. Verwende stattdessen Start- und Endpunkt.")
             # Fallback: Nur Start- und Endpunkt des Originals verwenden
             indices_to_keep = [0, len(df_full) - 1] if len(df_full) > 1 else [0]
             indices_to_keep = list(set(indices_to_keep)) # Eindeutig machen
             df_simplified_with_index = df_full.iloc[indices_to_keep].copy()
             df_simplified_with_index['original_index'] = df_simplified_with_index.index
        elif len(simplified_points_np) < 2 and len(points_for_rdp_np) >=2 :
             print("[Warnung] RDP resultierte in weniger als 2 Punkten. Füge Original-Start/Endpunkte hinzu.")
             # Erstelle DataFrame aus den wenigen RDP-Punkten
             df_rdp_temp = pd.DataFrame(simplified_points_np, columns=['Longitude', 'Latitude'])
             # Füge Start- und Endpunkte des Originals hinzu
             start_point_orig_coords = df_full.iloc[[0]][['Longitude', 'Latitude']]
             end_point_orig_coords = df_full.iloc[[-1]][['Longitude', 'Latitude']]
             
             df_combined = pd.concat([start_point_orig_coords, df_rdp_temp, end_point_orig_coords], ignore_index=True)
             df_combined.drop_duplicates(subset=['Longitude', 'Latitude'], keep='first', inplace=True)
             
             # Jetzt Indizes für diese Punkte finden
             df_full_indexed = df_full.copy()
             df_full_indexed['original_index'] = df_full_indexed.index
             df_simplified_with_index = pd.merge(
                 df_combined.round(decimals=6), # Runde für Merge
                 df_full_indexed[['Longitude', 'Latitude', 'original_index']].round(decimals=6),
                 on=['Longitude', 'Latitude'],
                 how='left'
             ).drop_duplicates(subset=['Longitude', 'Latitude'], keep='first')
        else:
            # Erstelle einen DataFrame aus den simplifizierten Punkten (Longitude, Latitude)
            df_simplified_coords = pd.DataFrame(simplified_points_np, columns=['Longitude_s', 'Latitude_s'])

            # Um die 'original_index' Spalte zu bekommen: Merge mit dem Original-DataFrame.
            # Füge dem Original-DataFrame eine Index-Spalte hinzu, falls noch nicht vorhanden
            df_full_indexed = df_full.copy()
            df_full_indexed['original_index'] = df_full_indexed.index

            # Runden der Koordinaten für einen robusteren Merge (Float-Präzision)
            # Wähle eine sinnvolle Anzahl von Dezimalstellen, die für GPX-Daten typisch ist (z.B. 6-7)
            precision = 6 
            df_simplified_coords_rounded = df_simplified_coords.round({'Longitude_s': precision, 'Latitude_s': precision})
            df_full_indexed_rounded = df_full_indexed.round({'Longitude': precision, 'Latitude': precision})
            
            # Umbenennen für den Merge, damit klar ist, welche Spalten gemerged werden
            df_simplified_coords_rounded.rename(columns={'Longitude_s': 'Longitude', 'Latitude_s': 'Latitude'}, inplace=True)

            # Merge, um den original_index zu erhalten
            # Wir nehmen die Spalten 'Latitude', 'Longitude', 'original_index' aus df_full_indexed
            # und mergen sie mit den simplifizierten Koordinaten.
            # Wichtig: Es können durch RDP Punkte entstehen, die nicht exakt einem Originalpunkt entsprechen,
            # sondern auf einer Linie dazwischen liegen. RDP wählt aber typischerweise Originalpunkte aus.
            # Ein `how='left'` auf den gerundeten Koordinaten sollte die meisten Treffer liefern.
            df_simplified_with_index = pd.merge(
                df_simplified_coords_rounded, # Enthält jetzt 'Longitude', 'Latitude' (gerundet)
                df_full_indexed_rounded[['Longitude', 'Latitude', 'original_index']],
                on=['Longitude', 'Latitude'],
                how='left'
            )
            # Originale, ungerundete Koordinaten wiederherstellen (aus dem Merge oder neu aus df_full holen)
            # Da wir auf gerundeten Werten gemerged haben, sind Lat/Lon in df_simplified_with_index gerundet.
            # Um die präziseren Originalkoordinaten für diese Indizes zu bekommen:
            if 'original_index' in df_simplified_with_index.columns and not df_simplified_with_index['original_index'].isnull().all():
                # Entferne Duplikate, die durch den Merge auf gerundeten Werten entstehen könnten, behalte ersten Treffer
                df_simplified_with_index.drop_duplicates(subset=['Longitude', 'Latitude'], keep='first', inplace=True)
                
                # Hole die präzisen Lat/Lon für die gefundenen Indizes
                # Zuerst NaNs im Index entfernen, falls der Merge nicht für alle geklappt hat
                valid_indices_df = df_simplified_with_index.dropna(subset=['original_index']).copy()
                valid_indices_df['original_index'] = valid_indices_df['original_index'].astype(int)

                # Erstelle den finalen DataFrame neu mit den präzisen Werten
                final_simplified_df = df_full.iloc[valid_indices_df['original_index'].values][['Latitude', 'Longitude']].copy()
                final_simplified_df['original_index'] = valid_indices_df['original_index'].values
                df_simplified_with_index = final_simplified_df.reset_index(drop=True)
            else: # Fallback, falls Indizes nicht zugeordnet werden konnten
                 print("[Warnung] Originalindizes konnten nicht zuverlässig zugeordnet werden. Speichere nur gerundete Lat/Lon.")
                 # In diesem Fall haben wir nur die gerundeten Koordinaten
                 df_simplified_with_index = df_simplified_coords_rounded[['Latitude', 'Longitude']].copy()


        # --- Start- und Endpunkt des Original-Tracks sicherstellen (mit Index) ---
        if not df_full.empty:
            start_orig_data = df_full.iloc[[0]].copy()
            start_orig_data['original_index'] = start_orig_data.index[0]
            
            end_orig_data = df_full.iloc[[-1]].copy()
            end_orig_data['original_index'] = end_orig_data.index[0]

            # Füge sie hinzu und entferne Duplikate basierend auf original_index
            df_simplified_with_index = pd.concat(
                [start_orig_data[['Latitude', 'Longitude', 'original_index']],
                 df_simplified_with_index, # df_simplified_with_index sollte schon 'original_index' haben, wenn erfolgreich
                 end_orig_data[['Latitude', 'Longitude', 'original_index']]],
                ignore_index=True
            )
            if 'original_index' in df_simplified_with_index.columns:
                df_simplified_with_index.drop_duplicates(subset=['original_index'], keep='first', inplace=True)
                df_simplified_with_index.sort_values(by='original_index', inplace=True)
            else: # Fallback, falls 'original_index' fehlt
                df_simplified_with_index.drop_duplicates(subset=['Latitude', 'Longitude'], keep='first', inplace=True)
            
            df_simplified_with_index.reset_index(drop=True, inplace=True)


        if df_simplified_with_index.empty:
            print("[Warnung] Simplifizierung führte zu leerem DataFrame.")
            # Notwendige Spalten für leeren Output
            cols_out = ['Latitude', 'Longitude', 'original_index']
            df_to_save = pd.DataFrame(columns=cols_out)
        else:
            output_cols = ['Latitude', 'Longitude']
            if 'original_index' in df_simplified_with_index.columns:
                output_cols.append('original_index')
                # Konvertiere original_index sicher zu Integer
                df_simplified_with_index['original_index'] = pd.to_numeric(df_simplified_with_index['original_index'], errors='coerce').astype('Int64')

            df_to_save = df_simplified_with_index[output_cols].copy()


        print(f"[Info] Endgültige Anzahl simplifizierter Punkte: {len(df_to_save)}")
        df_to_save.to_csv(output_simplified_csv, index=False, encoding='utf-8', float_format='%.6f')
        print(f"[OK] Vereinfachte API-Trackdaten mit Indizes gespeichert: {output_simplified_csv}")

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_full_track_csv}")
        pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index']).to_csv(output_simplified_csv, index=False) # Leere Datei
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler bei der Vereinfachung: {input_full_track_csv} - {e}")
        pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index']).to_csv(output_simplified_csv, index=False) # Leere Datei
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simplify track points from full CSV and keep original indices.")
    parser.add_argument("--input-csv", required=True, help="Path to the input full track data CSV (output of 2_parse_gpx_full.py).")
    parser.add_argument("--output", required=True, help="Path to save the simplified CSV (Lat, Lon, original_index).")
    parser.add_argument("--epsilon", type=float, default=0.0001, help="Epsilon value for RDP simplification (in degrees).")
    args = parser.parse_args()

    simplify_track_with_indexing(args.input_csv, args.output, args.epsilon)