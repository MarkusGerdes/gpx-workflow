#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV_METADATA_TEMPLATE.py
Standardisierte Metadaten-Functions für CSV-Ausgabedateien im GPX Workflow
"""

import os
import getpass
from datetime import datetime
from typing import Dict, List, Optional, Any

def create_csv_metadata_header(
    script_name: str,
    script_version: str,
    input_files: List[str],
    processing_parameters: Optional[Dict[str, Any]] = None,
    api_metadata: Optional[Dict[str, Any]] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Erstellt standardisierte Metadaten-Header für CSV-Ausgabedateien.
    
    Args:
        script_name: Name des verarbeitenden Scripts
        script_version: Version des Scripts
        input_files: Liste der Input-Dateien
        processing_parameters: Dict mit Verarbeitungsparametern
        api_metadata: Dict mit API-bezogenen Metadaten
        additional_metadata: Dict mit zusätzlichen, script-spezifischen Metadaten
    
    Returns:
        List[str]: Zeilen für den CSV-Header (mit # am Anfang)
    """
    timestamp = datetime.now()
    user = getpass.getuser()
    
    header_lines = [
        f"# === GPX WORKFLOW PROCESSING METADATA ===",
        f"# Processed_By: {script_name} v{script_version}",
        f"# Processing_Timestamp: {timestamp.isoformat()}",
        f"# Processing_Date: {timestamp.strftime('%Y-%m-%d')}",
        f"# Processing_Time: {timestamp.strftime('%H:%M:%S')}",
        f"# User: {user}",
        f"# Hostname: {os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'unknown'))}",
        f"# Working_Directory: {os.getcwd()}",
    ]
    
    # Input-Dateien
    if input_files:
        header_lines.append(f"# Input_Files_Count: {len(input_files)}")
        for i, input_file in enumerate(input_files, 1):
            if os.path.exists(input_file):
                file_stats = os.stat(input_file)
                file_size_kb = file_stats.st_size / 1024
                file_modified = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                header_lines.extend([
                    f"# Input_File_{i}: {os.path.basename(input_file)}",
                    f"# Input_File_{i}_Path: {input_file}",
                    f"# Input_File_{i}_Size_KB: {file_size_kb:.1f}",
                    f"# Input_File_{i}_Modified: {file_modified}"
                ])
            else:
                header_lines.append(f"# Input_File_{i}: {input_file} (NOT FOUND)")
    
    # Verarbeitungsparameter
    if processing_parameters:
        header_lines.append(f"# === PROCESSING PARAMETERS ===")
        for key, value in processing_parameters.items():
            header_lines.append(f"# Param_{key}: {value}")
    
    # API-Metadaten (falls vorhanden)
    if api_metadata:
        header_lines.append(f"# === API METADATA ===")
        for key, value in api_metadata.items():
            if value is not None:
                header_lines.append(f"# API_{key}: {value}")
    
    # Zusätzliche Metadaten
    if additional_metadata:
        header_lines.append(f"# === ADDITIONAL METADATA ===")
        for key, value in additional_metadata.items():
            header_lines.append(f"# {key}: {value}")
    
    # Abschluss-Zeile
    header_lines.append(f"# === END METADATA ===")
    
    return header_lines

