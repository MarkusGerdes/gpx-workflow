#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10c_power_visualization.py
---------------------------
Static power visualization with metadata tracking (v2.0.0)
Creates clean 3-segment power profile PNG (like speed profile)
"""

SCRIPT_NAME = "10c_power_visualization.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Static power visualization with performance tracking - creates 3-segment power profile PNG"
LAST_UPDATED = "2025-06-12"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

CHANGELOG = """
v2.0.0 (2025-06-12): Static power visualization with v2.0.0 metadata tracking
- Clean 3-segment power profile (like speed profile)
- Only power line (red) + elevation area (blue) - no gradient complexity
- Gradient-adaptive data reduction for performance
- Comprehensive metadata tracking compatible with v2.0.0 template system
- PNG output with text header metadata for Script 11 integration
"""

DEFAULT_CONFIG_SECTION = "power_visualization"
INPUT_FILE_PATTERN = "*.csv (power data, surface data)"
OUTPUT_FILE_PATTERN = "*.png (static power profile)"

PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "pandas>=1.3.0",
    "matplotlib>=3.5.0",
    "numpy>=1.21.0",
    "PyYAML>=5.4.0"
]

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import yaml
import csv

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

def save_metadata_as_text_header(png_path: str, metadata: dict):
    """Save metadata as text header in PNG file for Script 11 integration."""
    try:
        # Create metadata text header
        metadata_text = f"""# Power Visualization Performance Metadata
