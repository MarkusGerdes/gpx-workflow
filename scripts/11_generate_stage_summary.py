#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_generate_stage_summary.py
----------------------------
Aggregates results from previous steps (statistics, profile plot, map,
peak data, place descriptions) into a final HTML summary report and
generates a PDF version using pdfkit.

Requires 'markdown', 'pdfkit', 'pandas'.
Requires 'wkhtmltopdf' to be installed and in PATH for PDF generation.
"""

import sys
import os
import argparse
import pandas as pd
from markdown import markdown
import pdfkit
import base64 # To embed images directly for better PDF conversion
from pathlib import Path
from typing import Optional 
from geopy.distance import distance as geopy_distance 

# NEU: tqdm importieren (mit Fallback)
try:
    from tqdm import tqdm
except ImportError:
    print("[Warnung] tqdm nicht gefunden (pip install tqdm), Fortschrittsbalken für Straßenliste wird nicht angezeigt.")
    def tqdm(iterable, *args, **kwargs): # Dummy-Funktion
        return iterable

# --- Helper Functions ---

def read_file_content(path: str, default: str = "") -> str:
    """Reads text file content, returns default if not found or error."""
    if path and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[Warnung] Fehler beim Lesen von {path}: {e}")
            return default
    return default

def image_to_base64(img_path: str) -> Optional[str]:
    """Converts an image file to a base64 data URI."""
    if not img_path or not os.path.exists(img_path):
        return None
    try:
        ext = Path(img_path).suffix.lower().strip('.')
        if ext == 'svg': ext = 'svg+xml' # Correct MIME type for SVG
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/{ext};base64,{encoded_string}"
    except Exception as e:
        print(f"[Warnung] Fehler beim Konvertieren von Bild zu Base64 ({img_path}): {e}")
        return None

def calculate_distance_for_group(group: pd.DataFrame) -> float:
    """Calculates the summed geodetic distance between consecutive points in a group."""
    dist_km = 0.0
    group['Latitude'] = pd.to_numeric(group['Latitude'], errors='coerce')
    group['Longitude'] = pd.to_numeric(group['Longitude'], errors='coerce')
    group = group.dropna(subset=['Latitude', 'Longitude'])
    if len(group) < 2: return 0.0
    coords = list(zip(group['Latitude'], group['Longitude']))
    for i in range(len(coords) - 1):
        try:
            segment_dist = geopy_distance(coords[i], coords[i+1]).km
            dist_km += segment_dist
        except ValueError: continue
    return dist_km

# --- Main Generation Function ---

def generate_summary(args):
    """Generates the HTML and PDF summary reports."""
    print(f"[Info] Generating final summary for: {args.basename}")

    # --- 1. Load Data ---
    print("[Info] Lade Daten...")
    # Statistics
    stats_html = "<tr><td colspan='2'>Statistiken nicht verfügbar oder fehlerhaft.</td></tr>" # Fallback
    if args.stats_csv and os.path.exists(args.stats_csv):
        try:
            stats_df = pd.read_csv(args.stats_csv)
            # --- KORREKTUR: Generiere HTML nur aus vorhandenen Zeilen ---
            if not stats_df.empty:
                stats_html = "\n".join([f"<tr><td>{row['Statistik']}</td><td>{row['Wert']}</td></tr>"
                                       for _, row in stats_df.iterrows() if pd.notna(row['Wert'])]) # Füge nur Zeilen hinzu, wenn Wert nicht NaN/None ist
            # Wenn nach Filterung leer, behalte Fallback
            if not stats_html.strip():
                 stats_html = "<tr><td colspan='2'>Keine gültigen Statistiken verfügbar.</td></tr>"
            # ---------------------------------------------------------
        except Exception as e:
            print(f"[Warnung] Fehler beim Lesen der Statistik-CSV ({args.stats_csv}): {e}")
            stats_html = f"<tr><td colspan='2'>Fehler beim Laden der Statistik-CSV: {e}</td></tr>"

    # Sorted Places List

    # Peak/Segment Data (Optional display)
    peak_segment_html = "<p>Keine Peak/Segment Daten verfügbar.</p>"
    if args.peak_csv and os.path.exists(args.peak_csv):
        try:
            peak_df = pd.read_csv(args.peak_csv)
            if not peak_df.empty:
                # Format a simple summary or table
                peak_html_parts = []
                valid_segments = peak_df[peak_df['item_type'] == 'Valid Segment'].copy()
                peaks_only = peak_df[peak_df['item_type'] == 'Peak'].copy()

                if not peaks_only.empty:
                    peak_html_parts.append("<h4>Top Peaks:</h4><ul>")
                    for _, peak_row in peaks_only.iterrows():
                         peak_html_parts.append(f"<li>Peak {int(peak_row['peak_rank'])}: {peak_row['peak_elev_m']:.0f} m @ {peak_row['peak_dist_km']:.1f} km</li>")
                    peak_html_parts.append("</ul>")

                if not valid_segments.empty:
                    peak_html_parts.append("<h4>Zugehörige Anstiege:</h4>")
                    # Use pandas to_html for a quick table (can be styled better)
                    valid_segments['peak_rank'] = valid_segments['peak_rank'].astype(int) # Format Rank
                    cols_to_show = ['peak_rank', 'segment_direction', 'segment_start_km', 'segment_end_km', 'segment_length_m', 'segment_gain_m']
                    peak_html_parts.append(
                        valid_segments[cols_to_show].to_html(index=False, classes="table table-sm table-bordered table-hover", border=0, float_format='%.1f')
                    )

                peak_segment_html = "\n".join(peak_html_parts)

        except Exception as e:
            print(f"[Warnung] Fehler beim Lesen der Peak/Segment-CSV ({args.peak_csv}): {e}")


    # Markdown Descriptions
    markdown_content = read_file_content(args.markdown_text, "<p>Keine Beschreibungen verfügbar.</p>")
    descriptions_html = markdown(markdown_content) if markdown_content else "<p>Keine Beschreibungen verfügbar.</p>"

    # --- NEU: Lade Geocodierte Route (Schritt 4) für Straßenliste ---
    street_list_html = "<li>Keine Straßendaten verfügbar.</li>"
    if args.geocoded_opt_csv and os.path.exists(args.geocoded_opt_csv):
        print("[Info] Verarbeite geocodierte Route für Straßenliste...")
        try:
            df_loc = pd.read_csv(args.geocoded_opt_csv, dtype=str, keep_default_na=False)
            if not df_loc.empty and all(c in df_loc.columns for c in ['Street', 'City', 'PostalCode', 'Latitude', 'Longitude']):
                df_loc['Latitude'] = pd.to_numeric(df_loc['Latitude'], errors='coerce')
                df_loc['Longitude'] = pd.to_numeric(df_loc['Longitude'], errors='coerce')
                df_loc.dropna(subset=['Latitude', 'Longitude'], inplace=True)

                if not df_loc.empty:
                    df_loc['Street'] = df_loc['Street'].fillna('Unbekannte Straße')
                    df_loc['City'] = df_loc['City'].fillna('Unbekannter Ort')
                    df_loc['PostalCode'] = df_loc['PostalCode'].fillna('Keine PLZ')

                    # Block-ID nur basierend auf Street und City
                    df_loc['block_id'] = (df_loc[['Street', 'City']] != df_loc[['Street', 'City']].shift()).any(axis=1).cumsum()

                    street_blocks_html_parts = [] # Liste für HTML-Teile
                    current_city_group = None # Um den aktuellen Ort zu verfolgen

                    # Gruppiere zuerst nach Stadt, dann innerhalb der Stadt nach Straßenblöcken
                    # Behalte die ursprüngliche Reihenfolge der Städte bei, wie sie auf der Route erscheinen
                    # Dazu erstellen wir eine eindeutige, geordnete Liste von Städten aus df_loc
                    ordered_cities_on_route = df_loc.drop_duplicates(subset=['City'], keep='first')['City'].tolist()
                    # Filtere "Unbekannter Ort" etc. hier schon raus, falls gewünscht für die Überschriften
                    ignore_cities_for_header = ["Unbekannter Ort", "Fehler", "nan", "None"]
                    
                    print(f"[Info] Analysiere Straßenverlauf für {len(ordered_cities_on_route)} potentielle Ortsabschnitte...")

                    for city_name in tqdm(ordered_cities_on_route, desc="Processing Cities for Street List"):
                        if city_name in ignore_cities_for_header:
                            continue

                        # Filtere den DataFrame für die aktuelle Stadt
                        city_df = df_loc[df_loc['City'] == city_name].copy()
                        if city_df.empty:
                            continue

                        # Füge die Ortsüberschrift hinzu
                        street_blocks_html_parts.append(f"<h5 class='city-street-header'>{city_name}</h5>")
                        street_blocks_html_parts.append("<ul class='street-list-city'>") # Starte eine neue Unterliste für diese Stadt

                        # Gruppiere innerhalb der Stadt nach Straßenblöcken
                        # Die block_id wurde bereits global berechnet, wir müssen hier nur die Blöcke der aktuellen Stadt nehmen
                        city_grouped_by_block = city_df.groupby('block_id')

                        for block_id, group in city_grouped_by_block:
                            if len(group) < 1: continue

                            first_row = group.iloc[0]
                            street = first_row['Street']
                            # City ist hier immer city_name
                            postal = first_row['PostalCode']

                            block_dist_km = calculate_distance_for_group(group.copy())

                            # Straßenname und PLZ für die Anzeige (ohne den Ort, da er schon in der Überschrift steht)
                            street_display_name = street if street and street not in ["nan", "None"] else "Unbekannte Straße"
                            postal_display_name = f", {postal}" if postal and postal not in ["Keine PLZ", "nan", "None"] else ""

                            street_blocks_html_parts.append(f"<li>{street_display_name}{postal_display_name} - ca. {block_dist_km:.2f} km</li>")
                        
                        street_blocks_html_parts.append("</ul>") # Schließe die Unterliste für diese Stadt

                    if street_blocks_html_parts:
                        street_list_html = "\n".join(street_blocks_html_parts)
                    else:
                        street_list_html = "<li>Keine relevanten Straßenabschnitte gefunden.</li>"
                else:
                    street_list_html = "<li>Keine gültigen Koordinaten in geocodierter Route für Straßenliste.</li>"
            else:
                print("[Warnung] Geocodierte CSV ungültig oder Spalten fehlen.")
        except Exception as e:
            print(f"[Warnung] Fehler Verarbeitung geocodierte Route: {e}")
            street_list_html = f"<li>Fehler bei Verarbeitung: {e}</li>"
    else:
        print("[Warnung] Geocodierte Routen-CSV nicht gefunden.")


    # --- 2. Prepare Assets for Embedding ---
    print("[Info] Bereite Assets vor (Base64-Einbettung für PDF)...")
    # Convert images to Base64 for reliable PDF rendering
    profile_plot_base64 = image_to_base64(args.profile_png)
    map_screenshot_base64 = image_to_base64(args.map_png)
    # Optional: Speed profile image
    speed_profile_base64 = image_to_base64(args.speed_profile) if args.speed_profile else None


    # Paths relative to the final HTML file's location for iframe and image fallbacks
    # Assuming output HTML is in 'output/' directory
    relative_map_html_path = os.path.basename(args.map_html) if args.map_html else None
    # Use the profile plot path directly (it might be the annotated or original one)
    relative_profile_plot_path = os.path.basename(args.profile_png) if args.profile_png else None
    relative_map_screenshot_path = os.path.basename(args.map_png) if args.map_png else None
    relative_speed_plot_path = os.path.basename(args.speed_profile) if args.speed_profile else None


    # --- 3. Construct HTML ---
    print("[Info] Erstelle HTML-Inhalt...")
    # Use Bootstrap for basic styling
    # Embed CSS directly for better PDF conversion
    bootstrap_css_path = Path(__file__).parent / "bootstrap.min.css" # Assumes CSS is besides script
    # Read CSS content if file exists
    try:
         with open(bootstrap_css_path, "r") as f_css:
              bootstrap_css = f_css.read()
    except FileNotFoundError:
         print("[Warnung] bootstrap.min.css nicht gefunden. Verwende CDN Fallback (nur für HTML-Ansicht).")
         # Provide CDN link as fallback for HTML view, won't work reliably in PDF
         bootstrap_css = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/css/bootstrap.min.css"/>'


    html_template = f"""
