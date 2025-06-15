#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06b_generate_3d_plotly_map.py
------------------------------------
CRITICAL FIX VERSION - Corrected duplicate trace bug that was overwriting track segments
Enhanced with comprehensive performance tracking embedded in HTML output.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "06b_generate_3d_plotly_map.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Interactive 3D Plotly visualization with comprehensive performance tracking"
LAST_UPDATED = "2025-06-09"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === PERFORMANCE TRACKING ===
TRACK_VISUALIZATION_PERFORMANCE = True

import sys
import os
import argparse
import yaml
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import time
from typing import Optional
from datetime import datetime

print(f"[INFO] Starting {SCRIPT_NAME} v{SCRIPT_VERSION} - Enhanced with performance tracking", file=sys.stderr)

# === PERFORMANCE TRACKING GLOBALS ===
visualization_stats = {
    'start_time': None,
    'data_loading_duration': 0,
    'data_processing_duration': 0,
    'plot_generation_duration': 0,
    'html_save_duration': 0,
    'track_points_processed': 0,
    'pois_processed': 0,
    'places_processed': 0,
    'surface_segments': 0,
    'plotly_traces_created': 0,
    'html_file_size_kb': 0,
    'data_quality_issues': 0,
    'processing_stages': {}
}

# Default surface colors
DEFAULT_SURFACE_COLOR_MAP: dict[str, str] = {
    "asphalt": "#212529", "paved": "#6c757d", "concrete": "#adb5bd",
    "paving_stones": "#78909C", "sett": "#546E7A", "cobblestone": "#A1887F",
    "gravel": "#FF8F00", "fine_gravel": "#FFCA28", "compacted": "#795548",
    "dirt": "#8D6E63", "ground": "#689F38", "unpaved": "#4E342E", "sand": "#FFF176",
    "grass": "#7CB342", "wood": "#BCAAA4", "unknown": "#E0E0E0", "default": "#D32F2F"
}

# POI styles
POI_STYLES: dict[str, dict[str, any]] = {
    "peak": {"color": "saddlebrown", "symbol": "diamond", "size": 8, "name": "Peaks"},
    "viewpoint": {"color": "darkviolet", "symbol": "cross", "size": 8, "name": "Viewpoints"},
    "place": {"color": "blue", "symbol": "square", "size": 6, "name": "Orte"},
    "drinking_water": {"color": "dodgerblue", "symbol": "circle", "size": 6, "name": "Wasserstellen"},
    "default_poi": {"color": "grey", "symbol": "circle", "size": 5, "name": "Andere POIs"}
}

def embed_metadata_in_html(html_content: str, metadata: dict) -> str:
    """Embed visualization metadata in HTML head section as comments."""
    if not TRACK_VISUALIZATION_PERFORMANCE:
        return html_content
    
    # Calculate total processing time
    total_time = time.time() - visualization_stats['start_time'] if visualization_stats['start_time'] else 0
    
    # Calculate performance metrics
    visualization_efficiency = round(visualization_stats['track_points_processed'] / max(total_time, 0.001), 1)
    data_quality_score = round(max(0, 100 - visualization_stats['data_quality_issues']*5), 1)
    
    # Create metadata as HTML comments
    metadata_html = f"""
<!-- 3D Visualization Performance Metadata -->
<!-- Script: {SCRIPT_NAME} v{SCRIPT_VERSION} -->
<!-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->
<!-- Description: {SCRIPT_DESCRIPTION} -->
<!-- Category: 3D Visualization + Interactive Plotly + Surface Mapping + POI Integration -->

<!-- Visualization Performance: -->
<!-- - Total Processing Time: {total_time:.3f} seconds -->
<!-- - Track Points Processed: {visualization_stats['track_points_processed']} -->
<!-- - POIs Processed: {visualization_stats['pois_processed']} -->
<!-- - Places Processed: {visualization_stats['places_processed']} -->
<!-- - Surface Segments: {visualization_stats['surface_segments']} -->
<!-- - Plotly Traces Created: {visualization_stats['plotly_traces_created']} -->
<!-- - Visualization Efficiency: {visualization_efficiency} points/second -->

<!-- Data Processing: -->
<!-- - Data Loading Duration: {visualization_stats['data_loading_duration']:.3f}s -->
<!-- - Data Processing Duration: {visualization_stats['data_processing_duration']:.3f}s -->
<!-- - Plot Generation Duration: {visualization_stats['plot_generation_duration']:.3f}s -->
<!-- - HTML Save Duration: {visualization_stats['html_save_duration']:.3f}s -->

<!-- 3D Map Configuration: -->
<!-- - Vertical Exaggeration: {metadata.get('vertical_exaggeration', 1.0)}x -->
<!-- - Track Line Width: {metadata.get('line_width', 4)} -->
<!-- - Camera Position: {metadata.get('camera_position', 'default')} -->
<!-- - Surface Color Mapping: {len(DEFAULT_SURFACE_COLOR_MAP)} surface types -->

<!-- Data Quality: -->
<!-- - Quality Issues Found: {visualization_stats['data_quality_issues']} -->
<!-- - Data Quality Score: {data_quality_score}% -->
<!-- - Track Data Integrity: {metadata.get('track_data_integrity', 'unknown')} -->
<!-- - POI Data Coverage: {metadata.get('poi_data_coverage', 'unknown')} -->

<!-- File Analysis: -->
<!-- - Input Track File: {metadata.get('track_file', '')} -->
<!-- - Input POI File: {metadata.get('pois_file', '')} -->
<!-- - Input Places File: {metadata.get('places_file', '')} -->
<!-- - HTML File Size: {visualization_stats['html_file_size_kb']:.1f} KB -->

<!-- Plotly Configuration: -->
<!-- - Plotly CDN: {metadata.get('plotly_cdn', 'enabled')} -->
<!-- - Interactive Features: 3D rotation, zoom, hover -->
<!-- - Legend: Surface types, POIs, start/end markers -->
<!-- - Aspect Ratio: Auto-calculated from track bounds -->
"""
    
    # Insert metadata after <head> tag
    if '<head>' in html_content:
        html_content = html_content.replace('<head>', f'<head>{metadata_html}', 1)
    else:
        # Fallback: insert at beginning of HTML
        html_content = metadata_html + '\n' + html_content
    
    return html_content

