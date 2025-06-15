#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Surface_Batch_Processing.py
Batch-Verarbeitung für Surface-Daten mit SQLite-Cache
"""

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging

# Import der Surface-Funktionen
try:
    from SQLiteSurfaceCache import SQLiteSurfaceCache
    # Import der Hauptfunktion aus dem Surface-Script
    sys.path.append('.')
    import importlib.util
    
    # Dynamischer Import der Surface-Funktion
    spec = importlib.util.spec_from_file_location(
        "surface_module", 
        "4b_fetch_surface_grouped_SQLiteCache.py"
    )
    surface_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(surface_module)
    fetch_surface_data_with_sqlite_cache = surface_module.fetch_surface_data_with_sqlite_cache
    
except ImportError as e:
    print(f"Fehler beim Import: {e}")
    print("Stellen Sie sicher, dass alle erforderlichen Dateien vorhanden sind:")
    print("- SQLiteSurfaceCache.py")
    print("- 4b_fetch_surface_grouped_SQLiteCache.py")
    sys.exit(1)

def setup_logging(verbose=False):
    """Konfiguriert Logging für Batch-Processing"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Log-Datei erstellen
    log_file = f"surface_batch_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return log_file

def find_surface_input_files(input_dir, pattern="*location*.csv"):
    """Findet alle Surface-Input-Dateien (mit Location-Daten)"""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input-Verzeichnis nicht gefunden: {input_dir}")
    
    # Verschiedene Patterns für Location-Dateien
    patterns = [
        "*location*.csv",
        "*with_location*.csv", 
        "*geocoded*.csv",
        "*reverse_geocode*.csv"
    ]
    
    files = []
    for pattern in patterns:
        files.extend(input_path.glob(pattern))
    
    # Duplikate entfernen und sortieren
    unique_files = sorted(list(set(files)))
    
    return unique_files

def find_reference_file(location_file, input_dir):
    """Findet die entsprechende Referenzdatei für Distanz/Höhendaten"""
    location_path = Path(location_file)
    input_path = Path(input_dir)
    
    # Versuche verschiedene Patterns für Referenzdateien
    base_name = location_path.stem
    
    # Entferne bekannte Location-Suffixe
    for suffix in ["_with_location", "_location", "_optimized", "_geocoded"]:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break
    
    # Suche nach entsprechender Referenzdatei
    ref_patterns = [
        f"{base_name}_track_data_full_with_elevation.csv",
        f"2c_{base_name}_*.csv",
        f"{base_name}_full*.csv",
        f"{base_name}_elevation*.csv"
    ]
    
    for pattern in ref_patterns:
        ref_files = list(input_path.glob(pattern))
        if ref_files:
            return ref_files[0]  # Nimm die erste gefundene
    
    # Fallback: Suche im gleichen Verzeichnis wie die Location-Datei
    location_dir = location_path.parent
    for pattern in ref_patterns:
        ref_files = list(location_dir.glob(pattern))
        if ref_files:
            return ref_files[0]
    
    return None

def generate_output_filename(input_file, output_dir):
    """Generiert den Output-Dateinamen für Surface-Daten"""
    input_path = Path(input_file)
    output_path = Path(output_dir)
    
    # Erstelle Output-Verzeichnis falls nicht vorhanden
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generiere neuen Dateinamen
    base_name = input_path.stem
    
    # Entferne Location-Suffixe und füge Surface-Suffix hinzu
    for suffix in ["_with_location", "_location", "_optimized", "_geocoded"]:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break
    
    output_filename = f"{base_name}_surface_data.csv"
    return output_path / output_filename

def check_if_processed(output_file, resume=False):
    """Prüft ob Datei bereits verarbeitet wurde"""
    if not resume:
        return False
    
    output_path = Path(output_file)
    if not output_path.exists():
        return False
    
    # Prüfe ob Datei leer oder defekt ist
    try:
        df = pd.read_csv(output_path, nrows=1)
        return len(df.columns) > 5  # Mindestens einige Spalten sollten da sein
    except:
        return False