<!DOCTYPE html>
<html lang='de'>
<head>
    <meta charset='UTF-8'>
    <title>Etappenübersicht – {args.basename}</title>
    <style>
        /* Embed Bootstrap CSS */
        {bootstrap_css}

        /* Custom Styles */
        @page {{ size: A4 portrait; margin: 1cm; }} /* Ensure PDF is A4 */
        body {{ font-family: sans-serif; padding-top: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 960px; margin: auto; background-color: #ffffff; padding: 25px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #004085; border-bottom: 2px solid #dee2e6; padding-bottom: 0.3em; margin-top: 1.5em; }}
        h1 {{ text-align: center; margin-bottom: 1em; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 1em auto; border: 1px solid #ddd; border-radius: 4px; }}
        iframe {{ width: 100%; height: 500px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 1em; }}
        table {{ margin-bottom: 1.5em; }}
        .stats-table td:first-child {{ font-weight: bold; width: 40%; }}
        .places-list ul {{ list-style-type: none; padding-left: 0; }}
        .places-list li {{ margin-bottom: 0.5em; border-bottom: 1px dotted #eee; padding-bottom: 0.3em; }}
        .segment-summary table {{ font-size: 0.85em; }}
        .markdown-content {{ line-height: 1.6; }}
        .markdown-content h2 {{ font-size: 1.6em; margin-top: 1.5em; }} /* Style h2 from markdown */
        .markdown-content h3 {{ font-size: 1.3em; border-bottom: 1px solid #eee; color: #333; }}

        /* PDF specific styles */
        .pdf-only {{ display: none; }}
        .html-only {{ display: block; }}

        @media print {{
            .html-only {{ display: none; }}
            .pdf-only {{ display: block; }}
            body {{ background-color: #ffffff; }} /* White background for printing */
            .container {{ box-shadow: none; border: none; padding: 0; margin: 0; max-width: 100%; }}
            img {{ page-break-inside: avoid; }} /* Try to keep images on one page */
            iframe {{ display: none; }} /* Hide iframe in PDF */
        }}
    </style>
</head>
<body>
<div class='container'>
    <h1>Etappenübersicht: {args.basename}</h1>

    <!-- Section: Karte -->
    <h2>🗺️ Karte</h2>
    <div class="html-only">
        <!-- NEU: Statisches Bild für HTML-Ansicht (vor dem iFrame) -->
        {f"<div><img src='{relative_map_screenshot_path}' alt='Übersichtskarte'></div><hr>" if relative_map_screenshot_path else '<p>Kein Kartenbild verfügbar.</p>'}
        {f"<iframe src='{relative_map_html_path}'></iframe>" if relative_map_html_path else "<p>Keine interaktive Karte verfügbar.</p>"}
    </div>
    <div class="pdf-only">
        {f"<img src='{map_screenshot_base64}' alt='Karten-Screenshot'>" if map_screenshot_base64 else '<p>Kein Kartenbild verfügbar.</p>'}
    </div>

    <!-- Section: Streckenstatistiken -->
        <h2>📊 Statistiken</h2>
        <table class="table table-striped table-bordered stats-table">
            <thead><tr><th>Merkmal</th><th>Wert</th></tr></thead>
            <tbody>
                {stats_html} <!-- Wird jetzt dynamisch gefüllt -->
            </tbody>
        </table>

    <!-- Section: Höhenprofil -->
    <h2>📈 Höhenprofil</h2>
    {f"<img src='{profile_plot_base64}' alt='Höhenprofil'>" if profile_plot_base64 else '<p>Kein Höhenprofil verfügbar.</p>'}

    <!-- Optional Section: Geschwindigkeitsprofil -->
    {f"<h2>⏱️ Geschwindigkeitsprofil</h2><img src='{speed_profile_base64}' alt='Geschwindigkeitsprofil'>" if speed_profile_base64 else ''}

    <!-- Optional Section: Peak/Segment Details -->
    <h2>⛰️ Peak & Anstiegs-Analyse</h2>
    <div class="segment-summary">{peak_segment_html}</div>

    <!-- NEUER ABSCHNITT: Straßenliste -->
    <h2>🛣️ Straßenverlauf (approximiert)</h2>
    <div class="street-list"><ul>{street_list_html}</ul></div>

    <!-- Section: Beschreibungen -->
    <h2>📝 Beschreibungen & Highlights (über GEMINI 2.0)</h2>
    <div class="markdown-content">
        {descriptions_html}
    </div>

    <!-- Optional Section: Weitere Daten (z.B. Oberfläche, Leistung) -->
    {f"<!-- TODO: Hier könnten Oberflächendaten ({args.surface_data}) oder Leistungsdaten ({args.power_data}) angezeigt werden -->" if args.surface_data or args.power_data else ""}

</div>
</body>
</html>
    """

    # --- 4. Save HTML ---
    print(f"[Info] Speichere HTML: {args.output_html}")
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(args.output_html)
        if output_dir:
             os.makedirs(output_dir, exist_ok=True)
        with open(args.output_html, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"[OK] HTML-Datei gespeichert: {args.output_html}")
    except Exception as e:
        print(f" Fehler beim Schreiben der HTML-Datei '{args.output_html}': {e}")
        sys.exit(1) # Exit if HTML fails, PDF depends on it

    # --- 5. Generate PDF ---
    print(f"[Info] Generiere PDF: {args.output_pdf}")
    try:
        # pdfkit configuration
        options = {
            'page-size': 'A4',
            'margin-top': '10mm',
            'margin-right': '10mm',
            'margin-bottom': '10mm',
            'margin-left': '10mm',
            'encoding': "UTF-8",
            'enable-local-file-access': None, # IMPORTANT for local images/CSS
            'quiet': '', # Suppress wkhtmltopdf output unless error
            'load-error-handling': 'ignore', # Ignore minor loading errors (e.g., missing fonts)
            'load-media-error-handling': 'ignore'
        }
        # Path to wkhtmltopdf executable (optional, usually found if in PATH)
        # config = pdfkit.configuration(wkhtmltopdf='path/to/wkhtmltopdf.exe') # Uncomment and set path if needed
        # pdfkit.from_file(args.output_html, args.output_pdf, options=options, configuration=config) # Use with config
        pdfkit.from_file(args.output_html, args.output_pdf, options=options) # Use without explicit config path

        print(f"[OK] PDF-Datei gespeichert: {args.output_pdf}")

    except FileNotFoundError as e:
         print(f" Fehler: 'wkhtmltopdf' nicht gefunden oder nicht im Pfad. PDF kann nicht erstellt werden.")
         print(f"   Bitte installieren und ggf. Pfad konfigurieren: {e}")
         # Don't exit - HTML was created successfully
    except OSError as e:
         # Catch potential wkhtmltopdf execution errors
         print(f" Fehler bei der PDF-Erstellung (wkhtmltopdf: {e}).")
         if "Done" not in str(e) and "Error" in str(e): # Crude check if wkhtmltopdf reported an error
              print("   Mögliche Ursachen: Fehler im HTML/CSS, fehlende Schriftarten, Berechtigungsprobleme.")
         # Don't exit - HTML was created successfully
    except Exception as e:
        print(f" Unerwarteter Fehler bei der PDF-Erstellung: {e}")
        # Don't exit - HTML was created successfully


# ------------------------------------------------------------
#  Command Line Interface
# ------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HTML and PDF summary reports for a GPX stage.")

    # Required arguments matching Snakefile rule inputs/outputs
    parser.add_argument("--basename", required=True, help="Basename of the stage (e.g., TT25_D6_1_Buriano).")
    parser.add_argument("--stats-csv", required=True, help="Path to the overall statistics CSV.")
    parser.add_argument("--profile-png", required=True, help="Path to the (potentially annotated) profile plot PNG.")
    parser.add_argument("--peak-csv", required=True, help="Path to the peak/segment data CSV.")
    parser.add_argument("--map-html", required=True, help="Path to the interactive map HTML.")
    parser.add_argument("--map-png", required=True, help="Path to the map screenshot PNG.")
    parser.add_argument("--markdown-text", required=True, help="Path to the place descriptions Markdown file.")
    parser.add_argument("--sorted-places", required=True, help="Path to the sorted places CSV.")
    parser.add_argument("--geocoded-opt-csv", required=True, help="Path to optimized track CSV with location (4).")
    parser.add_argument("--output-html", required=True, help="Path to save the final HTML summary.")
    parser.add_argument("--output-pdf", required=True, help="Path to save the final PDF summary.")

    # Optional arguments for potential future enhancements
    parser.add_argument("--speed-profile", help="Optional path to the speed profile PNG.")
    parser.add_argument("--surface-data", help="Optional path to the surface data CSV.")
    parser.add_argument("--power-data", help="Optional path to the power estimate CSV.")

    args = parser.parse_args()
    generate_summary(args)