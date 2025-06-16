#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10b_power_processing.py
-----------------------
Calculates or simulates cycling power and speed based on a physics model.

Modes:
- 'analysis': Calculates power based on actual speed data from a GPX track.
- 'simulation': Simulates speed and time based on a target power output.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "10b_power_processing.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Dual-mode cycling power analysis and speed simulation."
LAST_UPDATED = "2025-06-09"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.2"

# === IMPORTS ===
import argparse
import math
import os
import sys
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime
from pathlib import Path

# Import Metadaten-System
sys.path.append(str(Path(__file__).parent.parent / "project_management"))
from CSV_METADATA_TEMPLATE import write_csv_with_metadata

# === PHYSICAL CONSTANTS & MODEL PARAMETERS ===
G = 9.81  # Gravity in m/s^2
RHO = 1.225  # Air density in kg/m^3

# Aerodynamic drag parameters (CdA in m^2) based on bike type and posture
# This is the most practical way to model aerodynamic drag.
CDA_PARAMS = {
    # Hollandrad / City-Bike
    'city_upright': 0.70,
    # Mountainbike
    'mtb_upright': 0.60,
    # Touring / Trekkingrad
    'touring_normal': 0.50,
    # Gravel-Bike
    'gravel_hoods': 0.42,
    'gravel_drops': 0.35,
    # Rennrad
    'road_hoods': 0.36,
    'road_drops': 0.30,
    # Zeitfahrrad
    'tt_aero': 0.22
}

# Rolling resistance coefficients (Cr) based on OSM tags
ROLL_RESISTANCE_MAP = {
    'asphalt': 0.003, 'concrete': 0.0035, 'chipseal': 0.004,
    'gravel': 0.008, 'fine_gravel': 0.007, 'compacted': 0.006,
    'ground': 0.012, 'earth': 0.015, 'dirt': 0.018,
    'sand': 0.025, 'grass_paver': 0.020, 'unpaved': 0.022,
    'grass': 0.035, 'mud': 0.050, 'sand_loose': 0.040,
    'cobblestone': 0.012, 'sett': 0.010, 'paving_stones': 0.005,
    'wood': 0.008, 'metal': 0.004,
    'unknown': 0.015
}

# === CORE PHYSICS FUNCTIONS ===

def calculate_power_from_speed(speed_ms, gradient, Cr, mass_kg, cda_value, wind_ms=0):
    """Calculates the required power to maintain a given speed."""
    v = speed_ms
    v_wind = v + wind_ms
    slope_angle = math.atan(gradient)
    
    # Forces
    F_air = 0.5 * RHO * cda_value * v_wind**2 * np.sign(v_wind)
    F_roll = Cr * mass_kg * G * math.cos(slope_angle)
    F_climb = mass_kg * G * math.sin(slope_angle)
    
    # Power components
    P_total = (F_air + F_roll + F_climb) * v
    P_air = F_air * v
    P_roll = F_roll * v
    P_climb = F_climb * v

    return {
        'Power_W': P_total if P_total > 0 else 0, # Power cannot be negative when moving
        'Power_Air_W': P_air,
        'Power_Roll_W': P_roll,
        'Power_Climb_W': P_climb
    }

def solve_for_speed_from_power(target_power_w, gradient, Cr, mass_kg, cda_value, wind_ms=0):
    """Numerically solves for speed given a constant power output."""
    v_low, v_high = 0.0, 30.0  # 0 to 108 km/h search range

    for _ in range(30): # Bisection method for 30 iterations
        v_mid = (v_low + v_high) / 2.0
        if v_mid < 1e-6:
             # If power is negative (downhill), speed is not zero. We just need a guess.
             # The solver will find the correct equilibrium speed.
             power_at_v_mid = -1
        else:
             power_at_v_mid = calculate_power_from_speed(
                v_mid, gradient, Cr, mass_kg, cda_value, wind_ms
             )['Power_W']

        if power_at_v_mid < target_power_w:
            v_low = v_mid
        else:
            v_high = v_mid
            
    return (v_low + v_high) / 2.0

# === HELPER FUNCTIONS ===

# Metadata system availability - now properly available
METADATA_SYSTEM_AVAILABLE = True

