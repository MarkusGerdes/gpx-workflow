#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_generate_stage_summary.py
------------------------------------
Aggregates results into a final HTML summary report and PDF.
"""

SCRIPT_NAME = "11_generate_stage_summary.py"
SCRIPT_VERSION = "1.1.2" # Einführung einer Versionskontrolle, lauffaehiges Script, Meta Daten 2c, 4

import sys
import os
import argparse
import pandas as pd
from markdown import markdown
import pdfkit
import base64
from pathlib import Path
from typing import Optional, Dict # Dict hinzugefügt
from datetime import datetime
from geopy.distance import distance as geopy_distance
import json 

try:
    from tqdm import tqdm
except ImportError:
    print("[Warnung] tqdm nicht gefunden. Fortschrittsbalken werden nicht angezeigt.")
    def tqdm(iterable, *args, **kwargs): return iterable

# --- Globale Konstanten / Standardwerte ---
# Wird überschrieben, wenn aus Config geladen oder als Arg übergeben
DEFAULT_SURFACE_COLORS: Dict[str, str] = {
    "asphalt": "#212529", "paved": "#6c757d", "concrete": "#adb5bd",
    "paving_stones": "#78909C", "sett": "#546E7A", "cobblestone": "#A1887F",
    "compacted": "#795548", "fine_gravel": "#FFCA28", "gravel": "#FF8F00",
    "dirt": "#8D6E63", "ground": "#689F38", "unpaved": "#4E342E",
    "sand": "#FFF176", "grass": "#7CB342", "wood": "#BCAAA4",
    "unknown": "#E0E0E0", "default": "#D32F2F"
}

# --- Helper Functions ---
def read_file_content(path: str, default: str = "") -> str:
    if path and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.read()
        except Exception as e: print(f"[Warnung] Fehler Lesen {path}: {e}"); return default
    return default

def image_to_base64(img_path: str) -> Optional[str]:
    if not img_path or not os.path.exists(img_path): return None
    try:
        ext = Path(img_path).suffix.lower().strip('.'); mime = f"image/{ext}"
        if ext == 'svg': mime = 'image/svg+xml'
        with open(img_path, "rb") as img_file:
            return f"data:{mime};base64,{base64.b64encode(img_file.read()).decode('utf-8')}"
    except Exception as e: print(f"[Warnung] Fehler Base64 {img_path}: {e}"); return None

def calculate_distance_for_group(group: pd.DataFrame) -> float:
    dist_km = 0.0
    group_copy = group.copy() # Auf Kopie arbeiten
    group_copy['Latitude'] = pd.to_numeric(group_copy['Latitude'], errors='coerce')
    group_copy['Longitude'] = pd.to_numeric(group_copy['Longitude'], errors='coerce')
    group_copy = group_copy.dropna(subset=['Latitude', 'Longitude'])
    if len(group_copy) < 2: return 0.0
    coords = list(zip(group_copy['Latitude'], group_copy['Longitude']))
    for i in range(len(coords) - 1):
        try: dist_km += geopy_distance(coords[i], coords[i+1]).km
        except ValueError: continue
    return dist_km

def parse_metadata_from_csv_header(filepath: str) -> Dict[str, str]:
    """Liest Kommentarzeilen am Anfang einer CSV und parst sie als Metadaten."""
    metadata = {}
    if not filepath or not os.path.exists(filepath):
        return {"Error": f"Datei nicht gefunden: {filepath}"}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("#"):
                    line_content = line.lstrip('# ').strip()
                    if ':' in line_content:
                        key, value = line_content.split(':', 1)
                        metadata[key.strip()] = value.strip()
                else:
                    # Sobald eine Zeile nicht mit # beginnt, stoppen wir (Annahme: Daten beginnen)
                    break
    except Exception as e:
        metadata["Error"] = f"Fehler beim Lesen/Parsen des Headers von {filepath}: {e}"
    return metadata

# --- Main Generation Function ---
def generate_summary(args, surface_color_config: Dict[str, str]):
    print(f"[Info] Erstelle Zusammenfassung für: {args.basename}")
    run_start_time_report = datetime.now() # Define run_start_time_report

    # Emojis (könnten auch aus Config kommen)
    WORLD_MAP_EMOJI = "\N{WORLD MAP}" # 🗺️
    STATS_EMOJI = "\N{BAR CHART}" # 📊
    SURFACE_DIST_EMOJI = "\N{RAILWAY TRACK}" # 🛤️
    PROFILE_EMOJI = "\N{CHART WITH UPWARDS TREND}" # 📈
    SPEED_EMOJI = "\N{STOPWATCH}" # ⏱️
    PEAK_EMOJI = "\N{MOUNTAIN}" # ⛰️
    STREET_LIST_EMOJI = "\N{MOTORWAY}" # 🛣️
    DESCRIPTION_EMOJI = "\N{MEMO}" # 📝
    METADATA_EMOJI = "\N{SCROLL}" #    

    # --- 1. Lade Basis-Daten ---
    print("[Info] Lade Basis-Daten...")
    stats_html = "<tr><td colspan='2'>Statistiken nicht verfügbar.</td></tr>"
    if args.stats_csv and os.path.exists(args.stats_csv):
        try:
            stats_df = pd.read_csv(args.stats_csv, comment='#')
            if not stats_df.empty:
                stats_html = "\n".join([f"<tr><td>{r['Statistik']}</td><td>{r.get('Wert', 'N/A')}</td></tr>"
                                       for _, r in stats_df.iterrows()]) # .get('Wert') für Sicherheit
            if not stats_html.strip(): stats_html = "<tr><td colspan='2'>Keine gültigen Statistiken.</td></tr>"
        except Exception as e: stats_html = f"<tr><td colspan='2'>Fehler Statistik-CSV: {e}</td></tr>"

    peak_segment_html = "<p>Keine Peak/Segment Daten.</p>"
    if args.peak_csv and os.path.exists(args.peak_csv):
        try:
            peak_df = pd.read_csv(args.peak_csv, comment='#')
            if not peak_df.empty:
                parts = []
                peaks = peak_df[peak_df['item_type'] == 'Peak']
                segments = peak_df[peak_df['item_type'] == 'Valid Segment']
                if not peaks.empty:
                    parts.append("<h3>Top Peaks:</h3><ul>") # H3 statt H4 für bessere Hierarchie
                    for _, r in peaks.iterrows(): parts.append(f"<li>P{int(r['peak_rank'])}: {r['peak_elev_m']:.0f}m @ {r['peak_dist_km']:.1f}km</li>")
                    parts.append("</ul>")
                if not segments.empty:
                    parts.append("<h3>Zugehörige Anstiege:</h3>") # H3
                    cols = ['peak_rank','segment_direction','segment_start_km','segment_end_km','segment_length_m','segment_gain_m']
                    segments_display = segments.copy()
                    if 'peak_rank' in segments_display.columns:
                        segments_display['peak_rank'] = segments_display['peak_rank'].astype(int)
                    parts.append(segments_display[cols].to_html(index=False, classes="table table-sm table-striped table-hover", border=0, float_format='%.1f'))
                if parts: peak_segment_html = "\n".join(parts)
        except Exception as e: print(f"[Warnung] Fehler Peak-CSV: {e}")

    markdown_content = read_file_content(args.markdown_text, "<p>Keine Beschreibungen verfügbar.</p>")
    descriptions_html = markdown(markdown_content, extensions=['tables', 'fenced_code'])

    # --- NEU: Metadaten aus verschiedenen Quellen sammeln ---
    print("[Info] Lese Metadaten aus den Input-Dateien...", file=sys.stderr)
    all_metadata_html = "<h4>Verarbeitungs-Historie & Datenquellen:</h4><dl class='metadata-list'>"

    # Struktur: (Titel für den Report, Dateipfad-Argument, Präfix für Keys aus dem Header)
    metadata_sources = [
        ("GPX Parsing & Basistrack (1, 2)", args.input_csv_step2, "GPXParse"), # Annahme: parse_gpx_full schreibt Header
        ("Höhenanreicherung (2c)", args.track_csv_with_elevation, "ElevationAPI"),
        ("Reverse Geocoding (4)", args.geocoded_opt_csv, "ReverseGeocodeAPI"), # Wenn 4_reverse_geocode Header schreibt
        ("Oberflächenabfrage (4b)", args.surface_data, "SurfaceAPI"),
        ("Service POI Sammlung (5a)", args.service_pois_csv, "ServicePOI_API"), # Neues Argument
        ("Peak/Viewpoint Sammlung (5b)", args.peak_pois_json, "PeakViewPOI_API"), # JSON braucht andere Behandlung
        ("POI Filterung (5c)", args.pois_csv, "POIFilter"),
        ("Ortsanreicherung (8c)", args.sorted_places, "PlacesEnrich")
    ]

    for title, filepath_arg, key_prefix in metadata_sources:
        if filepath_arg and os.path.exists(filepath_arg):
            all_metadata_html += f"<dt>{title}</dt><dd><ul>"
            
            if filepath_arg.endswith(".json"): # Spezielle Behandlung für JSON Metadaten
                try:
                    with open(filepath_arg, 'r', encoding='utf-8') as f_json:
                        json_data = json.load(f_json)
                    meta_dict = json_data.get("metadata", {}) # Annahme: Metadaten sind unter "metadata"
                    if not meta_dict: meta_dict = {"Info": "Kein 'metadata'-Objekt im JSON gefunden."}
                except Exception as e_json:
                    meta_dict = {"JSON Parsing Error": str(e_json)}
            else: # Für CSVs
                meta_dict = parse_metadata_from_csv_header(filepath_arg)

            for key, value in meta_dict.items():
                # Zeige nur relevante Metadaten oder filtere sie hier
                # if "API_" in key or "Script" in key or "Timestamp" in key:
                all_metadata_html += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
            all_metadata_html += "</ul></dd>"
        else:
            all_metadata_html += f"<dt>{title}</dt><dd><ul><li>Input-Datei nicht gefunden oder nicht angegeben.</li></ul></dd>"
            
    all_metadata_html += f"<dt>Report Erstellung ({SCRIPT_NAME})</dt>"
    all_metadata_html += f"<dd><ul><li>Version: {SCRIPT_VERSION}</li><li>Generiert am: {run_start_time_report.strftime('%Y-%m-%d %H:%M:%S')}</li></ul></dd>"
    all_metadata_html += "</dl>"
    # --- ENDE METADATEN ---
 
    # --- 2. Lade und bereite Daten für Straßenliste und Oberflächenverteilung vor ---
    df_report_data = pd.DataFrame() # Haupt-DataFrame für den Report
    
    if args.geocoded_opt_csv and os.path.exists(args.geocoded_opt_csv):
        try:
            df_report_data = pd.read_csv(args.geocoded_opt_csv,
                                         dtype={'Street': str, 'City': str, 'PostalCode': str, 'original_index': 'Int64'},
                                         keep_default_na=False, comment='#')
            for col in ['Street', 'City', 'PostalCode']:
                if col in df_report_data.columns:
                    df_report_data[col] = df_report_data[col].replace('', f'{col}_(Leer)')
        except Exception as e:
            print(f"[Warnung] Fehler beim Laden von geocoded_opt_csv ({args.geocoded_opt_csv}): {e}")

    if args.surface_data and os.path.exists(args.surface_data):
        try:
            df_surface_raw = pd.read_csv(args.surface_data, dtype=str, keep_default_na=False, comment='#')
            if 'original_index' in df_surface_raw.columns:
                 df_surface_raw['original_index'] = pd.to_numeric(df_surface_raw['original_index'], errors='coerce').astype('Int64')
                 
                 # Merge nur, wenn df_report_data nicht leer ist und beide original_index haben
                 if not df_report_data.empty and 'original_index' in df_report_data.columns:
                    print("[Info] Merge geocodierte Route mit Oberflächendaten...")
                    cols_from_surface = ['original_index', 'Surface', 'Tracktype', 'Highway', 'Smoothness', args.dist_col_name_from_config]
                    cols_present = [c for c in cols_from_surface if c in df_surface_raw.columns]
                    
                    if 'original_index' in cols_present and args.dist_col_name_from_config in cols_present:
                        df_surface_subset = df_surface_raw[cols_present].drop_duplicates(subset=['original_index'])
                        df_report_data = pd.merge(df_report_data, df_surface_subset, on='original_index', how='left', suffixes=('', '_surf'))
                        
                        for s_col in ['Surface', 'Tracktype', 'Highway', 'Smoothness']:
                            if s_col not in df_report_data.columns: df_report_data[s_col] = 'N/A'
                            else: df_report_data[s_col] = df_report_data[s_col].fillna('N/A')
                        
                        dist_final_col = args.dist_col_name_from_config
                        if f"{dist_final_col}_surf" in df_report_data.columns:
                            df_report_data.rename(columns={f"{dist_final_col}_surf": dist_final_col}, inplace=True)
                        if dist_final_col not in df_report_data.columns: df_report_data[dist_final_col] = 0.0
                        else: df_report_data[dist_final_col] = pd.to_numeric(df_report_data[dist_final_col], errors='coerce').fillna(0.0)
                        print(f"[Info] Merge abgeschlossen. Angereicherter DataFrame hat {len(df_report_data)} Zeilen.")
                    else: print(f"[Warnung] 'original_index' oder Distanzspalte '{args.dist_col_name_from_config}' nicht in Roh-Oberflächendaten für Merge.")
                 else: print("[Warnung] Basis-DataFrame (df_report_data) für Merge leer oder ohne 'original_index'.")
            else: print(f"[Warnung] 'original_index' fehlt in Oberflächendatei: {args.surface_data}")
        except Exception as e: print(f"[Warnung] Fehler beim Laden/Mergen der Oberflächendaten: {e}")

    # Fallbacks, falls df_report_data nach allem leer ist oder Spalten fehlen
    if df_report_data.empty:
        print("[Warnung] df_report_data ist leer. Viele Sektionen werden Standardtext haben.")
    for expected_col in ['Surface', 'Tracktype', 'Highway', 'Smoothness', args.dist_col_name_from_config, 'Latitude', 'Longitude', 'Street', 'City', 'PostalCode']:
        if expected_col not in df_report_data.columns:
            df_report_data[expected_col] = 'N/A' if expected_col in ['Surface', 'Tracktype', 'Highway', 'Smoothness', 'Street', 'City', 'PostalCode'] else 0.0


    # --- 3. Erstelle HTML-Komponenten ---
    surface_legend_html_report = "<p>Keine Oberflächendaten für Legende.</p>"
    if 'Surface' in df_report_data.columns and not df_report_data.empty:
        unique_s = df_report_data['Surface'].astype(str).str.lower().unique()
        unique_s = [s for s in unique_s if s and s != 'n/a' and s != 'surface_(leer)']
        if not unique_s and 'unknown' in surface_color_config: unique_s = ['unknown']
        
        items_list = []
        s_in_legend = set()
        for s_k in unique_s:
            if s_k in surface_color_config: s_in_legend.add(s_k)
        if 'unknown' in surface_color_config and 'unknown' not in s_in_legend: s_in_legend.add('unknown')
        
        for s_key_sorted in sorted(list(s_in_legend)):
            color = surface_color_config.get(s_key_sorted, surface_color_config.get("default", "#CCCCCC"))
            name = s_key_sorted.replace("_", " ").capitalize()
            items_list.append(f'<li><span style="background-color:{color};"></span><span>{name}</span></li>')
        if items_list:
            surface_legend_html_report = f"""<div class="surface-legend-box"><h3>Legende Oberflächen</h3><ul>{''.join(items_list)}</ul></div>"""

    street_list_html = "<li>Straßenliste nicht erstellt.</li>"
    if not df_report_data.empty and all(c in df_report_data.columns for c in ['Street', 'City', 'Latitude', 'Longitude', 'Surface']):
        print("[Info] Erstelle Straßenliste...")
        # ... (Logik für street_list_html mit <details> und der neuen HTML-Struktur,
        #      verwendet df_report_data, das jetzt alle Spalten hat)
        #      Die Block-ID Erstellung und Iteration muss hier rein.
        #      (Code von deiner letzten Version hier einfügen und an df_report_data anpassen)
        # --- (Beginn Logik für Straßenliste, angepasst) ---
        block_def_cols_sl = ['Street', 'City', 'Surface', 'Tracktype', 'Highway', 'Smoothness']
        actual_block_def_cols_sl = [col for col in block_def_cols_sl if col in df_report_data.columns]
        
        if actual_block_def_cols_sl:
            group_key_series_sl = pd.Series(zip(*(df_report_data[col].astype(str) for col in actual_block_def_cols_sl)))
            is_new_block_sl = group_key_series_sl.ne(group_key_series_sl.shift())
            if not df_report_data.empty: is_new_block_sl.iloc[0] = True
            df_report_data['block_id_report_sl'] = is_new_block_sl.cumsum()
        else:
            if not df_report_data.empty: df_report_data['block_id_report_sl'] = 1

        html_parts_sl = []
        current_city_h_sl = None
        city_order_sl = df_report_data.drop_duplicates(subset=['City'], keep='first')['City'].tolist()
        ignore_cities_h_sl = ["Unbekannter Ort", "City_(Leer)", "N/A", "OrtUnbekanntFürBlock"]

        for city_val_sl in tqdm(city_order_sl, desc="Generiere Straßenliste"):
            if city_val_sl in ignore_cities_h_sl: continue
            city_df_grp_sl = df_report_data[df_report_data['City'] == city_val_sl]
            if city_df_grp_sl.empty: continue

            city_street_items_html_sl = []
            for _, block_df_grp_sl in city_df_grp_sl.groupby('block_id_report_sl'):
                if block_df_grp_sl.empty: continue
                first_sl = block_df_grp_sl.iloc[0]
                s_name_sl = first_sl.get('Street', 'N/A')
                s_postal_sl = first_sl.get('PostalCode', 'N/A')
                s_surf_sl = str(first_sl.get('Surface', 'Unbekannt')).lower()
                s_tracktype_sl = first_sl.get('Tracktype', 'N/A')
                s_highway_sl = first_sl.get('Highway', 'N/A')
                s_smooth_sl = first_sl.get('Smoothness', 'N/A')
                dist_block_sl = calculate_distance_for_group(block_df_grp_sl)

                s_display_sl = s_name_sl if s_name_sl not in ['N/A', 'Street_(Leer)', 'StraßeUnbekanntFürBlock'] else "Unbenannte Straße"
                p_display_sl = f", {s_postal_sl}" if s_postal_sl not in ['N/A', 'Keine PLZ', 'PostalCode_(Leer)'] else ""
                
                surface_text_parts_sl = []
                main_surf_class_sl = f"surface-{s_surf_sl.replace(' ', '_').replace('/', '_')}" # Ersetze Leerzeichen/Slashes für CSS
                if s_surf_sl not in ['unknown', 'n/a', '']: surface_text_parts_sl.append(f'<span class="main-surface {main_surf_class_sl}">{s_surf_sl.capitalize()}</span>')
                
                extra_info_sl = []
                if s_highway_sl not in ['N/A', 'none_found_in_radius', 'none_selected_from_candidates', 'api_query_failed', '']: extra_info_sl.append(f"Typ: {s_highway_sl}")
                if s_tracktype_sl not in ['N/A', '']: extra_info_sl.append(f"Güte: {s_tracktype_sl}")
                if s_smooth_sl not in ['N/A', '']: extra_info_sl.append(f"Belag: {s_smooth_sl}")
                
                details_surf_str_sl = "".join(surface_text_parts_sl)
                if extra_info_sl: details_surf_str_sl += f" <span class='extra-info'>({', '.join(extra_info_sl)})</span>"

                city_street_items_html_sl.append(f'<li><div class="street-name-km"><span class="street-name">{s_display_sl}{p_display_sl}</span><span class="street-km">- ca. {dist_block_sl:.2f} km</span></div><div class="surface-details">{details_surf_str_sl if details_surf_str_sl else " "}</div></li>')
            
            if city_street_items_html_sl:
                html_parts_sl.append(f"<details><summary>{city_val_sl}</summary><ul>{''.join(city_street_items_html_sl)}</ul></details>")
        
        if html_parts_sl: street_list_html = "\n".join(html_parts_sl)
        else: street_list_html = "<p>Keine relevanten Straßenabschnitte gefunden.</p>"
        # --- (Ende Logik für Straßenliste) ---


    surface_distribution_table_html = "<p>Keine Daten für Oberflächenverteilung.</p>"
    if not df_report_data.empty and 'Surface' in df_report_data.columns and args.dist_col_name_from_config in df_report_data.columns:
        try:
            # ... (Logik für surface_distribution_table_html mit Segment_Laenge_km_Report, wie zuletzt besprochen) ...
            # (Code von deiner letzten Version hier einfügen und an df_report_data anpassen)
            # --- (Beginn Logik für Oberflächentabelle, angepasst) ---
            df_for_summary_dist = df_report_data.copy()
            if 'original_index' in df_for_summary_dist.columns: df_for_summary_dist.sort_values(by='original_index', inplace=True)
            df_for_summary_dist['Latitude'] = pd.to_numeric(df_for_summary_dist['Latitude'], errors='coerce')
            df_for_summary_dist['Longitude'] = pd.to_numeric(df_for_summary_dist['Longitude'], errors='coerce')
            df_for_summary_dist.dropna(subset=['Latitude', 'Longitude'], inplace=True)
            df_for_summary_dist.reset_index(drop=True, inplace=True)

            s_lengths = []
            if len(df_for_summary_dist) > 1:
                for i in range(len(df_for_summary_dist)):
                    if i == 0: s_lengths.append(0.0)
                    else:
                        p1 = (df_for_summary_dist.loc[i-1, 'Latitude'], df_for_summary_dist.loc[i-1, 'Longitude'])
                        p2 = (df_for_summary_dist.loc[i, 'Latitude'], df_for_summary_dist.loc[i, 'Longitude'])
                        try: s_lengths.append(geopy_distance(p1, p2).km)
                        except ValueError: s_lengths.append(0.0)
            elif not df_for_summary_dist.empty: s_lengths.append(0.0)

            if len(s_lengths) == len(df_for_summary_dist): df_for_summary_dist['Segment_Length_Calc'] = s_lengths
            else: df_for_summary_dist['Segment_Length_Calc'] = 0.0
            
            if 'Segment_Length_Calc' in df_for_summary_dist.columns:
                summary_surf_dist = df_for_summary_dist.groupby('Surface')['Segment_Length_Calc'].sum().reset_index()
                summary_surf_dist.rename(columns={'Segment_Length_Calc': 'Distanz (km)'}, inplace=True)
            else: summary_surf_dist = pd.DataFrame(columns=['Surface', 'Distanz (km)'])

            total_d_val = summary_surf_dist['Distanz (km)'].sum()
            if total_d_val > 0: summary_surf_dist['Anteil (%)'] = (summary_surf_dist['Distanz (km)'] / total_d_val) * 100
            else: summary_surf_dist['Anteil (%)'] = 0.0
            summary_surf_dist = summary_surf_dist.sort_values(by='Distanz (km)', ascending=False)
            
            if summary_surf_dist['Distanz (km)'].sum() < 0.01:
                surface_distribution_table_html = "<p>Keine signifikanten Distanzen für Oberflächenverteilung.</p>"
            else:
                surface_distribution_table_html = summary_surf_dist.to_html(index=False, classes="table table-sm table-striped", border=0, float_format='%.2f')
        except Exception as e_s_sum_final:
            print(f"[Warnung] Fehler Erstellung Oberflächenverteilungstabelle: {e_s_sum_final}")
            surface_distribution_table_html = f"<p>Fehler bei Oberflächenverteilung: {e_s_sum_final}</p>"
        # --- (Ende Logik für Oberflächentabelle) ---


    # --- 4. Assets für Embedding ---
    print("[Info] Bereite Assets vor...")
    print(f"[DEBUG] args.profile_png Pfad: '{args.profile_png}'")
    if args.profile_png and os.path.exists(args.profile_png):
        print(f"[DEBUG] profile_png Datei existiert: {args.profile_png}")
    else:
        print(f"[DEBUG] profile_png Datei NICHT gefunden oder Pfad leer: {args.profile_png}")

    profile_plot_base64 = image_to_base64(args.profile_png)
    print(f"[DEBUG] profile_plot_base64 ist None? {profile_plot_base64 is None}")
    if profile_plot_base64 and len(profile_plot_base64) < 200: # Sehr kurze Base64 Strings sind verdächtig
        print(f"[DEBUG] profile_plot_base64 (erste 100 Zeichen): {profile_plot_base64[:100]}")

    plotly_3d_map_filename = os.path.basename(args.plotly_3d_html) if args.plotly_3d_html and os.path.exists(args.plotly_3d_html) else None
    
    profile_plot_base64 = image_to_base64(args.profile_png)
    map_screenshot_base64 = image_to_base64(args.map_png)
    speed_profile_base64 = image_to_base64(args.speed_profile) if args.speed_profile and os.path.exists(args.speed_profile) else None

    # --- Inhalte für Karten-Sektion vorbereiten ---
    map_png_filename = os.path.basename(args.map_png) if args.map_png and os.path.exists(args.map_png) else None
    map_html_filename = os.path.basename(args.map_html) if args.map_html and os.path.exists(args.map_html) else None
    
    html_only_map_content = f"""
    <div class="html-only">
        {f"<div><img src='{map_png_filename}' alt='Übersichtskarte' class='overview-map-image'></div><hr>" if map_png_filename else '<p>Kein Karten-Screenshot verfügbar.</p>'}
        <div class="mobile-only">
            <button class="toggle-map-button" onclick="toggleInteractiveMap()">Interaktive Karte anzeigen/ausblenden</button>
        </div>
        <div id="interactiveMapContainer" class="interactive-map-container desktop-only">
            {f"<iframe src='{map_html_filename}' class='interactive-map-iframe' title='Interaktive Streckenkarte'></iframe>" if map_html_filename else "<p>Keine interaktive Karte verfügbar.</p>"}
        </div>
    </div>"""
    pdf_only_map_content = f"""
    <div class="pdf-only">
        {f"<img src='{map_screenshot_base64}' alt='Karten-Screenshot' class='overview-map-image'>" if map_screenshot_base64 else '<p>Kein Karten-Screenshot für PDF verfügbar.</p>'}
    </div>"""

    # --- 5. HTML-Template ---
    # (Laden von bootstrap_css wie zuletzt korrigiert)
    # (HTML-Template mit ALLEN {{ und }} für CSS-Klammern und korrekten Emoji-Variablen)
    # (Der JavaScript-Block für den Toggle-Button muss auch im Template sein)
    # Der HTML-Template String aus deinem Beispiel-HTML ist hier die Vorlage.
    # Wichtig: Alle Python-Variablen müssen mit einfachen {var} eingefügt werden.
    # Alle literalen CSS-Klammern müssen {{ und }} sein.

    # (Hier folgt der lange html_template String, der jetzt die CSS-Variablen aus der Config verwenden sollte
    # und alle CSS-Klammern korrekt escaped hat, sowie die Emojis als Variablen einfügt)
    # Ich kürze ihn hier ab, da er sehr lang ist, aber die Struktur ist wichtig.
    
    # Lade CSS-Variablen aus der Config (Beispiel)
    # Dies sollte idealerweise einmal am Anfang von generate_summary geschehen
    # und die Farbwerte dann im CSS-Teil des Templates verwendet werden.
    # Für dieses Beispiel nehme ich an, die CSS-Variablen sind direkt im CSS-String unten.
    
    # Lade Bootstrap CSS
    bootstrap_css = ""
    project_root = Path(__file__).resolve().parent.parent
    bootstrap_css_path = project_root / "bootstrap.min.css"
    print(f"[DEBUG] Suche nach bootstrap.min.css unter: {bootstrap_css_path}")
    if bootstrap_css_path.exists():
        try:
            with open(bootstrap_css_path, "r", encoding="utf-8") as f_css: bootstrap_css = f_css.read()
            print(f"[INFO] bootstrap.min.css lokal geladen von: {bootstrap_css_path}")
            if not bootstrap_css.strip(): bootstrap_css = "/* BOOTSTRAP CSS WAR LEER */"
        except Exception as e: bootstrap_css = f"/* FEHLER LADEN BOOTSTRAP: {e} */"
    else: bootstrap_css = "/* BOOTSTRAP CSS NICHT GEFUNDEN */"


    html_template = f"""