def write_csv_with_metadata(
    dataframe,
    output_path: str,
    script_name: str,
    script_version: str,
    input_files: List[str],
    processing_parameters: Optional[Dict[str, Any]] = None,
    api_metadata: Optional[Dict[str, Any]] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
    float_format: str = '%.6f'
) -> None:
    """
    Schreibt DataFrame mit standardisierten Metadaten-Header in CSV-Datei.
    
    Args:
        dataframe: Pandas DataFrame zum Speichern
        output_path: Pfad der Ausgabedatei
        script_name: Name des verarbeitenden Scripts
        script_version: Version des Scripts
        input_files: Liste der Input-Dateien
        processing_parameters: Dict mit Verarbeitungsparametern
        api_metadata: Dict mit API-bezogenen Metadaten
        additional_metadata: Dict mit zusätzlichen Metadaten
        float_format: Format für Fließkommazahlen
    """
    # Ausgabeverzeichnis erstellen
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Metadaten-Header erstellen
    header_lines = create_csv_metadata_header(
        script_name=script_name,
        script_version=script_version,
        input_files=input_files,
        processing_parameters=processing_parameters,
        api_metadata=api_metadata,
        additional_metadata=additional_metadata
    )
    
    try:
        # Metadaten-Header schreiben
        with open(output_path, 'w', encoding='utf-8') as f:
            for line in header_lines:
                f.write(line + "\n")
        
        # DataFrame anhängen
        dataframe.to_csv(
            output_path, 
            mode='a', 
            index=False, 
            encoding='utf-8',
            float_format=float_format,
            header=True
        )
        
        print(f"[OK] CSV mit Metadaten gespeichert: {output_path}")
        
    except Exception as e:
        print(f"[Fehler] Konnte CSV nicht schreiben: {output_path} - {e}")
        raise

def read_csv_metadata(csv_path: str) -> Dict[str, str]:
    """
    Liest Metadaten aus einem CSV-Header.
    
    Args:
        csv_path: Pfad zur CSV-Datei
    
    Returns:
        Dict[str, str]: Metadaten als Key-Value Paare
    """
    metadata = {}
    
    if not os.path.exists(csv_path):
        return {"Error": f"Datei nicht gefunden: {csv_path}"}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("#"):
                    line_content = line.lstrip('# ').strip()
                    if ':' in line_content:
                        key, value = line_content.split(':', 1)
                        metadata[key.strip()] = value.strip()
                else:
                    # Sobald eine Zeile nicht mit # beginnt, stoppen wir
                    break
        
        # Fallback-Metadaten hinzufügen falls Header leer
        if not metadata or len(metadata) <= 1:
            file_stats = os.stat(csv_path)
            metadata.update({
                "Processing_Timestamp": datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%dT%H:%M:%S'),
                "File_Size_KB": f"{file_stats.st_size / 1024:.1f}",
                "Status": "Verarbeitung abgeschlossen"
            })
            
    except Exception as e:
        metadata["Error"] = f"Fehler beim Lesen des Headers: {e}"
    
    return metadata

# === BEISPIEL-VERWENDUNG ===

def example_usage():
    """Beispiel wie die Metadaten-Functions verwendet werden."""
    import pandas as pd
    
    # Beispiel-DataFrame
    df = pd.DataFrame({
        'Latitude': [52.5200, 52.5201, 52.5202],
        'Longitude': [13.4050, 13.4051, 13.4052],
        'Elevation': [34.5, 35.1, 35.8]
    })
    
    # Metadaten definieren
    processing_params = {
        'sampling_distance_km': 0.5,
        'elevation_api': 'open-elevation',
        'coordinate_precision': 6
    }
    
    api_meta = {
        'provider': 'OpenElevation',
        'queries_made': 147,
        'cache_hits': 23,
        'success_rate': '98.6%'
    }
    
    additional_meta = {
        'track_name': 'Fehmarn_Umrundung',
        'total_distance_km': 78.4,
        'processing_quality': 'high'
    }
    
    # CSV mit Metadaten schreiben
    write_csv_with_metadata(
        dataframe=df,
        output_path="example_output_with_metadata.csv",
        script_name="example_script.py",
        script_version="1.0.0",
        input_files=["input_track.gpx", "config.yaml"],
        processing_parameters=processing_params,
        api_metadata=api_meta,
        additional_metadata=additional_meta
    )
    
    # Metadaten wieder lesen
    metadata = read_csv_metadata("example_output_with_metadata.csv")
    print("Gelesene Metadaten:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    example_usage()