def print_script_info():
    """Print script information header."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print("=" * 50)

# === DATA PROCESSING & WORKFLOW LOGIC ===

def load_and_merge_data(track_csv, surface_csv, metadata=None):
    """Loads and merges track and surface data."""
    print(f"Loading track data from: {track_csv}")
    df_track = pd.read_csv(track_csv, comment='#')
    
    print(f"Loading surface data from: {surface_csv}")
    df_surface = pd.read_csv(surface_csv, comment='#')
    
    # Check available columns
    print(f"Track columns: {list(df_track.columns)}")
    print(f"Surface columns: {list(df_surface.columns)}")
    
    # Check if original_index exists in both datasets
    has_original_index_track = 'original_index' in df_track.columns
    has_original_index_surface = 'original_index' in df_surface.columns
    
    if has_original_index_track and has_original_index_surface:
        print("Using original_index for precise merging")
        # Ensure compatible dtypes for merging on 'original_index'
        df_track['original_index'] = pd.to_numeric(df_track['original_index'], errors='coerce').astype('Int64')
        df_surface['original_index'] = pd.to_numeric(df_surface['original_index'], errors='coerce').astype('Int64')
        
        print("Merging track and surface data...")
        df_merged = pd.merge(df_track, df_surface[['original_index', 'Surface']], on='original_index', how='left')
    else:
        print("original_index not available in both datasets, using distance-based merging")
        
        # Find distance columns
        track_dist_cols = [col for col in df_track.columns if 'distanz' in col.lower() or 'distance' in col.lower()]
        surface_dist_cols = [col for col in df_surface.columns if 'distanz' in col.lower() or 'distance' in col.lower()]
        
        if track_dist_cols and surface_dist_cols:
            track_dist_col = track_dist_cols[0]
            surface_dist_col = surface_dist_cols[0]
            
            print(f"Using distance columns: {track_dist_col} (track) and {surface_dist_col} (surface)")
            
            # Round distances for matching
            df_track['distance_rounded'] = df_track[track_dist_col].round(3)
            df_surface['distance_rounded'] = df_surface[surface_dist_col].round(3)
            
            df_merged = pd.merge(df_track, df_surface[['distance_rounded', 'Surface']], 
                                on='distance_rounded', how='left')
        else:
            print("Warning: No suitable columns for merging found, using track data with unknown surface")
            df_merged = df_track.copy()
            df_merged['Surface'] = 'unknown'
    
    df_merged['Surface'] = df_merged['Surface'].fillna('unknown')
    
    return df_merged

def calculate_gradient(df, metadata=None):
    """Calculates point-to-point gradient."""
    print("Calculating gradient for each track segment...")
    elevation_diff = df['Elevation (m)'].diff()
    distance_diff = df['Distanz (km)'].diff() * 1000  # convert to meters
    # Avoid division by zero for identical points
    df['Gradient'] = (elevation_diff / distance_diff.where(distance_diff != 0)).fillna(0)
    return df

def run_power_analysis(df, mass_kg, cda_value, metadata=None):
    """Mode 1: Analyzes power based on existing speed data with GPS validation."""
    print("Running in 'analysis' mode...")
    
    # Set processing mode in metadata
    if metadata is not None:
        metadata['processing_mode'] = 'analysis'

    if 'Geschwindigkeit (km/h)' not in df.columns:
        raise ValueError("Input CSV for 'analysis' mode must contain 'Geschwindigkeit (km/h)' column.")

    # GPS-VALIDIERUNG: Plausible Geschwindigkeiten
    speed_col = 'Geschwindigkeit (km/h)'
    original_speed = df[speed_col].copy()
    
    # Geschwindigkeits-Plausibilitätsprüfung - VERSCHÄRFT
    MAX_REALISTIC_SPEED = 65  # km/h - Verschärft für normale Radfahrer
    MAX_ACCELERATION = 10     # km/h pro GPS-Punkt (realistischere Beschleunigung)
    MIN_REALISTIC_SPEED = 2   # km/h - Minimum für fahrende Bewegung
    
    print(f"Original speed range: {df[speed_col].min():.1f} - {df[speed_col].max():.1f} km/h")
    
    # 1. Extreme Geschwindigkeiten identifizieren
    extreme_speeds = df[speed_col] > MAX_REALISTIC_SPEED
    very_extreme = df[speed_col] > 80  # Völlig unrealistische Werte
    print(f"Extreme speeds (>{MAX_REALISTIC_SPEED} km/h): {extreme_speeds.sum()} points")
    print(f"Very extreme speeds (>80 km/h): {very_extreme.sum()} points")
    
    # 2. AGGRESSIVE Geschwindigkeits-Glättung
    df['speed_smoothed'] = df[speed_col].copy()
    
    # Erste Runde: Harte Begrenzung für völlig unrealistische Werte
    df.loc[very_extreme, 'speed_smoothed'] = MAX_REALISTIC_SPEED
    
    # Zweite Runde: Geschwindigkeits-Sprünge glätten
    for i in range(1, len(df)):
        speed_diff = abs(df['speed_smoothed'].iloc[i] - df['speed_smoothed'].iloc[i-1])
        
        if speed_diff > MAX_ACCELERATION:
            # Aggressivere Glättung: Verwende gewichteten Durchschnitt
            prev_speed = df['speed_smoothed'].iloc[i-1]
            if i < len(df) - 1:
                next_speed = df['speed_smoothed'].iloc[i+1]
                # Gewichteter Durchschnitt: 70% vorheriger, 30% nächster Wert
                df.loc[df.index[i], 'speed_smoothed'] = prev_speed * 0.7 + next_speed * 0.3
            else:
                # Am Ende: verwende vorherigen Wert
                df.loc[df.index[i], 'speed_smoothed'] = prev_speed
    
    # Vierte Runde: Rolling median für weitere Glättung
    df['speed_smoothed'] = df['speed_smoothed'].rolling(window=5, center=True, min_periods=1).median()
    
    # Fünfte Runde: Zusätzliche Power-orientierte Glättung
    # Entferne extreme Geschwindigkeits-Oszillationen die unrealistische Power-Spitzen verursachen
    df['speed_smoothed'] = df['speed_smoothed'].rolling(window=3, center=True, min_periods=1).mean()
    
    # Vierte Runde: Finale Begrenzung basierend auf realistischen Percentilen
    percentile_95 = df['speed_smoothed'].quantile(0.95)
    realistic_max = min(MAX_REALISTIC_SPEED, percentile_95 * 1.1)  # Max 10% über 95. Percentile
    
    extreme_after_smoothing = df['speed_smoothed'] > realistic_max
    df.loc[extreme_after_smoothing, 'speed_smoothed'] = realistic_max
    
    # Minimum speed check
    too_slow = df['speed_smoothed'] < MIN_REALISTIC_SPEED
    df.loc[too_slow, 'speed_smoothed'] = MIN_REALISTIC_SPEED
    
    changes_made = (df['speed_smoothed'] != original_speed).sum()
    print(f"GPS speed corrections made: {changes_made} points")
    print(f"Corrected speed range: {df['speed_smoothed'].min():.1f} - {df['speed_smoothed'].max():.1f} km/h")
    
    # Verwende die korrigierte Geschwindigkeit für Power-Berechnung
    power_results = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Analyzing Power"):
        speed_ms = row['speed_smoothed'] / 3.6  # Verwende korrigierte Geschwindigkeit
        surface_type = str(row['Surface']).lower()
        Cr = ROLL_RESISTANCE_MAP.get(surface_type, ROLL_RESISTANCE_MAP['unknown'])
        gradient = row['Gradient']

        power_dict = calculate_power_from_speed(speed_ms, gradient, Cr, mass_kg, cda_value)
        power_results.append(power_dict)
    
    df_power = pd.DataFrame(power_results)
    
    # POST-PROCESSING: Power-Glättung für realistischere Kurven
    # Ähnlich dem professionellen Tool glätten wir die Power-Werte
    print(f"[Info] Applying power smoothing for realistic curves...")
    
    # 1. Entferne extreme Power-Spitzen (>95. Percentile * 1.2)
    power_95th = df_power['Power_W'].quantile(0.95)
    extreme_power_threshold = power_95th * 1.2
    extreme_power_mask = df_power['Power_W'] > extreme_power_threshold
    
    if extreme_power_mask.sum() > 0:
        print(f"[Info] Smoothing {extreme_power_mask.sum()} extreme power spikes (>{extreme_power_threshold:.0f}W)")
        # Ersetze extreme Werte durch rolling median der Umgebung
        df_power.loc[extreme_power_mask, 'Power_W'] = df_power['Power_W'].rolling(window=5, center=True, min_periods=1).median().loc[extreme_power_mask]
    
    # 2. Allgemeine Power-Glättung für natürlichere Kurven
    df_power['Power_W'] = df_power['Power_W'].rolling(window=3, center=True, min_periods=1).mean()
    
    # 3. SELECTIVE component smoothing - AIR resistance should NOT be smoothed!
    # Air resistance naturally varies with speed and should show this variation
    # Only roll and climb resistance benefit from smoothing
    smoothing_components = ['Power_Roll_W', 'Power_Climb_W']  # Exclude Power_Air_W!
    for component in smoothing_components:
        if component in df_power.columns:
            df_power[component] = df_power[component].rolling(window=3, center=True, min_periods=1).mean()
    
    print(f"[Info] SELECTIVE component smoothing: Roll and Climb smoothed, Air resistance kept raw for variation")
    
    print(f"[Info] Power smoothing complete. New range: {df_power['Power_W'].min():.0f} - {df_power['Power_W'].max():.0f}W")
    
    # Behalte sowohl Original- als auch korrigierte Geschwindigkeit
    df['Geschwindigkeit_Original (km/h)'] = original_speed
    df['Geschwindigkeit (km/h)'] = df['speed_smoothed']  # Überschreibe mit korrigierter Version
    df = df.drop(columns=['speed_smoothed'])  # Entferne temporäre Spalte
    
    return pd.concat([df, df_power], axis=1)

def run_speed_simulation(df, mass_kg, cda_value, target_power, metadata):
    """Mode 2: Simulates speed based on a target power with metadata tracking."""
    print(f"Running in 'simulation' mode with target power: {target_power}W...")
    
    simulation_start_time = datetime.now()
    metadata['processing_mode'] = 'simulation'
    metadata['target_power_w'] = target_power

    simulated_speeds_ms = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Simulating Speed"):
        surface_type = str(row['Surface']).lower()
        Cr = ROLL_RESISTANCE_MAP.get(surface_type, ROLL_RESISTANCE_MAP['unknown'])
        gradient = row['Gradient']

        speed_ms = solve_for_speed_from_power(target_power, gradient, Cr, mass_kg, cda_value)
        simulated_speeds_ms.append(speed_ms)

    df['Simulated_Speed_ms'] = simulated_speeds_ms
    df['Simulated_Speed_kmh'] = df['Simulated_Speed_ms'] * 3.6

    # Calculate simulated time based on the new speed profile
    distance_diff_m = df['Distanz (km)'].diff().fillna(0) * 1000
    segment_time_s = distance_diff_m / df['Simulated_Speed_ms'].where(df['Simulated_Speed_ms'] != 0)
    df['Simulated_Time_s'] = segment_time_s.cumsum().fillna(0)
    
    df['Target_Power_W'] = target_power
    
    # Simulation statistics for metadata
    simulation_stats = {
        'min_simulated_speed_kmh': round(df['Simulated_Speed_kmh'].min(), 1),
        'max_simulated_speed_kmh': round(df['Simulated_Speed_kmh'].max(), 1),
        'mean_simulated_speed_kmh': round(df['Simulated_Speed_kmh'].mean(), 1),
        'total_simulated_time_hours': round(df['Simulated_Time_s'].iloc[-1] / 3600, 2),
        'total_distance_km': round(df['Distanz (km)'].iloc[-1], 2)
    }
    
    metadata['simulation_analysis'] = simulation_stats
    
    # Processing time
    simulation_time = (datetime.now() - simulation_start_time).total_seconds()
    metadata['simulation_processing_time_sec'] = round(simulation_time, 3)
    
    return df

# === MAIN EXECUTION BLOCK ===

def main():
    """Main function to orchestrate the power processing workflow with comprehensive metadata tracking."""
    run_start_time = datetime.now()
    
    print_script_info()
    
    parser = argparse.ArgumentParser(
        description=SCRIPT_DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # --- Mode Selection ---
    parser.add_argument(
        "--target-power", 
        type=int,
        default=None,
        help="Target power in Watts for simulation. If provided, the script runs in 'simulation' mode.\n"
             "If omitted, the script runs in 'analysis' mode and requires speed data in the input."
    )
    
    # --- File Paths ---
    parser.add_argument("--track-csv", required=True, help="Path to track CSV. For analysis, needs speed. For simulation, needs elevation.")
    parser.add_argument("--surface-csv", required=True, help="Path to surface data CSV.")
    parser.add_argument("--output-csv", required=True, help="Path for the output CSV file.")
    
    # --- Physics Parameters ---
    parser.add_argument("--mass", type=float, required=True, help="Total mass (rider + bike + gear) in kg.")
    parser.add_argument("--position", required=True, choices=list(CDA_PARAMS.keys()), help="Rider's aerodynamic position key.")
    
    args = parser.parse_args()

    # Initialize comprehensive metadata tracking
    metadata = {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'timestamp': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'processing_mode': None,
        'success': False,
        'error_message': None,
        'total_runtime_sec': 0.0,
        'data_quality_score': 0.0
    }

    # --- Determine Mode and Validate ---
    is_simulation_mode = args.target_power is not None
    
    print(f"--- {SCRIPT_NAME} v{SCRIPT_VERSION} ---")
    
    try:
        # Processing parameters for metadata
        processing_parameters = {
            'rider_mass_kg': args.mass,
            'aerodynamic_position': args.position,
            'cda_value_m2': CDA_PARAMS[args.position],
            'target_power_w': args.target_power if is_simulation_mode else None,
            'physics_model': 'advanced_cycling_power_model',
            'air_density_kg_m3': RHO,
            'gravity_ms2': G
        }
        
        # Load and prepare data
        df = load_and_merge_data(args.track_csv, args.surface_csv, metadata)
        df = calculate_gradient(df, metadata)
        
        cda_value = CDA_PARAMS[args.position]
        
        # Execute the chosen mode
        if is_simulation_mode:
            df_final = run_speed_simulation(df, args.mass, cda_value, args.target_power, metadata)
            
            # Summary for simulation
            avg_speed = df_final['Simulated_Speed_kmh'].mean()
            total_time_s = df_final['Simulated_Time_s'].iloc[-1]
            total_hours = int(total_time_s // 3600)
            total_minutes = int((total_time_s % 3600) // 60)
            
            print("\n--- Simulation Summary ---")
            print(f"Target Power: {args.target_power} W")
            print(f"Average Simulated Speed: {avg_speed:.1f} km/h")
            print(f"Total Estimated Time: {total_hours}h {total_minutes}min")

        else: # Analysis Mode
            df_final = run_power_analysis(df, args.mass, cda_value, metadata)
            
            # Summary for analysis
            avg_power = df_final['Power_W'].mean()
            max_power = df_final['Power_W'].max()
            
            print("\n--- Analysis Summary ---")
            print(f"Average Power: {avg_power:.1f} W")
            print(f"Max Power: {max_power:.1f} W")

        # Calculate data quality score
        quality_factors = []
        
        # Merge success contributes 30%
        merge_success = metadata.get('merge_success_rate', 0)
        quality_factors.append((merge_success / 100) * 30)
        
        # Speed correction rate (lower is better) contributes 25%
        if 'speed_validation' in metadata:
            correction_rate = metadata['speed_validation'].get('correction_rate_percent', 0)
            speed_quality = max(0, (100 - correction_rate) / 100) * 25
            quality_factors.append(speed_quality)
        else:
            quality_factors.append(25)  # Full points for simulation mode
        
        # Surface diversity contributes 20%
        surface_diversity = min(metadata.get('unique_surfaces', 1), 5) / 5 * 20
        quality_factors.append(surface_diversity)
        
        # Data completeness contributes 25%
        completeness = min(len(df_final), metadata.get('track_points_loaded', 1)) / metadata.get('track_points_loaded', 1) * 25
        quality_factors.append(completeness)
        
        metadata['data_quality_score'] = round(sum(quality_factors), 1)
        metadata['success'] = True
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)

        # Save final result with comprehensive metadata
        output_dir = os.path.dirname(args.output_csv)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Prepare input files list
        input_files = [args.track_csv, args.surface_csv]
        
        # API metadata (none used, but structure maintained)
        api_metadata = {
            'physics_model_used': 'cycling_power_equations',
            'aerodynamic_model': 'fixed_cda_by_position',
            'rolling_resistance_model': 'surface_based_coefficients',
            'numerical_solver': 'bisection_method_30_iterations'
        }
        
        # Additional metadata with all tracking info
        additional_metadata = {
            'total_data_points': len(df_final),
            'processing_quality': 'high' if metadata['data_quality_score'] > 80 else 'medium' if metadata['data_quality_score'] > 60 else 'low',
            'physics_model_version': '2.1.0',
            'speed_validation_performed': 'speed_validation' in metadata,
            'power_smoothing_applied': True,
            'selective_component_smoothing': True
        }
        
        # Merge all metadata sections
        if 'speed_validation' in metadata:
            additional_metadata.update({f'speed_{k}': v for k, v in metadata['speed_validation'].items()})
        if 'power_analysis' in metadata:
            additional_metadata.update({f'power_{k}': v for k, v in metadata['power_analysis'].items()})
        if 'simulation_analysis' in metadata:
            additional_metadata.update({f'simulation_{k}': v for k, v in metadata['simulation_analysis'].items()})
        if 'gradient_stats' in metadata:
            additional_metadata.update({f'gradient_{k}': v for k, v in metadata['gradient_stats'].items()})
        
        # Add surface distribution info
        if 'surface_distribution' in metadata:
            for surface, percentage in metadata['surface_distribution'].items():
                additional_metadata[f'surface_{surface}_percent'] = percentage
        
        try:
            if METADATA_SYSTEM_AVAILABLE:
                write_csv_with_metadata(
                    dataframe=df_final,
                    output_path=args.output_csv,
                    script_name=SCRIPT_NAME,
                    script_version=SCRIPT_VERSION,
                    input_files=input_files,
                    processing_parameters=processing_parameters,
                    api_metadata=api_metadata,
                    additional_metadata=additional_metadata,
                    float_format='%.3f'
                )
                print(f"\n[SUCCESS] Processing complete with metadata. Output saved to: {args.output_csv}")
            else:
                # Fallback to standard CSV
                df_final.to_csv(args.output_csv, index=False, float_format='%.3f')
                print(f"\n[SUCCESS] Processing complete (no metadata). Output saved to: {args.output_csv}")
                
        except Exception as e:
            print(f"[ERROR] Failed to save with metadata: {e}")
            # Emergency fallback
            df_final.to_csv(args.output_csv, index=False, float_format='%.3f')
            print(f"[FALLBACK] Basic CSV saved to: {args.output_csv}")
        
        # Print comprehensive summary
        print("\n" + "="*60)
        print("POWER PROCESSING SUMMARY")
        print("="*60)
        processing_mode = metadata.get('processing_mode', 'unknown')
        print(f"Mode: {processing_mode.upper() if processing_mode else 'UNKNOWN'}")
        print(f"Data Quality Score: {metadata['data_quality_score']}/100")
        print(f"Total Runtime: {metadata['total_runtime_sec']}s")
        print(f"Track Points: {metadata.get('track_points_loaded', 0)}")
        print(f"Surface Merge Rate: {metadata.get('merge_success_rate', 0)}%")
        
        if is_simulation_mode:
            sim_stats = metadata.get('simulation_analysis', {})
            print(f"Target Power: {args.target_power}W")
            print(f"Avg Simulated Speed: {sim_stats.get('mean_simulated_speed_kmh', 0):.1f} km/h")
            print(f"Total Time: {sim_stats.get('total_simulated_time_hours', 0):.1f}h")
        else:
            power_stats = metadata.get('power_analysis', {})
            speed_stats = metadata.get('speed_validation', {})
            print(f"Avg Power: {power_stats.get('mean_power_w', 0):.1f}W")
            print(f"Max Power: {power_stats.get('max_power_w', 0):.1f}W")
            print(f"Speed Corrections: {speed_stats.get('corrections_made', 0)} ({speed_stats.get('correction_rate_percent', 0):.1f}%)")
        
        print(f"Surface Types: {metadata.get('unique_surfaces', 0)}")
        print("="*60)

    except FileNotFoundError as e:
        metadata['success'] = False
        metadata['error_message'] = f"Input file not found: {e}"
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[ERROR] Input file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        metadata['success'] = False
        metadata['error_message'] = f"Processing error: {str(e)}"
        metadata['total_runtime_sec'] = round((datetime.now() - run_start_time).total_seconds(), 3)
        print(f"[ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()