<!DOCTYPE html><html lang='de'><head><meta charset='UTF-8'><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Etappenübersicht – {args.basename}</title>
    <style>
        {bootstrap_css}
    /* Custom Styles */
    :root {{# CSS Variablen Definition #
        --font-family-sans-serif: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        
        /* Farbpalette inspiriert vom Fahrradrahmen & Natur */
        --frame-base-gray: #7A8B8B;  /* Ein neutraleres Grau, basierend auf deinem Rahmen */
        --accent-green: #689F38;   /* Ein sattes, natürliches Grün */
        --accent-orange: #FFA000;  /* Ein warmes Orange für Highlights */

        --dark-text: #2c3e50;      /* Dunkles Blau/Grau für Text, gute Lesbarkeit */
        --medium-gray-border: #bdc3c7; /* Helles Grau für Ränder */
        --light-green-bg: #e8f5e9; /* Sehr helles, gedämpftes Grün für Seitenhintergrund */
        --card-bg: #ffffff;
        
        --heading-color: var(--dark-text);
        --text-color: var(--dark-text);
        --link-color: var(--accent-green);
        --link-hover-color: #558B2F; /* Dunkleres Grün für Hover */
        --border-color: var(--medium-gray-border);
        --table-header-bg: #f0f3f4; /* Sehr helles Grau für Tabellenköpfe */
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: var(--font-family-sans-serif);
        line-height: 1.6;
        color: var(--text-color);
        background-color: var(--light-green-bg); 
        padding: 1rem 0;
    }}

    .container {{
        max-width: 960px;
        margin: 0 auto;
        padding: 20px;
        background-color: var(--card-bg);
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
    }}

    h1, h2, h3 {{
        color: var(--heading-color);
        margin-bottom: 0.75em;
        margin-top: 1.5em;
        padding-bottom: 0.3em;
        border-bottom: 2px solid var(--border-color);
    }}
    h1:first-child, h2:first-child, h3:first-child {{ /* Beachte: CSS-Regeln ohne Deklarationen brauchen trotzdem die Klammern */
        margin-top: 0;
    }}

    h1 {{
        text-align: center;
        font-size: 2rem;
        margin-bottom: 1em;
        color: var(--frame-base-gray); 
    }}
    h2 {{ font-size: 1.6rem; color: var(--accent-green); }}
    h3 {{ font-size: 1.3rem; color: var(--heading-color); border-bottom-width: 1px; }}

    img.overview-map-image {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
        border: 1px solid var(--border-color);
        border-radius: 4px;
    }}

    .interactive-map-container {{# CSS-Regeln ohne Deklarationen brauchen trotzdem die Klammern #
        margin-top: 1em;
        margin-bottom: 2em;
    }}
    
    .interactive-map-iframe {{
        width: 100%;
        height: 500px;
        border: 1px solid var(--border-color);
        border-radius: 4px;
    }}

    .desktop-only {{ display: none; }}
    .mobile-only {{ display: block; }}

    .toggle-map-button {{
        display: block;
        width: 100%;
        padding: 0.75em;
        margin-bottom: 1em;
        background-color: var(--accent-green);
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        text-align: center;
        font-size: 1em;
        font-weight: bold;
    }}
    .toggle-map-button:hover {{
        background-color: var(--link-hover-color);
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1.5em;
        font-size: 0.9rem;
    }}
    th, td {{
        padding: 0.6em 0.5em;
        text-align: left;
        border: 1px solid var(--border-color);
    }}
    th {{
        background-color: var(--table-header-bg);
        font-weight: bold;
        color: var(--heading-color);
    }}
    tr:nth-child(even) {{
        background-color: #f9f9f9; 
    }}
    .stats-table td:first-child {{
        font-weight: bold;
        width: 40%;
        color: var(--heading-color); 
    }}
    .segment-summary table {{
        font-size: 0.85em;
    }}
    .table-responsive-container {{
        overflow-x: auto; 
    }}

    .surface-legend-box {{
        padding: 15px;
        border: 1px solid var(--border-color);
        border-radius: 5px;
        margin-top: 20px;
        margin-bottom: 20px;
        background-color: #fdfdfd; 
    }}
    .surface-legend-box h3 {{
        margin-top: 0;
        margin-bottom: 12px;
        font-size: 1.2em;
        color: var(--heading-color);
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 8px;
        text-align: left;
    }}
    .surface-legend-box ul {{
        list-style-type: none;
        padding-left: 0;
        margin-bottom: 0;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
    }}
    .surface-legend-box li {{
        font-size: 0.85em;
        display: flex;
        align-items: center;
        flex-basis: calc(33.333% - 10px);
    }}
    .surface-legend-box li span:first-child {{
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 1px solid #888;
        margin-right: 6px;
        vertical-align: middle;
    }}
    /* Die folgenden :nth-child Regeln sind spezifisch für die Anzahl der Legenden-Items. */
    /* Wenn die Anzahl dynamisch ist, ist es besser, Klassen zu verwenden oder die Styles inline zu setzen, */
    /* wie du es im Python-Code für die Legende bereits tust. */
    /* Ich lasse sie hier aus, da dein Python-Code die background-color inline setzt. */
    /* .surface-legend-box li:nth-child(1) span:first-child {{ background-color: #5D4037; }} */
    /* ... etc ... */


    .street-list details {{
        margin-bottom: 0.5em;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        background-color: #fdfdfd;
    }}
    .street-list summary {{
        padding: 0.6em 0.85em;
        background-color: var(--table-header-bg);
        cursor: pointer;
        font-weight: bold;
        color: var(--heading-color);
        list-style-type: "► "; 
    }}
    .street-list details[open] > summary {{
        list-style-type: "▼ "; 
        background-color: #dde3e7; 
    }}
    .street-list summary:hover {{
        background-color: #d8dcdf;
    }}
    
    .street-list ul {{
        list-style-type: none;
        padding: 0.5em 0.85em 0.85em 0.85em ;
    }}
    .street-list li {{
        display: flex; 
        justify-content: space-between; 
        align-items: flex-start; 
        border-bottom: 1px dotted #eee;
        padding: 0.5em 0; 
        font-size: 0.9em;
        gap: 10px; 
    }}
    .street-list li:last-child {{
        border-bottom: none;
    }}

    .street-name-km {{
        flex-grow: 1; 
    }}
    .street-name-km .street-name {{
        display: block; 
    }}
    .street-name-km .street-km {{
        color: #555;
        font-size: 0.9em;
    }}

    .surface-details {{
        flex-shrink: 0; 
        width: 220px;  
        text-align: right;
        font-size: 0.85em;
        color: #444;
    }}
    .surface-details .main-surface {{
        font-weight: bold;
        padding: 0.1em 0.4em; 
        border-radius: 3px; 
        color: var(--card-bg); 
    }}
    .surface-details .extra-info {{
        display: block; 
        font-size: 0.9em;
        color: #666;
        margin-top: 0.2em;
    }}
    .surface-details small {{ 
        color: #777;
    }}

    /* Klassen für Oberflächenfarben in der Straßenliste (dynamisch aus surface_color_config) */
    /* Diese werden im Python-Code generiert und hier eingefügt, wenn du sie nicht inline setzt */
    /* Beispiel: .surface-asphalt {{ background-color: #5D4037; }} */
    { "".join([f".surface-{key.replace(' ', '_').replace('/', '_')} {{ background-color: {val}; }}" for key, val in surface_color_config.items() if key != "default"]) }
    /* Spezifische Textfarben für helle Hintergründe, falls nötig */
    .surface-fine_gravel {{ color: var(--dark-text) !important; }}
    .surface-unknown {{ color: var(--dark-text) !important; }}
    .surface-unpaved {{ color: var(--dark-text) !important; }} /* Wenn Orange als Hintergrund für Unpaved verwendet wird */
    .surface-sand {{ color: var(--dark-text) !important; }} /* Wenn Sand sehr hell ist */


    .markdown-content {{
        line-height: 1.7;
        margin-top: 1.5em;
    }}
    .markdown-content article {{
        margin-bottom: 2em;
        padding: 1em;
        border-left: 3px solid var(--accent-green);
        background-color: #fdfdfd;
        border-radius: 0 4px 4px 0; 
    }}
    .markdown-content h2 {{ 
        font-size: 1.4em; 
        margin-top: 0;
        color: var(--frame-base-gray);
        border-bottom-width: 1px;
    }}
    .markdown-content h3 {{
        font-size: 1.15em;
        color: var(--dark-text);
        border-bottom: none;
        margin-top: 1em;
    }}
    .markdown-content p {{
        margin-bottom: 1em;
    }}
    .markdown-content strong {{
        color: var(--accent-green); 
    }}
    .markdown-content em, .markdown-content i {{
        color: var(--accent-orange); 
    }}
    .markdown-content p > strong:first-child {{ 
        font-size: 1.5em;
        margin-right: 0.2em;
    }}

    hr {{
        border: 0;
        height: 1px;
        background-color: var(--border-color);
        margin: 2em 0;
    }}

    /* HTML/PDF spezifische Anzeige */
    .pdf-only {{
        display: none; /* Im Browser ausblenden */
    }}
    .html-only {{
        display: block; /* Im Browser anzeigen (Standard, aber explizit) */
    }}

    @media print {{
        .html-only {{
            display: none !important; /* Im Druck/PDF ausblenden */
        }}
        .pdf-only {{
            display: block !important; /* Im Druck/PDF anzeigen */
        }}
        /* Optional: Button für interaktive Karte im Druck ausblenden */
        .toggle-map-button {{
            display: none !important;
        }}
        /* Optional: Den interaktiven Karten-Container im Druck ausblenden */
        #interactiveMapContainer.interactive-map-container {{
            display: none !important;
        }}
        
        /* NEUE REGELN FÜR <details> IM DRUCK/PDF */
        .street-list details {{  /* CSS-Regel Block beginnt */
            page-break-inside: avoid; /* Versucht, Umbrüche innerhalb eines Details-Blocks zu vermeiden */
        }} /* CSS-Regel Block endet */
        .street-list details[open] summary ~ * {{ /* CSS-Regel Block beginnt */
            display: block; /* Inhalt anzeigen */
        }} /* CSS-Regel Block endet */
        .street-list details summary::before, /* Pfeile entfernen/ändern, falls sie stören */
        .street-list details summary::-webkit-details-marker {{ /* CSS-Regel Block beginnt */
            display: none !important; /* Standard-Pfeil ausblenden */
        }} /* CSS-Regel Block endet */
        .street-list details summary {{ /* CSS-Regel Block beginnt */
            list-style-type: none !important; /* Standard-Pfeil auch hier entfernen */
            cursor: default; /* Cursor im PDF nicht als klickbar anzeigen */
            /* Optional: Füge einen statischen Indikator hinzu, wenn du möchtest */
            /* content: "▼ "; /* oder einfach nichts */
        }} /* CSS-Regel Block endet */
        /* WICHTIGSTE REGEL: Alle <details> im Druck standardmäßig öffnen */
        .street-list details {{ /* CSS-Regel Block beginnt */
            display: block !important; /* Stellt sicher, dass der Block existiert */
        }} /* CSS-Regel Block endet */
        .street-list details > summary {{ /* CSS-Regel Block beginnt */
            /* Optional: Aussehen der Zusammenfassung im PDF anpassen */
            /* background-color: #f0f0f0 !important; */ /* Beispiel */
        }} /* CSS-Regel Block endet */
        .street-list details > *:not(summary) {{ /* CSS-Regel Block beginnt */
            display: block !important; /* Macht den Inhalt sichtbar */
        }} /* CSS-Regel Block endet */
        /* Ende NEUE REGELN */
        
    }}

    /* Desktop-spezifische Stile */
    @media (min-width: 768px) {{
        body {{
            padding: 2rem;
        }}
        .container {{
            padding: 30px;
        }}
        h1 {{font-size: 2.5rem; }}
        h2 {{font-size: 1.8rem; }}
        h3 {{font-size: 1.4rem; }}

        .interactive-map-container {{
            display: block !important; 
        }}
        .mobile-only {{ display: none; }}
        .desktop-only {{ display: block; }}

        .surface-legend-box ul {{
            display: grid; /* Grid für Desktop ist eine gute Alternative zu column-count */
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); /* Spaltenbreite anpassen */
            gap: 5px 15px;
            column-count: auto; /* Deaktiviere column-count, wenn Grid verwendet wird */
        }}
         .surface-legend-box li {{
            flex-basis: auto; /* Nicht mehr nötig bei Grid-Layout für ul */
            /* display: flex; align-items: center; <-- bleibt gut für Inhalt des li */
        }}
    }}
