#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
6_generate_map.py (V2 - Korrigiert)
-----------------
Generates an interactive Folium map displaying:
1. The full GPX track.
2. Relevant POIs (filtered by step 5c).
3. Markers for the simplified track points (from step 2b).
"""

import sys
import os
import argparse
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import numpy as np
from typing import Optional # Optional importieren

# Helper function for Peak colors
def get_color_by_elevation(elev_str):
    """Assigns color based on elevation string."""
    try:
        elev = float(elev_str)
        if elev >= 1500: return "darkred"
        elif elev >= 1000: return "red"
        elif elev >= 700: return "orange"
        elif elev >= 400: return "lightred"
        elif elev >= 200: return "green"
        elif elev > 0: return "blue"
        else: return "gray"
    except (ValueError, TypeError):
        return "gray"


def generate_map(track_csv_path: str, pois_csv_path: str,
                 reduced_track_csv_path: Optional[str], # Optional hinzugefügt
                 output_html_path: str):
    """Generates the Folium map."""
    print(f"[Info] Generating map: {output_html_path}")

    # Initialize DataFrames
    track_df = pd.DataFrame()
    pois_df = pd.DataFrame()
    reduced_points_df = pd.DataFrame()

    try: # Erster Try-Block für Haupt-Daten
        output_dir = os.path.dirname(output_html_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)

        # Load Full Track Data
        track_df = pd.read_csv(track_csv_path)
        if not all(col in track_df.columns for col in ["Latitude", "Longitude"]):
             raise ValueError("Track CSV must contain 'Latitude' and 'Longitude'.")
        if track_df.empty: raise ValueError("Track CSV is empty.")

        # Load Relevant POIs Data
        if pois_csv_path and os.path.exists(pois_csv_path):
            try:
                pois_df = pd.read_csv(pois_csv_path)
                if pois_df.empty: print("[Warnung] Relevante POI Datei ist leer.")
                # Spaltenprüfung und -ergänzung für POIs
                required_poi_cols = ["Latitude", "Longitude", "Typ", "Name"]
                if not all(col in pois_df.columns for col in required_poi_cols):
                     print(f"[Warnung] POI CSV fehlen Spalten: {required_poi_cols}. Darstellung könnte unvollständig sein.")
                     for col_to_add in ["Typ", "Name", "Adresse", "Elevation", "Entfernung_m"]:
                          if col_to_add not in pois_df.columns: pois_df[col_to_add] = "N/A"
            except Exception as e_poi: # Spezifischere Exception für POI-Datei
                print(f"[Warnung] Fehler beim Laden der POI-CSV '{pois_csv_path}': {e_poi}. Karte wird ohne POIs erstellt.")
                pois_df = pd.DataFrame() # Sicherstellen, dass es ein leerer DF ist
        else:
            print(f"[Warnung] POI-CSV nicht angegeben oder nicht gefunden: {pois_csv_path}. Karte wird ohne POIs erstellt.")
            # pois_df ist bereits als leerer DF initialisiert

    except Exception as e_main: # Fängt Fehler vom Track-Laden ab
        print(f" Fehler beim Laden der Haupt-Input-Dateien: {e_main}")
        sys.exit(1)


    # --- KORREKTUR: Laden der reduzierten Punkte AUSSERHALB des ersten try-except ---
    # NEU: Load Reduced Track Points Data (optional)
    if reduced_track_csv_path and os.path.exists(reduced_track_csv_path):
        try:
            reduced_points_df = pd.read_csv(reduced_track_csv_path)
            if not all(col in reduced_points_df.columns for col in ["Latitude", "Longitude"]):
                print("[Warnung] Reduzierte Track-CSV hat nicht Lat/Lon. Marker werden nicht gezeichnet.")
                reduced_points_df = pd.DataFrame()
            elif reduced_points_df.empty:
                print("[Info] Reduzierte Track-CSV ist leer.")
        except Exception as e_reduced:
             print(f"[Warnung] Fehler beim Laden der reduzierten Track-CSV '{reduced_track_csv_path}': {e_reduced}")
             reduced_points_df = pd.DataFrame() # Sicherstellen, dass es ein leerer DF ist
    else:
        print("[Info] Keine reduzierte Track-CSV für Marker angegeben oder gefunden.")
    # --------------------------------------------------------------------------------

    # Create map centered around track midpoint
    # Stelle sicher, dass track_df nicht leer ist, bevor auf .mean() zugegriffen wird
    if track_df.empty:
        print(" Track-Daten sind leer, Karte kann nicht zentriert werden.")
        # Erstelle eine Dummy-Karte oder beende mit Fehler
        m = folium.Map(location=[0,0], zoom_start=2) # Dummy-Karte
        try:
            m.save(output_html_path); print(f"[OK] Dummy-Karte gespeichert: {output_html_path}")
        except Exception as e_save: print(f" Fehler beim Speichern der Dummy-Karte: {e_save}")
        sys.exit(1) # Beende, da keine sinnvolle Karte erstellt werden kann

    center_lat = track_df['Latitude'].mean()
    center_lon = track_df['Longitude'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    # Add Track PolyLine
    track_coords = track_df[['Latitude', 'Longitude']].values.tolist()
    folium.PolyLine(locations=track_coords, color='blue', weight=3, opacity=0.7, tooltip="Route").add_to(m)

    # --- NEU: Add Markers for Reduced Track Points ---
    if not reduced_points_df.empty:
        reduced_points_group = folium.FeatureGroup(name="Reduzierte Punkte (API-Optimierung)", show=True).add_to(m)
        print(f"[Info] Füge {len(reduced_points_df)} Marker für reduzierte Punkte hinzu...")
        for idx, row in reduced_points_df.iterrows():
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=2, color='orange', fill=True, fill_color='yellow',
                stroke=True, weight=1,
                fill_opacity=0.8, tooltip=f"Reduzierter Punkt {idx}"
            ).add_to(reduced_points_group)
    # -----------------------------------------------

    # Add POIs with specific styling
    if not pois_df.empty:
        service_cluster = MarkerCluster(name="Service POIs").add_to(m)
        icon_mapping = {
            "drinking_water": ("tint", "blue"), "supermarket": ("shopping-cart", "orange"),
            "bicycle": ("bicycle", "darkblue"), "bakery": ("cutlery", "lightred"),
            "restaurant": ("cutlery", "red"), "cafe": ("coffee", "purple"),
            "default": ("info-sign", "gray")
        }
        peaks_group = folium.FeatureGroup(name="Peaks").add_to(m)
        viewpoints_group = folium.FeatureGroup(name="Viewpoints").add_to(m)

        for idx, row in pois_df.iterrows():
            try: # Füge try-except für jede Zeile hinzu, um robust zu sein
                lat = row["Latitude"]; lon = row["Longitude"]
                poi_type = str(row.get("Typ", "unbekannt")).lower()
                name = str(row.get("Name", "Unbenannt"))
                address = str(row.get("Adresse", "N/A")) if pd.notna(row.get("Adresse")) else "N/A"
                elevation = str(row.get("Elevation", "N/A")) if pd.notna(row.get("Elevation")) else "N/A"
                distance = int(row.get("Entfernung_m", -1)) if pd.notna(row.get("Entfernung_m")) else -1

                popup_html = f"<b>{name}</b> ({poi_type.capitalize()})<br>"
                if address != "N/A": popup_html += f"Adresse: {address}<br>"
                if elevation != "N/A" and elevation != "nan": popup_html += f"Höhe: {elevation} m<br>"
                if distance != -1: popup_html += f"Entfernung zur Route: {distance} m"

                if poi_type == "peak":
                    color = get_color_by_elevation(elevation)
                    folium.CircleMarker(location=[lat, lon], radius=6, color=color, fill=True, fill_color=color, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=300), tooltip=f"{name} ({elevation}m)").add_to(peaks_group)
                elif poi_type == "viewpoint":
                    folium.Marker(location=[lat, lon], popup=folium.Popup(popup_html, max_width=300), tooltip=f"{name} (Viewpoint)", icon=folium.Icon(color="cadetblue", icon="eye", prefix="fa")).add_to(viewpoints_group)
                else: # Default: Service POIs -> Cluster
                    icon_name, icon_color, prefix = "info-sign", "gray", "glyphicon"
                    found_icon = False
                    for key, (i_name, i_color) in icon_mapping.items():
                         if key in poi_type:
                             prefix = "fa" if i_name in ["cutlery", "coffee", "bicycle", "tint", "shopping-cart", "eye"] else "glyphicon" # Erweitere FA-Liste
                             icon_name, icon_color = i_name, i_color; found_icon = True; break
                    if not found_icon: icon_name, icon_color = icon_mapping["default"]; prefix = "glyphicon"
                    folium.Marker(location=[lat, lon], popup=folium.Popup(popup_html, max_width=300), tooltip=f"{name} ({poi_type})", icon=folium.Icon(icon=icon_name, prefix=prefix, color=icon_color)).add_to(service_cluster)
            except Exception as e_row:
                print(f"[Warnung] Fehler beim Verarbeiten eines POIs (Index {idx}): {e_row}")
                continue # Nächsten POI versuchen

    # Add Layer Control to toggle groups/layers
    folium.LayerControl().add_to(m)

    # Fit map bounds to the track
    if not track_df.empty: # Nur wenn Track-Daten vorhanden sind
        m.fit_bounds([[track_df['Latitude'].min(), track_df['Longitude'].min()],
                      [track_df['Latitude'].max(), track_df['Longitude'].max()]])

    # Save map
    try:
        m.save(output_html_path)
        print(f"[OK] Interaktive Karte gespeichert: {output_html_path}")
    except Exception as e_save:
        print(f" Fehler beim Speichern der Karte: {e_save}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Folium map with full track, POIs, and optional reduced track markers.")
    parser.add_argument("--track-csv", required=True, help="Path to the full track data CSV file.")
    parser.add_argument("--pois-csv", required=True, help="Path to the relevant POIs CSV file.")
    # KORREKTUR: Argument zum Parser hinzufügen
    parser.add_argument("--reduced-track-csv", help="Optional: Path to the simplified track points CSV.")
    parser.add_argument("--output-html", required=True, help="Path to save the output HTML map file.")
    args = parser.parse_args()

    # KORREKTUR: Argument an Funktion übergeben
    generate_map(args.track_csv, args.pois_csv, args.reduced_track_csv, args.output_html)