#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10d_detailed_power_analysis.py v2.0.0
--------------------------------------
Enhanced power analysis with Markdown output, peak analysis, and comprehensive metrics.
Includes rider configuration, position data, and detailed component peak analysis.
"""

import pandas as pd
import numpy as np
import argparse
import sys
import yaml
from datetime import timedelta
from pathlib import Path

def analyze_component_peaks(df):
    """Analyze peaks for each power component with detailed context."""
    components = {
        'Power_Air_W': 'Luftwiderstand',
        'Power_Roll_W': 'Rollwiderstand', 
        'Power_Climb_W': 'Steigungswiderstand'
    }
    
    peak_analysis = {}
    
    for col, name in components.items():
        if col not in df.columns:
            continue
            
        peak_idx = df[col].idxmax()
        if pd.isna(peak_idx):
            continue
            
        peak_row = df.loc[peak_idx]
        
        # Extract contextual information
        peak_info = {
            'power': peak_row[col],
            'total_power': peak_row.get('Power_W', 0),
            'speed': peak_row.get('Geschwindigkeit (km/h)', 0),
            'gradient': peak_row.get('Gradient (%)', 0),
            'surface': peak_row.get('surface', 'unknown'),
            'distance': peak_row.get('Distanz (km)', 0),
            'elevation': peak_row.get('Elevation (m)', 0)
        }
        
        # Calculate energy ratios at peak
        total_at_peak = peak_row.get('Power_W', 1)
        peak_info['percentage_of_total'] = (peak_info['power'] / total_at_peak * 100) if total_at_peak > 0 else 0
        
        # Calculate other components at this moment
        other_components = {}
        for other_col, other_name in components.items():
            if other_col != col and other_col in df.columns:
                other_power = peak_row.get(other_col, 0)
                other_components[other_name] = {
                    'power': other_power,
                    'percentage': (other_power / total_at_peak * 100) if total_at_peak > 0 else 0
                }
        
        peak_info['other_components'] = other_components
        peak_analysis[name] = peak_info
    
    return peak_analysis

def analyze_power_zones(df, ftp_watts=None):
    """Analyze power distribution across training zones."""
    
    if 'Power_W' not in df.columns:
        print("[ERROR] No Power_W column found for zone analysis")
        return None, None
    
    power_data = df['Power_W'].dropna()
    
    # Estimate FTP if not provided
    if ftp_watts is None:
        high_power_segments = power_data[power_data > 200]
        if len(high_power_segments) > 0:
            ftp_watts = int(high_power_segments.quantile(0.85))
        else:
            ftp_watts = int(power_data.quantile(0.75))
    
    print(f"[Info] Using FTP: {ftp_watts}W ({'estimated' if ftp_watts is None else 'provided'})")
    
    # Power zones based on FTP (standard cycling zones)
    zones = {
        1: {"name": "Active Recovery", "min": 0, "max": int(ftp_watts * 0.55)},
        2: {"name": "Endurance", "min": int(ftp_watts * 0.56), "max": int(ftp_watts * 0.75)},
        3: {"name": "Tempo", "min": int(ftp_watts * 0.76), "max": int(ftp_watts * 0.90)},
        4: {"name": "Lactate Threshold", "min": int(ftp_watts * 0.91), "max": int(ftp_watts * 1.05)},
        5: {"name": "VO2 Max", "min": int(ftp_watts * 1.06), "max": int(ftp_watts * 1.20)},
        6: {"name": "Anaerobic", "min": int(ftp_watts * 1.21), "max": int(ftp_watts * 1.50)},
        7: {"name": "Neuromuscular Power", "min": int(ftp_watts * 1.51), "max": 9999}
    }
    
    zone_analysis = []
    total_time = len(power_data)
    
    for zone_num, zone_info in zones.items():
        zone_mask = (power_data >= zone_info["min"]) & (power_data <= zone_info["max"])
        time_in_zone = zone_mask.sum()
        percentage = (time_in_zone / total_time) * 100
        
        if time_in_zone > 0:
            avg_power_in_zone = power_data[zone_mask].mean()
            max_power_in_zone = power_data[zone_mask].max()
        else:
            avg_power_in_zone = 0
            max_power_in_zone = 0
        
        zone_analysis.append({
            "Zone": zone_num,
            "Name": zone_info["name"],
            "Range": f"{zone_info['min']}-{zone_info['max']}W",
            "Time (min)": round(time_in_zone / 60, 1),
            "Percentage": round(percentage, 1),
            "Avg Power": round(avg_power_in_zone, 0),
            "Max Power": round(max_power_in_zone, 0)
        })
    
    return pd.DataFrame(zone_analysis), ftp_watts

def calculate_power_statistics(df):
    """Calculate comprehensive power statistics."""
    
    if 'Power_W' not in df.columns:
        return None, None
    
    power_data = df['Power_W'].dropna()
    
    stats = {
        "Total Data Points": len(power_data),
        "Duration (min)": round(len(power_data) / 60, 1),
        "Average Power": round(power_data.mean(), 1),
        "Median Power": round(power_data.median(), 1),
        "Maximum Power": round(power_data.max(), 1),
        "Minimum Power": round(power_data.min(), 1),
        "Standard Deviation": round(power_data.std(), 1),
        "95th Percentile": round(power_data.quantile(0.95), 1),
        "75th Percentile": round(power_data.quantile(0.75), 1),
        "25th Percentile": round(power_data.quantile(0.25), 1),
    }
    
    # Power curve analysis
    power_curve = {}
    durations = [5, 10, 20, 30, 60, 300, 600, 1200, 3600]
    
    for duration in durations:
        if len(power_data) >= duration:
            rolling_avg = power_data.rolling(window=duration, min_periods=duration).mean()
            best_effort = rolling_avg.max()
            power_curve[f"Best {duration}s"] = round(best_effort, 1) if not pd.isna(best_effort) else 0
    
    return stats, power_curve

def analyze_power_components(df):
    """Analyze power components breakdown."""
    
    components = ['Power_Air_W', 'Power_Roll_W', 'Power_Climb_W']
    available_components = [col for col in components if col in df.columns]
    
    if not available_components:
        return None
    
    component_stats = {}
    total_power = df['Power_W'].sum()
    
    for component in available_components:
        component_data = df[component].dropna()
        if len(component_data) > 0:
            component_sum = component_data.sum()
            component_avg = component_data.mean()
            percentage = (component_sum / total_power) * 100 if total_power > 0 else 0
            
            clean_name = component.replace('Power_', '').replace('_W', '')
            
            component_stats[clean_name] = {
                "Average (W)": round(component_avg, 1),
                "Total (Wh)": round(component_sum / 3600, 1),
                "Percentage": round(percentage, 1)
            }
    
    return component_stats

def calculate_performance_metrics(df, rider_weight_kg=None):
    """Calculate performance metrics."""
    
    if 'Power_W' not in df.columns:
        return None
    
    power_data = df['Power_W'].dropna()
    metrics = {}
    
    metrics["Average Power"] = f"{power_data.mean():.1f} W"
    metrics["Max Power"] = f"{power_data.max():.1f} W"
    
    if rider_weight_kg:
        avg_watts_per_kg = power_data.mean() / rider_weight_kg
        max_watts_per_kg = power_data.max() / rider_weight_kg
        metrics["Avg W/kg"] = f"{avg_watts_per_kg:.2f} W/kg"
        metrics["Max W/kg"] = f"{max_watts_per_kg:.2f} W/kg"
    
    if 'Geschwindigkeit (km/h)' in df.columns:
        speed_data = df['Geschwindigkeit (km/h)'].dropna()
        if len(speed_data) == len(power_data):
            avg_speed = speed_data.mean()
            avg_power = power_data.mean()
            efficiency = avg_power / avg_speed if avg_speed > 0 else 0
            metrics["Power Efficiency"] = f"{efficiency:.1f} W per km/h"
            metrics["Average Speed"] = f"{avg_speed:.1f} km/h"
    
    duration_hours = len(power_data) / 3600
    total_energy_kj = (power_data.sum() / 1000)
    avg_energy_rate = total_energy_kj / duration_hours if duration_hours > 0 else 0
    
    metrics["Total Energy"] = f"{total_energy_kj:.1f} kJ"
    metrics["Energy Rate"] = f"{avg_energy_rate:.1f} kJ/h"
    
    if len(power_data) > 30:
        rolling_30s = power_data.rolling(window=30, min_periods=30).mean()
        fourth_power = rolling_30s ** 4
        avg_fourth_power = fourth_power.mean()
        normalized_power = avg_fourth_power ** 0.25
        metrics["Normalized Power"] = f"{normalized_power:.1f} W"
    
    return metrics

def generate_markdown_version(power_csv, ftp_watts=None, rider_weight_kg=None):
    """Generate enhanced Markdown version with rider config and peak analysis."""
    
    # Load data
    try:
        df = pd.read_csv(power_csv, comment='#', encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(power_csv, comment='#', encoding='latin-1')
        except Exception as e:
            print(f"[ERROR] Could not load {power_csv}: {e}")
            return
    except Exception as e:
        print(f"[ERROR] Could not load {power_csv}: {e}")
        return
    
    # Generate output filename
    output_path = power_csv.replace('10b_', '10d_').replace('_power_data.csv', '_detailed_power_analysis.md')
    
    # Create markdown content
    md_content = []
    
    # Header
    md_content.append("# 🚴‍♂️ Detaillierte Power-Analyse")
    md_content.append("")
    md_content.append(f"**Datei:** `{Path(power_csv).name}`  ")
    md_content.append(f"**Datenpunkte:** {len(df):,}  ")
    md_content.append(f"**Generiert:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_content.append("")
    
    # Rider Configuration
    md_content.append("## ⚙️ Fahrer-Konfiguration")
    md_content.append("")
    md_content.append("| Parameter | Wert | Beschreibung |")
    md_content.append("|-----------|------|--------------|")
    md_content.append(f"| **Fahrergewicht** | {rider_weight_kg or 75} kg | Für W/kg Berechnungen |")
    md_content.append(f"| **Gesamtmasse** | {(rider_weight_kg or 75) + 10} kg | Fahrer + Ausrüstung |")
    md_content.append(f"| **Position** | Gravel (Hauben) | Gravel-Bike Position auf den Hauben |")
    md_content.append(f"| **CdA-Wert** | 0.37 m² | Luftwiderstandsfläche |")
    if ftp_watts:
        md_content.append(f"| **FTP** | {ftp_watts} W | Functional Threshold Power |")
    md_content.append("")
    
    # Get analysis data
    stats, power_curve = calculate_power_statistics(df)
    zone_df, estimated_ftp = analyze_power_zones(df, ftp_watts)
    components = analyze_power_components(df)
    performance = calculate_performance_metrics(df, rider_weight_kg)
    
    # Basic Statistics
    if stats:
        md_content.append("## 📊 Grundstatistiken")
        md_content.append("")
        md_content.append("| Metrik | Wert |")
        md_content.append("|--------|------|")
        
        for key, value in stats.items():
            md_content.append(f"| **{key}** | {value} |")
        md_content.append("")
        
        # Power Curve
        md_content.append("### ⚡ Power Curve (Best Efforts)")
        md_content.append("")
        md_content.append("| Dauer | Beste Leistung |")
        md_content.append("|-------|----------------|")
        for duration, power in power_curve.items():
            md_content.append(f"| **{duration}** | {power} W |")
        md_content.append("")
    
    # Power Zones
    if zone_df is not None:
        md_content.append("## 🎯 Power-Zonen-Verteilung")
        md_content.append("")
        md_content.append(f"**FTP (Functional Threshold Power):** {estimated_ftp} W  ")
        md_content.append(f"*{'Geschätzt' if ftp_watts is None else 'Konfiguriert'}*")
        md_content.append("")
        
        md_content.append("| Zone | Name | Bereich | Zeit (min) | Prozent | Ø Leistung | Max Leistung |")
        md_content.append("|------|------|---------|------------|---------|------------|--------------|")
        
        for _, row in zone_df.iterrows():
            md_content.append(f"| **{row['Zone']}** | {row['Name']} | {row['Range']} | {row['Time (min)']} | {row['Percentage']}% | {row['Avg Power']} W | {row['Max Power']} W |")
        md_content.append("")
    
    # Power Components Analysis
    if components:
        md_content.append("## ⚡ Power-Komponenten-Breakdown")
        md_content.append("")
        
        md_content.append("| Komponente | Durchschnitt | Gesamt | Anteil |")
        md_content.append("|------------|--------------|--------|--------|")
        
        component_names = {
            'Air': '🌬️ Luftwiderstand',
            'Roll': '⚙️ Rollwiderstand', 
            'Climb': '⛰️ Steigungswiderstand'
        }
        
        for component, data in components.items():
            display_name = component_names.get(component, component)
            md_content.append(f"| **{display_name}** | {data['Average (W)']} W | {data['Total (Wh)']} Wh | {data['Percentage']}% |")
        md_content.append("")
        
        # Enhanced Peak Analysis
        md_content.append("### 🏔️ Peak-Analyse der Komponenten")
        md_content.append("")
        
        # Find component peaks with detailed analysis
        peak_analysis = analyze_component_peaks(df)
        
        for component_key, component_name in component_names.items():
            if f'Power_{component_key}_W' in df.columns:
                col = f'Power_{component_key}_W'
                peak_idx = df[col].idxmax()
                
                if not pd.isna(peak_idx):
                    peak_row = df.loc[peak_idx]
                    emoji = component_name.split()[0]
                    clean_name = component_name.split()[1]
                    
                    md_content.append(f"#### {emoji} {clean_name} Peak")
                    md_content.append("")
                    md_content.append("| Parameter | Wert |")
                    md_content.append("|-----------|------|")
                    
                    peak_power = peak_row[col]
                    total_power = peak_row.get('Power_W', peak_power)
                    percentage = (peak_power / total_power * 100) if total_power > 0 else 0
                    
                    md_content.append(f"| **Peak Power** | {peak_power:.1f} W ({percentage:.1f}% der Gesamtleistung) |")
                    md_content.append(f"| **Distanz** | {peak_row.get('Distanz (km)', 0):.2f} km |")
                    md_content.append(f"| **Geschwindigkeit** | {peak_row.get('Geschwindigkeit (km/h)', 0):.1f} km/h |")
                    md_content.append(f"| **Steigung** | {peak_row.get('Gradient (%)', 0):.1f}% |")
                    md_content.append(f"| **Untergrund** | {peak_row.get('surface', 'unknown')} |")
                    md_content.append(f"| **Höhe** | {peak_row.get('Elevation (m)', 0):.0f} m |")
                    md_content.append(f"| **Gesamtleistung** | {total_power:.1f} W |")
                    md_content.append("")
                    
                    # Other components at peak moment
                    md_content.append("**Andere Komponenten zum Peak-Zeitpunkt:**")
                    md_content.append("")
                    
                    for other_key, other_name in component_names.items():
                        if other_key != component_key and f'Power_{other_key}_W' in df.columns:
                            other_power = peak_row.get(f'Power_{other_key}_W', 0)
                            other_percentage = (other_power / total_power * 100) if total_power > 0 else 0
                            clean_other_name = other_name.split()[1]
                            md_content.append(f"- **{clean_other_name}:** {other_power:.1f} W ({other_percentage:.1f}%)")
                    md_content.append("")
    
    # Performance Metrics
    if performance:
        md_content.append("## 🏆 Performance-Bewertung")
        md_content.append("")
        md_content.append("| Metrik | Wert |")
        md_content.append("|--------|------|")
        
        for metric, value in performance.items():
            md_content.append(f"| **{metric}** | {value} |")
        md_content.append("")
    
    # Additional Insights
    md_content.append("## 💡 Zusätzliche Insights")
    md_content.append("")
    md_content.append("| Parameter | Wert |")
    md_content.append("|-----------|------|")
    
    if 'Elevation (m)' in df.columns:
        elevation_gain = df['Elevation (m)'].diff().where(df['Elevation (m)'].diff() > 0).sum()
        md_content.append(f"| **Gesamter Höhengewinn** | {elevation_gain:.0f} m |")
    
    if 'Distanz (km)' in df.columns:
        total_distance = df['Distanz (km)'].max()
        md_content.append(f"| **Gesamtdistanz** | {total_distance:.1f} km |")
    
    if 'Power_W' in df.columns:
        variability_index = df['Power_W'].std() / df['Power_W'].mean()
        md_content.append(f"| **Power Variabilität Index** | {variability_index:.2f} |")
    
    md_content.append("")
    md_content.append("---")
    md_content.append("")
    md_content.append("*Generiert mit dem GPX Workflow Power-Analyse-System*")
    
    # Write to file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))
        print(f"[OK] Markdown report generated: {output_path}")
    except Exception as e:
        print(f"[ERROR] Could not write Markdown report: {e}")

def print_detailed_analysis(power_csv, ftp_watts=None, rider_weight_kg=None):
    """Generate and print comprehensive power analysis."""
    
    print("="*60)
    print("DETAILED POWER ANALYSIS REPORT")
    print("="*60)
    
    # Load data
    try:
        df = pd.read_csv(power_csv, comment='#', encoding='utf-8')
        print(f"[OK] Loaded data: {len(df)} data points")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(power_csv, comment='#', encoding='latin-1')
            print(f"[OK] Loaded data: {len(df)} data points")
        except Exception as e:
            print(f"[ERROR] Could not load {power_csv}: {e}")
            return
    except Exception as e:
        print(f"[ERROR] Could not load {power_csv}: {e}")
        return
    
    # 1. GRUNDSTATISTIKEN
    print("\n" + "="*40)
    print("GRUNDSTATISTIKEN")
    print("="*40)
    
    stats, power_curve = calculate_power_statistics(df)
    if stats:
        for key, value in stats.items():
            print(f"{key:.<30} {value}")
        
        print(f"\n{'POWER CURVE (Best Efforts)':<30}")
        print("-" * 40)
        for duration, power in power_curve.items():
            print(f"{duration:.<30} {power}W")
    
    # 2. POWER ZONEN VERTEILUNG
    print("\n" + "="*40)
    print("POWER ZONEN VERTEILUNG")
    print("="*40)
    
    zone_df, estimated_ftp = analyze_power_zones(df, ftp_watts)
    if zone_df is not None:
        print(f"FTP (Functional Threshold Power): {estimated_ftp}W\n")
        print(zone_df.to_string(index=False))
    
    # 3. POWER KOMPONENTEN
    print("\n" + "="*40)
    print("POWER KOMPONENTEN BREAKDOWN")
    print("="*40)
    
    components = analyze_power_components(df)
    if components:
        for component, data in components.items():
            print(f"\n{component.upper()}:")
            for metric, value in data.items():
                print(f"  {metric:.<25} {value}")
    else:
        print("Keine Power-Komponenten verfuegbar (Air, Roll, Climb)")
    
    # 4. PERFORMANCE BEWERTUNG
    print("\n" + "="*40)
    print("PERFORMANCE BEWERTUNG")
    print("="*40)
    
    performance = calculate_performance_metrics(df, rider_weight_kg)
    if performance:
        for metric, value in performance.items():
            print(f"{metric:.<30} {value}")
    
    # 5. ZUSAETZLICHE INSIGHTS
    print("\n" + "="*40)
    print("ZUSAETZLICHE INSIGHTS")
    print("="*40)
    
    if 'Elevation (m)' in df.columns:
        elevation_gain = df['Elevation (m)'].diff().where(df['Elevation (m)'].diff() > 0).sum()
        print(f"{'Total Elevation Gain':.<30} {elevation_gain:.0f}m")
    
    if 'Distanz (km)' in df.columns:
        total_distance = df['Distanz (km)'].max()
        print(f"{'Total Distance':.<30} {total_distance:.1f}km")
    
    if 'Power_W' in df.columns:
        variability_index = df['Power_W'].std() / df['Power_W'].mean()
        print(f"{'Power Variability Index':.<30} {variability_index:.2f}")
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Detailed Power Analysis - Comprehensive cycling power statistics",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--power-csv", required=True,
                       help="Path to power data CSV from 10b_power_processing.py")
    parser.add_argument("--ftp", type=int, default=None,
                       help="Functional Threshold Power in Watts (estimated if not provided)")
    parser.add_argument("--rider-weight", type=float, default=None,
                       help="Rider weight in kg for W/kg calculations")
    parser.add_argument("--markdown", action='store_true',
                       help="Also generate Markdown version of the report")
    
    args = parser.parse_args()
    
    # Generate text analysis
    print_detailed_analysis(args.power_csv, args.ftp, args.rider_weight)
    
    # Generate markdown version if requested (or by default)
    if args.markdown or True:  # Always generate markdown for now
        generate_markdown_version(args.power_csv, args.ftp, args.rider_weight)

if __name__ == "__main__":
    main()
