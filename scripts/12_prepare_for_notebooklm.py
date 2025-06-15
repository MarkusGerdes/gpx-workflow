#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_prepare_for_notebooklm.py
----------------------------
Consolidates GPX analysis results into a structured markdown file
optimized for AI knowledge systems like Google NotebookLM.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "12_prepare_for_notebooklm.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Advanced markdown consolidation with processing performance tracking and metadata export"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === IMPORTS ===
import pandas as pd
import argparse
import os
from pathlib import Path
import sys
from datetime import datetime
import csv
import time

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def save_metadata_csv(basename: str, metadata: dict):
    """Save detailed metadata about export processing performance."""
    metadata_csv_path = f"output/{basename}_notebooklm_export_metadata.csv"
    
    try:
        os.makedirs(os.path.dirname(metadata_csv_path), exist_ok=True)
        
        with open(metadata_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header-Kommentare
            writer.writerow(['# NotebookLM Export Metadata'])
            writer.writerow([f'# Script: {SCRIPT_NAME} v{SCRIPT_VERSION}'])
            writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([f'# Basename: {basename}'])
            writer.writerow(['# Performance tracking for markdown consolidation and export processing'])
            writer.writerow([])
            
            # CSV-Header
            writer.writerow(['Metric', 'Value', 'Unit', 'Category'])
            
            # Schreibe alle Metadaten
            for key, value in metadata.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        category = key.replace('_', ' ').title()
                        metric = sub_key.replace('_', ' ').title()
                        
                        if 'time' in sub_key.lower():
                            unit = 'seconds'
                        elif 'size' in sub_key.lower() or 'length' in sub_key.lower():
                            unit = 'bytes' if 'size' in sub_key.lower() else 'characters'
                        elif 'count' in sub_key.lower():
                            unit = 'items'
                        elif 'percentage' in sub_key.lower():
                            unit = '%'
                        else:
                            unit = 'value'
                            
                        writer.writerow([metric, sub_value, unit, category])
                else:
                    unit = 'seconds' if 'time' in key.lower() else 'value'
                    category = 'General'
                    writer.writerow([key.replace('_', ' ').title(), value, unit, category])
                    
        print(f"[Info] Export metadata saved: {metadata_csv_path}")
        
    except Exception as e:
        print(f"[Warning] Could not save metadata CSV: {e}")

# --- Einführender Text für die konsolidierte Datei ---
INTRODUCTION_TEXT = """
Dieser Bericht fasst die detaillierte Analyse der GPX-Route '{basename}' zusammen.
Die folgenden Abschnitte enthalten statistische Auswertungen, Informationen zu
Höhenprofil, Peaks, Oberflächenbeschaffenheit, interessanten Punkten (POIs)
entlang der Strecke, durchfahrenen Orten sowie eine KI-generierte
Beschreibung der Highlights.

Diese Daten können als Wissensbasis für Fragen zur Tourplanung,
Charakteristik der Strecke oder spezifischen Details verwendet werden.
"""

# --- Formatierungsfunktionen für jeden CSV-Typ ---

def format_stats_csv(filepath: str) -> str:
    """Formatiert die Gesamtstatistiken der Tour."""
    if not os.path.exists(filepath):
        return "## Tour-Statistiken\n\n- Daten nicht verfügbar.\n\n"
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            return "## Tour-Statistiken\n\n- Keine statistischen Daten vorhanden.\n\n"
        
        md_string = "## Tour-Statistiken\n\n"
        md_string += "Diese Statistiken geben einen Gesamtüberblick über die Tour, basierend auf den GPX-Daten und optionalen externen Höhendaten.\n\n"
        for _, row in df.iterrows():
            md_string += f"- **{row['Statistik']}:** {row.get('Wert', 'N/A')}\n"
        return md_string + "\n"
    except Exception as e:
        return f"## Tour-Statistiken\n\n- Fehler beim Lesen der Statistikdaten: {e}\n\n"

def format_peaks_segments_csv(filepath: str) -> str:
    """Formatiert die Peak- und Segmentanalyse."""
    if not os.path.exists(filepath):
        return "## Peak- und Segmentanalyse\n\n- Daten nicht verfügbar.\n\n"
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            return "## Peak- und Segmentanalyse\n\n- Keine Peak- oder Segmentdaten vorhanden.\n\n"

        md_string = "## Peak- und Segmentanalyse\n\n"
        md_string += "Diese Analyse identifiziert die signifikantesten Gipfel (Peaks) auf der Route und die dazugehörigen Anstiege. Die Daten basieren auf dem geglätteten Höhenprofil.\n\n"
        
        peaks = df[df['item_type'] == 'Peak']
        segments = df[df['item_type'] == 'Valid Segment']

        if not peaks.empty:
            md_string += "### Top Peaks (Gipfel):\n"
            for _, r in peaks.iterrows():
                md_string += f"- Peak {int(r['peak_rank'])}: Höhe **{r['peak_elev_m']:.0f} m** bei Kilometer {r['peak_dist_km']:.1f}\n"
        
        if not segments.empty:
            md_string += "\n### Signifikante Anstiege zu den Peaks:\n"
            for _, r in segments.iterrows():
                direction = "Anstieg zum Peak (von davor)" if r['segment_direction'] == "backward" else "Anstieg nach dem Peak"
                md_string += (f"- Zu Peak {int(r['peak_rank'])} ({direction}): "
                              f"Höhengewinn **+{r['segment_gain_m']:.0f} m** über eine Distanz von {r['segment_length_m']:.0f} m "
                              f"(von km {r['segment_start_km']:.1f} bis km {r['segment_end_km']:.1f})\n")
        
        if peaks.empty and segments.empty:
            md_string += "- Keine signifikanten Peaks oder Anstiege gemäß den Kriterien gefunden.\n"
            
        return md_string + "\n"
    except Exception as e:
        return f"## Peak- und Segmentanalyse\n\n- Fehler beim Lesen der Peak-/Segmentdaten: {e}\n\n"

def format_surface_data_csv(filepath: str, dist_col_name: str, performance_data: dict) -> str:
    """Formatiert die Oberflächenverteilung entlang der Route mit Performance-Tracking."""
    section_start_time = time.time()
    print(f"[DEBUG 12 - Surface Func] Aufruf für: {filepath}, Distanzspalte: '{dist_col_name}'", file=sys.stderr)
    
    if not os.path.exists(filepath):
        print(f"[DEBUG 12 - Surface Func] Datei nicht gefunden: {filepath}", file=sys.stderr)
        return "## Oberflächenverlauf\n\n- Daten nicht verfügbar.\n\n"
    
    try:
        df = pd.read_csv(filepath)
        print(f"[DEBUG 12 - Surface Func] Geladen: {filepath}, Zeilen: {len(df)}, Spalten: {df.columns.tolist()}", file=sys.stderr)

        if df.empty:
            print(f"[DEBUG 12 - Surface Func] DataFrame ist initial leer.", file=sys.stderr)
            return "## Oberflächenverlauf\n\n- Keine Oberflächendaten vorhanden.\n\n"
        
        required_cols = ['Surface', dist_col_name, 'Latitude', 'Longitude']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            print(f"[DEBUG 12 - Surface Func] Fehlende Spalten: {missing}. Verfügbare Spalten: {df.columns.tolist()}", file=sys.stderr)
            return f"## Oberflächenverlauf\n\n- Benötigte Spalten für Oberflächenanalyse nicht gefunden: {missing}.\n\n"

        md_string = "## Oberflächenverlauf\n\n"
        md_string += "Die folgende Auflistung zeigt die Verteilung der verschiedenen Wegoberflächen entlang der Route...\n\n"
        
        if 'original_index' in df.columns:
            df['original_index'] = pd.to_numeric(df['original_index'], errors='coerce')
            df.dropna(subset=['original_index'], inplace=True)
            if not df.empty: 
                df.sort_values(by='original_index', inplace=True)
                df.reset_index(drop=True, inplace=True)
            print(f"[DEBUG 12 - Surface Func] Nach original_index Sortierung: {len(df)} Zeilen.", file=sys.stderr)

        if df.empty:
            print(f"[DEBUG 12 - Surface Func] DataFrame nach original_index Verarbeitung leer.", file=sys.stderr)
            return "## Oberflächenverlauf\n\n- Keine Daten nach Index-Verarbeitung.\n\n"

        df['Surface_Group'] = (df['Surface'].astype(str).str.lower() != df['Surface'].astype(str).str.lower().shift()).cumsum()
        print(f"[DEBUG 12 - Surface Func] Surface_Group erstellt. Einzigartige Gruppen-IDs: {df['Surface_Group'].nunique()}", file=sys.stderr)
        
        surface_summary = []
        
        df[dist_col_name] = pd.to_numeric(df[dist_col_name], errors='coerce')
        if df[dist_col_name].isna().all():
             print(f"[DEBUG 12 - Surface Func] Distanzspalte '{dist_col_name}' enthält nur NaNs.", file=sys.stderr)
             return "## Oberflächenverlauf\n\n- Keine validen Distanzwerte in den Oberflächendaten.\n\n"

        valid_distances = df[dist_col_name].dropna()
        total_route_distance = valid_distances.max() - valid_distances.min() if not valid_distances.empty else 0
        print(f"[DEBUG 12 - Surface Func] Berechnete Gesamtstrecke für Prozent: {total_route_distance:.2f} km", file=sys.stderr)

        for group_id, group in df.groupby('Surface_Group'):
            if group.empty: 
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} ist leer, übersprungen.", file=sys.stderr)
                continue
            surface = group['Surface'].iloc[0].lower() 
            
            start_km_val = group[dist_col_name].iloc[0]
            end_km_val = group[dist_col_name].iloc[-1]

            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id}: Surface='{surface}', Start={start_km_val}, End={end_km_val}", file=sys.stderr)

            if pd.isna(start_km_val) or pd.isna(end_km_val):
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} übersprungen wegen NaN in Start/End km.", file=sys.stderr)
                continue
                
            length_km = end_km_val - start_km_val
            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id}: Länge berechnet={length_km:.2f}", file=sys.stderr)

            if length_km < 0.01: 
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} übersprungen wegen Länge < 0.01km.", file=sys.stderr)
                continue 
            
            surface_summary.append({'Surface': surface.capitalize(), 'Length_km': length_km})
            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} zu surface_summary hinzugefügt: {surface.capitalize()}, {length_km:.2f}km", file=sys.stderr)

        if not surface_summary:
            print(f"[DEBUG 12 - Surface Func] surface_summary Liste ist leer nach Verarbeitung aller Gruppen.", file=sys.stderr)
            md_string += "- Keine detaillierten Oberflächenabschnitte verfügbar oder alle Segmente zu kurz.\n"
        else:
            summary_df = pd.DataFrame(surface_summary)
            surface_totals = summary_df.groupby('Surface')['Length_km'].sum().sort_values(ascending=False)
            
            if total_route_distance > 0:
                for surface_type, length in surface_totals.items():
                    percentage = (length / total_route_distance) * 100
                    md_string += f"- **{surface_type}:** ca. {length:.2f} km ({percentage:.1f}%)\n"
            else:
                for surface_type, length in surface_totals.items():
                     md_string += f"- **{surface_type}:** ca. {length:.2f} km\n"
            print(f"[DEBUG 12 - Surface Func] Finale Markdown-Sektion für Oberflächen erstellt.", file=sys.stderr)
            
        # Performance-Tracking für diese Sektion
        performance_data['section_processing']['surface_data_processing_time'] = time.time() - section_start_time
        performance_data['section_processing']['surface_markdown_length'] = len(md_string)
        performance_data['section_processing']['surface_groups_processed'] = len(surface_summary) if surface_summary else 0
        
        return md_string + "\n"
    except Exception as e:
        import traceback
        performance_data.setdefault('error_handling', {})['surface_processing_error'] = str(e)
        performance_data['section_processing']['surface_data_processing_time'] = time.time() - section_start_time
        print(f"[FEHLER 12 - Surface Func] Unerwarteter Fehler in format_surface_data_csv: {e}\n{traceback.format_exc()}", file=sys.stderr)
        return f"## Oberflächenverlauf\n\n- Fehler beim Lesen/Verarbeiten der Oberflächendaten: {e}\n\n"

