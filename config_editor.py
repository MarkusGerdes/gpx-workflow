#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_editor.py
------------------------------------
Streamlit-based configuration editor for GPX Workflow.
Provides a user-friendly GUI to edit config.yaml parameters.
"""

# === TOOL METADATA ===
TOOL_NAME = "GPX Workflow Config Editor"
TOOL_VERSION = "1.0.0"
TOOL_DESCRIPTION = "Streamlit GUI for editing GPX workflow configuration"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (2025-06-07): Added versioning system, improved documentation
v0.9.x (pre-2025): Original Streamlit interface with 10 tabs
"""

import streamlit as st
import yaml
from pathlib import Path
import pandas as pd
from datetime import datetime

# Standardpfad zur config.yaml (kann angepasst werden)
CONFIG_PATH = Path("config.yaml")

# Helferfunktion zum Laden der YAML-Datei
def load_config(path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {} # Leeres Dict, falls Datei nicht existiert

# Helferfunktion zum Speichern der YAML-Datei
def save_config(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, sort_keys=False, indent=2, default_flow_style=False)

# Helferfunktion zum Anzeigen von verschachtelten Dicts (für Debugging oder komplexe Strukturen)
def display_nested_dict(data, indent=0):
    for key, value in data.items():
        if isinstance(value, dict):
            st.markdown(f"{' ' * indent * 4}**{key}:**")
            display_nested_dict(value, indent + 1)
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            st.markdown(f"{' ' * indent * 4}**{key}:** (Liste von Objekten)")
            for i, item in enumerate(value):
                st.markdown(f"{' ' * (indent + 1) * 4}- Objekt {i+1}:")
                display_nested_dict(item, indent + 2)
        else:
            st.markdown(f"{' ' * indent * 4}**{key}:** {value}")


# --- Hauptanwendung ---
st.set_page_config(layout="wide", page_title="GPX Workflow Konfiguration")

# Header with version info
st.title(f"⚙️ {TOOL_NAME}")
st.markdown(f"**Version {TOOL_VERSION}** | Letzte Aktualisierung: {LAST_UPDATED} | Config-Kompatibilität: {CONFIG_COMPATIBILITY}")
st.markdown("Bearbeiten Sie hier die Parameter für Ihren GPX-Analyse-Workflow. Änderungen werden in der `config.yaml`-Datei gespeichert.")

# Show tool info in expandable section
with st.expander("ℹ️ Tool-Informationen & Changelog"):
    st.markdown(f"**Beschreibung:** {TOOL_DESCRIPTION}")
    st.markdown(f"**Autor:** {AUTHOR}")
    st.markdown("**Changelog:**")
    st.code(CHANGELOG, language="markdown")

# Lade aktuelle Konfiguration
config_data = load_config(CONFIG_PATH)
if not config_data:
    st.warning(f"Konfigurationsdatei `{CONFIG_PATH}` nicht gefunden. Es werden Standardwerte oder leere Felder angezeigt. Änderungen werden in einer neuen Datei gespeichert.")

# --- Sidebar für Navigation oder globale Aktionen ---
st.sidebar.header("Aktionen")
if st.sidebar.button("Konfiguration Speichern", type="primary", use_container_width=True):
    # Add metadata to config before saving
    config_data["_metadata"] = {
        "last_edited_by": TOOL_NAME,
        "last_edited_version": TOOL_VERSION,
        "last_edited_date": datetime.now().isoformat(),
        "config_version": CONFIG_COMPATIBILITY
    }
    save_config(CONFIG_PATH, config_data)
    st.sidebar.success(f"Konfiguration in `{CONFIG_PATH}` gespeichert!")
    st.toast("Konfiguration erfolgreich gespeichert!", icon="🎉")

st.sidebar.markdown("---")
if st.sidebar.toggle("Roh-Konfiguration anzeigen (Debugging)", False):
    st.sidebar.subheader("Aktuelle Roh-Konfiguration (YAML-Format)")
    st.sidebar.code(yaml.dump(config_data, sort_keys=False, indent=2), language="yaml")

# --- Tabs für verschiedene Konfigurationsabschnitte ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "1. API Vereinfachung",
    "2. Profilanalyse",
    "3. Geocoding & Oberfläche",
    "4. POI Suche",
    "5. Ortsfilterung",
    "6. Gemini API",
    "7. Watt-Schätzung",
    "8. Design & Farben",
    "9. Speed Profil",
    "10. (Sonstige)"
])

