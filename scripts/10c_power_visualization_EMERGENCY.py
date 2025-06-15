#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10c_power_visualization.py - EMERGENCY SIMPLIFIED VERSION
----------------------------------------------------------
CRITICAL BUGFIX: Eliminiert alle potentiellen Infinite Loops durch drastische Vereinfachung
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "10c_power_visualization.py"
SCRIPT_VERSION = "2.1.0-EMERGENCY"
SCRIPT_DESCRIPTION = "Emergency simplified power visualization - no infinite loops"
LAST_UPDATED = "2025-06-09"
AUTHOR = "Markus"

import argparse
import os
import sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yaml
from datetime import datetime
import time

def simple_uniform_sampling(df, max_points=1000):
    """ULTRA-SIMPLE uniform sampling - NO LOOPS, NO COMPLEXITY."""
    if len(df) <= max_points:
        return df
    
    # Simple step calculation - GUARANTEED to terminate
    step = max(1, len(df) // max_points)
    indices = list(range(0, len(df), step))
    
    # Ensure we don't exceed max_points
    if len(indices) > max_points:
        indices = indices[:max_points]
    
    # Always include last point if we have data
    if len(df) > 0 and len(indices) > 0 and indices[-1] != len(df) - 1:
        indices[-1] = len(df) - 1
        
    return df.iloc[indices].copy().reset_index(drop=True)

def load_surface_colors():
    """Simple default surface colors - no file I/O complexity."""
    return {
        'asphalt': '#212529',
        'paved': '#6c757d', 
        'concrete': '#adb5bd',
        'gravel': '#FF8F00',
        'dirt': '#8D6E63',
        'unknown': '#E0E0E0',
        'default': '#D32F2F'
    }

def merge_data_simple(power_csv, surface_csv):
    """SIMPLE data merge - minimal processing."""
    print(f"Loading power data: {power_csv}")
    df_power = pd.read_csv(power_csv, comment='#')
    
    print(f"Loading surface data: {surface_csv}")
    df_surface = pd.read_csv(surface_csv, comment='#')
    
    print(f"Power columns: {list(df_power.columns)}")
    print(f"Surface columns: {list(df_surface.columns)}")
    
    # Find distance column
    distance_col = None
    for col in df_power.columns:
        if 'distanz' in col.lower() or 'distance' in col.lower():
            distance_col = col
            break
    
    if not distance_col:
        raise ValueError("No distance column found")
    
    print(f"Using distance column: {distance_col}")
    
    # Simple merge - just add unknown surface to all points
    df_merged = df_power.copy()
    df_merged['Surface'] = 'unknown'
    
    print(f"Merged data: {len(df_merged)} rows")
    return df_merged, distance_col

def create_simple_visualization(df, distance_col, output_html, max_points=1000):
    """ULTRA-SIMPLE visualization - guaranteed to complete."""
    print(f"Creating simple visualization with {len(df)} points...")
    
    # STEP 1: Simple sampling
    if len(df) > max_points:
        print(f"Sampling down to {max_points} points...")
        df = simple_uniform_sampling(df, max_points)
    
    print(f"Working with {len(df)} points")
    
    # STEP 2: Determine what to plot
    has_power = 'Power_W' in df.columns
    has_elevation = 'Elevation (m)' in df.columns
    
    if has_power:
        power_col = 'Power_W'
        power_label = 'Power (W)'
    else:
        # Fallback to speed
        speed_cols = [col for col in df.columns if 'geschwindigkeit' in col.lower() or 'speed' in col.lower()]
        if speed_cols:
            power_col = speed_cols[0]
            power_label = 'Speed (km/h)'
        else:
            raise ValueError("No power or speed column found")
    
    print(f"Using {power_col} for visualization")
    
    # STEP 3: Create simple single plot (NO SEGMENTS to avoid complexity)
    fig = go.Figure()
    
    # Add power/speed trace
    fig.add_trace(go.Scatter(
        x=df[distance_col],
        y=df[power_col],
        mode='lines',
        name=power_label,
        line=dict(color='red', width=2)
    ))
    
    # Add elevation if available  
    if has_elevation:
        fig.add_trace(go.Scatter(
            x=df[distance_col],
            y=df['Elevation (m)'],
            mode='lines',
            name='Elevation (m)',
            line=dict(color='blue', width=1),
            yaxis='y2'
        ))
        
        # Setup dual y-axes
        fig.update_layout(
            yaxis=dict(title=power_label, side='left', color='red'),
            yaxis2=dict(title='Elevation (m)', side='right', overlaying='y', color='blue')
        )
    
    # STEP 4: Simple layout
    total_distance = df[distance_col].max()
    
    fig.update_layout(
        title=f"Power Analysis - Simple View ({len(df)} points, {total_distance:.1f} km)",
        xaxis_title="Distance (km)",
        template="plotly_white",
        width=1200,
        height=600
    )
    
    # STEP 5: Save HTML
    print(f"Saving to {output_html}...")
    fig.write_html(output_html)
    print(f"[OK] Visualization saved: {output_html}")
    
    # Quick file size check
    if os.path.exists(output_html):
        file_size = os.path.getsize(output_html) / 1024 / 1024  # MB
        print(f"File size: {file_size:.2f} MB")
    
    return fig

def main():
    """Main function - SIMPLIFIED to eliminate all potential infinite loops."""
    parser = argparse.ArgumentParser(description="Emergency simplified power visualization")
    parser.add_argument("--power-csv", required=True)
    parser.add_argument("--surface-csv", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--output-png", default=None)
    parser.add_argument("--config-file", default="config.yaml")
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--max-points", type=int, default=1000)
    
    args = parser.parse_args()
    
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print("EMERGENCY MODE: Ultra-simplified visualization")
    
    start_time = time.time()
    
    try:
        # STEP 1: Load and merge data (simplified)
        df_merged, distance_col = merge_data_simple(args.power_csv, args.surface_csv)
        
        # STEP 2: Create simple visualization
        fig = create_simple_visualization(
            df_merged, 
            distance_col, 
            args.output_html, 
            args.max_points
        )
        
        # STEP 3: Optional PNG (with timeout protection)
        if args.output_png:
            try:
                print("Attempting PNG export...")
                fig.write_image(args.output_png, width=1200, height=600)
                print(f"[OK] PNG saved: {args.output_png}")
            except Exception as e:
                print(f"[Warning] PNG export failed (expected): {e}")
        
        elapsed = time.time() - start_time
        print(f"\n[SUCCESS] Completed in {elapsed:.1f} seconds")
        
        # Summary
        mode = "Analysis" if 'Power_W' in df_merged.columns else "Speed"
        print(f"Mode: {mode}")
        print(f"Data points: {len(df_merged)}")
        print(f"Distance: {df_merged[distance_col].min():.1f} - {df_merged[distance_col].max():.1f} km")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        
        # Create emergency HTML
        try:
            with open(args.output_html, 'w') as f:
                f.write(f"<html><body><h1>Visualization Error</h1><p>{e}</p></body></html>")
            print(f"Emergency HTML created: {args.output_html}")
        except:
            pass
            
        sys.exit(1)

if __name__ == "__main__":
    main()
