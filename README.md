# 🚴‍♂️ GPX Workflow Analysis System

Ein umfassendes Python-basiertes System zur Analyse von GPX-Dateien mit erweiterten Visualisierungen, Leistungsanalyse und geografischen Erkenntnissen.

## 📋 Überblick

Dieses System transformiert GPX-Dateien in detaillierte, interaktive Analysen mit:

- **🗺️ Höhenprofil & Peak-Analyse** mit automatischer Segmenterkennung
- **⚡ Leistungsschätzung & Power-Visualisierung** für Radtouren
- **🌍 Reverse Geocoding** mit intelligenter Ortserkennung
- **🗺️ Oberflächenanalyse** (Asphalt, Schotter, etc.) via Overpass API
- **📍 POI-Erkennung** (Services, Aussichtspunkte, Peaks)
- **🤖 KI-gestützte Beschreibungen** via Google Gemini
- **📊 Interaktive 3D-Karten** mit Plotly
- **📄 Automatisierte Berichte** (HTML & PDF)

## 🛠️ Installation & Setup

### Voraussetzungen

```bash
Python 3.8+
Streamlit (für Config-Editor)
```

### Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

**Core-Pakete:**
- `folium` - Interaktive Karten
- `numpy`, `pandas` - Datenverarbeitung  
- `matplotlib`, `plotly` - Visualisierungen
- `snakemake` - Workflow-Management
- `geopy` - Geocoding
- `google-generativeai` - KI-Beschreibungen
- `shapely`, `scipy` - Geometrie & Algorithmen
- `selenium` - Browser-Automatisierung
- `overpy` - OpenStreetMap-Abfragen

### Zusätzliche Installation für Power-Visualisierung

```bash
pip install kaleido pyyaml
```

### API-Konfiguration

**Google Gemini API:**
```bash
export GOOGLE_API_KEY="your_gemini_api_key"
```

**Elevation API:** 
Für Höhendaten wird die Open-Elevation API verwendet (kostenlos).

## 🚀 Schnellstart

### 1. Konfiguration bearbeiten

```bash
streamlit run config_editor.py
```

Öffnet eine benutzerfreundliche Oberfläche zur Anpassung aller Parameter.

### 2. GPX-Dateien hinzufügen

```bash
# GPX-Dateien in den data/ Ordner kopieren
cp your_track.gpx data/
```

### 3. Workflow ausführen

```bash
# Komplette Analyse für alle GPX-Dateien
snakemake --cores 4

# Nur bestimmte Ausgaben generieren
snakemake output/11_your_track_stage_summary_final.html
```

## 📁 Projektstruktur

```
gpx_workflow_GEMINI/
├── 📄 config.yaml              # Zentrale Konfiguration
├── 📄 Snakefile               # Workflow-Definition
├── 📄 requirements.txt        # Python-Abhängigkeiten
├── 📂 data/                   # Input GPX-Dateien
├── 📂 scripts/                # Verarbeitungsscripts
├── 📂 output/                 # Generierte Analysen
│   ├── 📂 SQLliteDB/         # Geocoding & Surface Cache
│   └── 📄 *_stage_summary_final.html
├── 📂 logs/                   # Verarbeitungslogs
└── 📂 project_management/     # Dokumentation
```

## 🔄 Workflow-Schritte

Das System verarbeitet GPX-Dateien in einer definierten Reihenfolge:

### Phase 1: Datenaufbereitung
1. **GPX → CSV Konvertierung** - Extraktion der Trackpunkte
2. **API-Optimierung** - Reduzierung der Datenpunkte (Ramer-Douglas-Peucker)
3. **Höhendaten** - Ergänzung via Elevation API
4. **Geschwindigkeitsberechnung** - Mit konfigurierbarer Glättung

### Phase 2: Geografische Anreicherung
4. **Reverse Geocoding** - Ortsnamen mit SQLite-Cache
5. **Oberflächenanalyse** - Straßenbelag via Overpass API
6. **POI-Sammlung** - Services, Peaks & Viewpoints
7. **Ortsfilterung** - Relevante Orte entlang der Route

### Phase 3: Analyse & Visualisierung
8. **Peak-Analyse** - Automatische Segment- und Gipfelerkennung
9. **Leistungsschätzung** - Wattzahl basierend auf Physik-Modell
10. **Power-Visualisierung** - Gradient-basierte Farbkodierung
11. **3D-Kartenerstellung** - Interaktive Plotly-Visualisierung

