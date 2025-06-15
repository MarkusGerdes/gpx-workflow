#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_3d_plotly_map.py
-------------------------
Generates an interactive 3D plot of a GPX track using Plotly.
Allows for vertical exaggeration of the elevation.
"""

import sys
import os
import argparse
import pandas as pd
import plotly.graph_objects as go

def create_3d_plotly_track(
    track_csv_path: str,
    output_html_path: str,
    vertical_exaggeration: float = 1.0,
    line_color: str = 'deepskyblue',
    line_width: int = 4,
    plot_title_prefix: str = "Interaktive 3D GPX-Strecke"
):
    """
    Creates and saves an interactive 3D Plotly plot from track data.

    Args:
        track_csv_path (str): Path to the CSV file containing track data
                              (must include 'Latitude', 'Longitude', 'Elevation (m)').
        output_html_path (str): Path to save the output HTML file.
        vertical_exaggeration (float): Factor to exaggerate the elevation.
                                       1.0 = no exaggeration. > 1.0 for exaggeration.
        line_color (str): Color of the track line.
        line_width (int): Width of the track line.
        plot_title_prefix (str): Prefix for the plot title.
    """
    print(f"[Info] Generating 3D Plotly map for: {track_csv_path}")
    print(f"  Vertical Exaggeration: {vertical_exaggeration}")

    # --- Lade Track-Daten ---
    try:
        df = pd.read_csv(track_csv_path)
        required_cols = ['Latitude', 'Longitude', 'Elevation (m)']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Input CSV must contain columns: {', '.join(required_cols)}")
        if df.empty:
            print(f"[Warnung] Track CSV ist leer: {track_csv_path}")
            # Create an empty HTML file or a message
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write("<html><body><h1>Track data is empty. Cannot generate 3D plot.</h1></body></html>")
            print(f"[OK] Leere HTML-Datei gespeichert: {output_html_path}")
            sys.exit(0) # Success, as an output file is expected by Snakemake

        # Stelle sicher, dass die Spalten numerisch sind und keine NaNs haben
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Elevation (m)'] = pd.to_numeric(df['Elevation (m)'], errors='coerce')
        df.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)

        if df.empty:
            print(f"[Warnung] Keine gültigen Datenpunkte nach Bereinigung in: {track_csv_path}")
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write("<html><body><h1>No valid track points after cleanup.</h1></body></html>")
            print(f"[OK] Leere HTML-Datei gespeichert: {output_html_path}")
            sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {track_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen oder Verarbeiten der CSV '{track_csv_path}': {e}")
        sys.exit(1)

    # --- Anwenden der vertikalen Überhöhung ---
    df['Elevation_Exaggerated'] = df['Elevation (m)'] * vertical_exaggeration

    # --- Erstelle Plotly Figur ---
    fig = go.Figure()

    # Track-Linie hinzufügen
    fig.add_trace(go.Scatter3d(
        x=df['Longitude'],
        y=df['Latitude'],
        z=df['Elevation_Exaggerated'], # Verwende die überhöhte Elevation
        mode='lines',
        line=dict(
            color=line_color,
            width=line_width
        ),
        hoverinfo='text', # Zeige benutzerdefinierten Hover-Text
        text=[f"Lat: {lat:.4f}<br>Lon: {lon:.4f}<br>Höhe: {elev:.1f} m (orig.)<br>Dist: {dist:.2f} km"
              for lat, lon, elev, dist in zip(df['Latitude'], df['Longitude'], df['Elevation (m)'], df.get('Distanz (km)', [0]*len(df)))],
        name='GPX Track'
    ))

    # Optional: Start- und Endpunkte markieren
    if len(df) > 0:
        fig.add_trace(go.Scatter3d(
            x=[df['Longitude'].iloc[0]],
            y=[df['Latitude'].iloc[0]],
            z=[df['Elevation_Exaggerated'].iloc[0]],
            mode='markers',
            marker=dict(size=6, color='green', symbol='circle'),
            name='Start',
            hoverinfo='text',
            text=f"Start<br>Höhe: {df['Elevation (m)'].iloc[0]:.1f} m"
        ))
        if len(df) > 1:
            fig.add_trace(go.Scatter3d(
                x=[df['Longitude'].iloc[-1]],
                y=[df['Latitude'].iloc[-1]],
                z=[df['Elevation_Exaggerated'].iloc[-1]],
                mode='markers',
                marker=dict(size=6, color='red', symbol='x'),
                name='Ende',
                hoverinfo='text',
                text=f"Ende<br>Höhe: {df['Elevation (m)'].iloc[-1]:.1f} m"
            ))

    # --- Layout anpassen ---
    plot_title = f"{plot_title_prefix}"
    if vertical_exaggeration != 1.0:
        plot_title += f" (Höhe {vertical_exaggeration}x überhöht)"

    # Berechne die Achsenverhältnisse, um eine realistische Grundrissdarstellung zu erhalten,
    # während die Z-Achse unabhängig skaliert werden kann.
    lon_range = df['Longitude'].max() - df['Longitude'].min()
    lat_range = df['Latitude'].max() - df['Latitude'].min()
    elev_range_exaggerated = df['Elevation_Exaggerated'].max() - df['Elevation_Exaggerated'].min()

    # Um die Skalierung etwas zu normalisieren, damit der Plot nicht zu flach/gestreckt aussieht
    # Dies ist ein heuristischer Ansatz.
    # Ziel: Die X- und Y-Ausdehnung sollten im Plot vergleichbar erscheinen.
    #       Die Z-Ausdehnung wird dann relativ dazu skaliert.
    scene_aspectratio = dict(x=1, y=lat_range/lon_range if lon_range > 0 else 1, z=0.5) # Startwert für Z
    if elev_range_exaggerated > 0 and lon_range > 0 : # Vermeide Division durch Null
         # Versuche Z so zu skalieren, dass es im Verhältnis zu X/Y "sichtbar" ist.
         # Ein Faktor von 0.3 bis 0.7 für z im Verhältnis zur längeren X/Y-Achse ist oft gut.
         # Die tatsächliche Skalierung im 3D-Plot wird durch die Kameraansicht stark beeinflusst.
         # Dieser Wert ist mehr eine Richtlinie für die Proportionen der Achsen-Ticks.
        scene_aspectratio['z'] = max(0.2, min(1.0, (elev_range_exaggerated / (max(lon_range, lat_range) * 111000 * 0.001)) * 10 )) # grobe Normalisierung und Skalierung

    fig.update_layout(
        title=plot_title,
        scene=dict(
            xaxis_title='Longitude',
            yaxis_title='Latitude',
            zaxis_title=f'Höhe (überhöht, m)',
            # aspectmode='data' # 'data' ist gut für gleiche Skalierung pro Einheit auf allen Achsen, aber nicht ideal mit Überhöhung
            aspectmode='manual', # Erlaubt manuelle Einstellung der Verhältnisse
            aspectratio=scene_aspectratio,
            camera=dict(
                eye=dict(x=1.25, y=1.25, z=0.75) # Anpassung der Start-Kameraposition
            )
        ),
        margin=dict(l=10, r=10, b=10, t=50, pad=4), # Kleinere Ränder
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="right", x=1)
    )

    # --- Speichere als HTML ---
    try:
        output_dir = os.path.dirname(output_html_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        fig.write_html(output_html_path, full_html=True, include_plotlyjs='cdn')
        print(f"[OK] Interaktive 3D-Karte gespeichert: {output_html_path}")
    except Exception as e:
        print(f"[Fehler] Konnte HTML-Datei nicht schreiben: {output_html_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an interactive 3D Plotly map of a GPX track.")
    parser.add_argument("--track-csv", required=True,
                        help="Path to the input CSV file with track data (must include 'Latitude', 'Longitude', 'Elevation (m)').")
    parser.add_argument("--output-html", required=True,
                        help="Path to save the output HTML plot file.")
    parser.add_argument("--exaggeration", type=float, default=1.0,
                        help="Vertical exaggeration factor for elevation (e.g., 2.5 for 2.5x exaggeration). Default: 1.0 (none).")
    parser.add_argument("--color", type=str, default="deepskyblue",
                        help="Color of the track line (e.g., 'red', '#FF0000'). Default: 'deepskyblue'.")
    parser.add_argument("--width", type=int, default=4,
                        help="Width of the track line. Default: 4.")
    parser.add_argument("--title-prefix", type=str, default="Interaktive 3D GPX-Strecke",
                        help="Prefix for the plot title.")
    args = parser.parse_args()

    create_3d_plotly_track(
        args.track_csv,
        args.output_html,
        args.exaggeration,
        args.color,
        args.width,
        args.title_prefix
    )