# --- Tab 1: API Vereinfachung (Schritt 2b) ---
with tab1:
    st.header("1. Datenvereinfachung für API-Nutzung (Schritt 2b)")
    api_config = config_data.setdefault("api_simplification", {})

    api_config["method"] = st.selectbox(
        "Methode zur Vereinfachung",
        options=["rdp", "winkel"], # Füge hier ggf. mehr Optionen hinzu
        index=["rdp", "winkel"].index(api_config.get("method", "rdp")),
        help="Methode zur Reduzierung der Trackpunkte für API-Abfragen. 'rdp' ist Ramer-Douglas-Peucker."
    )

    if api_config["method"] == "rdp":
        api_config["rdp_epsilon"] = st.number_input(
            "RDP Epsilon (in Grad)",
            value=float(api_config.get("rdp_epsilon", 0.0001)),
            min_value=0.000001,
            max_value=0.1,
            step=0.00001,
            format="%.6f",
            help="Toleranz für RDP. Kleinere Werte = mehr Punkte, genauere Route. 0.0001 ≈ 11 Meter."
        )
    elif api_config["method"] == "winkel":
        st.subheader("Parameter für 'winkel'-Methode (Beispiel)")
        api_config["window_size"] = st.number_input("Fenstergröße (Winkel)", value=int(api_config.get("window_size", 6)), min_value=2)
        api_config["min_angle_threshold"] = st.number_input("Min. Winkel-Schwelle", value=float(api_config.get("min_angle_threshold", 75.0)), min_value=0.0, max_value=180.0)
        # ... weitere Parameter für "winkel"
    config_data["api_simplification"] = api_config # Zurückschreiben ins Haupt-Dict

# --- Tab 2: Profilanalyse (Schritt 3) ---
with tab2:
    st.header("2. Peak/Profil Analyse & Plotting (Schritt 3)")
    profile_conf = config_data.setdefault("profile_analysis", {})

    st.subheader("Savitzky-Golay Glättung")
    col_smooth1, col_smooth2 = st.columns(2)
    profile_conf["smooth_window"] = col_smooth1.number_input(
        "Glättungs-Fenstergröße",
        value=int(profile_conf.get("smooth_window", 11)),
        min_value=3, step=2, # Ungerade Zahlen
        help="Fenstergröße für Savitzky-Golay-Filter. Muss ungerade und >= 3 sein."
    )
    profile_conf["smooth_poly"] = col_smooth2.number_input(
        "Polynomordnung Glättung",
        value=int(profile_conf.get("smooth_poly", 2)),
        min_value=1,
        help="Polynomordnung für Savitzky-Golay-Filter. Muss kleiner als Fenstergröße sein."
    )
    if profile_conf["smooth_poly"] >= profile_conf["smooth_window"]:
        st.warning("Polynomordnung muss kleiner als die Fenstergröße sein!")


    st.subheader("Segmenterkennung")
    profile_conf["gain_threshold"] = st.number_input(
        "Mindestgewinn für Segment [m]",
        value=float(profile_conf.get("gain_threshold", 30.0)),
        min_value=0.0, step=1.0, format="%.1f",
        help="Ein Anstieg gilt als signifikantes Segment, wenn er diesen Höhengewinn überschreitet."
    )
    profile_conf["eps_height"] = st.number_input(
        "Höhen-Toleranz für flache Abschnitte [m]",
        value=float(profile_conf.get("eps_height", 0.3)),
        min_value=0.0, step=0.05, format="%.2f",
        help="Kleine Höhenänderungen unter diesem Wert werden ignoriert."
    )

    st.subheader("Peak-Erkennung")
    profile_conf["min_peak_prominence_m"] = st.number_input(
        "Mindestprominenz für Peaks [m]",
        value=float(profile_conf.get("min_peak_prominence_m", 50.0)),
        min_value=0.0, step=5.0, format="%.1f",
        help="Wie stark muss sich ein Gipfel von seiner Umgebung abheben, um erkannt zu werden?"
    )
    profile_conf["peak_edge_km"] = st.number_input(
        "Toleranz für Peaks nahe Start/Ende [km]",
        value=float(profile_conf.get("peak_edge_km", 0.25)),
        min_value=0.0, step=0.05, format="%.2f",
        help="Peaks innerhalb dieser Distanz zum Start/Ende des Tracks werden ggf. anders behandelt."
    )

    st.subheader("Plotting")
    profile_conf["plot_dpi"] = st.number_input("Plot DPI (Auflösung)", value=int(profile_conf.get("plot_dpi", 250)), min_value=72, max_value=600, step=10)
    col_plot1, col_plot2 = st.columns(2)
    profile_conf["plot_x_tick_major"] = col_plot1.number_input("Plot X-Achse Haupt-Ticks [km]", value=float(profile_conf.get("plot_x_tick_major", 2.5)), min_value=0.1, step=0.1, format="%.1f")
    profile_conf["plot_x_tick_minor"] = col_plot2.number_input("Plot X-Achse Neben-Ticks [km]", value=float(profile_conf.get("plot_x_tick_minor", 1.0)), min_value=0.1, step=0.1, format="%.1f")

    st.subheader("Pausenerkennung")
    profile_conf["pause_min_duration_s"] = st.number_input(
        "Min. Dauer einer Pause [s]",
        value=float(profile_conf.get("pause_min_duration_s", 60.0)),
        min_value=0.0, step=10.0, format="%.1f",
        help="Minimale Zeitdauer, die als Pause gewertet wird, wenn kaum Bewegung stattfindet."
    )
    profile_conf["pause_max_distance_m"] = st.number_input(
        "Max. Distanz während Pause [m]",
        value=float(profile_conf.get("pause_max_distance_m", 5.0)),
        min_value=0.0, step=0.5, format="%.1f",
        help="Maximale zurückgelegte Distanz zwischen zwei Punkten, damit der Zeitraum noch als Teil einer Pause gilt."
    )
    config_data["profile_analysis"] = profile_conf