### Phase 4: Berichtsgenerierung
12. **KI-Beschreibungen** - Gemini API für Ortsbeschreibungen
13. **Stage Summary** - Umfassender HTML/PDF-Bericht
14. **NotebookLM Export** - Aufbereitung für weitere KI-Analyse

## ⚙️ Konfiguration

### Wichtige Parameter in `config.yaml`:

```yaml
# Datenvereinfachung
api_simplification:
  method: "rdp"
  rdp_epsilon: 0.0001  # ~11m Toleranz

# Leistungsschätzung  
power_estimation:
  total_mass_kg: 75
  rider_weight_kg: 65
  target_power_watts: null  # null = Analyse, Wert = Simulation

# Oberflächenanalyse
surface_query:
  query_radius_m: 80
  cache_tolerance_km: 0.1

# Peak-Erkennung
profile_analysis:
  min_peak_prominence_m: 50.0
  gain_threshold: 30.0
```

### Zwei Betriebsmodi:

**Analyse-Modus** (`target_power_watts: null`):
- Schätzt benötigte Leistung basierend auf Topografie
- Zeigt, was für die gefahrene Geschwindigkeit nötig war

**Simulations-Modus** (`target_power_watts: 180`):
- Berechnet erreichbare Geschwindigkeiten bei gegebener Leistung
- Für Tourenplanung und "Was-wäre-wenn" Szenarien

## 📊 Ausgabeformate

### Visualisierungen
- **Höhenprofil** (.png) - Mit Peaks, Orten & Oberflächentypen
- **Geschwindigkeitsprofil** (.png) - Mit Pausenerkennung
- **Power-Visualisierung** (.png/.html) - Gradient-Farbkodierung
- **3D-Karte** (.html) - Interaktive Plotly-Darstellung
- **Übersichtskarte** (.html/.png) - Folium mit POIs

### Datenexporte
- **CSV-Dateien** - Alle Zwischenergebnisse verfügbar
- **Stage Summary** (.html/.pdf) - Vollständiger Analysebericht
- **NotebookLM** (.md) - Für KI-gestützte Nachbearbeitung

## 🎯 Anwendungsfälle

### Für Radfahrer
- **Tourenplanung** - Leistungsbedarf einschätzen
- **Trainingsanalyse** - Detaillierte Leistungsauswertung
- **Streckenoptimierung** - Oberflächentypen berücksichtigen

### Für Forscher & Analysten  
- **Geografische Studien** - Automatisierte Routenklassifizierung
- **Verkehrsanalyse** - Oberflächenverteilung und Infrastruktur
- **KI-Training** - Strukturierte Geodaten-Aufbereitung

### Für Entwickler
- **Modulares System** - Einzelne Schritte separat nutzbar
- **Erweiterbar** - Neue Analyseschritte leicht integrierbar
- **Caching** - SQLite-basierte Optimierung für API-Calls

## 🔧 Erweiterte Features

### Intelligentes Caching
- **SQLite-basiert** für Geocoding & Oberflächendaten
- **Toleranz-basierte Suche** - Wiederverwendung naher Punkte
- **Cache-Administration** - Tools zur Verwaltung und Optimierung

### Performance-Monitoring
- **Pipeline-Tracking** - Automatische Zeiterfassung
- **Bottleneck-Erkennung** - Identifikation langsamer Schritte  
- **Qualitäts-Metriken** - Überwachung der Datenqualität

### Flexible Oberflächenanalyse
```yaml
surface_query:
  urban:
    query_radius_m: 50    # Städtische Gebiete
  rural: 
    query_radius_m: 150   # Ländliche Gebiete
  performance:
    cache_tolerance_km: 0.15  # Optimiert für Speed
```

## 🤝 Beitragen

Das Projekt ist modular aufgebaut - neue Features können als separate Scripts implementiert und in den Snakemake-Workflow integriert werden.

### Entwicklungsrichtlinien
- Jeder Schritt als eigenständiges Python-Script
- Konfiguration über `config.yaml`
- Umfassendes Logging für Debugging
- Fehlerbehandlung mit Fallback-Mechanismen

## 📄 Lizenz

Open Source - Details siehe Lizenz-Datei.

## 📞 Support

Bei Fragen oder Problemen:
- **Issues** - Für Bugs und Feature-Requests
- **Dokumentation** - Siehe `project_management/` Ordner
- **Logs** - Detaillierte Informationen in `logs/` Ordner

---

**🎯 Entwickelt für präzise, automatisierte GPX-Analyse mit modernsten Tools und KI-Integration.**