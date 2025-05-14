#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
9_query_gemini.py
-----------------
Reads a CSV file containing a sorted list of places (output of step 8).
Queries the Google Gemini API for each place to generate a descriptive text
focused on cycling relevance. Saves the combined descriptions to a Markdown file.

Requires a .env file in the project root with GEMINI_API_KEY=YOUR_API_KEY.
Requires 'requests' and 'python-dotenv' libraries.
"""

import sys
import os
import argparse
import pandas as pd
import requests
import time
from dotenv import load_dotenv
from typing import Optional # <--- DIESE ZEILE HINZUFÜGEN

# --- Globale Konfiguration (könnte auch in config.yaml ausgelagert werden) ---
# Modell und API-Endpunkt (aktuell für v1beta, ggf. anpassen)
GEMINI_MODEL = "gemini-1.5-flash-latest" # Oder gemini-1.5-pro-latest etc.
GEMINI_API_BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
REQUEST_TIMEOUT = 60  # Timeout für API-Anfragen in Sekunden
RETRY_DELAY = 5       # Wartezeit zwischen Wiederholungsversuchen in Sekunden
MAX_RETRIES = 3       # Maximale Anzahl Wiederholungsversuche pro Ort

# --- Lade API Key ---
load_dotenv() # Lädt Variablen aus .env Datei
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print(" Fehler: GEMINI_API_KEY nicht in .env Datei gefunden oder Umgebungsvariable nicht gesetzt.")
    sys.exit(1)

def query_gemini_api(api_key: str, prompt: str) -> Optional[str]:
    """Sends a prompt to the Gemini API and returns the generated text or None on error."""
    headers = {
        "Content-Type": "application/json",
        # Neu: Der API Key wird jetzt direkt im Request Header übergeben
        "x-goog-api-key": api_key
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # Optional: Safety Settings, Generation Config etc. hinzufügen
        # "safetySettings": [...],
        # "generationConfig": { "temperature": 0.7, ... }
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                GEMINI_API_BASE_URL, # URL ohne API Key
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            response_data = response.json()

            # Extrahiere den Text aus der komplexeren Struktur der Gemini-Antwort
            if "candidates" in response_data and response_data["candidates"]:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"] and candidate["content"]["parts"]:
                    return candidate["content"]["parts"][0].get("text", "").strip()
                elif "finishReason" in candidate and candidate["finishReason"] != "STOP":
                     # Handle cases where generation was blocked (SAFETY, etc.)
                     print(f"    -> Warnung: Gemini-Generierung für Ort gestoppt ({candidate['finishReason']}).")
                     return None # Oder spezifischer Fehlertext?
            # Fallback, falls Struktur unerwartet ist
            print(f"    -> Warnung: Unerwartete Gemini-Antwortstruktur.")
            # print(response_data) # Zum Debuggen
            return None

        except requests.exceptions.Timeout:
            print(f"    -> Fehler: Timeout bei API-Anfrage (Versuch {attempt + 1}/{MAX_RETRIES}). Warte {RETRY_DELAY}s...")
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            print(f"    -> Fehler: API-Anfrage fehlgeschlagen (Status: {status_code}, Versuch {attempt + 1}/{MAX_RETRIES}): {e}")
            # Bei bestimmten Fehlern (z.B. 429 Too Many Requests) länger warten?
            if status_code == 429:
                print(f"    -> Rate Limit vermutlich erreicht. Warte {RETRY_DELAY * 2}s...")
                time.sleep(RETRY_DELAY * 2)
                continue # Zum nächsten Versuch springen ohne die normale Wartezeit
        except Exception as e: # Andere unerwartete Fehler
             print(f"    -> Unerwarteter Fehler bei API-Abfrage (Versuch {attempt + 1}/{MAX_RETRIES}): {e}")

        # Warte vor dem nächsten Versuch (außer nach 429)
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    print(f"    -> Fehler: Konnte keine Antwort von Gemini nach {MAX_RETRIES} Versuchen erhalten.")
    return None


def generate_descriptions(input_csv_path: str, output_md_path: str):
    """Generates descriptions for places using Gemini API."""
    print(f"[Info] Generating descriptions for places in: {input_csv_path}")

    # --- Lade Input-CSV ---
    try:
        places_df = pd.read_csv(input_csv_path)
        if places_df.empty:
            print(f"[Warnung] Input CSV ist leer: {input_csv_path}")
             # Leere Markdown-Datei erstellen
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write("# Tagesorte & Highlights\n\n*(Keine Orte zum Beschreiben gefunden)*\n")
            print(f"[OK] Leere Markdown-Datei gespeichert: {output_md_path}")
            sys.exit(0)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Fehler beim Lesen der Input-CSV '{input_csv_path}': {e}")
        sys.exit(1)

    # Spalte 'Ort' prüfen
    if "Ort" not in places_df.columns:
        print(f"Fehler: Spalte 'Ort' fehlt in Places-Datei: {input_csv_path}")
        sys.exit(1)

    # --- Generiere Beschreibungen und schreibe Markdown ---
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_md_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_md_path, "w", encoding="utf-8") as f:
            # Optional: Einen generellen Einleitungstext hinzufügen
            f.write("# 🌍 Tagesorte & Highlights für die Tour\n\n")
            f.write("Hier ein paar Eindrücke zu den Orten, die auf dieser Etappe liegen:\n\n")

            # Iteriere durch die sortierten Orte
            total_places = len(places_df)
            for idx, row in places_df.iterrows():
                place = str(row["Ort"]).strip() # Stelle sicher, dass es ein String ist
                print(f"[{idx+1}/{total_places}] Verarbeite Ort: {place}")

                if not place or place in ["Unbekannter Ort", "Fehler", "nan"]:
                     print("    -> Überspringe ungültigen Ortsnamen.")
                     continue

                # Erstelle den Prompt für Gemini
                # Fokus etwas mehr auf Radfahren und weniger auf reine Fakten?
                prompt = (
                    f"Du bist ein begeisterter und kenntnisreicher Rad-Guide für Touren in Italien.\n"
                    f"Beschreibe den Ort '{place}' in maximal drei prägnanten Absätzen für Radfahrer, die dort auf einer Tour durchkommen:\n\n"
                    f"1.  **Kurze Vorstellung:** Was ist das Besondere an '{place}'? (z.B. Lage, historischer Kern, kulinarische Spezialität, Aussicht). Gib eine grobe Einordnung (z.B. Bergdorf, Stadt am Fluss, etc.).\n"
                    f"2.  **Radtour-Relevanz:** Warum lohnt sich hier ein Stopp oder die Durchfahrt? Gibt es spezielle Herausforderungen (steile Anstiege/Abfahrten in der Nähe?), schöne Ausblicke vom Rad aus, gute Pausenmöglichkeiten (Cafés mit Platz für Räder, Brunnen, Schattenplätze) oder fahrradfreundliche Infrastruktur?\n"
                    f"3.  **Kleiner Tipp/Highlight:** Eine besondere Empfehlung für Radfahrer (z.B. bester Espresso, Fotospot, kurze lohnende Abstecher zu Fuß).\n\n"
                    f"Schreibe lebendig und motivierend. Verwende Markdown für **Hervorhebungen**."
                )

                # Rufe die API auf
                gemini_text = query_gemini_api(api_key, prompt)

                # Schreibe das Ergebnis in die Markdown-Datei
                f.write(f"## {place}\n\n")
                if gemini_text:
                    f.write(f"{gemini_text}\n\n")
                    print(f"    -> Beschreibung für {place} erhalten.")
                else:
                    f.write("*(Fehler bei der Abfrage oder keine Beschreibung verfügbar)*\n\n")
                    print(f"    -> !! Fehler oder keine Beschreibung für {place}.")

                # Kurze Pause zwischen den API-Aufrufen (optional, aber empfohlen)
                time.sleep(1.5) # Etwas mehr als 1 Sekunde

        print(f"\n[OK] Markdown-Datei mit Beschreibungen gespeichert: {output_md_path}")

    except IOError as e:
        print(f" Fehler beim Schreiben der Markdown-Datei '{output_md_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f" Unerwarteter Fehler beim Generieren der Beschreibungen: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Google Gemini API to generate descriptions for places listed in a CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to the sorted places CSV file (output of step 8).")
    parser.add_argument("--output-md", required=True, help="Path to save the output Markdown file.")
    args = parser.parse_args()

    generate_descriptions(args.input_csv, args.output_md)