def format_pois_csv(filepath: str) -> str:
    """Formatiert die Liste der relevanten POIs."""
    if not os.path.exists(filepath):
        return "## Relevante Punkte entlang der Strecke (POIs)\n\n- Daten nicht verfügbar.\n\n"
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            return "## Relevante Punkte entlang der Strecke (POIs)\n\n- Keine relevanten POIs gefunden.\n\n"
        
        md_string = "## Relevante Punkte entlang der Strecke (POIs)\n\n"
        md_string += "Diese Liste enthält interessante Punkte (Points of Interest) wie Gipfel, Aussichtspunkte oder Service-Einrichtungen, die in der Nähe der Route liegen. Die Höhenangaben stammen entweder direkt aus OpenStreetMap oder wurden von der Route abgeleitet.\n\n"
        
        # Gruppiere nach Typ für bessere Lesbarkeit
        for poi_type, group in df.groupby('Typ'):
            if group.empty: 
                continue
            md_string += f"### {poi_type.replace('_', ' ').capitalize()}:\n"
            for _, row in group.iterrows():
                name = row.get('Name', 'Unbekannt')
                elev_info = f", Höhe: {row['Elevation']:.0f}m" if pd.notna(row.get('Elevation')) else ""
                dist_info = f" (ca. {row['Entfernung_m']:.0f}m von der Route entfernt"
                track_dist_info = f", bei km {row['Nearest_Track_Dist_km']:.1f} der Route)" if pd.notna(row.get('Nearest_Track_Dist_km')) else ")"
                if pd.isna(row.get('Entfernung_m')) or row.get('Entfernung_m', -1) < 0:
                    dist_info = ")"
                    track_dist_info = ""
                
                md_string += f"- **{name}**{elev_info}{dist_info}{track_dist_info}\n"
            md_string += "\n"
            
        return md_string
    except Exception as e:
        return f"## Relevante Punkte entlang der Strecke (POIs)\n\n- Fehler beim Lesen der POI-Daten: {e}\n\n"

