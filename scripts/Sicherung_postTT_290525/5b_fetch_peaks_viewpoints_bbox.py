#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5b_fetch_peaks_viewpoints_bbox.py
---------------------------------
Finds peaks (natural=peak) and viewpoints (tourism=viewpoint) within an
expanded bounding box of an original GPX track using the Overpass API.
Saves results to a JSON file.
""" # <-- Docstring korrekt geschlossen

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import requests
from shapely.geometry import LineString, Point # Requires shapely
import json
import time

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# --- Ab hier beginnt die Funktion fetch_peaks_viewpoints ---
def fetch_peaks_viewpoints(input_gpx_path: str, output_json_path: str, buffer_degrees: float):
    """Fetches peaks and viewpoints within the GPX bounding box + buffer."""
    print(f"[Info] Fetching Peaks/Viewpoints for BBOX of: {input_gpx_path}")
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_json_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(input_gpx_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

    except FileNotFoundError:
        print(f"[Fehler] Eingabedatei nicht gefunden: {input_gpx_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fehler] Konnte GPX-Datei nicht laden oder parsen: {input_gpx_path} - {e}")
        sys.exit(1)

    # Extract points (lon, lat for shapely)
    points_lon_lat = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Grundlegende Validierung der Koordinaten
                if -180 <= point.longitude <= 180 and -90 <= point.latitude <= 90:
                    points_lon_lat.append((point.longitude, point.latitude))
                else:
                    print(f"[Warnung] Ungültige Koordinate übersprungen: Lon={point.longitude}, Lat={point.latitude}")


    if len(points_lon_lat) < 2:
        print(f"[Warnung] Weniger als 2 gültige Punkte in {input_gpx_path}. BBOX nicht sinnvoll bestimmbar.")
        # Save empty JSON structure
        output_data = {"bbox_used": None, "elements": []}
        try:
            # Sicherstellen, dass der Output-Ordner existiert (erneut, falls leer)
            output_dir = os.path.dirname(output_json_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            print(f"[OK] Leere JSON gespeichert: {output_json_path}")
        except Exception as e:
            print(f"[Fehler] Konnte leere JSON nicht schreiben: {output_json_path} - {e}")
        return # Wichtig: Funktion hier beenden

    # Calculate bounding box using Shapely
    try:
        track_line = LineString(points_lon_lat)
        minx, miny, maxx, maxy = track_line.bounds
        # Zusätzliche Prüfung auf degenerierte BBOX
        if not (maxx > minx and maxy > miny):
             print(f"[Warnung] Degenerierte BBOX berechnet ({minx},{miny},{maxx},{maxy}). Möglicherweise nur ein Punkt oder vertikale/horizontale Linie.")
             # Sinnvolles Fallback? Oder mit Puffer weitermachen?
             # Wir machen weiter, Overpass sollte damit umgehen können.

    except Exception as e:
         print(f"[Fehler] Konnte Bounding Box nicht berechnen (Shapely Error?): {e}")
         sys.exit(1)

    # Apply buffer
    bbox = (miny - buffer_degrees, minx - buffer_degrees,
            maxy + buffer_degrees, maxx + buffer_degrees)
    # Format bbox for Overpass: South,West,North,East (miny, minx, maxy, maxx)
    # Stellen sicher, dass Zahlen korrekt formatiert sind (keine wissenschaftliche Notation etc.)
    bbox_query_str = f"{bbox[0]:.8f},{bbox[1]:.8f},{bbox[2]:.8f},{bbox[3]:.8f}"
    print(f"[Info] Using BBOX (S,W,N,E): {bbox_query_str}")

    # Build Overpass query
    query = f"""
    [out:json][timeout:90];
    (
      node["natural"="peak"](bbox:{bbox_query_str});
      node["tourism"="viewpoint"](bbox:{bbox_query_str});
      // Optional: Suche auch auf Ways, nicht nur Nodes
      // way["natural"="peak"](bbox:{bbox_query_str});
      // way["tourism"="viewpoint"](bbox:{bbox_query_str});
    );
    // Gebe Nodes aus, die Teil der gefundenen Ways sind ODER direkt gefundene Nodes
    out body; // Gibt Nodes, Ways, Relations aus
    >;       // Rekursiv runter: Holt Nodes, die zu gefundenen Ways gehören
    out skel qt; // Gibt Geometrieinformationen aus
    """ # <-- Korrekt geschlossen

    # Execute Overpass query
    elements = []
    try:
        # print(f"[Debug] Sende Overpass Query:\n{query}") # Bei Bedarf einkommentieren
        response = requests.post(OVERPASS_URL, data={'data': query}, timeout=100)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        elements = data.get("elements", [])
        print(f"[Info] Overpass query successful, {len(elements)} elements found in BBOX.")

    except requests.exceptions.HTTPError as e:
         print(f"❌ Fehler bei Overpass API Request (HTTP {e.response.status_code}): {e.response.text}")
         elements = []
    except requests.exceptions.RequestException as e:
        print(f"❌ Fehler bei Overpass API Request (Connection/Timeout etc.): {e}")
        elements = []
    except json.JSONDecodeError as e:
         print(f"❌ Fehler beim Parsen der Overpass JSON Antwort: {e}")
         elements = []
    except Exception as e: # Catch other potential errors
         print(f"❌ Unerwarteter Fehler bei Overpass Abfrage: {e}")
         elements = []


    # Structure results
    output_data = {
        "bbox_used": list(bbox), # Convert tuple to list for JSON compatibility
        "elements": []
    }
    for elem in elements:
        # Ensure it's a node with coordinates
        if elem.get("type") == "node" and "lat" in elem and "lon" in elem:
             tags = elem.get("tags", {})
             elem_type = tags.get("natural", tags.get("tourism", "Unbekannt"))
             # Versuche, Höhe als Float zu parsen, sonst None
             elevation_val = None
             try:
                 elevation_str = tags.get("ele")
                 if elevation_str is not None:
                     elevation_val = float(elevation_str)
             except (ValueError, TypeError):
                 elevation_val = None # Bleibt None bei Parsing-Fehler

             output_data["elements"].append({
                 "id": elem.get("id"),
                 "latitude": elem["lat"],
                 "longitude": elem["lon"],
                 "type": elem_type.lower(), # Konsistent Kleinbuchstaben für Typ
                 "name": tags.get("name"), # Kann None sein
                 "Elevation_OSM": elevation_val, # Als Float oder None speichern
                 "tags": tags # Store all tags for potential future use
             })

    # Save to JSON
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_json_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] {len(output_data['elements'])} Peaks/Viewpoints gespeichert: {output_json_path}")
    except Exception as e:
        print(f"[Fehler] Konnte JSON nicht schreiben: {output_json_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch peaks and viewpoints within the bbox of a GPX file.")
    parser.add_argument("--input-gpx", required=True, help="Path to the input original GPX file.")
    parser.add_argument("--output-json", required=True, help="Path to save the output JSON file.")
    parser.add_argument("--buffer", type=float, default=0.05, help="Buffer to add around the bounding box in degrees.")
    args = parser.parse_args()

    fetch_peaks_viewpoints(args.input_gpx, args.output_json, args.buffer)