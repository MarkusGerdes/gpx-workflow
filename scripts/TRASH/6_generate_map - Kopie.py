#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
6_generate_map.py
-----------------
Generates an interactive Folium map displaying the full GPX track
and relevant POIs (filtered by step 5c), with specific styling
for peaks and viewpoints.
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
import numpy as np # For checking NaN

# Helper function for Peak colors (can be moved to a shared utility file)
def get_color_by_elevation(elev_str):
    """Assigns color based on elevation string."""
    try:
        elev = float(elev_str)
        if elev >= 1500: return "darkred"
        elif elev >= 1000: return "red"
        elif elev >= 700: return "orange"
        elif elev >= 400: return "lightred" # Changed from orange
        elif elev >= 200: return "green"
        elif elev > 0: return "blue"
        else: return "gray" # For below 0 or invalid
    except (ValueError, TypeError):
        return "gray" # Return gray if elevation is not a valid number


def generate_map(track_csv_path: str, pois_csv_path: str,
                 reduced_track_csv_path: Optional[str],
                 output_html_path: str):
    """Generates the Folium map."""
    print(f"[Info] Generating map: {output_html_path}")

    try:
        output_dir = os.path.dirname(output_html_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)

        # Load Full Track Data
        track_df = pd.read_csv(track_csv_path)
        if not all(col in track_df.columns for col in ["Latitude", "Longitude"]):
             raise ValueError("Track CSV must contain 'Latitude' and 'Longitude'.")
        if track_df.empty: raise ValueError("Track CSV is empty.")

        # Load Relevant POIs Data
        pois_df = pd.DataFrame() # Default empty
        if pois_csv_path and os.path.exists(pois_csv_path):
            try:
                pois_df = pd.read_csv(pois_csv_path)
                if pois_df.empty: print("[Warnung] Relevante POI Datei ist leer.")
            elif not all(col in pois_df.columns for col in ["Latitude", "Longitude", "Typ", "Name"]):
                 print("[Warnung] POI CSV fehlen erwartete Spalten (Typ, Name). Darstellung könnte unvollständig sein.")
                 # Add missing columns if they don't exist to prevent errors later
                 for col in ["Typ", "Name", "Adresse", "Elevation", "Entfernung_m"]:
                      if col not in pois_df.columns: pois_df[col] = "N/A"


        except FileNotFoundError:
            print(f"[Warnung] Relevante POI Datei nicht gefunden: {pois_csv_path}. Karte wird ohne POIs erstellt.")
            pois_df = pd.DataFrame() # Empty DataFrame

    except Exception as e:
        print(f" Fehler beim Laden der Input-Dateien: {e}")
        sys.exit(1)

        reduced_points_df = pd.DataFrame() # Default empty
        if reduced_track_csv_path and os.path.exists(reduced_track_csv_path):
            try:
                reduced_points_df = pd.read_csv(reduced_track_csv_path)
                if not all(col in reduced_points_df.columns for col in ["Latitude", "Longitude"]):
                    print("[Warnung] Reduzierte Track-CSV hat nicht Lat/Lon. Marker werden nicht gezeichnet.")
                    reduced_points_df = pd.DataFrame() # Leeren, wenn Spalten fehlen
                elif reduced_points_df.empty:
                    print("[Info] Reduzierte Track-CSV ist leer.")
            except Exception as e:
                 print(f"[Warnung] Fehler beim Laden der reduzierten Track-CSV '{reduced_track_csv_path}': {e}")
        else:
            print("[Info] Keine reduzierte Track-CSV für Marker angegeben oder gefunden.")


    except Exception as e:
        print(f"❌ Fehler beim Laden der Input-Dateien: {e}")
        sys.exit(1)

    # Create map centered around track midpoint
    center_lat = track_df['Latitude'].mean()
    center_lon = track_df['Longitude'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    # Add Track PolyLine
    track_coords = track_df[['Latitude', 'Longitude']].values.tolist()
    folium.PolyLine(locations=track_coords, color='blue', weight=3, opacity=0.7, tooltip="Route").add_to(m)

    if not reduced_points_df.empty:
        reduced_points_group = folium.FeatureGroup(name="Reduzierte Punkte (API-Optimierung)", show=False).add_to(m) # Default: ausgeblendet
        print(f"[Info] Füge {len(reduced_points_df)} Marker für reduzierte Punkte hinzu...")
        for idx, row in reduced_points_df.iterrows():
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=3, # Kleinere Marker
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=0.6,
                tooltip=f"Reduzierter Punkt {idx}"
            ).add_to(reduced_points_group)

    # Add POIs with specific styling
    if not pois_df.empty:
        # --- Service POIs: Use Marker Cluster ---
        service_cluster = MarkerCluster(name="Service POIs").add_to(m)
        # Mapping for service icons (extend as needed)
        icon_mapping = {
            "drinking_water": ("tint", "blue"),
            "supermarket": ("shopping-cart", "orange"),
            "bicycle": ("bicycle", "darkblue"),
            "bakery": ("cutlery", "lightred"), # FontAwesome mapping needed for cutlery
            "restaurant": ("cutlery", "red"),   # FontAwesome mapping needed for cutlery
            "cafe": ("coffee", "purple"), # FontAwesome mapping needed for coffee
            "default": ("info-sign", "gray") # Default icon
        }

        # --- Peaks and Viewpoints: Add directly to map (no cluster) ---
        peaks_group = folium.FeatureGroup(name="Peaks").add_to(m)
        viewpoints_group = folium.FeatureGroup(name="Viewpoints").add_to(m)

        for idx, row in pois_df.iterrows():
            lat = row["Latitude"]
            lon = row["Longitude"]
            poi_type = str(row.get("Typ", "unbekannt")).lower()
            name = str(row.get("Name", "Unbenannt"))
            # Handle potential NaN or None values gracefully
            address = str(row.get("Adresse", "N/A")) if pd.notna(row.get("Adresse")) else "N/A"
            elevation = str(row.get("Elevation", "N/A")) if pd.notna(row.get("Elevation")) else "N/A"
            distance = int(row.get("Entfernung_m", -1)) if pd.notna(row.get("Entfernung_m")) else -1

            popup_html = f"<b>{name}</b> ({poi_type.capitalize()})<br>"
            if address != "N/A": popup_html += f"Adresse: {address}<br>"
            if elevation != "N/A": popup_html += f"Höhe: {elevation} m<br>"
            if distance != -1: popup_html += f"Entfernung zur Route: {distance} m"

            # --- Styling based on Type ---
            if poi_type == "peak":
                color = get_color_by_elevation(elevation)
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{name} ({elevation}m)"
                ).add_to(peaks_group) # Add to specific group

            elif poi_type == "viewpoint":
                 folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{name} (Viewpoint)",
                    # Use FontAwesome icon for eye
                    icon=folium.Icon(color="cadetblue", icon="eye", prefix="fa")
                ).add_to(viewpoints_group) # Add to specific group

            else: # Default: Service POIs -> Cluster
                icon_name = "info-sign" # default glyphicon
                icon_color = "gray" # default color
                prefix = "glyphicon" # default prefix

                # Find appropriate icon from mapping
                found_icon = False
                for key, (i_name, i_color) in icon_mapping.items():
                     if key in poi_type:
                         # Check prefix needed (FontAwesome vs Glyphicon)
                         if i_name in ["cutlery", "coffee", "bicycle", "tint"]: # Add other fa icons here
                              prefix = "fa"
                         else:
                              prefix = "glyphicon"
                         icon_name = i_name
                         icon_color = i_color
                         found_icon = True
                         break
                if not found_icon:
                     icon_name, icon_color = icon_mapping["default"]
                     prefix = "glyphicon"


                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{name} ({poi_type})",
                    icon=folium.Icon(icon=icon_name, prefix=prefix, color=icon_color)
                ).add_to(service_cluster) # Add to cluster group

    # Add Layer Control to toggle groups/layers
    folium.LayerControl().add_to(m)

    # Fit map bounds to the track
    m.fit_bounds([[track_df['Latitude'].min(), track_df['Longitude'].min()],
                  [track_df['Latitude'].max(), track_df['Longitude'].max()]])

    # Save map
    try:
        m.save(output_html_path)
        print(f"[OK] Interaktive Karte gespeichert: {output_html_path}")
    except Exception as e:
        print(f" Fehler beim Speichern der Karte: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an interactive Folium map with GPX track and relevant POIs.")
    parser.add_argument("--track-csv", required=True, help="Path to the full track data CSV file.")
    parser.add_argument("--pois-csv", required=True, help="Path to the relevant POIs CSV file.")
    parser.add_argument("--output-html", required=True, help="Path to save the output HTML map file.")
    args = parser.parse_args()

    generate_map(args.track_csv, args.pois_csv, args.output_html)