# --- Tab 3: Geocoding & Oberfläche (Schritt 4, 4b) ---
with tab3:
    st.header("3. Reverse Geocoding & Oberflächenabfrage")
    geo_conf = config_data.setdefault("geocoding", {})
    surface_conf = config_data.setdefault("surface_query", {})

    st.subheader("Reverse Geocoding (Schritt 4)")
    geo_conf["sampling_distance_km"] = st.slider(
        "Sampling-Distanz für Geocoding [km]",
        min_value=0.1, max_value=5.0,
        value=float(geo_conf.get("sampling_distance_km", 0.5)),
        step=0.1, format="%.1f km",
        help="Nur jeden x-ten Kilometer wird eine Adresse von Nominatim abgefragt, um API-Limits einzuhalten."
    )

    st.subheader("Oberflächenabfrage (Schritt 4b)")
    surface_conf["query_radius_m"] = st.number_input(
        "Suchradius für Oberfläche [m]",
        value=int(surface_conf.get("query_radius_m", 80)),
        min_value=10, max_value=500, step=10,
        help="Radius um einen Trackpunkt, in dem Overpass nach Wegen mit Oberflächen-Tags sucht."
    )
    surface_conf["reference_distance_column_name"] = st.text_input(
        "Name der Distanzspalte in Referenz-CSV (aus 2c)",
        value=surface_conf.get("reference_distance_column_name", "Distanz (km)"),
        help="Wichtig für die korrekte Zuordnung der Oberflächensegmente zur Original-Kilometrierung."
    )
    # query_interval_km nicht mehr in 4b, daher hier auskommentiert
    # surface_conf["query_interval_km"] = st.slider(
    # "Abfrageintervall für Overpass [km]",
    # min_value=0.05, max_value=2.0,
    # value=float(surface_conf.get("query_interval_km", 0.2)),
    # step=0.05, format="%.2f km",
    # help="Intervall entlang der Route, in dem Overpass abgefragt wird."
    # )
    config_data["geocoding"] = geo_conf
    config_data["surface_query"] = surface_conf


