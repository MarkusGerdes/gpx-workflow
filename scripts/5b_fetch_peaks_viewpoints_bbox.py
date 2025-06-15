#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5b_fetch_peaks_viewpoints_bbox.py
---------------------------------
Finds peaks (natural=peak) and viewpoints (tourism=viewpoint) within an
expanded bounding box of an original GPX track using the Overpass API.
Saves results to a JSON file with detailed performance tracking.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "5b_fetch_peaks_viewpoints_bbox.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Bbox-based peaks and viewpoints fetching from Overpass API with performance tracking"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic bbox querying functionality
v1.1.0 (2025-06-07): Standardized header, improved error handling and coordinate validation
v2.0.0 (2025-06-07): Enhanced metadata system with API performance tracking and detailed processing metrics
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "peaks_viewpoints"
INPUT_FILE_PATTERN = "*.gpx"
OUTPUT_FILE_PATTERN = "*_peaks_viewpoints.json"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "gpxpy>=1.4.0",
    "requests>=2.25.0",
    "shapely>=1.7.0",
    "pandas>=1.3.0"
]

# === API CONFIGURATION ===
API_ENDPOINT = "http://overpass-api.de/api/interpreter"
API_TIMEOUT = 100
API_USER_AGENT = "gpx_workflow_v2_peaks_fetcher"
DEFAULT_BUFFER_DEGREES = 0.05
MAX_RESULTS_LIMIT = 1000

# === PERFORMANCE TRACKING ===
TRACK_API_PERFORMANCE = True
TRACK_PROCESSING_STAGES = True
TRACK_BBOX_CALCULATIONS = True

import sys
import os
import argparse
import gpxpy
import gpxpy.gpx
import requests
from shapely.geometry import LineString, Point
import json
import time
import pandas as pd
from datetime import datetime

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# === PERFORMANCE TRACKING GLOBALS ===
processing_stats = {
    'start_time': None,
    'api_requests': 0,
    'api_success': 0,
    'api_errors': 0,
    'elements_found': 0,
    'bbox_calculation_time': 0,
    'api_response_time': 0,
    'processing_stages': {}
}

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Performance Tracking: {TRACK_API_PERFORMANCE}")
    print("=" * 50)

def log_stage(stage_name: str, duration: float = None, details: dict = None):
    """Log processing stage for performance tracking."""
    processing_stats['processing_stages'][stage_name] = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'details': details or {}
    }

def save_performance_metadata(output_json_path: str, metadata: dict):
    """Save processing metadata to CSV file."""
    if not TRACK_API_PERFORMANCE:
        return
    
    # Create metadata CSV path
    base_path = output_json_path.replace('.json', '_metadata.csv')
    
    # Calculate total processing time
    total_time = time.time() - processing_stats['start_time'] if processing_stats['start_time'] else 0
    
    # Prepare metadata row
    metadata_row = {
        'timestamp': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'input_file': metadata.get('input_file', ''),
        'output_file': os.path.basename(output_json_path),
        'processing_time_seconds': round(total_time, 2),
        'api_requests_total': processing_stats['api_requests'],
        'api_requests_successful': processing_stats['api_success'],
        'api_requests_failed': processing_stats['api_errors'],
        'api_response_time_seconds': round(processing_stats['api_response_time'], 2),
        'bbox_calculation_time_seconds': round(processing_stats['bbox_calculation_time'], 2),
        'elements_found': processing_stats['elements_found'],
        'bbox_buffer_degrees': metadata.get('buffer_degrees', DEFAULT_BUFFER_DEGREES),
        'bbox_coordinates': metadata.get('bbox_coordinates', ''),
        'gpx_points_processed': metadata.get('gpx_points', 0),
        'peaks_found': metadata.get('peaks_found', 0),
        'viewpoints_found': metadata.get('viewpoints_found', 0),
        'api_success_rate': round(processing_stats['api_success'] / max(processing_stats['api_requests'], 1) * 100, 1),
        'avg_api_response_time': round(processing_stats['api_response_time'] / max(processing_stats['api_requests'], 1), 2),
        'overpass_query_length': metadata.get('query_length', 0),
        'overpass_timeout_seconds': API_TIMEOUT,
        'coordinate_validation_errors': metadata.get('coord_validation_errors', 0)
    }
    
    # Convert to DataFrame and save
    df = pd.DataFrame([metadata_row])
    df.to_csv(base_path, index=False, encoding='utf-8', float_format='%.3f')
    print(f"[Metadata] Performance data saved: {base_path}")