def process_single_file(input_file, ref_file, output_file, radius, dist_col_ref, 
                       cache_db, cache_tolerance, force_api, verbose):
    """Verarbeitet eine einzelne Datei"""
    logger = logging.getLogger(__name__)
    
    try:
        start_time = time.time()
        
        logger.info(f"Verarbeite: {Path(input_file).name}")
        logger.info(f"  Referenz: {Path(ref_file).name if ref_file else 'Keine'}")
        logger.info(f"  Output: {Path(output_file).name}")
        
        # Surface-Verarbeitung durchführen
        fetch_surface_data_with_sqlite_cache(
            input_track_loc_idx_csv=str(input_file),
            full_track_ref_csv_path=str(ref_file) if ref_file else "",
            output_surface_csv_path=str(output_file),
            query_radius_m=radius,
            dist_col_in_ref=dist_col_ref,
            cache_db_path=cache_db,
            cache_tolerance_km=cache_tolerance,
            force_api=force_api,
            verbose=verbose
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Ergebnis prüfen
        if Path(output_file).exists():
            df = pd.read_csv(output_file)
            logger.info(f"  ✅ Erfolgreich! {len(df)} Zeilen in {duration:.1f}s")
            return True, duration
        else:
            logger.error(f"  ❌ Output-Datei nicht erstellt!")
            return False, duration
            
    except Exception as e:
        logger.error(f"  ❌ Fehler: {e}")
        return False, 0

def main():
    parser = argparse.ArgumentParser(description="Surface Batch Processing mit SQLite Cache")
    parser.add_argument("--input-dir", required=True,
                       help="Verzeichnis mit Location-CSV-Dateien")
    parser.add_argument("--output-dir", required=True,
                       help="Output-Verzeichnis für Surface-Daten")
    parser.add_argument("--cache-db", default="surface_cache.db",
                       help="SQLite Surface Cache Datenbank")
    parser.add_argument("--radius", type=int, default=80,
                       help="Overpass API Abfrageradius in Metern")
    parser.add_argument("--dist-col-ref", default="Distanz (km)",
                       help="Name der Distanzspalte in Referenz-CSV")
    parser.add_argument("--cache-tolerance", type=float, default=0.1,
                       help="Cache-Suchtoleranz in km")
    parser.add_argument("--dry-run", action="store_true",
                       help="Zeige nur was verarbeitet würde")
    parser.add_argument("--resume", action="store_true",
                       help="Überspringe bereits verarbeitete Dateien")
    parser.add_argument("--max-files", type=int,
                       help="Maximale Anzahl zu verarbeitender Dateien")
    parser.add_argument("--force-api", action="store_true",
                       help="Erzwinge API-Calls, ignoriere Cache")
    parser.add_argument("--verbose", action="store_true",
                       help="Detailliertes Logging")
    
    args = parser.parse_args()
    
    # Logging einrichten
    log_file = setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("SURFACE BATCH PROCESSING GESTARTET")
    logger.info("=" * 60)
    logger.info(f"Input-Verzeichnis: {args.input_dir}")
    logger.info(f"Output-Verzeichnis: {args.output_dir}")
    logger.info(f"Cache-Datenbank: {args.cache_db}")
    logger.info(f"Abfrageradius: {args.radius}m")
    logger.info(f"Cache-Toleranz: {args.cache_tolerance}km")
    logger.info(f"Dry-Run: {args.dry_run}")
    logger.info(f"Resume: {args.resume}")
    logger.info(f"Max. Dateien: {args.max_files or 'Alle'}")
    logger.info(f"Log-Datei: {log_file}")
    
    # Cache-Status vor Start
    try:
        cache = SQLiteSurfaceCache(args.cache_db)
        initial_stats = cache.get_cache_statistics()
        cache.close