def format_places_csv(filepath: str) -> str:
    """Formatiert die Liste der relevanten Orte."""
    if not os.path.exists(filepath):
        return "## Durchfahrene / Nahegelegene Orte\n\n- Daten nicht verfügbar.\n\n"
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            return "## Durchfahrene / Nahegelegene Orte\n\n- Keine relevanten Orte gefunden.\n\n"
        
        md_string = "## Durchfahrene / Nahegelegene Orte\n\n"
        md_string += "Diese Orte wurden anhand der Geocodierung der Route identifiziert und nach ihrer Relevanz (z.B. Nähe zur Route) gefiltert. Die Höhenangabe bezieht sich auf den nächstgelegenen Punkt der Route zum Ortszentrum.\n\n"
        
        for _, row in df.iterrows():
            ort = row.get('Ort', 'Unbekannter Ort')
            dist_km_track = row.get('Nächster_Punkt_Distanz_km', 0)
            hoehe_track = row.get('Nächster_Punkt_Hoehe_m', 0)
            dist_to_route_m = row.get('Distanz_Center_zu_Route_m', -1)

            dist_to_route_info = f" (Zentrum ca. {dist_to_route_m:.0f}m von der Route entfernt)" if dist_to_route_m >= 0 else ""

            md_string += (f"- **{ort}**{dist_to_route_info}\n"
                          f"  - Die Route passiert diesen Ort (oder dessen Nähe) bei ca. km {dist_km_track:.1f} "
                          f"(Höhe dort ca. {hoehe_track:.0f}m).\n")
        return md_string + "\n"
    except Exception as e:
        return f"## Durchfahrene / Nahegelegene Orte\n\n- Fehler beim Lesen der Ortsdaten: {e}\n\n"

