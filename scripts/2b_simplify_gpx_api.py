#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2b_simplify_gpx_api.py
----------------------
Simplifies track points from a full track CSV using Ramer-Douglas-Peucker (RDP).
Optimizes track data for API calls while preserving route accuracy.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "2b_simplify_gpx_api.py"
SCRIPT_VERSION = "2.1.0"
SCRIPT_DESCRIPTION = "Track simplification using RDP algorithm with integrated metadata"
LAST_UPDATED = "2025-06-15"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v2.0.0 (2025-06-08): Vollständiges Performance-Tracking System für RDP-Track-Simplification
v2.1.0 (2025-06-15): Integrated metadata system directly into CSV output
- Removed external metadata files
- Direct integration with CSV_METADATA_TEMPLATE
- Simplified and streamlined processing
- Enhanced error handling with metadata preservation
"""

# === IMPORTS ===
import sys
import os
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import time
from rdp import rdp

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def simplify_track_with_indexing(input_full_track_csv: str, output_simplified_csv: str, epsilon: float):
    print(f"[Info] Simplifying track from CSV with indexing: {input_full_track_csv}")
    print(f"  Epsilon: {epsilon}")
    
    start_total_time = time.time()
    
    # Simplified metadata collection
    metadata = {
        'epsilon_value': epsilon,
        'original_points': 0,
        'simplified_points': 0,
        'final_points': 0,
        'point_reduction_percentage': 0,
        'processing_time_sec': 0,
        'successful_mappings': 0,
        'failed_mappings': 0,
        'algorithm_efficiency_points_per_sec': 0,
        'data_quality_score': 0
    }
    
    try:
        output_dir = os.path.dirname(output_simplified_csv)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # === INPUT LOADING ===
        df_full = pd.read_csv(input_full_track_csv, comment='#')
        metadata['original_points'] = len(df_full)
        
        if df_full.empty or len(df_full) < 2:
            print(f"[Warning] Input CSV '{input_full_track_csv}' is empty or has < 2 points.")
            df_to_save = pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index'])
            metadata['final_points'] = 0
        else:
            # === RDP ALGORITHM ===
            points_for_rdp_np = df_full[['Longitude', 'Latitude']].values
            print(f"[Info] Original number of points: {len(points_for_rdp_np)}")
            
            simplified_points_np = rdp(points_for_rdp_np, epsilon=epsilon)
            metadata['simplified_points'] = len(simplified_points_np)
            print(f"[Info] Number of points after RDP: {len(simplified_points_np)}")
            
            # === INDEX MAPPING ===
            if len(simplified_points_np) == 0:
                # Fallback: Use start and end points
                indices_to_keep = [0, len(df_full) - 1] if len(df_full) > 1 else [0]
                df_simplified_with_index = df_full.iloc[indices_to_keep].copy()
                df_simplified_with_index['original_index'] = df_simplified_with_index.index
                metadata['successful_mappings'] = len(df_simplified_with_index)
            else:
                # Create DataFrame from simplified points
                df_simplified_coords = pd.DataFrame(simplified_points_np, columns=['Longitude', 'Latitude'])
                
                # Prepare for index mapping
                df_full_indexed = df_full.copy()
                df_full_indexed['original_index'] = df_full_indexed.index
                
                # Round coordinates for robust merge
                precision = 6
                df_simplified_coords_rounded = df_simplified_coords.round(precision)
                df_full_indexed_rounded = df_full_indexed.round(precision)
                
                # Perform index mapping
                df_simplified_with_index = pd.merge(
                    df_simplified_coords_rounded,
                    df_full_indexed_rounded[['Longitude', 'Latitude', 'original_index']],
                    on=['Longitude', 'Latitude'],
                    how='left'
                )
                
                # Count successful mappings
                successful_mappings = (~df_simplified_with_index['original_index'].isnull()).sum()
                metadata['successful_mappings'] = successful_mappings
                metadata['failed_mappings'] = len(df_simplified_with_index) - successful_mappings
                
                # Restore precise coordinates
                if successful_mappings > 0:
                    valid_indices = df_simplified_with_index.dropna(subset=['original_index']).copy()
                    valid_indices['original_index'] = valid_indices['original_index'].astype(int)
                    
                    final_simplified_df = df_full.iloc[valid_indices['original_index'].values][['Latitude', 'Longitude']].copy()
                    final_simplified_df['original_index'] = valid_indices['original_index'].values
                    df_simplified_with_index = final_simplified_df.reset_index(drop=True)
            
            # === ENFORCE START/END POINTS ===
            start_point = df_full.iloc[[0]].copy()
            start_point['original_index'] = start_point.index[0]
            
            end_point = df_full.iloc[[-1]].copy()
            end_point['original_index'] = end_point.index[0]
            
            # Combine all points
            df_simplified_with_index = pd.concat([
                start_point[['Latitude', 'Longitude', 'original_index']],
                df_simplified_with_index,
                end_point[['Latitude', 'Longitude', 'original_index']]
            ], ignore_index=True)
            
            # Remove duplicates and sort
            df_simplified_with_index.drop_duplicates(subset=['original_index'], keep='first', inplace=True)
            df_simplified_with_index.sort_values(by='original_index', inplace=True)
            df_simplified_with_index.reset_index(drop=True, inplace=True)
            
            # Final output preparation
            df_to_save = df_simplified_with_index[['Latitude', 'Longitude', 'original_index']].copy()
            df_to_save['original_index'] = df_to_save['original_index'].astype('Int64')
            metadata['final_points'] = len(df_to_save)
        
        # === CALCULATE METADATA ===
        total_time = time.time() - start_total_time
        metadata['processing_time_sec'] = round(total_time, 3)
        
        if metadata['original_points'] > 0:
            metadata['point_reduction_percentage'] = round(
                (1 - metadata['final_points'] / metadata['original_points']) * 100, 1
            )
            metadata['algorithm_efficiency_points_per_sec'] = round(
                metadata['original_points'] / total_time, 1
            ) if total_time > 0 else 0
        
        # Quality score calculation
        if metadata['final_points'] >= 2:
            quality_score = min(100, (
                50 +  # Base score
                25 * (metadata['successful_mappings'] / max(1, metadata['simplified_points'])) +  # Mapping success
                25 * (metadata['final_points'] / max(1, metadata['original_points']))  # Point retention
            ))
        else:
            quality_score = 10
        
        metadata['data_quality_score'] = round(quality_score, 1)
        
        # === SAVE WITH INTEGRATED METADATA ===
        # Prepare processing parameters
        processing_parameters = {
            'epsilon_value': epsilon,
            'coordinate_precision': 6,
            'algorithm': 'Ramer-Douglas-Peucker'
        }
        
        # Prepare additional metadata
        additional_metadata = {
            'original_points_count': metadata['original_points'],
            'simplified_points_count': metadata['simplified_points'],
            'final_output_points': metadata['final_points'],
            'point_reduction_percentage': metadata['point_reduction_percentage'],
            'processing_time_sec': metadata['processing_time_sec'],
            'successful_index_mappings': metadata['successful_mappings'],
            'failed_index_mappings': metadata['failed_mappings'],
            'algorithm_efficiency_points_per_sec': metadata['algorithm_efficiency_points_per_sec'],
            'data_quality_score': metadata['data_quality_score'],
            'track_simplification_mode': 'api_optimization',
            'start_end_points_enforced': True
        }
        
        # Write CSV with integrated metadata
        write_csv_with_metadata(
            dataframe=df_to_save,
            output_path=output_simplified_csv,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_full_track_csv],
            processing_parameters=processing_parameters,
            api_metadata=None,
            additional_metadata=additional_metadata,
            float_format='%.6f'
        )
        
        print(f"[Info] Final simplified points: {len(df_to_save)}")
        print(f"[Performance] Processing time: {total_time:.3f} seconds")
        print(f"[Performance] Point reduction: {metadata['point_reduction_percentage']:.1f}%")
        print(f"[Performance] Quality score: {metadata['data_quality_score']}/100")
        print(f"[OK] Simplified API track data with metadata saved: {output_simplified_csv}")
        
    except FileNotFoundError:
        print(f"[Error] Input file not found: {input_full_track_csv}")
        # Create empty CSV with metadata
        df_empty = pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index'])
        write_csv_with_metadata(
            dataframe=df_empty,
            output_path=output_simplified_csv,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_full_track_csv],
            processing_parameters={'epsilon_value': epsilon, 'error': 'file_not_found'},
            additional_metadata={'processing_error': 'Input file not found', 'final_output_points': 0}
        )
        sys.exit(1)
    except Exception as e:
        print(f"[Error] Error during simplification: {input_full_track_csv} - {e}")
        # Create empty CSV with error metadata
        df_empty = pd.DataFrame(columns=['Latitude', 'Longitude', 'original_index'])
        write_csv_with_metadata(
            dataframe=df_empty,
            output_path=output_simplified_csv,
            script_name=SCRIPT_NAME,
            script_version=SCRIPT_VERSION,
            input_files=[input_full_track_csv],
            processing_parameters={'epsilon_value': epsilon, 'error': 'processing_failed'},
            additional_metadata={'processing_error': str(e), 'final_output_points': 0}
        )
        sys.exit(1)

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Simplify track points from full CSV and keep original indices.")
    parser.add_argument("--input-csv", required=True, help="Path to the input full track data CSV (output of 2_parse_gpx_full.py).")
    parser.add_argument("--output", required=True, help="Path to save the simplified CSV (Lat, Lon, original_index).")
    parser.add_argument("--epsilon", type=float, default=0.0001, help="Epsilon value for RDP simplification (in degrees).")
    args = parser.parse_args()

    simplify_track_with_indexing(args.input_csv, args.output, args.epsilon)