def fetch_peaks_viewpoints(input_gpx_path: str, output_json_path: str, buffer_degrees: float):
    """Fetches peaks and viewpoints within the GPX bounding box + buffer."""
    processing_stats['start_time'] = time.time()
    print(f"[Info] Fetching Peaks/Viewpoints for BBOX of: {input_gpx_path}")
    
    metadata = {
        'input_file': os.path.basename(input_gpx_path),
        'buffer_degrees': buffer_degrees,
        'coord_validation_errors': 0
    }
    
    stage_start = time.time()
    
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

    log_stage("gpx_parsing", time.time() - stage_start)
    stage_start = time.time()

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
                    metadata['coord_validation_errors'] += 1

    metadata['gpx_points'] = len(points_lon_lat)
    log_stage("coordinate_extraction", time.time() - stage_start, {'points_extracted': len(points_lon_lat)})

    if len(points_lon_lat) < 2:
        print(f"[Warnung] Weniger als 2 gültige Punkte in {input_gpx_path}. BBOX nicht sinnvoll bestimmbar.")
        # Save empty JSON structure
        output_data = {"bbox_used": None, "elements": [], "metadata": metadata}
        try:
            # Sicherstellen, dass der Output-Ordner existiert (erneut, falls leer)
            output_dir = os.path.dirname(output_json_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            print(f"[OK] Leere JSON gespeichert: {output_json_path}")
            save_performance_metadata(output_json_path, metadata)
        except Exception as e:
            print(f"[Fehler] Konnte leere JSON nicht schreiben: {output_json_path} - {e}")
        return # Wichtig: Funktion hier beenden

    # Calculate bounding box using Shapely
    bbox_start = time.time()
    try:
        track_line = LineString(points_lon_lat)
        minx, miny, maxx, maxy = track_line.bounds
        # Zusätzliche Prüfung auf degenerierte BBOX
        if not (maxx > minx and maxy > miny):
             print(f"[Warnung] Degenerierte BBOX berechnet ({minx},{miny},{maxx},{maxy}). Möglicherweise nur ein Punkt oder vertikale/horizontale Linie.")

    except Exception as e:
         print(f"[Fehler] Konnte Bounding Box nicht berechnen (Shapely Error?): {e}")
         sys.exit(1)

    # Apply buffer
    bbox = (miny - buffer_degrees, minx - buffer_degrees,
            maxy + buffer_degrees, maxx + buffer_degrees)
    # Format bbox for Overpass: South,West,North,East (miny, minx, maxy, maxx)
    bbox_query_str = f"{bbox[0]:.8f},{bbox[1]:.8f},{bbox[2]:.8f},{bbox[3]:.8f}"
    print(f"[Info] Using BBOX (S,W,N,E): {bbox_query_str}")
    
    processing_stats['bbox_calculation_time'] = time.time() - bbox_start
    metadata['bbox_coordinates'] = bbox_query_str
    log_stage("bbox_calculation", processing_stats['bbox_calculation_time'], {'bbox': bbox_query_str})

    # Build Overpass query
    query = f"""
    [out:json][timeout:90];
    (
      node["natural"="peak"](bbox:{bbox_query_str});
      node["tourism"="viewpoint"](bbox:{bbox_query_str});
    );
    out body;
    >;
    out skel qt;
    """
    
    metadata['query_length'] = len(query)

    # Execute Overpass query
    elements = []
    api_start = time.time()
    processing_stats['api_requests'] += 1
    
    try:
        response = requests.post(OVERPASS_URL, data={'data': query}, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", [])
        processing_stats['api_success'] += 1
        print(f"[Info] Overpass query successful, {len(elements)} elements found in BBOX.")

    except requests.exceptions.HTTPError as e:
         print(f"❌ Fehler bei Overpass API Request (HTTP {e.response.status_code}): {e.response.text}")
         processing_stats['api_errors'] += 1
         elements = []
    except requests.exceptions.RequestException as e:
        print(f"❌ Fehler bei Overpass API Request (Connection/Timeout etc.): {e}")
        processing_stats['api_errors'] += 1
        elements = []
    except json.JSONDecodeError as e:
         print(f"❌ Fehler beim Parsen der Overpass JSON Antwort: {e}")
         processing_stats['api_errors'] += 1
         elements = []
    except Exception as e:
         print(f"❌ Unerwarteter Fehler bei Overpass Abfrage: {e}")
         processing_stats['api_errors'] += 1
         elements = []

    processing_stats['api_response_time'] = time.time() - api_start
    processing_stats['elements_found'] = len(elements)
    log_stage("api_query", processing_stats['api_response_time'], {'elements_found': len(elements)})

    # Structure results
    stage_start = time.time()
    output_data = {
        "bbox_used": list(bbox),
        "elements": []
    }
    
    peaks_count = 0
    viewpoints_count = 0
    
    for elem in elements:
        # Ensure it's a node with coordinates
        if elem.get("type") == "node" and "lat" in elem and "lon" in elem:
             tags = elem.get("tags", {})
             elem_type = tags.get("natural", tags.get("tourism", "Unbekannt"))
             
             # Count types
             if elem_type == "peak":
                 peaks_count += 1
             elif elem_type == "viewpoint":
                 viewpoints_count += 1
             
             # Versuche, Höhe als Float zu parsen, sonst None
             elevation_val = None
             try:
                 elevation_str = tags.get("ele")
                 if elevation_str is not None:
                     elevation_val = float(elevation_str)
             except (ValueError, TypeError):
                 elevation_val = None

             output_data["elements"].append({
                 "id": elem.get("id"),
                 "latitude": elem["lat"],
                 "longitude": elem["lon"],
                 "type": elem_type.lower(),
                 "name": tags.get("name"),
                 "Elevation_OSM": elevation_val,
                 "tags": tags
             })

    metadata['peaks_found'] = peaks_count
    metadata['viewpoints_found'] = viewpoints_count
    log_stage("data_processing", time.time() - stage_start, {'peaks': peaks_count, 'viewpoints': viewpoints_count})

    # Save to JSON
    try:
        # Sicherstellen, dass der Output-Ordner existiert
        output_dir = os.path.dirname(output_json_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] {len(output_data['elements'])} Peaks/Viewpoints gespeichert: {output_json_path}")
        
        # Save performance metadata
        save_performance_metadata(output_json_path, metadata)
        
    except Exception as e:
        print(f"[Fehler] Konnte JSON nicht schreiben: {output_json_path} - {e}")
        sys.exit(1)

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Fetch peaks and viewpoints within the bbox of a GPX file.")
    parser.add_argument("--input-gpx", required=True, help="Path to the input original GPX file.")
    parser.add_argument("--output-json", required=True, help="Path to save the output JSON file.")
    parser.add_argument("--buffer", type=float, default=0.05, help="Buffer to add around the bounding box in degrees.")
    args = parser.parse_args()

    fetch_peaks_viewpoints(args.input_gpx, args.output_json, args.buffer)
