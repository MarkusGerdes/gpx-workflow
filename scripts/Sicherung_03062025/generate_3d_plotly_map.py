#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_3d_plotly_map.py
-------------------------
Generates an interactive 3D plot of a GPX track using Plotly.
Allows for vertical exaggeration and colors track segments by surface type.
"""

SCRIPT_NAME = "generate_3d_plotly_map.py"
SCRIPT_VERSION = "1.1.2" # Einführung einer Versionskontrolle, lauffaehiges Script, vertikaler Linien Test

import sys
import os
import argparse
import yaml 
import numpy as np
import pandas as pd
import plotly 
import plotly.graph_objects as go
from typing import Optional

print(f"[DEBUG] Skript gestartet. Python-Version: {sys.version}", file=sys.stderr)
print(f"[DEBUG] Pandas-Version: {pd.__version__}", file=sys.stderr)
print(f"[DEBUG] Plotly-Version: {plotly.__version__}", file=sys.stderr)

# Deine SURFACE_COLOR_MAP von 6_generate_map.py oder aus config.yaml
# Stelle sicher, dass sie hier verfügbar ist
# -----------------------------------------------------------------------------
# STANDARD-FARBKARTE: Diese wird verwendet, wenn keine YAML geladen wird
# ODER wenn die YAML-Datei/der Schlüssel nicht gefunden wird.
# !!! WICHTIG: Diese Map sollte mit den Farben aus deiner config.yaml
# !!! (Abschnitt surface_colors) ÜBEREINSTIMMEN, wenn du Konsistenz willst
# !!! und die YAML-Ladefunktion nicht nutzt oder sie fehlschlägt.
# -----------------------------------------------------------------------------
DEFAULT_SURFACE_COLOR_MAP: dict[str, str] = {
    # Befestigte Oberflächen (Grau-/Schwarztöne) - ABGELEICHNET MIT DEINER config.yaml
    "asphalt": "#212529",
    "paved": "#6c757d",
    "concrete": "#adb5bd",
    "paving_stones": "#78909C",
    "sett": "#546E7A",
    "cobblestone": "#A1887F",

    # Gravel & Lose Oberflächen - ABGELEICHNET MIT DEINER config.yaml
    "gravel": "#FF8F00",
    "fine_gravel": "#FFCA28",
    "compacted": "#795548",
    "dirt": "#8D6E63",
    "ground": "#689F38",
    "unpaved": "#4E342E",
    "sand": "#FFF176",

    # Andere - ABGELEICHNET MIT DEINER config.yaml
    "grass": "#7CB342",
    "wood": "#BCAAA4",

    # Fallbacks & Spezielles
    "unknown": "#E0E0E0",       # Farbe für 'unknown' aus deiner config.yaml
    "default": "#D32F2F",       # Farbe für 'default' aus deiner config.yaml
    "none_found_in_radius": "#E0E0E0", # Gleich wie unknown
    "none_selected_from_candidates": "#E0E0E0",
    "api_query_failed": "#E0E0E0",
}

# --- NEU: Farb- und Symboldefinitionen für POIs ---
# HIER MUSS POI_STYLES DEFINIERT WERDEN
POI_STYLES: dict[str, dict[str, any]] = {
    "peak": {"color": "saddlebrown", "symbol": "diamond", "size": 2, "name": "Peaks"},
    "viewpoint": {"color": "darkviolet", "symbol": "cross", "size": 3, "name": "Viewpoints"}, 
    "place": {"color": "blue", "symbol": "square", "size": 3, "name": "Orte"},
    "city": {"color": "darkblue", "symbol": "square-open", "size": 3, "name": "Städte"}, 
    "town": {"color": "blue", "symbol": "square", "size": 3, "name": "Ortschaften"},
    "village": {"color": "cadetblue", "symbol": "square-open", "size": 3, "name": "Dörfer"},
    "drinking_water": {"color": "dodgerblue", "symbol": "circle", "size": 3, "name": "Wasserstellen"},
    "supermarket": {"color": "orange", "symbol": "circle-open", "size": 2, "name": "Supermärkte"}, # Geändert
    "bakery": {"color": "lightsalmon", "symbol": "circle", "size": 2, "name": "Bäckereien"}, # Geändert
    "restaurant": {"color": "firebrick", "symbol": "diamond-open", "size": 2, "name": "Restaurants"}, # Geändert
    "cafe": {"color": "chocolate", "symbol": "diamond", "size": 2, "name": "Cafés"}, # Geändert
    "bicycle": {"color": "darkgreen", "symbol": "cross", "size": 3, "name": "Fahrradläden"}, # Geändert
    "default_poi": {"color": "grey", "symbol": "circle", "size": 2, "name": "Andere POIs"} # Geändert
}
# --- ENDE NEUE DEFINITION ---

def load_surface_colors_from_yaml(yaml_path: Optional[str]) -> dict[str, str]:
    """
    Lädt die Oberflächenfarben aus einer YAML-Datei.
    Verwendet DEFAULT_SURFACE_COLOR_MAP als Fallback.
    """
    if yaml_path and os.path.exists(yaml_path):
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # Annahme: Farben sind unter 'surface_colors' in der YAML
                loaded_colors = config.get("surface_colors")
                if isinstance(loaded_colors, dict):
                    print(f"[INFO] Oberflächenfarben erfolgreich aus YAML geladen: {yaml_path}", file=sys.stderr)
                    # Stelle sicher, dass 'default' und 'unknown' vorhanden sind, falls nicht in YAML
                    if 'default' not in loaded_colors:
                        loaded_colors['default'] = DEFAULT_SURFACE_COLOR_MAP.get('default', 'red')
                    if 'unknown' not in loaded_colors:
                        loaded_colors['unknown'] = DEFAULT_SURFACE_COLOR_MAP.get('unknown', 'lightgray')
                    return loaded_colors
                else:
                    print(f"[WARNUNG] 'surface_colors' Schlüssel in YAML nicht gefunden oder kein Dictionary: {yaml_path}. Verwende Standardfarben.", file=sys.stderr)
        except Exception as e:
            print(f"[WARNUNG] Fehler beim Laden der Farben aus YAML ({yaml_path}): {e}. Verwende Standardfarben.", file=sys.stderr)
    else:
        if yaml_path: # Pfad wurde gegeben, aber Datei nicht gefunden
            print(f"[WARNUNG] YAML-Datei für Oberflächenfarben nicht gefunden: {yaml_path}. Verwende Standardfarben.", file=sys.stderr)
        # else: Kein Pfad gegeben, Standardfarben werden sowieso verwendet.

    return DEFAULT_SURFACE_COLOR_MAP # Fallback

def get_color_by_elevation(elev_val: Optional[float], default_color="gray"):
    """Assigns color based on elevation value."""
    if pd.isna(elev_val): return default_color
    try:
        elev = float(elev_val)
        if elev >= 1500: return POI_STYLES.get("peak", {}).get("color", "darkred") # Nutze Peak Farbe
        elif elev >= 1000: return "red"
        elif elev >= 700: return "orange"
        elif elev >= 400: return "salmon"
        elif elev >= 200: return "green"
        elif elev > 0: return "blue" # Für niedrige Peaks/Hügel
        else: return default_color
    except (ValueError, TypeError):
        return default_color

def create_3d_plotly_track_with_pois( # Name angepasst
    track_csv_path: str,
    pois_csv_path: str, # NEU: Pfad zur relevanten POI-Datei (5c Output)
    places_csv_path: str, # NEU: Pfad zur relevanten Orte-Datei (8c Output)
    output_html_path: str,
    vertical_exaggeration: float = 1.0,
    plot_title_prefix: str = "Interaktive 3D GPX-Strecke",
    default_line_width: int = 4,
    surface_colors_yaml_path: Optional[str] = None
):
    active_surface_color_map = load_surface_colors_from_yaml(surface_colors_yaml_path)
    print(f"[DEBUG] Funktion create_3d_plotly_track_with_pois gestartet.", file=sys.stderr)
    print(f"[Info] Generating 3D Plotly map for: {track_csv_path}")
    print(f"  POIs from: {pois_csv_path}")
    print(f"  Places from: {places_csv_path}")
    print(f"  Vertical Exaggeration: {vertical_exaggeration}")

    df_track = pd.DataFrame()
    df_pois_all = pd.DataFrame() # Für POIs aus 5c
    df_places_enriched = pd.DataFrame() # Für Orte aus 8c

    try:
        # --- Track-Daten laden ---
        print(f"[DEBUG] Stage 1: Vor dem Laden von df_track: {track_csv_path}", file=sys.stderr)
        df_track = pd.read_csv(track_csv_path, comment='#')
        print(f"[DEBUG] Stage 2: df_track geladen, {len(df_track)} Zeilen.", file=sys.stderr)        
        # ... (Datenbereinigung für df_track wie in deiner letzten funktionierenden Version) ...
        if df_track.empty: # Frühzeitiger Ausstieg, wenn Track leer ist
            # ... (leere HTML schreiben und exit(0)) ...
            raise ValueError("Track CSV ist leer oder enthält keine gültigen Daten nach Bereinigung.")

        required_track_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Surface']
        if 'Elevation_m' in df_track.columns and 'Elevation (m)' not in df_track.columns:
            df_track.rename(columns={'Elevation_m': 'Elevation (m)'}, inplace=True)
        if not all(col in df_track.columns for col in required_track_cols):
            missing = [col for col in required_track_cols if col not in df_track.columns]
            raise ValueError(f"Track CSV fehlt Spalten: {missing}. Gefunden: {df_track.columns.tolist()}")

        for col in ['Latitude', 'Longitude', 'Elevation (m)']:
            df_track[col] = pd.to_numeric(df_track[col], errors='coerce')
        df_track['Surface'] = df_track['Surface'].fillna('unknown').astype(str).str.lower()
        df_track.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)

        if 'original_index' in df_track.columns:
            df_track['original_index'] = pd.to_numeric(df_track['original_index'], errors='coerce')
            df_track.dropna(subset=['original_index'], inplace=True)
            if not df_track.empty: df_track.sort_values(by='original_index', inplace=True)
            df_track.reset_index(drop=True, inplace=True)
        
        if df_track.empty:
            print(f"[DEBUG] Stage X: df_track ist nach pd.read_csv leer.", file=sys.stderr)
            raise ValueError("Track CSV ist leer oder enthält keine gültigen Daten nach Bereinigung.")
        print(f"[DEBUG] Track-Daten erfolgreich geladen. {len(df_track)} Punkte.", file=sys.stderr)

        # --- POI-Daten laden (aus 5c) ---
        if pois_csv_path and os.path.exists(pois_csv_path):
            print(f"[DEBUG] Lade POI-CSV: {pois_csv_path}", file=sys.stderr)
            df_pois_all = pd.read_csv(pois_csv_path, comment='#')
            # Benötigte Spalten: Latitude, Longitude, Typ, Name, Elevation (finale Höhe)
            # Stelle sicher, dass 'Elevation' die finale, angereicherte Höhe ist
            for col in ['Latitude', 'Longitude', 'Elevation']: # 'Elevation' sollte die finale sein
                if col in df_pois_all.columns:
                    df_pois_all[col] = pd.to_numeric(df_pois_all[col], errors='coerce')
            df_pois_all.dropna(subset=['Latitude', 'Longitude', 'Elevation'], inplace=True) # Nur POIs mit Geo-Daten und Höhe
            df_pois_all['Typ'] = df_pois_all['Typ'].fillna('unknown').astype(str).str.lower()
            df_pois_all['Name'] = df_pois_all['Name'].fillna('Unbenannter POI')
            df_pois_all = df_pois_all[df_pois_all['Name'] != 'Unbenannter POI'].copy()            
            print(f"[DEBUG] POI-Daten (5c) geladen. {len(df_pois_all)} POIs nach Filterung.", file=sys.stderr)            
        else:
            print(f"[WARNUNG] POI-Datei (5c) nicht gefunden: {pois_csv_path}", file=sys.stderr)

        # --- Orte-Daten laden (aus 8c) ---
        if places_csv_path and os.path.exists(places_csv_path):
            print(f"[DEBUG] Lade Orte-CSV: {places_csv_path}", file=sys.stderr)
            df_places_enriched = pd.read_csv(places_csv_path, comment='#')
            # Benötigte Spalten: Ort (Name), Latitude_Center, Longitude_Center, Nächster_Punkt_Hoehe_m
            for col in ['Latitude_Center', 'Longitude_Center', 'Nächster_Punkt_Hoehe_m']:
                if col in df_places_enriched.columns:
                    df_places_enriched[col] = pd.to_numeric(df_places_enriched[col], errors='coerce')
            df_places_enriched.dropna(subset=['Latitude_Center', 'Longitude_Center', 'Nächster_Punkt_Hoehe_m'], inplace=True)
            df_places_enriched['Ort'] = df_places_enriched['Ort'].fillna('Unbenannter Ort')
            df_places_enriched = df_places_enriched[df_places_enriched['Ort'] != 'Unbenannter Ort'].copy()            
            print(f"[DEBUG] Orte-Daten (8c) geladen. {len(df_places_enriched)} Orte nach Filterung.", file=sys.stderr)
        else:
            print(f"[WARNUNG] Orte-Datei (8c) nicht gefunden: {places_csv_path}", file=sys.stderr)

    except FileNotFoundError as fnf_err:
        # ... (Fehlerbehandlung) ...
        sys.exit(1)
    except ValueError as val_err:
        # ... (Fehlerbehandlung) ...
        sys.exit(1)
    except Exception as e:
        # ... (Fehlerbehandlung) ...
        sys.exit(1)

    # --- Plot-Erstellung ---
    df_track['Elevation_Exaggerated'] = df_track['Elevation (m)'] * vertical_exaggeration
    min_original_elevation = df_track['Elevation (m)'].min()
    max_original_elevation = df_track['Elevation (m)'].max()

    fig = go.Figure()

    # --- Track-Liniensegmente (Korrigiert) ---
    legend_added_surfaces = set()
    df_track['surface_block'] = (df_track['Surface'] != df_track['Surface'].shift()).cumsum()
    last_point_data_for_connection = None
    for block_id, segment_data_orig in df_track.groupby('surface_block'):
        if segment_data_orig.empty: continue
        current_segment_data = segment_data_orig.copy()
        current_surface_type = current_segment_data['Surface'].iloc[0]
        if last_point_data_for_connection is not None:
            if not (last_point_data_for_connection['Longitude'] == current_segment_data['Longitude'].iloc[0] and \
                    last_point_data_for_connection['Latitude'] == current_segment_data['Latitude'].iloc[0]):
                connection_point_values = last_point_data_for_connection.to_dict()
                connection_point_values['Surface'] = current_surface_type
                connection_df = pd.DataFrame([connection_point_values])
                current_segment_data = pd.concat([connection_df, current_segment_data], ignore_index=True)
        if len(current_segment_data) < 2:
            if not segment_data_orig.empty: last_point_data_for_connection = segment_data_orig.iloc[-1].copy()
            continue
        
        segment_color = active_surface_color_map.get(current_surface_type, active_surface_color_map.get('default', 'fuchsia'))
        dist_col_name = next((col for col in ['Distanz (km)', 'Distanz_km_orig_track'] if col in current_segment_data.columns), None)
        hover_texts_track = [ f"Surface: {str(r.get('Surface','N/A')).capitalize()}<br>Lat: {r['Latitude']:.4f}<br>Lon: {r['Longitude']:.4f}<br>Höhe: {r['Elevation (m)']:.1f} m (orig.)<br>Dist: {r.get(dist_col_name, 0.0):.2f} km" for _, r in current_segment_data.iterrows()]            
       
        # KORREKTER TRACE FÜR TRACK-SEGMENTE
        fig.add_trace(go.Scatter3d(
            x=current_segment_data['Longitude'],
            y=current_segment_data['Latitude'],
            z=current_segment_data['Elevation_Exaggerated'],
            mode='lines',
            line=dict(color=segment_color, width=default_line_width),
            hoverinfo='text',
            hovertext=hover_texts_track, # Verwende die Hovertexte für den Track
            name=current_surface_type.capitalize() if current_surface_type not in legend_added_surfaces else '',
            showlegend=(current_surface_type not in legend_added_surfaces)
        ))
        
        if current_surface_type not in legend_added_surfaces: legend_added_surfaces.add(current_surface_type)
        if not segment_data_orig.empty: last_point_data_for_connection = segment_data_orig.iloc[-1].copy()

    # --- HIER DEN CODE FÜR VERTIKALE LINIEN EINFÜGEN ---
    # Annahme: 'df_track' ist der DataFrame, der den gesamten Track enthält
    # und die Spalten 'Longitude', 'Latitude', 'Elevation (m)' (Originalhöhe)
    # und 'Elevation_Exaggerated' (bereits überhöhte Höhe für den Plot) besitzt.

    x_lines = []
    y_lines = []
    z_lines = []

    if not df_track.empty: 
        for i in range(0, len(df_track), 1): # Iteriere über jeden Punkt des gesamten Tracks
            point = df_track.iloc[i]
            lon = point['Longitude']
            lat = point['Latitude']
            # Verwende die bereits überhöhte Höhe für die Spitze der Linie,
            # da die Hauptstrecke auch mit dieser Höhe gezeichnet wird.
            z_top = point['Elevation_Exaggerated'] 
            z_bottom = 0  # Basis der Linie auf Z=0 
                          # ODER min_original_elevation * vertical_exaggeration wenn die Szene höher anfängt
                          # ODER eine feste Basishöhe, die sinnvoll ist

            x_lines.extend([lon, lon, None]) 
            y_lines.extend([lat, lat, None])
            z_lines.extend([z_top, z_bottom, None])

        if x_lines: 
            fig.add_trace(go.Scatter3d(
                x=x_lines,
                y=y_lines,
                z=z_lines,
                mode='lines',
                line=dict(color='rgba(150, 150, 150, 1.0)', width=1, dash='dash'), # Etwas dunkleres Grau, gestrichelt
                hoverinfo='none',
                showlegend=False,
                name='Höhenschraffur (Test)' 
            ))
    # --- ENDE DES CODES FÜR VERTIKALE LINIEN ---

    # --- Start- und Endpunkte des Tracks (wie vorher) ---
    # ... (dein Code für Start-/Endpunkte) ...
    if not df_track.empty:
        fig.add_trace(go.Scatter3d(x=[df_track['Longitude'].iloc[0]], y=[df_track['Latitude'].iloc[0]], z=[df_track['Elevation_Exaggerated'].iloc[0]], mode='markers', marker=dict(size=2, color='green', symbol='circle-open', line=dict(width=2, color='DarkGreen')), name='Start', hovertext=f"Start<br>Höhe: {df_track['Elevation (m)'].iloc[0]:.1f} m", hoverinfo="text"))
        if len(df_track) > 1:
            fig.add_trace(go.Scatter3d(x=[df_track['Longitude'].iloc[-1]], y=[df_track['Latitude'].iloc[-1]], z=[df_track['Elevation_Exaggerated'].iloc[-1]], mode='markers', marker=dict(size=4, color='darkred', symbol='x', line=dict(width=2, color='DarkRed')), name='Ende', hovertext=f"Ende<br>Höhe: {df_track['Elevation (m)'].iloc[-1]:.1f} m", hoverinfo="text"))

        fig.add_trace(go.Scatter3d(
            x=current_segment_data['Longitude'],       # Verwende current_segment_data
            y=current_segment_data['Latitude'],        # Verwende current_segment_data
            z=current_segment_data['Elevation_Exaggerated'], # Verwende current_segment_data
            mode='lines',                              # Modus ist 'lines' für den Track
            line=dict(color=segment_color, width=default_line_width), # Linienstil
            hoverinfo='text',
            hovertext=hover_texts_track,
            name=current_surface_type.capitalize() if current_surface_type not in legend_added_surfaces else '',
            showlegend=(current_surface_type not in legend_added_surfaces)
        ))

# --- POIs (aus 5c) hinzufügen ---
    if not df_pois_all.empty:
        desired_poi_types = ["peak", "viewpoint", "drinking_water"] # Die Typen, die generell geplottet werden sollen
        
        df_pois_to_plot = df_pois_all[df_pois_all['Typ'].isin(desired_poi_types)].copy()
        print(f"[DEBUG] Anzahl POIs nach Filterung auf gewünschte Typen: {len(df_pois_to_plot)}", file=sys.stderr)

        if not df_pois_to_plot.empty:
            poi_types_in_filtered_data = df_pois_to_plot['Typ'].unique()
            print(f"[DEBUG] Zu zeichnende POI-Typen (nach DataFrame-Filter): {poi_types_in_filtered_data}", file=sys.stderr)

            for poi_type in poi_types_in_filtered_data:
                df_subset = df_pois_to_plot[df_pois_to_plot['Typ'] == poi_type].copy()
                if df_subset.empty:
                    continue

                # Stelle sicher, dass die 'Elevation' Spalte numerisch ist und fülle NaNs für die Plot-Höhe
                # Es ist besser, 'Elevation_Plot' direkt aus der Originalhöhe zu berechnen
                # und NaNs in 'Elevation' vorher zu behandeln oder Zeilen ohne Höhe zu überspringen.
                if 'Elevation' not in df_subset.columns or df_subset['Elevation'].isnull().all():
                    print(f"[WARNUNG] Keine gültigen Höhen für POI-Typ '{poi_type}' gefunden. Überspringe das Zeichnen dieses Typs.", file=sys.stderr)
                    continue
                
                # Entferne Zeilen, wo Elevation NaN ist, bevor 'Elevation_Plot' berechnet wird, um Fehler zu vermeiden
                df_subset.dropna(subset=['Elevation'], inplace=True)
                if df_subset.empty: # Nochmals prüfen, falls alle Zeilen NaN Elevation hatten
                    print(f"[WARNUNG] Alle POIs vom Typ '{poi_type}' hatten NaN Elevation. Überspringe.", file=sys.stderr)
                    continue

                df_subset['Elevation_Plot'] = df_subset['Elevation'] * vertical_exaggeration

                style = POI_STYLES.get(poi_type, POI_STYLES["default_poi"])
                
                hover_texts_poi = [f"<b>{name}</b> ({typ.capitalize()})<br>Höhe: {elev:.0f} m (orig.)"
                                   for name, typ, elev in zip(df_subset['Name'], df_subset['Typ'], df_subset['Elevation'])]

                # POI-Marker zeichnen
                fig.add_trace(go.Scatter3d(
                    x=df_subset['Longitude'],
                    y=df_subset['Latitude'],
                    z=df_subset['Elevation_Plot'], # Überhöhte Position für Marker
                    mode='markers' + ('+text' if poi_type in ["peak", "viewpoint"] else ''),
                    marker=dict(
                        size=style["size"],
                        color=get_color_by_elevation(df_subset['Elevation'].mean(), style["color"]) if poi_type == "peak" else style["color"],
                        symbol=style.get("symbol", "square")
                    ),
                    text=df_subset['Name'] if poi_type in ["peak", "viewpoint"] else None,
                    textposition="top center",
                    textfont=dict(size=9, color=style.get("color", "black")), # Farbe des Textes kann auch aus style kommen
                    hoverinfo='text',
                    hovertext=hover_texts_poi,
                    name=style["name"],
                    visible=True 
                ))

                # --- VERTIKALE LINIEN FÜR DEN AKTUELLEN POI-TYP HINZUFÜGEN ---
                x_poi_lines = []
                y_poi_lines = []
                z_poi_lines = []
                
                # Entscheide, für welche Typen Linien gezeichnet werden sollen und welche Farbe sie haben
                draw_lines_for_this_type = False
                line_color_rgba = None

                if poi_type == "peak":
                    draw_lines_for_this_type = True
                    line_color_rgba = 'rgba(139, 69, 19, 0.4)' # Halbtransparentes Braun
                elif poi_type == "viewpoint":
                    draw_lines_for_this_type = True # Optional: auch für Viewpoints
                    line_color_rgba = 'rgba(75, 0, 130, 0.4)' # Halbtransparentes Dunkelviolett (Indigo)
                # elif poi_type == "drinking_water": # Optional: auch für Trinkwasser
                #     draw_lines_for_this_type = True
                #     line_color_rgba = 'rgba(30, 144, 255, 0.4)' # Halbtransparentes Dodgerblue

                if draw_lines_for_this_type:
                    for _, poi_row in df_subset.iterrows(): # Iteriere über die gefilterten POIs dieses Typs
                        lon = poi_row['Longitude']
                        lat = poi_row['Latitude']
                        # z_top ist die 'Elevation_Plot', die bereits überhöht ist
                        z_top_line = poi_row['Elevation_Plot'] 
                        z_bottom_line = 0 # Basis der Linie auf Z=0

                        x_poi_lines.extend([lon, lon, None])
                        y_poi_lines.extend([lat, lat, None])
                        z_poi_lines.extend([z_top_line, z_bottom_line, None])

                    if x_poi_lines:
                        fig.add_trace(go.Scatter3d(
                            x=x_poi_lines,
                            y=y_poi_lines,
                            z=z_poi_lines,
                            mode='lines',
                            line=dict(color=line_color_rgba, width=1, dash='solid'), # Solide Linie hier als Beispiel
                            hoverinfo='none',
                            showlegend=False,
                            name=f'{poi_type.capitalize()} Höhenlinien' # Interner Name, nicht in Legende
                        ))
                # --- ENDE VERTIKALE LINIEN ---
        else:
            print("[INFO] Keine POIs der gewünschten Typen (peak, viewpoint, drinking_water) in den Daten gefunden.", file=sys.stderr)
    else:
        print("[INFO] df_pois_all ist leer, keine POIs zum Zeichnen.", file=sys.stderr)

    # --- Orte (aus 8c) hinzufügen ---
    if not df_places_enriched.empty:
        print(f"[DEBUG ORTE PLOT] Beginne Zeichnen für {len(df_places_enriched)} Orte (vor weiterer Filterung).", file=sys.stderr) # Debug 1        
        df_places_enriched['Elevation_Plot'] = df_places_enriched['Nächster_Punkt_Hoehe_m'] * vertical_exaggeration
        style = POI_STYLES.get("place", POI_STYLES.get("default_poi", {"color": "grey", "symbol": "circle", "size": 5, "name": "Orte"}))
        print(f"[DEBUG ORTE PLOT] Verwendeter Stil für Orte: {style}", file=sys.stderr) # Debug 2        
        hover_texts_places = [f"<b>{name}</b><br>Route bei ca.: {elev:.0f} m (orig.)" 
                              for name, elev in zip(df_places_enriched['Ort'], df_places_enriched['Nächster_Punkt_Hoehe_m'])]
        print(f"[DEBUG ORTE PLOT] hover_texts_places erstellt, Länge: {len(hover_texts_places)}", file=sys.stderr) # Debug

        fig.add_trace(go.Scatter3d(
            x=df_places_enriched['Longitude_Center'],
            y=df_places_enriched['Latitude_Center'],
            z=df_places_enriched['Elevation_Plot'],
            mode='markers+text',
            marker=dict(size=style["size"] + 1, color=style["color"], symbol=style["symbol"]),
            text=df_places_enriched['Ort'],
            textposition="top center",
            textfont=dict(size=10, color="blue", family="Arial, sans-serif"),
            hoverinfo='text',
            hovertext=hover_texts_places,
            name=style["name"],
            visible=True
        ))


    # --- Layout anpassen MIT KORREKTUR DER Z-ACHSE ---
    plot_title_final = f"{plot_title_prefix} nach Oberfläche"
    if vertical_exaggeration != 1.0:
        plot_title_final += f" (Visuelle Höhe {vertical_exaggeration}x überhöht)"

    # Generiere Ticks für die Z-Achse basierend auf originalen Höhen
    num_z_ticks = 7 # Anzahl der gewünschten Ticks auf der Z-Achse
    if pd.notna(min_original_elevation) and pd.notna(max_original_elevation) and max_original_elevation > min_original_elevation:
        z_tick_values_original = np.linspace(min_original_elevation, max_original_elevation, num_z_ticks)
        z_tick_values_exaggerated = z_tick_values_original * vertical_exaggeration
        z_tick_texts = [f"{val:.0f} m" for val in z_tick_values_original]
    else: # Fallback, falls keine validen Min/Max-Höhen
        z_tick_values_exaggerated = None
        z_tick_texts = None
        min_original_elevation = 0 # Für Range-Berechnung
        max_original_elevation = 1 if vertical_exaggeration == 0 else 100 * vertical_exaggeration # Default Range

    # Aspekt-Ratio Berechnung (wie vorher)
    lon_range = df_track['Longitude'].max() - df_track['Longitude'].min() if not df_track.empty else 1
    lon_range = df_track['Longitude'].max() - df_track['Longitude'].min() if not df_track.empty else 1
    lat_range = df_track['Latitude'].max() - df_track['Latitude'].min() if not df_track.empty else 1
    # Für die Z-Range im Aspekt-Ratio verwenden wir die *visuelle* (überhöhte) Range
    elev_display_range = (max_original_elevation * vertical_exaggeration) - (min_original_elevation * vertical_exaggeration) if pd.notna(min_original_elevation) and pd.notna(max_original_elevation) else 100

    scene_aspectratio_y = lat_range / lon_range if lon_range > 0 else 1
    scene_aspectratio_y = lat_range / lon_range if lon_range > 0 else 1
    scene_aspectratio_z = 0.5
    if elev_display_range > 0 and max(lon_range, lat_range) > 0:
        horizontal_scale_approx_deg = max(lon_range, lat_range)
        # Verhältnis der visuellen Höhenausdehnung zur horizontalen Ausdehnung (in Grad)
        # Ziel: z soll im Plot eine ähnliche "visuelle Länge" haben wie x oder y
        # Dies ist eine Heuristik und muss ggf. angepasst werden.
        # Ein Faktor von 0.3-0.7 * (horizontale Ausdehnung in Grad) ist oft ein guter Start für z.
        scene_aspectratio_z = (elev_display_range / (min_original_elevation + max_original_elevation if min_original_elevation + max_original_elevation >0 else 1) ) / (horizontal_scale_approx_deg  if horizontal_scale_approx_deg >0 else 1) * 0.5 # Beispiel
        scene_aspectratio_z = max(0.1, min(1.5, scene_aspectratio_z))


    fig.update_layout(
        title=plot_title_final,
        scene=dict(
            xaxis_title='Longitude',
            yaxis_title='Latitude',
            zaxis_title='Höhe (Original, m)', # Titel zeigt an, dass Labels originale Höhe sind
            zaxis=dict(
                tickvals=z_tick_values_exaggerated, # Positionen der Ticks auf der überhöhten Achse
                ticktext=z_tick_texts,             # Beschriftung der Ticks mit originalen Werten
                range=[min_original_elevation * vertical_exaggeration, max_original_elevation * vertical_exaggeration] # Visueller Range der Achse
            ),
            aspectmode='manual',
            aspectratio=dict(x=1, y=scene_aspectratio_y, z=scene_aspectratio_z),
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.8))
        ),
        margin=dict(l=10, r=10, b=10, t=60, pad=4),
        legend=dict(orientation="v", yanchor="top", y=0.95, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.7)", bordercolor="Gray", borderwidth=1)
    )

    # --- Speichern der HTML ---
    # ... (Speichern-Logik wie vorher) ...
    print(f"[DEBUG] Vor dem Speichern der HTML nach: {output_html_path}", file=sys.stderr)
    try:
        output_dir = os.path.dirname(output_html_path)
        if output_dir: os.makedirs(output_dir, exist_ok=True)
        fig.write_html(output_html_path, full_html=True, include_plotlyjs='cdn')
        print(f"[OK] Interaktive 3D-Karte mit POIs gespeichert: {output_html_path}")
        print(f"[INFO] Interaktive 3D-Karte mit POIs gespeichert (Log): {output_html_path}", file=sys.stderr)
    except Exception as e:
        print(f"[Fehler] Konnte HTML-Datei nicht schreiben: {output_html_path} - {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    print(f"[DEBUG] Funktion create_3d_plotly_track_with_pois beendet.", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an interactive 3D Plotly map with track, surfaces, and POIs.")
    parser.add_argument("--track-csv", required=True, help="Path to the input track CSV (output of 4b).")
    parser.add_argument("--pois-csv", required=True, help="Path to the relevant POIs CSV (output of 5c).") # Mache es required
    parser.add_argument("--places-csv", required=True, help="Path to the relevant enriched places CSV (output of 8c).") # Mache es required
    parser.add_argument("--output-html", required=True, help="Path to save the output HTML plot file.")
    parser.add_argument("--exaggeration", type=float, default=1.0, help="Vertical exaggeration factor. Default: 1.0.")
    parser.add_argument("--title-prefix", type=str, default="Interaktive 3D Ansicht", help="Prefix for the plot title.")
    parser.add_argument("--default-line-width", type=int, default=4, help="Default width for track line segments.")
    parser.add_argument("--surface-colors-yaml", default=None, help="Optional: Path to YAML file for surface colors.")

    args = parser.parse_args()
    create_3d_plotly_track_with_pois( # Funktionsname angepasst
        args.track_csv,
        args.pois_csv,
        args.places_csv,
        args.output_html,
        args.exaggeration,
        args.title_prefix,
        args.default_line_width,
        args.surface_colors_yaml
    )    
    print("[DEBUG] Skript erfolgreich beendet.", file=sys.stderr)