# --- Tab 4: POI Suche (Schritt 5a, 5b, 5c) ---
with tab4:
    st.header("4. POI-Suche & Filterung")
    poi_conf = config_data.setdefault("poi", {})

    st.subheader("Service-POI-Suche (Schritt 5a)")
    poi_conf["service_radius_m"] = st.number_input(
        "Suchradius Service-POIs [m]",
        value=int(poi_conf.get("service_radius_m", 150)),
        min_value=50, max_value=2000, step=50,
        help="Suchradius um die optimierten Trackpunkte für Shops, Trinkwasser etc."
    )
    poi_conf["service_sampling_distance_km"] = st.slider(
        "Sampling-Distanz Service-POIs [km]",
        min_value=0.1, max_value=10.0,
        value=float(poi_conf.get("service_sampling_distance_km", 0.5)),
        step=0.1, format="%.1f km",
        help="Abfrageintervall für Service-POIs entlang der *optimierten* Route."
    )

    st.subheader("Peak/Viewpoint BBOX-Suche (Schritt 5b)")
    poi_conf["peak_buffer_degrees"] = st.slider(
        "Puffer um Bounding Box für Peaks/Viewpoints [Grad]",
        min_value=0.001, max_value=0.5,
        value=float(poi_conf.get("peak_buffer_degrees", 0.05)),
        step=0.001, format="%.3f Grad",
        help="Vergrößert die Bounding Box der Gesamtroute, um nahegelegene Gipfel/Aussichtspunkte zu finden."
    )

    st.subheader("POI-Relevanzfilterung (Schritt 5c)")
    poi_conf["max_dist_service_km"] = st.slider(
        "Max. Distanz Service-POI zur *vollen* Route [km]",
        min_value=0.05, max_value=2.0,
        value=float(poi_conf.get("max_dist_service_km", 0.3)),
        step=0.05, format="%.2f km",
        help="Service-POIs, die weiter entfernt sind, werden als nicht relevant eingestuft."
    )
    poi_conf["max_dist_viewpoint_km"] = st.slider(
        "Max. Distanz Viewpoint zur *vollen* Route [km]",
        min_value=0.1, max_value=10.0,
        value=float(poi_conf.get("max_dist_viewpoint_km", 3.0)),
        step=0.1, format="%.1f km",
        help="Aussichtspunkte, die weiter entfernt sind, werden als nicht relevant eingestuft."
    )

    st.markdown("**Peak-Relevanzfilter (Distanz vs. Höhe):**")
    st.markdown("Definiert, welche Peaks basierend auf ihrer Entfernung zur Route und Mindesthöhe als relevant gelten. Die erste passende Regel greift.")

    # Dynamische Bearbeitung für peak_relevance_filter
    peak_filters = poi_conf.get("peak_relevance_filter", [])
    if not isinstance(peak_filters, list): # Sicherstellen, dass es eine Liste ist
        peak_filters = []

    # Temporäre Datenstruktur für Streamlit, um Änderungen zu handhaben
    if 'peak_filters_temp' not in st.session_state:
        st.session_state.peak_filters_temp = [dict(f) for f in peak_filters] # Kopie erstellen

    filter_container = st.container(border=True)
    cols = filter_container.columns([3,3,1])
    cols[0].write("Max. Distanz zur Route [km]")
    cols[1].write("Min. Höhe des Peaks [m]")

    for i, p_filter in enumerate(st.session_state.peak_filters_temp):
        cols = filter_container.columns([3,3,1])
        new_dist = cols[0].number_input(f"Max. Distanz {i+1}", value=float(p_filter.get("max_dist_km", 1.0)), min_value=0.1, step=0.1, format="%.1f", key=f"dist_{i}")
        new_elev = cols[1].number_input(f"Min. Höhe {i+1}", value=int(p_filter.get("min_elev_m", 100)), min_value=0, step=10, key=f"elev_{i}")

        st.session_state.peak_filters_temp[i]["max_dist_km"] = new_dist
        st.session_state.peak_filters_temp[i]["min_elev_m"] = new_elev

        if cols[2].button("🗑️", key=f"del_{i}", help="Diesen Filter entfernen"):
            st.session_state.peak_filters_temp.pop(i)
            st.rerun() # UI neu laden, um entfernten Filter zu zeigen

    if filter_container.button("➕ Peak-Filterregel hinzufügen"):
        st.session_state.peak_filters_temp.append({"max_dist_km": 1.0, "min_elev_m": 100})
        st.rerun()

    # Aktualisiere die Haupt-Konfiguration mit den temporären Werten beim Speichern (oben)
    # oder beim Verlassen des Tabs (wenn wir eine "Apply Changes"-Logik pro Tab hätten)
    poi_conf["peak_relevance_filter"] = st.session_state.peak_filters_temp
    config_data["poi"] = poi_conf

