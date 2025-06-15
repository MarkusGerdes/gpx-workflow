#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_prepare_for_notebooklm.py
----------------------------
Konsolidiert die Ergebnisse der GPX-Analyse für eine einzelne Tour
in eine gut strukturierte Markdown- oder Textdatei, die als Quelle
für KI-Modelle wie Google NotebookLM dienen kann.
"""

SCRIPT_NAME = "12_prepare_for_notebooklm.py"
SCRIPT_VERSION = "1.0.0" # Einführung einer Versionskontrolle, lauffaehiges Script

import pandas as pd
import argparse
import os
from pathlib import Path
import sys

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

def format_surface_data_csv(filepath: str, dist_col_name: str) -> str:
    """Formatiert die Oberflächenverteilung entlang der Route."""
    print(f"[DEBUG 12 - Surface Func] Aufruf für: {filepath}, Distanzspalte: '{dist_col_name}'", file=sys.stderr) # NEU
    if not os.path.exists(filepath):
        print(f"[DEBUG 12 - Surface Func] Datei nicht gefunden: {filepath}", file=sys.stderr) # NEU
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
                df.reset_index(drop=True, inplace=True) # Wichtig für korrekte .shift()
            print(f"[DEBUG 12 - Surface Func] Nach original_index Sortierung: {len(df)} Zeilen.", file=sys.stderr) # NEU

        if df.empty: # Erneute Prüfung nach Sortierung/dropna
            print(f"[DEBUG 12 - Surface Func] DataFrame nach original_index Verarbeitung leer.", file=sys.stderr) # NEU
            return "## Oberflächenverlauf\n\n- Keine Daten nach Index-Verarbeitung.\n\n"

        df['Surface_Group'] = (df['Surface'].astype(str).str.lower() != df['Surface'].astype(str).str.lower().shift()).cumsum()
        print(f"[DEBUG 12 - Surface Func] Surface_Group erstellt. Einzigartige Gruppen-IDs: {df['Surface_Group'].nunique()}", file=sys.stderr) # NEU
        
        surface_summary = []
        
        df[dist_col_name] = pd.to_numeric(df[dist_col_name], errors='coerce')
        if df[dist_col_name].isna().all():
             print(f"[DEBUG 12 - Surface Func] Distanzspalte '{dist_col_name}' enthält nur NaNs.", file=sys.stderr)
             return "## Oberflächenverlauf\n\n- Keine validen Distanzwerte in den Oberflächendaten.\n\n"

        valid_distances = df[dist_col_name].dropna()
        total_route_distance = valid_distances.max() - valid_distances.min() if not valid_distances.empty else 0
        print(f"[DEBUG 12 - Surface Func] Berechnete Gesamtstrecke für Prozent: {total_route_distance:.2f} km (Min: {valid_distances.min() if not valid_distances.empty else 'N/A'}, Max: {valid_distances.max() if not valid_distances.empty else 'N/A'})", file=sys.stderr)

        for group_id, group in df.groupby('Surface_Group'):
            if group.empty: 
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} ist leer, übersprungen.", file=sys.stderr) # NEU
                continue
            surface = group['Surface'].iloc[0].lower() 
            
            start_km_val = group[dist_col_name].iloc[0]
            end_km_val = group[dist_col_name].iloc[-1]

            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id}: Surface='{surface}', Roh-StartKm={start_km_val}, Roh-EndKm={end_km_val}", file=sys.stderr) # NEU

            if pd.isna(start_km_val) or pd.isna(end_km_val):
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} übersprungen wegen NaN in Roh Start/End km.", file=sys.stderr)
                continue
                
            length_km = end_km_val - start_km_val
            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id}: Länge berechnet={length_km:.2f}", file=sys.stderr) # NEU

            if length_km < 0.01: 
                print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} übersprungen wegen Länge < 0.01km.", file=sys.stderr)
                continue 
            
            surface_summary.append({'Surface': surface.capitalize(), 'Length_km': length_km})
            print(f"[DEBUG 12 - Surface Func] Gruppe {group_id} zu surface_summary hinzugefügt: {surface.capitalize()}, {length_km:.2f}km", file=sys.stderr) # NEU

        if not surface_summary:
            print(f"[DEBUG 12 - Surface Func] surface_summary Liste ist leer nach Verarbeitung aller Gruppen.", file=sys.stderr)
            md_string += "- Keine detaillierten Oberflächenabschnitte verfügbar oder alle Segmente zu kurz.\n"
        else:
            # ... (Rest der Formatierung mit surface_totals und Prozenten) ...
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
            
        return md_string + "\n"
    except Exception as e:
        import traceback
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
            if group.empty: continue
            md_string += f"### {poi_type.replace('_', ' ').capitalize()}:\n"
            for _, row in group.iterrows():
                name = row.get('Name', 'Unbekannt')
                elev_info = f", Höhe: {row['Elevation']:.0f}m" if pd.notna(row.get('Elevation')) else ""
                dist_info = f" (ca. {row['Entfernung_m']:.0f}m von der Route entfernt"
                track_dist_info = f", bei km {row['Nearest_Track_Dist_km']:.1f} der Route)" if pd.notna(row.get('Nearest_Track_Dist_km')) else ")"
                if pd.isna(row.get('Entfernung_m')) or row.get('Entfernung_m', -1) < 0: # Wenn Entfernung nicht valide ist
                    dist_info = ")" 
                    track_dist_info = "" # Dann auch keine Track-Distanz anzeigen
                
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

            dist_to_route_info = f" (Zentrum ca. {dist_to_route_m:.0f}m von der Route entfernt)" if dist_to_route_m >=0 else ""

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
        return content + "\n\n" # Stelle sicher, dass ein Absatz am Ende ist
    except Exception as e:
        return f"## KI-generierte Routenbeschreibung\n\n- Fehler beim Lesen der Markdown-Datei: {e}\n\n"

# --- Hauptfunktion ---
def main():
    parser = argparse.ArgumentParser(description="Konsolidiert GPX Analyseergebnisse für NotebookLM.")
    parser.add_argument("--basename", required=True, help="Basename der GPX-Datei für Titel.")
    parser.add_argument("--stats-csv", required=True, help="Pfad zur CSV mit Gesamtstatistiken.")
    parser.add_argument("--peak-csv", required=True, help="Pfad zur CSV mit Peak- und Segmentdaten.")
    parser.add_argument("--surface-data", required=True, help="Pfad zur CSV mit Oberflächendaten.")
    parser.add_argument("--dist-col-name-from-config", required=True, help="Name der Distanzspalte in Surface-Daten CSV.")
    parser.add_argument("--pois-csv", required=True, help="Pfad zur CSV mit relevanten POIs.")
    parser.add_argument("--places-csv", required=True, help="Pfad zur CSV mit relevanten Orten.")
    parser.add_argument("--gemini-md", required=True, help="Pfad zur Markdown-Datei mit Gemini-Beschreibungen.")
    parser.add_argument("--output-md", required=True, help="Pfad zur Ausgabe-Markdown-Datei.") # Geändert zu .md
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output_md)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Erstelle den globalen Einführungstext
    intro = INTRODUCTION_TEXT.format(basename=args.basename)

    # Sammle alle formatierten Inhalte
    all_content = intro
    all_content += format_stats_csv(args.stats_csv)
    all_content += format_peaks_segments_csv(args.peak_csv)
    all_content += format_surface_data_csv(args.surface_data, args.dist_col_name_from_config)
    all_content += format_pois_csv(args.pois_csv)
    all_content += format_places_csv(args.places_csv)
    all_content += read_markdown_file(args.gemini_md)

    try:
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(all_content)
        print(f"[OK] Konsolidierte Markdown-Datei für NotebookLM gespeichert: {args.output_md}")
    except Exception as e:
        print(f"[FEHLER] Schreiben der finalen Markdown-Datei fehlgeschlagen: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()