</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Etappenübersicht: {args.basename}</h1>
        </header>
        <main>
            <section>
                <h2>{WORLD_MAP_EMOJI} Karte</h2>
                {html_only_map_content}
                {pdf_only_map_content}
                {surface_legend_html_report}
            </section>
            <hr>
            <section>
                <h2>{STATS_EMOJI} Statistiken</h2>
                <div class="table-responsive-container">
                    <table class="stats-table">
                        <thead><tr><th>Merkmal</th><th>Wert</th></tr></thead>
                        <tbody>{stats_html}</tbody>
                    </table>
                </div>
            </section>
            <hr>
            <section>
                <h2>{SURFACE_DIST_EMOJI} Oberflächenverteilung</h2>
                <div class="table-responsive-container">
                    {surface_distribution_table_html}
                </div>
            </section>
            <hr>
            <section>
                <h2>{PROFILE_EMOJI} Höhenprofil & 3D-Ansicht </h2>
                {f"<img src='{profile_plot_base64}' alt='Höhenprofil der Etappe' class='overview-map-image'>" if profile_plot_base64 else '<p>Kein Höhenprofil verfügbar.</p>'}
                {f"<h3>Interaktive 3D-Streckenansicht</h3>" if plotly_3d_map_filename else "<p>Keine interaktive 3D-Ansicht verfügbar.</p>"}
                <div class="html-only interactive-map-container">
                    {f"<iframe src='{plotly_3d_map_filename}' class='interactive-map-iframe' style='height: 600px;' title='Interaktive 3D-Streckenansicht'></iframe>" if plotly_3d_map_filename else "<p>Keine interaktive 3D-Ansicht verfügbar.</p>"}
                </div>                
            </section>
            {f"<h2>{SPEED_EMOJI} Geschwindigkeitsprofil</h2><img src='{speed_profile_base64}' alt='Geschwindigkeitsprofil' class='overview-map-image'>" if speed_profile_base64 else ''}
            <hr>
            <section class="segment-summary">
                <h2>{PEAK_EMOJI} Peak & Anstiegs-Analyse</h2>
                {peak_segment_html}
            </section>
            <hr>
            <section class="street-list">
                <h2>{STREET_LIST_EMOJI} Straßenverlauf mit Oberflächen</h2>
                {street_list_html}
            </section>
            <hr>
            <section>
                <h2>{DESCRIPTION_EMOJI} Beschreibungen & Highlights</h2>
                <div class="markdown-content">{descriptions_html}</div>
            </section>
            <section id="processing-metadata">
                <h2>{METADATA_EMOJI} Verarbeitungsdetails & Datenquellen</h2>
                {all_metadata_html}
            </section>      
        </main>
    </div>
    <script>
        function toggleInteractiveMap() {{
            const container = document.getElementById('interactiveMapContainer');
            if (container.style.display === 'none' || container.style.display === '') {{
                container.style.display = 'block';
            }} else {{
                container.style.display = 'none';
            }}
        }}
        document.addEventListener('DOMContentLoaded', function() {{
            const interactiveMapContainer = document.getElementById('interactiveMapContainer');
            const toggleButton = document.querySelector('.toggle-map-button');
            if (window.innerWidth < 768) {{ // Mobile Ansicht
                 if(interactiveMapContainer) interactiveMapContainer.style.display = 'none';
                 if(toggleButton) toggleButton.style.display = 'block';
            }} else {{ // Desktop Ansicht
                if(interactiveMapContainer) interactiveMapContainer.style.display = 'block';
                if(toggleButton) toggleButton.style.display = 'none';
            }}
        }});
    </script>
