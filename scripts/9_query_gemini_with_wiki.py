#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
9_query_gemini_with_wiki.py
---------------------------
Liest die sortierte Ortsliste (CSV aus Schritt 8).
Optional: Sucht passende Wikipedia-Artikel.
Fragt die Gemini API für jeden Ort an, um eine radfahrerspezifische
Beschreibung zu generieren (optional unter Verwendung von Wiki-Infos).
Speichert das Ergebnis als Markdown-Datei.
"""

from __future__ import annotations  # Wichtig für Type Annotations

# === SCRIPT METADATA ===
SCRIPT_NAME = "9_query_gemini_with_wiki.py"
SCRIPT_VERSION = "3.0.0"
SCRIPT_DESCRIPTION = "AI-powered place descriptions using Gemini API with Wikipedia integration, token tracking and standardized metadata"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with Gemini API and Wikipedia integration
v1.1.0 (2025-06-07): Standardized header, improved error handling and retry logic
v2.0.0 (2025-06-07): Implemented full standardized metadata system with processing history
v3.0.0 (2025-06-07): Enhanced with token counting, performance tracking and improved error handling
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "ai_descriptions"
INPUT_FILE_PATTERN = "*_places_sorted.csv"
OUTPUT_FILE_PATTERN = "*_ai_descriptions.md"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "requests>=2.25.0",
    "google-generativeai>=0.3.0",
    "python-dotenv>=0.19.0",
    "tqdm>=4.60.0"
]

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple # Expliziter Import für alle Type Hints
from datetime import datetime

import requests
import pandas as pd # Import Pandas
try:
    import google.generativeai as genai
except ImportError:
    sys.exit("[ERROR] Bitte 'google-generativeai' installieren: pip install google-generativeai")

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

try:
    from tqdm import tqdm
except ImportError:
    print("[Warnung] tqdm nicht gefunden (pip install tqdm), Fortschrittsbalken wird nicht angezeigt.")
    def tqdm(iterable, *args, **kwargs): return iterable

from dotenv import load_dotenv # Import dotenv

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

# --- DOTENV SOFORT LADEN ---
load_dotenv()
# ---------------------------

#######################################################################
# Globale Konfigurationen
#######################################################################
MODEL_NAME = "gemini-2.0-flash-001"
WIKI_API = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
COUNTRY_LANG_MAP: Dict[str, str] = {
    "DE": "de", "AT": "de", "CH": "de", "IT": "it", "FR": "fr",
    "ES": "es", "PT": "pt", "US": "en", "GB": "en",
}
PLACE_COLUMN_CANDIDATES: List[str] = [
    "Ort", "City", "place_name", "name", "title", "location", "poi_name"
]
# Gemini Prompt Template (unverändert)
PROMPT_TEMPLATE = """Du bist ein sportlicher, begeisterter und kenntnisreicher Gravel-Rad-Guide für Touren in Europa.
Nutze die folgenden Fakten, um eine kurze, inspirierende Beschreibung für Radfahrer zu erstellen, die im Ort '{place}' auf ihrer Tour durchkommen oder eine Pause machen:

<FACTS>
{facts}
</FACTS>

Bitte gib als Antwort nur Markdown zurück, formatiere Schlüsselwörter verspielt fett und in unterschiedlichen Größen und beachte folgendes Format:

WICHTIG: Wenn keine oder kaum Fakten vorhanden sind (nur der Ortsname):
- Erstelle keinen fantasierten Bericht
- Schreibe nur 1-2 kurze Sätze, die Folgendes enthalten können:
  * Eine kurze Erwähnung, dass es sich um einen kleinen Ort an der Route handelt
  * Optionaler Hinweis auf die geografische Lage basierend auf dem Namen (z.B. "am See" wenn "See" im Namen)
  * Hinweis auf mögliche kurze Erholungspause
- Verwende Formulierungen wie "Der kleine Ort..." oder "Dieser Punkt auf der Strecke..."