def read_markdown_file(filepath: str) -> str:
    """Liest den Inhalt einer Markdown-Datei (z.B. von Gemini)."""
    if not os.path.exists(filepath):
        return "## KI-generierte Routenbeschreibung\n\n- Keine Beschreibung verfügbar.\n\n"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Optional: Füge hier einen Titel hinzu, wenn die Gemini-MD-Datei keinen hat
        if not content.strip().startswith("#"):
            content = "## KI-generierte Routenbeschreibung und Highlights\n\n" + content
        return content + "\n\n"
    except Exception as e:
        return f"## KI-generierte Routenbeschreibung\n\n- Fehler beim Lesen der Markdown-Datei: {e}\n\n"

# --- Hauptfunktion ---
def main():
    print_script_info()
    
    # === PERFORMANCE-TRACKING INITIALISIERUNG ===
    start_time = time.time()
    performance_data = {
        'processing_phases': {},
        'input_files': {},
        'section_processing': {},
        'output_generation': {},
        'error_handling': {},
        'content_stats': {}
    }
    
    print(f"[Performance] Export processing started at {datetime.now().strftime('%H:%M:%S')}")
    
    parser = argparse.ArgumentParser(description="Konsolidiert GPX Analyseergebnisse für NotebookLM.")
    parser.add_argument("--basename", required=True, help="Basename der GPX-Datei für Titel.")
    parser.add_argument("--stats-csv", required=True, help="Pfad zur CSV mit Gesamtstatistiken.")
    parser.add_argument("--peak-csv", required=True, help="Pfad zur CSV mit Peak- und Segmentdaten.")
    parser.add_argument("--surface-data", required=True, help="Pfad zur CSV mit Oberflächendaten.")
    parser.add_argument("--dist-col-name-from-config", required=True, help="Name der Distanzspalte in Surface-Daten CSV.")
    parser.add_argument("--pois-csv", required=True, help="Pfad zur CSV mit relevanten POIs.")
    parser.add_argument("--places-csv", required=True, help="Pfad zur CSV mit relevanten Orten.")
    parser.add_argument("--gemini-md", required=True, help="Pfad zur Markdown-Datei mit Gemini-Beschreibungen.")
    parser.add_argument("--output-md", required=True, help="Pfad zur Ausgabe-Markdown-Datei.")
    args = parser.parse_args()
    
    # === INPUT FILES PERFORMANCE TRACKING ===
    input_files_to_track = [
        ('stats_csv', args.stats_csv),
        ('peak_csv', args.peak_csv),
        ('surface_data', args.surface_data),
        ('pois_csv', args.pois_csv),
        ('places_csv', args.places_csv),
        ('gemini_md', args.gemini_md)
    ]
    
    for file_type, file_path in input_files_to_track:
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            performance_data['input_files'][file_type] = {
                'file_size_bytes': file_size,
                'file_size_kb': round(file_size / 1024, 2),
                'last_modified': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'exists': True
            }
        else:
            performance_data['input_files'][file_type] = {'exists': False}

    output_dir = os.path.dirname(args.output_md)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Erstelle den globalen Einführungstext
    intro = INTRODUCTION_TEXT.format(basename=args.basename)
    
    # === CONTENT PROCESSING MIT PERFORMANCE-TRACKING ===
    content_processing_start = time.time()
    
    # Sammle alle formatierten Inhalte
    all_content = intro
    performance_data['content_stats']['intro_length'] = len(intro)
    
    print("[Performance] Processing sections...")
    
    # Verarbeite jede Sektion mit Timing
    section_start = time.time()
    stats_content = format_stats_csv(args.stats_csv)
    all_content += stats_content
    performance_data['content_stats']['stats_section_length'] = len(stats_content)
    performance_data['section_processing']['stats_processing_time'] = time.time() - section_start
    
    section_start = time.time()
    peaks_content = format_peaks_segments_csv(args.peak_csv)
    all_content += peaks_content
    performance_data['content_stats']['peaks_section_length'] = len(peaks_content)
    performance_data['section_processing']['peaks_processing_time'] = time.time() - section_start
    
    # Surface-Data mit erweiterten Performance-Daten
    all_content += format_surface_data_csv(args.surface_data, args.dist_col_name_from_config, performance_data)
    
    section_start = time.time()
    pois_content = format_pois_csv(args.pois_csv)
    all_content += pois_content
    performance_data['content_stats']['pois_section_length'] = len(pois_content)
    performance_data['section_processing']['pois_processing_time'] = time.time() - section_start
    
    section_start = time.time()
    places_content = format_places_csv(args.places_csv)
    all_content += places_content
    performance_data['content_stats']['places_section_length'] = len(places_content)
    performance_data['section_processing']['places_processing_time'] = time.time() - section_start
    
    section_start = time.time()
    gemini_content = read_markdown_file(args.gemini_md)
    all_content += gemini_content
    performance_data['content_stats']['gemini_section_length'] = len(gemini_content)
    performance_data['section_processing']['gemini_processing_time'] = time.time() - section_start
    
    # Finale Content-Statistiken
    performance_data['processing_phases']['content_processing_time'] = time.time() - content_processing_start
    performance_data['content_stats']['total_content_length'] = len(all_content)
    performance_data['content_stats']['total_sections'] = 6

    # === OUTPUT GENERATION MIT PERFORMANCE-TRACKING ===
    output_generation_start = time.time()
    
    try:
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(all_content)
        
        # Output-Performance-Tracking
        output_file_size = os.path.getsize(args.output_md)
        performance_data['output_generation']['output_file_size_bytes'] = output_file_size
        performance_data['output_generation']['output_file_size_kb'] = round(output_file_size / 1024, 2)
        performance_data['output_generation']['write_time'] = time.time() - output_generation_start
        
        print(f"[OK] Konsolidierte Markdown-Datei für NotebookLM gespeichert: {args.output_md}")
        print(f"[Performance] Output file size: {performance_data['output_generation']['output_file_size_kb']} KB")
        
    except Exception as e:
        performance_data['error_handling']['output_write_error'] = str(e)
        performance_data['output_generation']['write_time'] = time.time() - output_generation_start
        print(f"[FEHLER] Schreiben der finalen Markdown-Datei fehlgeschlagen: {e}", file=sys.stderr)
        sys.exit(1)
    
    # === FINALES PERFORMANCE-TRACKING ===
    total_processing_time = time.time() - start_time
    performance_data['processing_phases']['total_processing_time'] = total_processing_time
    performance_data['processing_phases']['output_generation_time'] = time.time() - output_generation_start
    
    print(f"[Performance] Total export processing time: {total_processing_time:.2f} seconds")
    print(f"[Performance] Content efficiency: {performance_data['content_stats']['total_content_length'] / total_processing_time:.0f} chars/second")
    
    # Speichere Metadaten
    save_metadata_csv(args.basename, performance_data)

if __name__ == "__main__":
    main()