# Script: {SCRIPT_NAME} v{SCRIPT_VERSION}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Description: {SCRIPT_DESCRIPTION}
# Category: Power Visualization + Performance Tracking
#
# === PERFORMANCE METRICS ===
"""
        for category, metrics in metadata.items():
            if isinstance(metrics, dict):
                metadata_text += f"# {category.replace('_', ' ').title()}:\n"
                for metric_name, metric_value in metrics.items():
                    metadata_text += f"#   {metric_name}: {metric_value}\n"
            else:
                metadata_text += f"# {category}: {metrics}\n"
        
        metadata_text += "#\n# === END METADATA ===\n"
        
        # For PNG files, we'll create a companion metadata file
        # since PNG text insertion is complex
        metadata_file = png_path.replace('.png', '_metadata.txt')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write(metadata_text)
            
        print(f"[Info] Metadata saved: {metadata_file}")
        
    except Exception as e:
        print(f"[Warning] Could not save metadata: {e}")

def load_config():
    """Load configuration from config.yaml."""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"[WARNING] Could not load config.yaml: {e}")
        return {}

def gradient_adaptive_reduction(df, target_points=4000, gradient_threshold=2.0):
    """Gradient-adaptive data reduction with metadata tracking."""
    reduction_start = time.time()
    original_points = len(df)
    
    if original_points <= target_points:
        print(f"[REDUCTION] No reduction needed: {original_points} <= {target_points} points")
        return df, {
            'reduction_performed': False,
            'original_points': original_points,
            'final_points': original_points,
            'reduction_time_sec': time.time() - reduction_start,
            'reduction_ratio': 1.0
        }
    
    print(f"[REDUCTION] GRADIENT-ADAPTIVE reduction from {original_points} to ~{target_points} points...")
    
    df = df.copy()
    
    # Calculate gradient importance
    abs_gradient = df['Gradient_Percent'].abs()
    
    # Classify points by gradient importance
    steep_mask = abs_gradient > 5.0
    moderate_mask = (abs_gradient > gradient_threshold) & (abs_gradient <= 5.0)
    flat_mask = abs_gradient <= gradient_threshold
    
    # Mark other important features
    power_change = df['Power_W'].diff().abs()
    surface_change = (df['Surface'] != df['Surface'].shift())
    
    selected_indices = set()
    
    # 1. KEEP ALL STEEP AREAS + critical points
    critical_mask = (
        steep_mask |
        surface_change |
        (power_change > 30) |
        (df.index == 0) |
        (df.index == len(df)-1)
    )
    
    critical_indices = df[critical_mask].index
    selected_indices.update(critical_indices)
    
    # 2. MODERATE AREAS - adaptive sampling
    moderate_indices = df[moderate_mask & ~critical_mask].index
    if len(moderate_indices) > 0:
        moderate_step = max(1, 2)
        moderate_selected = moderate_indices[::moderate_step]
        selected_indices.update(moderate_selected)
    
    # 3. FLAT AREAS - heavy reduction
    flat_indices = df[flat_mask & ~critical_mask].index
    remaining_budget = target_points - len(selected_indices)
    
    if len(flat_indices) > 0 and remaining_budget > 0:
        flat_step = max(1, len(flat_indices) // remaining_budget)
        flat_selected = flat_indices[::flat_step]
        selected_indices.update(flat_selected)
    
    # Create final selection
    all_selected = sorted(selected_indices)
    result = df.loc[all_selected].copy()
    
    reduction_time = time.time() - reduction_start
    final_points = len(result)
    reduction_ratio = final_points / original_points
    
    metadata = {
        'reduction_performed': True,
        'original_points': original_points,
        'final_points': final_points,
        'reduction_time_sec': round(reduction_time, 3),
        'reduction_ratio': round(reduction_ratio, 3),
        'steep_points_kept': len(df[steep_mask]),
        'moderate_points_selected': len([i for i in moderate_indices if i in selected_indices]),
        'flat_points_selected': len([i for i in flat_indices if i in selected_indices]),
        'critical_points_kept': len(critical_indices)
    }
    
    print(f"[REDUCTION] Final selection: {final_points:,} points ({reduction_ratio*100:.1f}% of original)")
    
    return result, metadata

def create_power_visualization(power_csv, surface_csv, output_png, target_points=4000, gradient_threshold=2.0, smooth_window=20):
    """Create static power visualization with comprehensive metadata tracking."""
    
    run_start_time = datetime.now()
    print(f"[VISUALIZATION] Generating STATIC 3-segment power profile plot...")
    
    # Initialize metadata
    metadata = {
        'processing_phases': {},
        'data_quality': {},
        'visualization_settings': {},
        'performance_metrics': {},
        'error_handling': {}
    }
    
    try:
        # === DATA LOADING PHASE ===
        loading_start = time.time()
        
        # Load configuration
        config = load_config()
        
        # Load power data
        print(f"[DATA] Loading power data: {power_csv}")
        df_power = pd.read_csv(power_csv, comment='#')
        
        # Load surface data
        print(f"[DATA] Loading surface data: {surface_csv}")
        df_surface = pd.read_csv(surface_csv, comment='#')
        
        metadata['processing_phases']['data_loading_time'] = time.time() - loading_start
        metadata['data_quality']['power_data_rows'] = len(df_power)
        metadata['data_quality']['surface_data_rows'] = len(df_surface)
        
        # Check required columns
        required_power_cols = ['Distanz (km)', 'Elevation (m)', 'Power_W', 'Power_Air_W', 'Power_Roll_W', 'Power_Climb_W']
        missing_cols = [col for col in required_power_cols if col not in df_power.columns]
        if missing_cols:
            print(f"[WARNING] Missing power component columns: {missing_cols}")
            print("[INFO] Will use simplified visualization without component breakdown")
            use_power_components = False
        else:
            use_power_components = True
            print("[INFO] Power components available - will show component breakdown")
        
        metadata['data_quality']['has_elevation_data'] = 'Elevation (m)' in df_power.columns
        metadata['data_quality']['has_power_data'] = 'Power_W' in df_power.columns
        metadata['data_quality']['power_data_complete'] = not df_power['Power_W'].isna().any()
        
        # === DATA MERGING PHASE ===
        merging_start = time.time()
        print("[MERGE] Merging power and surface data...")
        
        df_power['dist_rounded'] = df_power['Distanz (km)'].round(3)
        df_surface['dist_rounded'] = df_surface['Distanz (km)'].round(3)
        
        # Check surface columns
        surface_cols = [col for col in df_surface.columns if 'surface' in col.lower()]
        
        if surface_cols:
            surface_col = surface_cols[0]
            surface_merge_cols = ['dist_rounded', surface_col]
            df_surface_for_merge = df_surface[surface_merge_cols].copy()
            
            df_merged = pd.merge(df_power, df_surface_for_merge, on='dist_rounded', how='left')
            
            if surface_col in df_merged.columns:
                df_merged['Surface'] = df_merged[surface_col].fillna('unknown')
                if surface_col != 'Surface':
                    df_merged = df_merged.drop(columns=[surface_col], errors='ignore')
            else:
                df_merged['Surface'] = 'unknown'
        else:
            df_merged = df_power.copy()
            df_merged['Surface'] = 'unknown'
        
        # Clean up
        df_merged = df_merged.drop(columns=['dist_rounded'], errors='ignore')
        
        metadata['processing_phases']['data_merging_time'] = time.time() - merging_start
        metadata['data_quality']['merged_data_rows'] = len(df_merged)
        metadata['data_quality']['surface_data_coverage'] = (df_merged['Surface'] != 'unknown').sum()
        
        # === GRADIENT CALCULATION PHASE ===
        gradient_start = time.time()
        print("[GRADIENT] Calculating gradients...")
        
        elevation_diff = df_merged['Elevation (m)'].diff()
        distance_diff = df_merged['Distanz (km)'].diff() * 1000  # to meters
        df_merged['Gradient_Percent'] = (elevation_diff / distance_diff.where(distance_diff != 0)).fillna(0)
        
        metadata['processing_phases']['gradient_calculation_time'] = time.time() - gradient_start
        metadata['data_quality']['gradient_data_complete'] = not df_merged['Gradient_Percent'].isna().any()
        metadata['data_quality']['max_gradient_percent'] = float(df_merged['Gradient_Percent'].abs().max())
        
        # === DATA REDUCTION PHASE ===
        print("[REDUCTION] Applying GRADIENT-ADAPTIVE reduction...")
        df_reduced, reduction_metadata = gradient_adaptive_reduction(df_merged, target_points, gradient_threshold)
        
        metadata['data_reduction'] = reduction_metadata
        
        # === SMOOTHING PHASE ===
        smoothing_start = time.time()
        
        if smooth_window > 1:
            print(f"[SMOOTHING] Applying smoothing with window size {smooth_window}")
            df_reduced['Power_Smoothed'] = df_reduced['Power_W'].rolling(
                window=smooth_window, center=True, min_periods=1
            ).mean()
            power_col_to_plot = 'Power_Smoothed'
            power_col_label = f'Power geglättet (W{smooth_window})'
            
            # Also smooth power components if available - BUT NOT roll resistance (surface changes)
            if use_power_components:
                # Roll resistance should NOT be smoothed - surface changes need to be visible
                df_reduced['Power_Roll_Smoothed'] = df_reduced['Power_Roll_W']  # No smoothing!
                
                # Air and climb resistance can be smoothed normally
                df_reduced['Power_Air_Smoothed'] = df_reduced['Power_Air_W'].rolling(
                    window=smooth_window, center=True, min_periods=1
                ).mean()
                df_reduced['Power_Climb_Smoothed'] = df_reduced['Power_Climb_W'].rolling(
                    window=smooth_window, center=True, min_periods=1
                ).mean()
                
                # Combined values for reference
                df_reduced['Power_Roll_Plus_Climb_Smoothed'] = (
                    df_reduced['Power_Roll_Smoothed'] + df_reduced['Power_Climb_Smoothed']
                )
        else:
            power_col_to_plot = 'Power_W'
            power_col_label = 'Power (W)'
            
            if use_power_components:
                df_reduced['Power_Roll_Smoothed'] = df_reduced['Power_Roll_W']  # No smoothing for surface changes
                df_reduced['Power_Air_Smoothed'] = df_reduced['Power_Air_W']
                df_reduced['Power_Climb_Smoothed'] = df_reduced['Power_Climb_W']
                df_reduced['Power_Roll_Plus_Climb_Smoothed'] = df_reduced['Power_Roll_Smoothed'] + df_reduced['Power_Climb_Smoothed']
        
        df_reduced['Elevation_Display'] = df_reduced['Elevation (m)']
        
        metadata['processing_phases']['smoothing_time'] = time.time() - smoothing_start
        metadata['visualization_settings']['smooth_window'] = smooth_window
        metadata['visualization_settings']['power_column_used'] = power_col_to_plot
        metadata['visualization_settings']['use_power_components'] = use_power_components
        
        # === VISUALIZATION PHASE ===
        plot_start = time.time()
        
        # Plot setup
        total_distance = df_reduced['Distanz (km)'].max()
        num_segments = 3
        segment_size = total_distance / num_segments
        print(f"[PLOT] Total distance: {total_distance:.1f} km, segment size: {segment_size:.1f} km")
        
        # Calculate Y-axis limits to include negative values
        max_power_overall = df_reduced[power_col_to_plot].max()
        if use_power_components:
            # Include all individual components for proper scaling
            min_power_overall = min(
                df_reduced['Power_Air_Smoothed'].min(),
                df_reduced['Power_Roll_Smoothed'].min(),
                df_reduced['Power_Climb_Smoothed'].min(),
                0  # Always include 0
            )
            max_power_overall = max(
                max_power_overall,
                df_reduced['Power_Air_Smoothed'].max(),
                df_reduced['Power_Roll_Smoothed'].max(),
                df_reduced['Power_Climb_Smoothed'].max()
            )
        else:
            min_power_overall = min(df_reduced[power_col_to_plot].min(), 0)
        
        y_axis_buffer = 1.05
        y_max = max_power_overall * y_axis_buffer
        y_min = min_power_overall * y_axis_buffer if min_power_overall < 0 else 0
        
        print(f"[PLOT] Y-axis range: {y_min:.0f} to {y_max:.0f} W (includes negative power support)")
        
        # Create figure
        fig, axes = plt.subplots(num_segments, 1, figsize=(14, 12), sharex=False)
        segment_stats = []
        
        # Process each segment
        for i in range(num_segments):
            start_km = i * segment_size
            end_km = (i + 1) * segment_size
            
            # Filter data for this segment
            segment_mask = (df_reduced['Distanz (km)'] >= start_km) & (df_reduced['Distanz (km)'] <= end_km)
            segment_df = df_reduced[segment_mask].copy()
            
            if segment_df.empty:
                print(f"[WARNING] Segment {i+1} is empty")
                continue
            
            # Statistics for this segment
            avg_power = segment_df[power_col_to_plot].mean()
            max_power_segment = segment_df[power_col_to_plot].max()
            segment_stats.append((i+1, start_km, end_km, avg_power, max_power_segment))
            
            # Plot power lines
            color_power = 'tab:red'
            color_air = 'tab:blue'      # Air resistance - blue
            color_roll = 'forestgreen'   # Roll resistance - green  
            color_climb = 'darkorange'   # Climb resistance - orange
            
            # 1. Plot total power (red line - most prominent)
            axes[i].plot(segment_df['Distanz (km)'], segment_df[power_col_to_plot], 
                        color=color_power, alpha=0.9, linewidth=2.0, label='Gesamt-Power', zorder=4)
            
            # 2. Plot individual power components if available (thinner lines)
            if use_power_components:
                # Air resistance (blue line)
                axes[i].plot(segment_df['Distanz (km)'], segment_df['Power_Air_Smoothed'], 
                            color=color_air, alpha=0.8, linewidth=1.0, label='Luftwiderstand', zorder=3)
                
                # Roll resistance (green line - no smoothing, shows surface changes!)
                axes[i].plot(segment_df['Distanz (km)'], segment_df['Power_Roll_Smoothed'], 
                            color=color_roll, alpha=0.8, linewidth=1.0, label='Rollwiderstand', zorder=2)
                
                # Climb resistance (orange line - can be negative!)
                axes[i].plot(segment_df['Distanz (km)'], segment_df['Power_Climb_Smoothed'], 
                            color=color_climb, alpha=0.8, linewidth=1.0, label='Steigungswiderstand', zorder=2)
            
            # 3. Average power line (dashed)
            axes[i].axhline(y=avg_power, color='darkred', linestyle='--', alpha=0.7, zorder=1)
            
            # 4. Zero line for reference (when negative values exist)
            if y_min < 0:
                axes[i].axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=0.8, zorder=1)
            
            # Create elevation twin axis
            ax2 = axes[i].twinx()
            color_elevation = 'tab:blue'
            
            # Calculate elevation range for this segment
            segment_min_elevation = segment_df['Elevation_Display'].min()
            segment_max_elevation = segment_df['Elevation_Display'].max()
            elevation_range = segment_max_elevation - segment_min_elevation
            
            # Buffer for better display
            elevation_buffer = max(10, elevation_range * 0.1)
            y_min_elevation = segment_min_elevation - elevation_buffer
            y_max_elevation = segment_max_elevation + elevation_buffer
            
            # Plot elevation area (blue)
            ax2.plot(segment_df['Distanz (km)'], segment_df['Elevation_Display'], 
                    color=color_elevation, alpha=0.3, linewidth=1.0, linestyle='-')
            ax2.fill_between(segment_df['Distanz (km)'], segment_df['Elevation_Display'], 
                            color=color_elevation, alpha=0.1)
            
            # Set proper Y-axis limits for elevation
            ax2.set_ylim(y_min_elevation, y_max_elevation)
            ax2.set_ylabel('Höhe (m)', color=color_elevation, fontsize=10)
            ax2.tick_params(axis='y', labelcolor=color_elevation, labelsize=9)
            
            # Legend
            legend_elements = []
            legend_elements.append(plt.Line2D([0], [0], color=color_power, linewidth=2.0, 
                                           label='Gesamt-Power', alpha=0.9))
            
            if use_power_components:
                legend_elements.append(plt.Line2D([0], [0], color=color_air, linewidth=1.0,
                                                 label='Luftwiderstand', alpha=0.8))
                legend_elements.append(plt.Line2D([0], [0], color=color_roll, linewidth=1.0,
                                                 label='Rollwiderstand', alpha=0.8))
                legend_elements.append(plt.Line2D([0], [0], color=color_climb, linewidth=1.0,
                                                 label='Steigungswiderstand', alpha=0.8))
            
            legend_elements.append(plt.Line2D([0], [0], color='darkred', linestyle='--', 
                                           label=f'Ø {avg_power:.0f} W'))
            
            # Configure axes
            axes[i].set_title(f'Segment {i+1}: {start_km:.0f}-{end_km:.0f} km ' + 
                             f'(Ø {avg_power:.0f} W, Max {max_power_segment:.0f} W)', 
                             fontsize=12, fontweight='bold')
            axes[i].set_ylabel(power_col_label, color=color_power, fontsize=10)
            axes[i].tick_params(axis='y', labelcolor=color_power, labelsize=9)
            axes[i].grid(True, which='major', linestyle=':', linewidth=0.5, color='gray', alpha=0.7)
            axes[i].legend(handles=legend_elements, loc='upper right', fontsize=9)
            axes[i].set_ylim(y_min, y_max)
            
            if i == 2:
                axes[i].set_xlabel('Distanz (km)', fontsize=11)
            axes[i].set_xlim(start_km, end_km)
        
        # Title and overall statistics
        basename = os.path.basename(output_png).replace("_power_visualization.png", "").replace("10c_", "")
        fig.suptitle(f'Power-Performance-Analyse (3-Segment) - {basename}', 
                    fontsize=14, fontweight='bold', y=0.98)
        
        # Calculate overall statistics
        overall_avg = df_reduced[power_col_to_plot].mean()
        overall_max = df_reduced[power_col_to_plot].max()
        
        # Create statistics text
        stats_text = f'Gesamtstrecke: {total_distance:.1f} km | Ø Power: {overall_avg:.0f} W | Max: {overall_max:.0f} W | Smooth: W{smooth_window}'
        
        # Layout
        top_margin = 0.94
        bottom_margin = 0.08
        stats_fontsize = 10
        
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=stats_fontsize, style='italic')
        
        plt.tight_layout()
        plt.subplots_adjust(top=top_margin, bottom=bottom_margin)
        
        metadata['processing_phases']['visualization_time'] = time.time() - plot_start
        metadata['visualization_settings']['figure_size'] = [14, 12]
        metadata['visualization_settings']['segments_count'] = num_segments
        metadata['visualization_settings']['plot_dpi'] = 250
        
        # === SAVE PHASE ===
        save_start = time.time()
        
        # Create output directory
        output_dir = os.path.dirname(output_png)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Save plot
        plot_dpi = 250
        plt.savefig(output_png, dpi=plot_dpi, bbox_inches='tight')
        plt.close(fig)
        
        metadata['processing_phases']['save_time'] = time.time() - save_start
        
        # === FINALIZE METADATA ===
        total_runtime_sec = (datetime.now() - run_start_time).total_seconds()
        
        metadata['performance_metrics']['total_runtime_sec'] = round(total_runtime_sec, 3)
        metadata['performance_metrics']['overall_avg_power'] = round(overall_avg, 1)
        metadata['performance_metrics']['overall_max_power'] = round(overall_max, 1)
        metadata['performance_metrics']['total_distance_km'] = round(total_distance, 2)
        metadata['performance_metrics']['visualization_efficiency_points_per_sec'] = round(len(df_reduced) / total_runtime_sec, 1) if total_runtime_sec > 0 else 0
        
        # Data quality score calculation
        quality_factors = [
            min(metadata['data_quality']['power_data_rows'] / 1000, 1.0) * 20,  # Data points quality (20%)
            (1 if metadata['data_quality']['has_elevation_data'] else 0.5) * 25,     # Elevation data availability (25%)
            (1 if metadata['data_quality']['has_power_data'] else 0.5) * 25,         # Power data availability (25%)
            (1 if metadata['data_quality']['surface_data_coverage'] > 0 else 0.5) * 15,       # Surface data availability (15%)
            min(metadata['data_reduction']['final_points'] / metadata['data_reduction']['original_points'], 1.0) * 15  # Data reduction efficiency (15%)
        ]
        metadata['performance_metrics']['data_quality_score'] = round(sum(quality_factors), 1)
        
        metadata['error_handling']['success'] = True
        metadata['error_handling']['error_message'] = None
        
        # Save metadata
        save_metadata_as_text_header(output_png, metadata)
        
        # Output segment statistics
        print(f"[STATS] Segment statistics:")
        for seg_num, start, end, avg, max_seg in segment_stats:
            print(f"  Segment {seg_num} ({start:.0f}-{end:.0f} km): Ø {avg:.0f} W, Max {max_seg:.0f} W")
        
        print(f"[SUCCESS] STATIC 3-segment power profile saved: {output_png}")
        print(f"[STATS] Final visualization: {len(df_reduced):,} data points, runtime: {total_runtime_sec:.1f}s")
        if use_power_components:
            print(f"[DESIGN] Individual components: Gesamt-Power (rot, 2.0) + Luft (blau, 1.0) + Roll (gruen, 1.0) + Steigung (orange, 1.0) + Hoehe (blau)")
        else:
            print(f"[DESIGN] Simple design: Power line (red) + elevation area (blue)")
        print(f"[QUALITY] Quality Score: {metadata['performance_metrics']['data_quality_score']}/100")
        
        return True
        
    except FileNotFoundError as e:
        metadata['error_handling']['success'] = False
        metadata['error_handling']['error_message'] = f'Input file not found: {e}'
        metadata['performance_metrics']['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[ERROR] Input file not found: {e}")
        
        # Save error metadata
        save_metadata_as_text_header(output_png.replace('.png', '_error.png'), metadata)
        return False
        
    except Exception as e:
        metadata['error_handling']['success'] = False
        metadata['error_handling']['error_message'] = f'Visualization error: {str(e)}'
        metadata['performance_metrics']['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[ERROR] {e}")
        import traceback
        print(f"[TRACEBACK] Full traceback:")
        print(traceback.format_exc())
        
        # Save error metadata
        save_metadata_as_text_header(output_png.replace('.png', '_error.png'), metadata)
        return False

def main():
    """Main function for command line usage and Snakemake integration."""
    parser = argparse.ArgumentParser(
        description=SCRIPT_DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("power_csv", help="Path to power data CSV from 10b_power_processing.py")
    parser.add_argument("surface_csv", help="Path to surface data CSV")
    parser.add_argument("output_png", help="Path for PNG output")
    parser.add_argument("--target-points", type=int, default=4000, help="Target number of data points after reduction")
    parser.add_argument("--gradient-threshold", type=float, default=2.0, help="Gradient threshold for adaptive reduction")
    parser.add_argument("--smooth-window", type=int, default=20, help="Smoothing window size")
    
    args = parser.parse_args()
    
    print_script_info()
    
    # Call main visualization function
    success = create_power_visualization(
        args.power_csv, 
        args.surface_csv, 
        args.output_png,
        args.target_points,
        args.gradient_threshold,
        args.smooth_window
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