# --- Tab 5: Ortsfilterung (Schritt 8c) ---
with tab5:
    st.header("5. Ortsfilterung (Schritt 8c)")
    place_filt_conf = config_data.setdefault("place_filtering", {})
    place_filt_conf["max_dist_center_to_route_m"] = st.number_input(
        "Max. Distanz Ortszentrum zur Route [m]",
        value=int(place_filt_conf.get("max_dist_center_to_route_m", 1000)),
        min_value=0, max_value=10000, step=100,
        help="Orte, deren geocodiertes Zentrum weiter als dieser Wert von der Route entfernt ist, werden ignoriert."
    )
    place_filt_conf["min_occurrences"] = st.number_input(
        "Min. Vorkommen des Ortes (Anzahl Punkte im Reverse Geocoding)",
        value=int(place_filt_conf.get("min_occurrences", 3)),
        min_value=1, step=1,
        help="Orte, die auf der Route nur sehr kurz durchfahren werden (weniger Punkte), können ignoriert werden."
    )
    # min_dist_in_place_km ist auskommentiert in der YAML, daher hier auch optional
    if "min_dist_in_place_km" in place_filt_conf:
         place_filt_conf["min_dist_in_place_km"] = st.number_input(
            "Min. Strecke im Ort [km] (Optional)",
            value=float(place_filt_conf.get("min_dist_in_place_km", 0.1)),
            min_value=0.0, step=0.05, format="%.2f",
            help="Optional: Orte ignorieren, in denen die Route weniger als diese Distanz verläuft."
        )
    config_data["place_filtering"] = place_filt_conf

# --- Tab 6: Gemini API (Schritt 9) ---
with tab6:
    st.header("6. Gemini API für Ortsbeschreibungen (Schritt 9)")
    gemini_conf = config_data.setdefault("gemini_wiki", {})
    gemini_conf["place_column"] = st.text_input(
        "Spaltenname mit Ortsnamen in CSV (aus 8c)",
        value=gemini_conf.get("place_column", "Ort"),
        help="Name der Spalte, die die zu beschreibenden Ortsnamen enthält. Leer lassen für automatische Erkennung."
    )
    gemini_conf["country_context"] = st.text_input(
        "ISO Ländercode für Wiki-Sprachwahl (z.B. DE, IT)",
        value=gemini_conf.get("country_context", "DE"),
        help="Beeinflusst die bevorzugte Sprache für Wikipedia-Abfragen, wenn wiki_lang='AUTO'."
    )
    gemini_conf["wiki_lang"] = st.text_input(
        "Wikipedia-Sprache (z.B. de, en) oder AUTO",
        value=gemini_conf.get("wiki_lang", "AUTO"),
        help="'AUTO' verwendet den country_context, sonst spezifischen Sprachcode."
    )
    gemini_conf["max_wiki_chars"] = st.number_input(
        "Max. Zeichenlänge für Wikipedia-Auszug",
        value=int(gemini_conf.get("max_wiki_chars", 1500)),
        min_value=100, max_value=5000, step=100,
        help="Begrenzt die Länge des Wikipedia-Textes, der an Gemini gesendet wird."
    )
    # model_name ist auskommentiert in YAML, ggf. hier hinzufügen wenn benötigt
    config_data["gemini_wiki"] = gemini_conf

# --- Tab 7: Watt-Schätzung (Schritt 10b) ---
with tab7:
    st.header("7. Watt-Schätzung (Schritt 10b - Platzhalter)")
    power_conf = config_data.setdefault("power_estimation", {})
    power_conf["total_mass_kg"] = st.number_input(
        "Gesamtmasse (Fahrer + Rad + Gepäck) [kg]",
        value=float(power_conf.get("total_mass_kg", 74.0)),
        min_value=20.0, step=0.5, format="%.1f"
    )
    power_conf["cda"] = st.number_input(
        "Luftwiderstandsfläche (CdA) [m²]",
        value=float(power_conf.get("cda", 0.35)),
        min_value=0.1, max_value=1.0, step=0.01, format="%.2f"
    )
    # crr_values ist komplexer (Dictionary), für ein UI ggf. anders darstellen
    # Fürs Erste als Textarea oder Roh-Anzeige, wenn es bearbeitbar sein soll.
    st.subheader("Rollwiderstandskoeffizienten (Crr) - Fortgeschritten")
    crr_values_yaml = yaml.dump(power_conf.get("crr_values", {"asphalt": 0.005, "default": 0.010}), indent=2)
    new_crr_yaml = st.text_area(
        "Crr-Werte (YAML-Format)",
        value=crr_values_yaml,
        height=150,
        help="Definiere hier Rollwiderstandswerte für verschiedene Oberflächen. Muss valides YAML sein."
    )
    try:
        power_conf["crr_values"] = yaml.safe_load(new_crr_yaml)
    except yaml.YAMLError:
        st.error("Ungültiges YAML-Format für Crr-Werte. Änderungen nicht übernommen.")

    config_data["power_estimation"] = power_conf

