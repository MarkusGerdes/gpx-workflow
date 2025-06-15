#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_3d_plotly_map.py (V2 - Mit Oberflächenfarben)
-------------------------
Generates an interactive 3D plot of a GPX track using Plotly.
Allows for vertical exaggeration and colors track segments by surface type.
"""
import sys
import os
import argparse
import yaml 
import pandas as pd
import plotly.graph_objects as go
from typing import Optional

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

def create_3d_plotly_track_with_surfaces(
    track_csv_path: str, # Dies sollte der Output von 4b sein (mit Surface-Info)
    output_html_path: str,
    vertical_exaggeration: float = 1.0,
    # line_color und line_width werden jetzt pro Segment bestimmt
    plot_title_prefix: str = "Interaktive 3D GPX-Strecke",
    default_line_width: int = 4,
    surface_colors_yaml_path: Optional[str] = None # Neuer Parameter    
):
    SURFACE_COLOR_MAP = load_surface_colors_from_yaml(surface_colors_yaml_path) # Farben laden
    print(f"[DEBUG] Funktion create_3d_plotly_track_with_surfaces gestartet.", file=sys.stderr)
    print(f"[Info] Generating 3D Plotly map with surfaces for: {track_csv_path}")
    print(f"  Vertical Exaggeration: {vertical_exaggeration}")

    try:
        print(f"[DEBUG] Versuche, CSV zu laden: {track_csv_path}", file=sys.stderr)        
        df = pd.read_csv(track_csv_path)
        print(f"[DEBUG] CSV geladen. Roh-Spalten: {df.columns.tolist()}", file=sys.stderr)

        if df.empty:
            print(f"[Warnung] Track CSV ist leer: {track_csv_path}", file=sys.stderr)
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write("<html><body><h1>Track data is empty. Cannot generate 3D plot.</h1></body></html>")
            print(f"[OK] Leere HTML-Datei gespeichert (da Input leer): {output_html_path}", file=sys.stderr)
            sys.exit(0) # Erfolgreich, da Output-Datei (leer) erstellt wurde
        
        # Benötigte Spalten: Latitude, Longitude, Elevation (m), Surface
        # Optional für Hover: Distanz (km) (aus 4b, sollte dort 'Distanz_km_orig_track' oder ähnlich heißen)
        # Passe die Spaltennamen ggf. an deine 4b_...csv an
        required_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Surface']
        if not all(col in df.columns for col in required_cols):
            # Versuche, 'Elevation (m)' zu 'Elevation_m' zu ändern, falls das der Fall ist
            if 'Elevation_m' in df.columns and 'Elevation (m)' not in df.columns:
                df.rename(columns={'Elevation_m': 'Elevation (m)'}, inplace=True)
            if not all(col in df.columns for col in required_cols):
                 raise ValueError(f"Input CSV must contain columns: {', '.join(required_cols)}")

        if df.empty:
            # ... (leere Datei Logik wie vorher) ...
            sys.exit(0)

        # Datenbereinigung
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Elevation (m)'] = pd.to_numeric(df['Elevation (m)'], errors='coerce')
        df['Surface'] = df['Surface'].fillna('unknown').astype(str).str.lower()
        df.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)

        # original_index für Sortierung, falls vorhanden und nicht sortiert
        if 'original_index' in df.columns:
            df['original_index'] = pd.to_numeric(df['original_index'], errors='coerce')
            df.dropna(subset=['original_index'], inplace=True)
            df.sort_values(by='original_index', inplace=True)
            df.reset_index(drop=True, inplace=True)


        if df.empty:
            # ... (leere Datei Logik nach Bereinigung) ...
            sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {track_csv_path}", file=sys.stderr)
        sys.exit(1) # Fehlercode für Snakemake
    except ValueError as ve:
        print(f"[Fehler] Problem mit Spalten oder Daten in CSV '{track_csv_path}': {ve}", file=sys.stderr)       
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Allgemeiner Fehler beim Laden/Vorbereiten der CSV '{track_csv_path}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[DEBUG] Daten erfolgreich geladen und vorbereitet. {len(df)} Punkte.", file=sys.stderr)
    df['Elevation_Exaggerated'] = df['Elevation (m)'] * vertical_exaggeration

    fig = go.Figure()
    legend_added_surfaces = set() # Um Legenden-Einträge eindeutig zu halten

    # Gruppiere nach aufeinanderfolgenden gleichen Oberflächen
    # Erzeuge eine Block-ID für jeden kontinuierlichen Oberflächenabschnitt
    df['surface_block'] = (df['Surface'] != df['Surface'].shift()).cumsum()

    for block_id, segment_df in df.groupby('surface_block'):
        if len(segment_df) < 2: # Ein Liniensegment benötigt mindestens 2 Punkte
            continue

        surface_type = segment_df['Surface'].iloc[0]
        segment_color = SURFACE_COLOR_MAP.get(surface_type, SURFACE_COLOR_MAP['default'])

        # Hover-Text vorbereiten
        # Stelle sicher, dass die Distanzspalte existiert, sonst Fallback
        dist_col_name = None
        if 'Distanz (km)' in segment_df.columns: # Von 2c
            dist_col_name = 'Distanz (km)'
        elif 'Distanz_km_orig_track' in segment_df.columns: # Von 4b
            dist_col_name = 'Distanz_km_orig_track'
        # ... füge weitere mögliche Namen hinzu oder mache es konfigurierbar ...

        hover_texts = []
        for _, row in segment_df.iterrows():
            dist_val = row.get(dist_col_name, 0.0) if dist_col_name else 0.0
            hover_texts.append(
                f"Surface: {surface_type.capitalize()}<br>"
                f"Lat: {row['Latitude']:.4f}<br>Lon: {row['Longitude']:.4f}<br>"
                f"Höhe: {row['Elevation (m)']:.1f} m (orig.)<br>"
                f"Dist: {dist_val:.2f} km"
            )

        fig.add_trace(go.Scatter3d(
            x=segment_df['Longitude'],
            y=segment_df['Latitude'],
            z=segment_df['Elevation_Exaggerated'],
            mode='lines',
            line=dict(
                color=segment_color,
                width=default_line_width
            ),
            hoverinfo='text',
            text=hover_texts,
            name=surface_type.capitalize() if surface_type not in legend_added_surfaces else '', # Name für Legende
            showlegend=surface_type not in legend_added_surfaces # Nur einmal pro Oberfläche anzeigen
        ))
        if surface_type not in legend_added_surfaces:
            legend_added_surfaces.add(surface_type)


    # Start- und Endpunkte (optional, wie vorher)
    if len(df) > 0:
        fig.add_trace(go.Scatter3d(
            x=[df['Longitude'].iloc[0]], y=[df['Latitude'].iloc[0]], z=[df['Elevation_Exaggerated'].iloc[0]],
            mode='markers', marker=dict(size=7, color='green', symbol='circle-open', line=dict(width=2, color='DarkGreen')), name='Start',
            hovertext=f"Start<br>Höhe: {df['Elevation (m)'].iloc[0]:.1f} m", hoverinfo="text"
        ))
        if len(df) > 1:
            fig.add_trace(go.Scatter3d(
                x=[df['Longitude'].iloc[-1]], y=[df['Latitude'].iloc[-1]], z=[df['Elevation_Exaggerated'].iloc[-1]],
                mode='markers', marker=dict(size=7, color='darkred', symbol='x', line=dict(width=2, color='DarkRed')), name='Ende',
                hovertext=f"Ende<br>Höhe: {df['Elevation (m)'].iloc[-1]:.1f} m", hoverinfo="text"
            ))


    # Layout anpassen (wie vorher, ggf. Anpassung der Achsen-Skalierung)
    plot_title = f"{plot_title_prefix} nach Oberfläche"
    if vertical_exaggeration != 1.0:
        plot_title += f" (Höhe {vertical_exaggeration}x überhöht)"

    lon_range = df['Longitude'].max() - df['Longitude'].min() if not df.empty else 1
    lat_range = df['Latitude'].max() - df['Latitude'].min() if not df.empty else 1
    elev_range_exaggerated = df['Elevation_Exaggerated'].max() - df['Elevation_Exaggerated'].min() if not df.empty else 1

    scene_aspectratio_y = lat_range / lon_range if lon_range > 0 else 1
    scene_aspectratio_z = 0.5 # Startwert
    if elev_range_exaggerated > 0 and max(lon_range, lat_range) > 0:
        # Normalisierungsfaktor, der die typische Umrechnung Grad zu Meter berücksichtigt
        # und eine zusätzliche Skalierung, um die Höhe sichtbar zu machen.
        # Dies ist weiterhin eine Heuristik!
        horizontal_scale_approx_meters = max(lon_range, lat_range) * 111000 * 0.001 # Grobe Umrechnung in km
        if horizontal_scale_approx_meters > 0:
             # Ziel: z-Ausdehnung soll etwa 10-50% der horizontalen Ausdehnung im Plot sein
            desired_z_ratio = 0.3
            z_scale_factor = (elev_range_exaggerated / (horizontal_scale_approx_meters * 1000)) # Verhältnis der realen Ausdehnungen
            scene_aspectratio_z = desired_z_ratio / z_scale_factor if z_scale_factor > 0 else 0.3
            scene_aspectratio_z = max(0.1, min(1.5, scene_aspectratio_z * vertical_exaggeration * 0.1 )) # Anpassen und begrenzen

    fig.update_layout(
        title=plot_title,
        scene=dict(
            xaxis_title='Longitude', yaxis_title='Latitude', zaxis_title=f'Höhe (überhöht, m)',
            aspectmode='manual', aspectratio=dict(x=1, y=scene_aspectratio_y, z=scene_aspectratio_z),
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.8))
        ),
        margin=dict(l=10, r=10, b=10, t=60, pad=4),
        legend=dict(orientation="v", yanchor="top", y=0.95, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.7)", bordercolor="Gray", borderwidth=1)
    ) # ENDE VON FIG.UPDATE_LAYOUT

    # --- KORREKTER SPEICHERBLOCK (NUR EINMAL UND KORREKT EINGERÜCKT) ---
    print(f"[DEBUG] Vor dem Speichern der HTML nach: {output_html_path}", file=sys.stderr)
    try:
        output_dir = os.path.dirname(output_html_path)
        if output_dir: # Nur erstellen, wenn output_dir nicht leer ist (d.h. nicht im aktuellen Verzeichnis)
            os.makedirs(output_dir, exist_ok=True)
        fig.write_html(output_html_path, full_html=True, include_plotlyjs='cdn')
        print(f"[OK] Interaktive 3D-Karte mit Oberflächen gespeichert: {output_html_path}") # Für Snakemake stdout
        print(f"[INFO] Interaktive 3D-Karte mit Oberflächen gespeichert (Log): {output_html_path}", file=sys.stderr) # Für Log
    except Exception as e:
        print(f"[Fehler] Konnte HTML-Datei nicht schreiben: {output_html_path} - {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    print(f"[DEBUG] Funktion create_3d_plotly_track_with_surfaces beendet.", file=sys.stderr)



if __name__ == "__main__":
    print("[DEBUG] __main__ Block gestartet.", file=sys.stderr)    
    parser = argparse.ArgumentParser(description="Generate an interactive 3D Plotly map of a GPX track with surface colors.")
    parser.add_argument("--track-csv", required=True,
                        help="Path to the input CSV file with track data (must include Lat, Lon, Elev, Surface). Typically output of 4b.")
    parser.add_argument("--output-html", required=True,
                        help="Path to save the output HTML plot file.")
    parser.add_argument("--exaggeration", type=float, default=1.0,
                        help="Vertical exaggeration factor for elevation. Default: 1.0.")
    parser.add_argument("--title-prefix", type=str, default="Interaktive 3D GPX-Strecke",
                        help="Prefix for the plot title.")
    parser.add_argument("--default-line-width", type=int, default=4,
                        help="Default width for track line segments.")
    parser.add_argument("--surface-colors-yaml", help="Path to YAML file defining surface colors.")                  
    # Optional: Pfad zur YAML-Datei für SURFACE_COLOR_MAP, falls nicht hardcoded
    # parser.add_argument("--surface-colors-yaml", help="Path to YAML file defining surface colors.")

    print("[DEBUG] Argumente werden geparst...", file=sys.stderr)
    args = parser.parse_args()
    print(f"[DEBUG] Argumente geparst: {args}", file=sys.stderr)

    # Hier könntest du die SURFACE_COLOR_MAP aus einer YAML laden, wenn --surface-colors-yaml angegeben ist

    create_3d_plotly_track_with_surfaces(
        args.track_csv,
        args.output_html,
        args.exaggeration,
        args.title_prefix,
        args.default_line_width
    )
    print("[DEBUG] Skript erfolgreich beendet.", file=sys.stderr)