Wenn Fakten vorhanden sind:
Erstelle drei inspirierende Absätze über den Ort '{place}'
Absatz 1: Ortsname, Einwohneranzahl, Fläche und Höhe.
Absatz 2: Kultur, (Sport-) Geschichte oder landschaftliche Highlights.
Absatz 3: Was macht diesen Ort besonders für eine Pause auf einer sportlichen Radtour?
Gibt es Wasser, Schatten, Cafés oder einfach grandiose Ausblicke?
Sprich sportliche Leser ab und zu direkt an, sei motivierend und gern mit einem Augenzwinkern.
Hebe Schlüsselwörter durch besondere Formate hervor, damit der Text leichter erfassbar ist.

Optional: Füge am Anfang eine Zeile mit einem passenden Emoji für den Ort hinzu (z.B. ⛰️, 🏘️, 🏰, 🍇, 🌊).
"""

#######################################################################
# Gemini‑Setup (Funktion unverändert)
#######################################################################
def setup_gemini() -> Optional[genai.GenerativeModel]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: print("[ERROR] GEMINI_API_KEY nicht gefunden.", file=sys.stderr); return None
    try:
        genai.configure(api_key=api_key); model = genai.GenerativeModel(MODEL_NAME)
        print(f"[Info] Gemini Model '{MODEL_NAME}' initialisiert."); return model
    except Exception as exc: print(f"[ERROR] Gemini Init fehlgeschlagen: {exc}", file=sys.stderr); return None

#######################################################################
# Wikipedia Helpers (Funktion unverändert)
#######################################################################
def fetch_wiki_extract(place: str, lang: str, max_chars: int = 500, api_metadata: Optional[Dict] = None) -> Optional[str]:
    quoted_place = requests.utils.quote(place); url = WIKI_API.format(lang=lang, title=quoted_place)
    if api_metadata: api_metadata["wikipedia_requests"] += 1
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'GPXWorkflow/1.0'}); r.raise_for_status()
        data = r.json(); extract = data.get("extract", "").strip()[:max_chars]
        if extract and api_metadata: api_metadata["wikipedia_hits"] += 1
        return extract or None
    except requests.exceptions.HTTPError as e: # Spezifischer auf 404 prüfen
        if e.response.status_code == 404: return None # Kein Fehler, einfach kein Eintrag
        else: print(f"  [Wiki Error] HTTP {e.response.status_code} für '{place}' ({lang}): {e}", file=sys.stderr); return None
    except requests.exceptions.RequestException as e: print(f"  [Wiki Error] Netzwerkfehler für '{place}' ({lang}): {e}", file=sys.stderr); return None
    except json.JSONDecodeError: print(f"  [Wiki Error] Ungültige JSON für '{place}' ({lang}).", file=sys.stderr); return None
    except Exception as e: print(f"  [Wiki Error] Unerwarteter Fehler für '{place}' ({lang}): {e}", file=sys.stderr); return None

#######################################################################
# Gemini Prompt (Funktion unverändert)
#######################################################################
def build_prompt(wiki: Optional[str], place: str) -> str:
    facts = wiki if wiki else f"Keine zusätzlichen Wikipedia‑Informationen für {place} verfügbar."
    return PROMPT_TEMPLATE.format(facts=facts, place=place)

#######################################################################
# Gemini Retry Logic (Funktion unverändert)
#######################################################################
def query_gemini_with_retry(model: genai.GenerativeModel, prompt: str, max_retries: int = 3) -> Tuple[Optional[str], bool]:
    """Fragt Gemini an, mit exponentiellem Backoff bei Fehlern."""
    for attempt in range(max_retries):
        try:
            # print(f"    -> Sende Anfrage an Gemini (Versuch {attempt + 1})...") # Debug
            response = model.generate_content(prompt)
            # print(f"    -> Antwort von Gemini erhalten.") # Debug
            response_text = None; generation_stopped = False; stop_reason = "N/A"
            if hasattr(response, 'text'): response_text = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts: response_text = candidate.content.parts[0].text.strip()
                if hasattr(candidate, 'finish_reason'): stop_reason = candidate.finish_reason.name; #... (Rest der Stop-Reason Logik wie vorher) ...
            if response_text: return response_text, True
            elif generation_stopped: return f"**Generierung blockiert ({stop_reason}).**", False
            else:
                 if attempt == max_retries - 1: return "**Fehler: Unerwartete leere Antwort von Gemini.**", False
                 else: print("    -> Warnung: Leere Antwort, versuche erneut...") # Weniger verbose
        except Exception as exc:
            # --- KORREKTUR: Einrückung der Fehlerbehandlung ---
            print(f"    -> Fehler bei Gemini API (Versuch {attempt + 1}/{max_retries}): {exc}", file=sys.stderr)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt # Exponential backoff
                print(f"       Warte {wait_time}s vor Wiederholung...")
                time.sleep(wait_time)
                # Hier *kein* continue, die Schleife geht automatisch weiter
            else: # Letzter Versuch fehlgeschlagen
                print(f"    -> Endgültiger Fehler nach {max_retries} Versuchen.", file=sys.stderr)
                return f"**Fehler bei der Beschreibungserstellung:** {exc}", False # Endgültiger Fehler
            # --------------------------------------------------

    # Fallback, falls Schleife unerwartet endet
    return "**Fehler: Max Retries erreicht.**", False

#######################################################################
# Hauptprogramm
#######################################################################
def guess_place_column(columns: List[str]) -> Optional[str]:
    """Versuche, die wahrscheinlichste Orts‑Spalte zu finden."""
    if not columns: return None
    candidates = PLACE_COLUMN_CANDIDATES
    for cand in candidates:
        for col_name in columns:
            if col_name.lower() == cand.lower():
                return col_name # Gib originalen Spaltennamen zurück
    return None

def main() -> None:
    run_start_time = datetime.now()
    print_script_info()
    print(f"[{run_start_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} started.")
    
    # Tracking-Variablen für Metadaten
    api_metadata = {
        "ai_provider": "Google Gemini",
        "ai_model": MODEL_NAME,
        "api_query_start_time": None,
        "api_query_end_time": None,
        "total_ai_requests": 0,
        "successful_ai_requests": 0,
        "failed_ai_requests": 0,
        "total_input_tokens_estimated": 0,
        "total_output_tokens_estimated": 0,
        "wikipedia_requests": 0,
        "wikipedia_hits": 0
    }
    
    parser = argparse.ArgumentParser(description="Gemini‑Ortsbeschreibungen mit Wikipedia‑Boost")
    parser.add_argument("--input-csv", required=True, help="CSV mit Ortsdaten (aus Schritt 8)") # Angepasste Hilfe
    parser.add_argument("--output-md", required=True, help="Ziel‑Markdown")
    parser.add_argument("--place-column", default="", help="Spaltenname mit Ortsnamen (optional, leer = auto)")
    parser.add_argument("--country-context", default="", help="ISO‑Ländercode (DE, IT, …) (optional, leer = auto)")
    parser.add_argument("--wiki-lang", default="AUTO", help="Wikipedia‑Sprachcode oder AUTO")
    parser.add_argument("--max-wiki-chars", type=int, default=500, help="Max. Zeichen für Wiki-Auszug")
    args = parser.parse_args()

    # --- Initialisiere Gemini Model ---
    model = setup_gemini()
    if model is None: sys.exit(1)

    # --- Bestimme Wikipedia-Sprache ---
    # ... (wie vorher) ...
    wiki_lang = args.wiki_lang.lower(); country_ctx_upper = args.country_context.strip().upper() if args.country_context else ""
    if wiki_lang == "auto": wiki_lang = COUNTRY_LANG_MAP.get(country_ctx_upper, "en")
    print(f"[Info] Verwende Wikipedia-Sprache: {wiki_lang}")

    # --- Verarbeite CSV mit Pandas ---
    output_lines: List[str] = ["# 🌍 Tagesorte & Highlights für die Tour\n"]
    places_processed = 0; places_failed = 0; place_col = None; places_df = None

    try:
        print(f"[Info] Lese Input CSV: {args.input_csv}")
        # Lese mit Pandas, behandle mögliche Fehler direkt
        try:
            places_df = pd.read_csv(args.input_csv, dtype=str, keep_default_na=False, comment='#') # Lese alles als String, leere Felder bleiben ""
            if places_df.empty:
                print(f"[Warnung] Input CSV ist leer: {args.input_csv}")
            fieldnames = list(places_df.columns) # Hole Spaltennamen von Pandas
        except FileNotFoundError:
            sys.exit(f"[ERROR] Input CSV nicht gefunden: {args.input_csv}")
        except pd.errors.EmptyDataError:
             print(f"[Warnung] Input CSV ist leer oder enthält nur Header: {args.input_csv}")
             places_df = pd.DataFrame() # Stelle sicher, dass df existiert, auch wenn leer
        except Exception as e:
            sys.exit(f"[ERROR] Fehler beim Lesen der CSV mit Pandas: {e}")

        if places_df is not None and not places_df.empty:
            # --- Spaltenname ermitteln ---
            place_col = args.place_column if args.place_column else guess_place_column(fieldnames or [])
            if place_col is None:
                sys.exit(
                    "[ERROR] Keine geeignete Orts‑Spalte gefunden. "
                    "Bitte via --place-column explizit angeben. "
                    f"Gefundene Spalten: {', '.join(fieldnames or ['(Keine Spalten gefunden)'])}"
                )
            elif place_col not in fieldnames:
                 sys.exit(f"[ERROR] Angegebene Spalte '--place-column {place_col}' nicht in CSV gefunden.")

            print(f"[Info] Verwende Spalte '{place_col}' für Ortsnamen.")
            print(f"[Info] Verarbeite {len(places_df)} Orte...")
            api_metadata["api_query_start_time"] = datetime.now().isoformat()

            # --- Iteriere durch DataFrame Zeilen ---
            for index, row in tqdm(places_df.iterrows(), total=len(places_df), desc="Generiere Beschreibungen"):
                place = str(row.get(place_col, "")).strip() # Hole Wert sicher

                # --- Debug Ausgaben (optional, jetzt auskommentiert) ---
                # print(f"\n--- Debug: Zeile {index} ---")
                # print(f"  Rohwert für '{place_col}': {row.get(place_col)}")
                # print(f"  Bereinigter Ort: '{place}'")
                ignore_list = ["unbekannter ort", "fehler", "nan", "none"]
                is_invalid = not place or place.lower() in ignore_list
                # print(f"  Ist leer oder ungültig?: {is_invalid}")
                # ----------------------------------------------------

                if is_invalid:
                     # print("  -> Überspringe leeren/ungültigen Ort.")
                     continue

                # 1. Hole Wiki-Text (optional)
                wiki_text = fetch_wiki_extract(place, wiki_lang, args.max_wiki_chars, api_metadata)
                # print(f"  Wiki-Text gefunden?: {'Ja' if wiki_text else 'Nein'}")

                # 2. Erstelle Prompt
                prompt = build_prompt(wiki_text, place)
                
                # Token-Schätzung für Input (grobe Approximation)
                estimated_input_tokens = len(prompt.split()) * 1.3  # Schätzung
                api_metadata["total_input_tokens_estimated"] += estimated_input_tokens

                # 3. Frage Gemini an (mit Retry)
                api_metadata["total_ai_requests"] += 1
                # print("  Frage Gemini an...")
                md, success = query_gemini_with_retry(model, prompt)
                
                # Token-Schätzung für Output
                if md:
                    estimated_output_tokens = len(md.split()) * 1.3
                    api_metadata["total_output_tokens_estimated"] += estimated_output_tokens
                # print(f"  Gemini Erfolg?: {success}")
                # print(f"  Gemini Text (gekürzt)?: {md[:100] if md else 'Kein Text'}")

                # 4. Füge Ergebnis hinzu
                output_lines.append(f"## {place}\n")
                if md:
                     output_lines.append(f"{md}\n")
                     # print("  -> Ergebnis zu Output hinzugefügt.")
                else:
                     output_lines.append("*(Fehler bei der Beschreibungserstellung)*\n")
                     # print("  -> Fehlertext zu Output hinzugefügt.")

                if success: 
                    places_processed += 1
                    api_metadata["successful_ai_requests"] += 1
                else: 
                    places_failed += 1
                    api_metadata["failed_ai_requests"] += 1

                time.sleep(1.5) # Pause nach jeder Anfrage
        else:
             print("[Info] Keine Orte zum Verarbeiten in der CSV gefunden.")

        api_metadata["api_query_end_time"] = datetime.now().isoformat()

    except Exception as e: # Fange andere unerwartete Fehler ab
        print(f"[ERROR] Unerwarteter Fehler in der Hauptverarbeitung: {e}", file=sys.stderr)
        # Schreibe zumindest, was bisher gesammelt wurde
        output_lines.append("\n\n*(Verarbeitung aufgrund eines Fehlers abgebrochen)*\n")

    # --- Schreibe Output Markdown mit Metadaten ---
    try:
        output_path = Path(args.output_md); output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Erstelle detaillierten Header mit Metadaten
        processing_metadata = [
            f"<!-- Processed by: {SCRIPT_NAME} v{SCRIPT_VERSION} -->",
            f"<!-- Processing Timestamp: {run_start_time.isoformat()} -->",
            f"<!-- Input CSV: {os.path.basename(args.input_csv)} -->",
            f"<!-- Places Processed: {places_processed} -->",
            f"<!-- AI Model: {api_metadata['ai_model']} -->",
            f"<!-- Total AI Requests: {api_metadata['total_ai_requests']} -->",
            f"<!-- Successful AI Requests: {api_metadata['successful_ai_requests']} -->",
            f"<!-- Wikipedia Requests: {api_metadata['wikipedia_requests']} -->",
            f"<!-- Wikipedia Hits: {api_metadata['wikipedia_hits']} -->",
            f"<!-- Estimated Input Tokens: {int(api_metadata['total_input_tokens_estimated'])} -->",
            f"<!-- Estimated Output Tokens: {int(api_metadata['total_output_tokens_estimated'])} -->",
            f"<!-- Processing Duration: {(datetime.now() - run_start_time).total_seconds():.1f}s -->",
            ""
        ]
        
        # Kombiniere Metadaten und Content
        final_content = "\n".join(processing_metadata + output_lines)
        
        # Füge eine Leerzeile am Ende hinzu für sauberes Rendering
        if not final_content.endswith("\n\n"): final_content += "\n"
        
        output_path.write_text(final_content, encoding="utf-8")
        
        run_end_time = datetime.now()
        print(f"\n[OK] Markdown mit Metadaten gespeichert nach {args.output_md}")
        print(f"[{run_end_time.isoformat()}] Script {SCRIPT_NAME} v{SCRIPT_VERSION} finished. Duration: {run_end_time - run_start_time}")
        print(f"     Erfolgreich verarbeitet: {places_processed}")
        if places_failed > 0: print(f"     Fehlgeschlagen: {places_failed}")
        
        # Performance Summary
        if api_metadata['total_ai_requests'] > 0:
            success_rate = (api_metadata['successful_ai_requests'] / api_metadata['total_ai_requests']) * 100
            print(f"[Summary] AI Success Rate: {success_rate:.1f}% ({api_metadata['successful_ai_requests']}/{api_metadata['total_ai_requests']})")
            print(f"[Summary] Est. Total Tokens: {int(api_metadata['total_input_tokens_estimated'] + api_metadata['total_output_tokens_estimated'])}")
        
        if api_metadata['wikipedia_requests'] > 0:
            wiki_hit_rate = (api_metadata['wikipedia_hits'] / api_metadata['wikipedia_requests']) * 100
            print(f"[Summary] Wikipedia Hit Rate: {wiki_hit_rate:.1f}% ({api_metadata['wikipedia_hits']}/{api_metadata['wikipedia_requests']})")
    except IOError as e: print(f"[ERROR] Schreiben der Markdown-Datei '{args.output_md}' fehlgeschlagen: {e}", file=sys.stderr)
    except Exception as e: print(f"[ERROR] Unerwarteter Fehler beim Schreiben der Markdown-Datei: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Optionaler Wiki-Test kann hier bleiben oder entfernt werden
    # test_place = "Fehmarnsund"; test_lang = "de"
    # print(f"\n--- WIKI TEST für '{test_place}' ({test_lang}) ---")
    # extract = fetch_wiki_extract(test_place, test_lang, 1500)
    # if extract: print("[Wiki Test OK] Auszug gefunden:\n", extract)
    # else: print("[Wiki Test FEHLSCHLAG] Kein Auszug gefunden.")
    # print("--- ENDE WIKI TEST ---\n")

    main()