# --- Tab 8: Design & Farben (Schritt 11) ---
with tab8:
    st.header("8. Design-Thema und Oberflächenfarben (für Report)")
    design_conf = config_data.setdefault("design_theme", {})
    surface_colors_conf = config_data.setdefault("surface_colors", {})

    st.subheader("Allgemeines Design-Thema (CSS-Variablen)")
    design_conf["font_family_sans_serif"] = st.text_input("Schriftfamilie", value=design_conf.get("font_family_sans_serif", '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'))
    # Farben mit st.color_picker
    design_conf["frame_base_gray"] = st.color_picker("Farbe: Rahmen Basis Grau", value=design_conf.get("frame_base_gray", "#7A8B8B"))
    design_conf["accent_green"] = st.color_picker("Farbe: Akzent Grün", value=design_conf.get("accent_green", "#689F38"))
    design_conf["accent_orange"] = st.color_picker("Farbe: Akzent Orange", value=design_conf.get("accent_orange", "#FFA000"))
    design_conf["dark_text"] = st.color_picker("Farbe: Dunkler Text", value=design_conf.get("dark_text", "#2c3e50"))
    design_conf["light_green_bg"] = st.color_picker("Farbe: Heller Grüner Hintergrund", value=design_conf.get("light_green_bg", "#e8f5e9"))
    # ... weitere Design-Farben

    st.subheader("Farben für Oberflächen-Typen")
    st.markdown("Diese Farben werden in der Kartenlegende und im Report verwendet.")
    cols_color_picker = st.columns(3)
    idx_color = 0
    sorted_surface_keys = sorted(surface_colors_conf.keys())

    for key in sorted_surface_keys:
        col = cols_color_picker[idx_color % 3]
        surface_colors_conf[key] = col.color_picker(f"Farbe für: {key.capitalize()}", value=surface_colors_conf.get(key, "#CCCCCC"), key=f"color_{key}")
        idx_color +=1

    config_data["design_theme"] = design_conf
    config_data["surface_colors"] = surface_colors_conf


# --- Tab 9: Speed Profile ---
with tab9:
    st.header("9. Geschwindigkeitsprofil Plotting (Schritt 3b - Platzhalter)")
    speed_conf = config_data.setdefault("speed_profile", {})
    speed_conf["smooth_window"] = st.number_input(
        "Glättungsfenster Geschwindigkeit",
        value=int(speed_conf.get("smooth_window", 5)),
        min_value=1,
        help="Fenstergröße für einen optionalen gleitenden Durchschnitt der Geschwindigkeit im Plot."
    )
    config_data["speed_profile"] = speed_conf

# --- Tab 10: Sonstige / Screenshot (aus Snakefile, nicht direkt aus config.yaml) ---
with tab10:
    st.header("10. Sonstige Workflow-Parameter")
    st.markdown("Parameter, die typischerweise im Snakefile oder als Kommandozeilenargumente übergeben werden, aber hier zur Übersicht oder für zukünftige Erweiterungen stehen könnten.")

    # Diese Werte sind nicht in der config.yaml, aber könnten hier informativ angezeigt werden
    # oder, falls gewünscht, auch in die config.yaml verschoben werden.
    st.subheader("Karten-Screenshot (Parameter aus Snakefile `screenshot_map`)")
    # Da diese nicht in config_data sind, können wir sie nicht direkt bearbeiten.
    # Man könnte sie hier hinzufügen, wenn man sie konfigurierbar machen will.
    # Beispiel:
    # screenshot_conf = config_data.setdefault("screenshot_settings", {})
    # screenshot_conf["width"] = st.number_input("Screenshot Breite [px]", value=screenshot_conf.get("width",1200))
    # ...

    st.info("Aktuell werden Screenshot-Parameter (Breite, Höhe, Delay) direkt in der `screenshot_map`-Regel im Snakefile verwaltet.")


# Logik zum Zurückschreiben der Änderungen beim Klick auf "Speichern" ist oben in der Sidebar.
# Stelle sicher, dass alle `config_data["abschnitt"] = jeweiliges_conf_dict`
# Zuweisungen *innerhalb* der `with tabX:` Blöcke erfolgen, damit die Änderungen
# im `config_data` Dictionary landen, bevor gespeichert wird.