</body>
</html>
"""

    # --- HTML und PDF speichern ---
    print(f"[Info] Speichere HTML: {args.output_html}")
    try:
        Path(args.output_html).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_html, "w", encoding="utf-8") as f: f.write(html_template)
        print(f"[OK] HTML gespeichert: {args.output_html}")
    except Exception as e: print(f" Fehler Schreiben HTML: {e}"); sys.exit(1)

    print(f"[Info] Generiere PDF: {args.output_pdf}")
    if not Path(args.output_html).exists():
        print(f"[Fehler] HTML-Datei {args.output_html} nicht gefunden, PDF kann nicht erstellt werden.")
        return 

    try:
        options = {'page-size':'A4','margin-top':'10mm','margin-right':'10mm','margin-bottom':'10mm','margin-left':'10mm',
                   'encoding':"UTF-8",'enable-local-file-access':None,'quiet':'','load-error-handling':'ignore','load-media-error-handling':'ignore'}
        pdfkit.from_file(args.output_html, args.output_pdf, options=options)
        print(f"[OK] PDF gespeichert: {args.output_pdf}")
    except Exception as e: print(f" Fehler PDF-Erstellung (wkhtmltopdf?): {e}")


# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HTML and PDF summary reports.")
    parser.add_argument("--basename", required=True)
    parser.add_argument("--stats-csv", required=True)
    parser.add_argument("--profile-png", required=True)
    parser.add_argument("--plotly-3d-html", required=True, help="Path to the interactive 3D Plotly HTML file.")
    parser.add_argument("--peak-csv", required=True)
    parser.add_argument("--geocoded-opt-csv", required=True)
    parser.add_argument("--surface-data", required=True)
    parser.add_argument("--map-html", required=True)
    parser.add_argument("--map-png", required=True)
    parser.add_argument("--markdown-text", required=True)
    parser.add_argument("--sorted-places", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--output-pdf", required=True)
    parser.add_argument("--speed-profile", help="Optional path to speed profile PNG.")
    parser.add_argument("--dist-col-name-from-config", required=True, help="Name of the original distance column...")

    # NEU: Argument für die Config-Datei, um Farben zu laden
    parser.add_argument("--config-file", default="config.yaml", help="Path to the config.yaml file.")
    # NEU: Argument für die CSV, die die Metadaten der Höhenanreicherung enthält
    parser.add_argument("--track-csv-with-elevation", required=True, help="Path to the track CSV with elevation and potentially API metadata (output of 2c).")

    # START OF CRITICAL ADDITIONS FOR THE ERROR
    parser.add_argument("--pois-csv", required=True, help="Path to relevant POIs CSV (output of 5c).")
    parser.add_argument("--input-csv-step2", required=True, help="Path to full track data CSV (output of 2, used for metadata).")
    parser.add_argument("--service-pois-csv", required=True, help="Path to raw service POIs CSV (output of 5a, used for metadata).")
    parser.add_argument("--peak-pois-json", required=True, help="Path to raw peak/viewpoint POIs JSON (output of 5b, used for metadata).")
    # END OF CRITICAL ADDITIONS FOR THE ERROR

    args = parser.parse_args()
    
    # Lade Farbkonfiguration aus config.yaml
    import yaml # Stelle sicher, dass PyYAML installiert ist: pip install PyYAML
    
    loaded_config = {}
    config_file_path = args.config_file # Oder ein fester Pfad, wenn nicht über Arg
    
    # Versuche, die Haupt-Config-Datei zu laden, die Snakemake verwendet
    # Gehe davon aus, dass config.yaml im Projekt-Root liegt (eine Ebene über scripts/)
    project_root_for_config = Path(__file__).resolve().parent.parent
    actual_config_path = project_root_for_config / "config.yaml" # Standardpfad

    if os.path.exists(actual_config_path):
        print(f"[Info] Lade Konfiguration aus: {actual_config_path}")
        try:
            with open(actual_config_path, 'r', encoding='utf-8') as f_conf:
                loaded_config = yaml.safe_load(f_conf)
        except Exception as e_conf:
            print(f"[Warnung] Fehler beim Laden der config.yaml ({actual_config_path}): {e_conf}")
            print("[Info] Verwende Standardfarben.")
    else:
        print(f"[Warnung] config.yaml nicht unter {actual_config_path} gefunden. Verwende Standardfarben.")

    # Hole die Farbkarte aus der geladenen Config oder nimm den Default
    # Der zweite Parameter von generate_summary erwartet jetzt die Farbkarte
    surface_colors_for_template = loaded_config.get("design_theme", {}).get("surface_colors", DEFAULT_SURFACE_COLORS)
    
    print(f"[DEBUG] Verwendete Farbkarte für Template: {surface_colors_for_template}")    
    
    generate_summary(args, surface_colors_for_template) # Übergebe die Farbkarte