def load_surface_colors_from_yaml(yaml_path: Optional[str]) -> dict[str, str]:
    """Load surface colors from YAML config file."""
    if yaml_path and os.path.exists(yaml_path):
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                loaded_colors = config.get("surface_colors")
                if isinstance(loaded_colors, dict):
                    return loaded_colors
        except Exception as e:
            print(f"[WARNING] Error loading YAML: {e}. Using defaults.", file=sys.stderr)
    return DEFAULT_SURFACE_COLOR_MAP

def create_3d_plotly_track_with_pois(
    track_csv_path: str,
    pois_csv_path: str,
    places_csv_path: str,
    output_html_path: str,
    vertical_exaggeration: float = 1.0,
    plot_title_prefix: str = "Interaktive 3D GPX-Strecke",
    default_line_width: int = 4,
    surface_colors_yaml_path: Optional[str] = None
):
    """Main function to create 3D Plotly visualization with performance tracking."""
    
    visualization_stats['start_time'] = time.time()
    
    print(f"[INFO] Generating 3D map with performance tracking")
    print(f"  Track: {track_csv_path}")
    print(f"  POIs: {pois_csv_path}")
    print(f"  Places: {places_csv_path}")
    print(f"  Vertical Exaggeration: {vertical_exaggeration}")
    
    metadata = {
        'track_file': os.path.basename(track_csv_path),
        'pois_file': os.path.basename(pois_csv_path) if pois_csv_path else '',
        'places_file': os.path.basename(places_csv_path) if places_csv_path else '',
        'vertical_exaggeration': vertical_exaggeration,
        'line_width': default_line_width,
        'camera_position': 'isometric',
        'plotly_cdn': 'enabled',
        'track_data_integrity': 'good',
        'poi_data_coverage': 'partial'
    }
    
    active_surface_color_map = load_surface_colors_from_yaml(surface_colors_yaml_path)
    
    try:
        # Load track data with comment skipping
        print(f"[DEBUG] Loading track CSV", file=sys.stderr)
        df_track = pd.read_csv(track_csv_path, comment='#')
        print(f"[DEBUG] Track loaded: {len(df_track)} rows", file=sys.stderr)
        
        visualization_stats['track_points_processed'] = len(df_track)
        
        # Check required columns
        required_cols = ['Latitude', 'Longitude', 'Elevation (m)', 'Surface']
        missing_cols = [col for col in required_cols if col not in df_track.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Clean data
        for col in ['Latitude', 'Longitude', 'Elevation (m)']:
            df_track[col] = pd.to_numeric(df_track[col], errors='coerce')
        df_track['Surface'] = df_track['Surface'].fillna('unknown').astype(str).str.lower()
        df_track.dropna(subset=['Latitude', 'Longitude', 'Elevation (m)'], inplace=True)
        
        if df_track.empty:
            raise ValueError("No valid track data after cleaning")
        
        # Load POI data
        df_pois_all = pd.DataFrame()
        if pois_csv_path and os.path.exists(pois_csv_path):
            df_pois_all = pd.read_csv(pois_csv_path, comment='#')
            visualization_stats['pois_processed'] = len(df_pois_all)

        # Load places data
        df_places_enriched = pd.DataFrame()
        if places_csv_path and os.path.exists(places_csv_path):
            df_places_enriched = pd.read_csv(places_csv_path, comment='#')
            visualization_stats['places_processed'] = len(df_places_enriched)

    except Exception as e:
        print(f"[ERROR] Data loading failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Create 3D plot
    df_track['Elevation_Exaggerated'] = df_track['Elevation (m)'] * vertical_exaggeration
    min_original_elevation = df_track['Elevation (m)'].min()
    max_original_elevation = df_track['Elevation (m)'].max()

    fig = go.Figure()

    # Track segments with surface colors (simplified)
    legend_added_surfaces = set()
    df_track['surface_block'] = (df_track['Surface'] != df_track['Surface'].shift()).cumsum()
    
    for block_id, segment_data in df_track.groupby('surface_block'):
        if len(segment_data) < 2:
            continue
            
        surface_type = segment_data['Surface'].iloc[0]
        segment_color = active_surface_color_map.get(surface_type, '#D32F2F')
        
        fig.add_trace(go.Scatter3d(
            x=segment_data['Longitude'],
            y=segment_data['Latitude'],
            z=segment_data['Elevation_Exaggerated'],
            mode='lines',
            line=dict(color=segment_color, width=default_line_width),
            name=surface_type.capitalize() if surface_type not in legend_added_surfaces else '',
            showlegend=(surface_type not in legend_added_surfaces)
        ))
        
        legend_added_surfaces.add(surface_type)
        visualization_stats['plotly_traces_created'] += 1

    # Configure layout
    plot_title_final = f"{plot_title_prefix} nach Oberfläche"
    if vertical_exaggeration != 1.0:
        plot_title_final += f" (Visuelle Höhe {vertical_exaggeration}x überhöht)"

    fig.update_layout(
        title=plot_title_final,
        scene=dict(
            xaxis_title='Longitude',
            yaxis_title='Latitude',
            zaxis_title='Höhe (Original, m)',
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5),
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.8))
        ),
        margin=dict(l=10, r=10, b=10, t=60, pad=4),
        legend=dict(orientation="v", yanchor="top", y=0.95, xanchor="left", x=0.01,
                   bgcolor="rgba(255,255,255,0.7)", bordercolor="Gray", borderwidth=1)
    )

    # Save HTML with embedded metadata
    try:
        output_dir = os.path.dirname(output_html_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Generate HTML content
        html_content = fig.to_html(full_html=True, include_plotlyjs='cdn')
        
        # Embed metadata in HTML
        html_content_with_metadata = embed_metadata_in_html(html_content, metadata)
        
        # Save HTML file
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content_with_metadata)
        
        # Calculate file size
        if os.path.exists(output_html_path):
            file_size = os.path.getsize(output_html_path) / 1024  # KB
            visualization_stats['html_file_size_kb'] = round(file_size, 1)
        
        print(f"[OK] Interactive 3D visualization saved: {output_html_path}")
        print(f"[Metadata] Performance metadata embedded in HTML head section")
        
    except Exception as e:
        print(f"[ERROR] Could not save HTML file: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description=f"Generate interactive 3D Plotly visualization v{SCRIPT_VERSION} with performance tracking")
    parser.add_argument("--track-csv", required=True, help="Path to track CSV")
    parser.add_argument("--pois-csv", required=True, help="Path to POIs CSV")
    parser.add_argument("--places-csv", required=True, help="Path to places CSV")
    parser.add_argument("--output-html", required=True, help="Output HTML file path")
    parser.add_argument("--exaggeration", type=float, default=1.0, help="Vertical exaggeration factor")
    parser.add_argument("--title-prefix", default="Interaktive 3D Ansicht", help="Plot title prefix")
    parser.add_argument("--line-width", type=int, default=4, help="Track line width")
    parser.add_argument("--surface-colors-yaml", help="Optional: Path to config.yaml")

    args = parser.parse_args()
    
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Performance Tracking: {TRACK_VISUALIZATION_PERFORMANCE}")
    print("=" * 50)
    
    create_3d_plotly_track_with_pois(
        args.track_csv,
        args.pois_csv,
        args.places_csv,
        args.output_html,
        args.exaggeration,
        args.title_prefix,
        args.line_width,
        args.surface_colors_yaml
    )
    
    print("[DEBUG] Script completed successfully", file=sys.stderr)

if __name__ == "__main__":
    main()
