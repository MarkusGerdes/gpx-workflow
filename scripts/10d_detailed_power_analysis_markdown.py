#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10d_detailed_power_analysis_markdown.py
----------------------------------------
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

def load_config(config_path="config.yaml"):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[WARNING] Could not load config: {e}")
        return {}

def get_rider_position_info(config):
    """Extract rider position information from config."""
    power_config = config.get('power_estimation', {})
    position_key = power_config.get('rider_position_cda_key', 'unknown')
    
    # Standard cycling positions and their aerodynamic properties
    positions = {
        'upright': {'name': 'Aufrecht (Stadtrad)', 'cda': 0.6, 'description': 'Entspannte Stadtposition'},
        'touring': {'name': 'Touren (Trekking)', 'cda': 0.4, 'description': 'Komfortable Tourenposition'},
        'road_hoods': {'name': 'Rennrad (Hauben)', 'cda': 0.35, 'description': 'Standard Rennradposition auf den Hauben'},
        'road_drops': {'name': 'Rennrad (Unterlenker)', 'cda': 0.3, 'description': 'Aerodynamische Position im Unterlenker'},
        'gravel_hoods': {'name': 'Gravel (Hauben)', 'cda': 0.37, 'description': 'Gravel-Bike Position auf den Hauben'},
        'mtb': {'name': 'Mountainbike', 'cda': 0.45, 'description': 'Aufrechte MTB-Position'},
        'tt_aero': {'name': 'Zeitfahren (Aero)', 'cda': 0.25, 'description': 'Voll-aerodynamische Zeitfahrposition'},
        'unknown': {'name': 'Unbekannt', 'cda': 0.35, 'description': 'Standard-Annahme'}
    }
    
    return positions.get(position_key, positions['unknown'])

def analyze_component_peaks(df):
    """Find peak power events for each component and their context."""
    
    components = {
        'Power_Air_W': 'Luftwiderstand',
        'Power_Roll_W': 'Rollwiderstand', 
        'Power_Climb_W': 'Steigungswiderstand'
    }
    
    peak_analysis = {}
    
    for col, name in components.items():
        if col not in df.columns:
            continue
            
        # Find peak power event
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
    
    # Power zones based on FTP
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
    power_curve = {}\n    durations = [5, 10, 20, 30, 60, 300, 600, 1200, 3600]\n    \n    for duration in durations:\n        if len(power_data) >= duration:\n            rolling_avg = power_data.rolling(window=duration, min_periods=duration).mean()\n            best_effort = rolling_avg.max()\n            power_curve[f"Best {duration}s"] = round(best_effort, 1) if not pd.isna(best_effort) else 0\n    \n    return stats, power_curve\n\ndef analyze_power_components(df):\n    \"\"\"Analyze power components breakdown.\"\"\"\n    \n    components = ['Power_Air_W', 'Power_Roll_W', 'Power_Climb_W']\n    available_components = [col for col in components if col in df.columns]\n    \n    if not available_components:\n        return None\n    \n    component_stats = {}\n    total_power = df['Power_W'].sum()\n    \n    for component in available_components:\n        component_data = df[component].dropna()\n        if len(component_data) > 0:\n            component_sum = component_data.sum()\n            component_avg = component_data.mean()\n            percentage = (component_sum / total_power) * 100 if total_power > 0 else 0\n            \n            clean_name = component.replace('Power_', '').replace('_W', '')\n            \n            component_stats[clean_name] = {\n                \"Average (W)\": round(component_avg, 1),\n                \"Total (Wh)\": round(component_sum / 3600, 1),\n                \"Percentage\": round(percentage, 1)\n            }\n    \n    return component_stats\n\ndef calculate_performance_metrics(df, rider_weight_kg=None):\n    \"\"\"Calculate performance metrics.\"\"\"\n    \n    if 'Power_W' not in df.columns:\n        return None\n    \n    power_data = df['Power_W'].dropna()\n    metrics = {}\n    \n    metrics[\"Average Power\"] = f\"{power_data.mean():.1f} W\"\n    metrics[\"Max Power\"] = f\"{power_data.max():.1f} W\"\n    \n    if rider_weight_kg:\n        avg_watts_per_kg = power_data.mean() / rider_weight_kg\n        max_watts_per_kg = power_data.max() / rider_weight_kg\n        metrics[\"Avg W/kg\"] = f\"{avg_watts_per_kg:.2f} W/kg\"\n        metrics[\"Max W/kg\"] = f\"{max_watts_per_kg:.2f} W/kg\"\n    \n    if 'Geschwindigkeit (km/h)' in df.columns:\n        speed_data = df['Geschwindigkeit (km/h)'].dropna()\n        if len(speed_data) == len(power_data):\n            avg_speed = speed_data.mean()\n            avg_power = power_data.mean()\n            efficiency = avg_power / avg_speed if avg_speed > 0 else 0\n            metrics[\"Power Efficiency\"] = f\"{efficiency:.1f} W per km/h\"\n            metrics[\"Average Speed\"] = f\"{avg_speed:.1f} km/h\"\n    \n    duration_hours = len(power_data) / 3600\n    total_energy_kj = (power_data.sum() / 1000)\n    avg_energy_rate = total_energy_kj / duration_hours if duration_hours > 0 else 0\n    \n    metrics[\"Total Energy\"] = f\"{total_energy_kj:.1f} kJ\"\n    metrics[\"Energy Rate\"] = f\"{avg_energy_rate:.1f} kJ/h\"\n    \n    if len(power_data) > 30:\n        rolling_30s = power_data.rolling(window=30, min_periods=30).mean()\n        fourth_power = rolling_30s ** 4\n        avg_fourth_power = fourth_power.mean()\n        normalized_power = avg_fourth_power ** 0.25\n        metrics[\"Normalized Power\"] = f\"{normalized_power:.1f} W\"\n    \n    return metrics\n\ndef generate_markdown_report(power_csv, config_path=\"config.yaml\", output_path=None):\n    \"\"\"Generate comprehensive Markdown power analysis report.\"\"\"\n    \n    # Load configuration\n    config = load_config(config_path)\n    power_config = config.get('power_estimation', {})\n    analysis_config = config.get('power_analysis', {})\n    \n    # Extract parameters\n    rider_weight_kg = power_config.get('rider_weight_kg', 75)\n    total_mass_kg = power_config.get('total_mass_kg', 85)\n    ftp_watts = analysis_config.get('ftp_watts', None)\n    \n    # Get rider position info\n    position_info = get_rider_position_info(config)\n    \n    # Load data\n    try:\n        df = pd.read_csv(power_csv, comment='#', encoding='utf-8')\n    except UnicodeDecodeError:\n        df = pd.read_csv(power_csv, comment='#', encoding='latin-1')\n    except Exception as e:\n        print(f\"[ERROR] Could not load {power_csv}: {e}\")\n        return\n    \n    # Generate output filename\n    if output_path is None:\n        base_name = Path(power_csv).stem.replace('10b_', '').replace('_power_data', '')\n        output_path = f\"output/10d_{base_name}_detailed_power_analysis.md\"\n    \n    # Start building markdown content\n    md_content = []\n    \n    # Header\n    md_content.append(\"# 🚴‍♂️ Detaillierte Power-Analyse\")\n    md_content.append(\"\")\n    md_content.append(f\"**Datei:** `{Path(power_csv).name}`  \")\n    md_content.append(f\"**Datenpunkte:** {len(df):,}  \")\n    md_content.append(f\"**Generiert:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\")\n    md_content.append(\"\")\n    \n    # Rider Configuration\n    md_content.append(\"## ⚙️ Fahrer-Konfiguration\")\n    md_content.append(\"\")\n    md_content.append(\"| Parameter | Wert | Beschreibung |\")\n    md_content.append(\"|-----------|------|--------------|\")\n    md_content.append(f\"| **Fahrergewicht** | {rider_weight_kg} kg | Für W/kg Berechnungen |\")\n    md_content.append(f\"| **Gesamtmasse** | {total_mass_kg} kg | Fahrer + Ausrüstung |\")\n    md_content.append(f\"| **Position** | {position_info['name']} | {position_info['description']} |\")\n    md_content.append(f\"| **CdA-Wert** | {position_info['cda']} m² | Luftwiderstandsfläche |\")\n    if ftp_watts:\n        md_content.append(f\"| **FTP** | {ftp_watts} W | Functional Threshold Power |\")\n    md_content.append(\"\")\n    \n    # Power Statistics\n    stats, power_curve = calculate_power_statistics(df)\n    if stats:\n        md_content.append(\"## 📊 Grundstatistiken\")\n        md_content.append(\"\")\n        md_content.append(\"| Metrik | Wert |\")\n        md_content.append(\"|--------|------|\")\n        \n        for key, value in stats.items():\n            md_content.append(f\"| **{key}** | {value} |\")\n        md_content.append(\"\")\n        \n        # Power Curve\n        md_content.append(\"### ⚡ Power Curve (Best Efforts)\")\n        md_content.append(\"\")\n        md_content.append(\"| Dauer | Beste Leistung |\")\n        md_content.append(\"|-------|----------------|\")\n        for duration, power in power_curve.items():\n            md_content.append(f\"| **{duration}** | {power} W |\")\n        md_content.append(\"\")\n    \n    # Power Zones\n    zone_df, estimated_ftp = analyze_power_zones(df, ftp_watts)\n    if zone_df is not None:\n        md_content.append(\"## 🎯 Power-Zonen-Verteilung\")\n        md_content.append(\"\")\n        md_content.append(f\"**FTP (Functional Threshold Power):** {estimated_ftp} W  \")\n        md_content.append(f\"*{'Geschätzt' if ftp_watts is None else 'Konfiguriert'}*\")\n        md_content.append(\"\")\n        \n        md_content.append(\"| Zone | Name | Bereich | Zeit (min) | Prozent | Ø Leistung | Max Leistung |\")\n        md_content.append(\"|------|------|---------|------------|---------|------------|--------------|\")\n        \n        for _, row in zone_df.iterrows():\n            md_content.append(f\"| **{row['Zone']}** | {row['Name']} | {row['Range']} | {row['Time (min)']} | {row['Percentage']}% | {row['Avg Power']} W | {row['Max Power']} W |\")\n        md_content.append(\"\")\n    \n    # Power Components\n    components = analyze_power_components(df)\n    if components:\n        md_content.append(\"## ⚡ Power-Komponenten-Breakdown\")\n        md_content.append(\"\")\n        \n        md_content.append(\"| Komponente | Durchschnitt | Gesamt | Anteil |\")\n        md_content.append(\"|------------|--------------|--------|--------|\")\n        \n        for component, data in components.items():\n            component_names = {\n                'Air': '🌬️ Luftwiderstand',\n                'Roll': '⚙️ Rollwiderstand', \n                'Climb': '⛰️ Steigungswiderstand'\n            }\n            display_name = component_names.get(component, component)\n            \n            md_content.append(f\"| **{display_name}** | {data['Average (W)']} W | {data['Total (Wh)']} Wh | {data['Percentage']}% |\")\n        md_content.append(\"\")\n        \n        # Component Peaks Analysis\n        peak_analysis = analyze_component_peaks(df)\n        if peak_analysis:\n            md_content.append(\"### 🏔️ Peak-Analyse der Komponenten\")\n            md_content.append(\"\")\n            \n            for component_name, peak_info in peak_analysis.items():\n                emoji_map = {\n                    'Luftwiderstand': '🌬️',\n                    'Rollwiderstand': '⚙️',\n                    'Steigungswiderstand': '⛰️'\n                }\n                emoji = emoji_map.get(component_name, '⚡')\n                \n                md_content.append(f\"#### {emoji} {component_name} Peak\")\n                md_content.append(\"\")\n                md_content.append(\"| Parameter | Wert |\")\n                md_content.append(\"|-----------|------|\")\n                md_content.append(f\"| **Peak Power** | {peak_info['power']:.1f} W ({peak_info['percentage_of_total']:.1f}% der Gesamtleistung) |\")\n                md_content.append(f\"| **Distanz** | {peak_info['distance']:.2f} km |\")\n                md_content.append(f\"| **Geschwindigkeit** | {peak_info['speed']:.1f} km/h |\")\n                md_content.append(f\"| **Steigung** | {peak_info['gradient']:.1f}% |\")\n                md_content.append(f\"| **Untergrund** | {peak_info['surface']} |\")\n                md_content.append(f\"| **Höhe** | {peak_info['elevation']:.0f} m |\")\n                md_content.append(f\"| **Gesamtleistung** | {peak_info['total_power']:.1f} W |\")\n                md_content.append(\"\")\n                \n                # Other components at peak moment\n                if peak_info['other_components']:\n                    md_content.append(\"**Andere Komponenten zum Peak-Zeitpunkt:**\")\n                    md_content.append(\"\")\n                    for other_name, other_data in peak_info['other_components'].items():\n                        md_content.append(f\"- **{other_name}:** {other_data['power']:.1f} W ({other_data['percentage']:.1f}%)\")\n                    md_content.append(\"\")\n    \n    # Performance Metrics\n    performance = calculate_performance_metrics(df, rider_weight_kg)\n    if performance:\n        md_content.append(\"## 🏆 Performance-Bewertung\")\n        md_content.append(\"\")\n        md_content.append(\"| Metrik | Wert |\")\n        md_content.append(\"|--------|------|\")\n        \n        for metric, value in performance.items():\n            md_content.append(f\"| **{metric}** | {value} |\")\n        md_content.append(\"\")\n    \n    # Additional Insights\n    md_content.append(\"## 💡 Zusätzliche Insights\")\n    md_content.append(\"\")\n    md_content.append(\"| Parameter | Wert |\")\n    md_content.append(\"|-----------|------|\")\n    \n    if 'Elevation (m)' in df.columns:\n        elevation_gain = df['Elevation (m)'].diff().where(df['Elevation (m)'].diff() > 0).sum()\n        md_content.append(f\"| **Gesamter Höhengewinn** | {elevation_gain:.0f} m |\")\n    \n    if 'Distanz (km)' in df.columns:\n        total_distance = df['Distanz (km)'].max()\n        md_content.append(f\"| **Gesamtdistanz** | {total_distance:.1f} km |\")\n    \n    if 'Power_W' in df.columns:\n        variability_index = df['Power_W'].std() / df['Power_W'].mean()\n        md_content.append(f\"| **Power Variabilität Index** | {variability_index:.2f} |\")\n    \n    md_content.append(\"\")\n    md_content.append(\"---\")\n    md_content.append(\"\")\n    md_content.append(\"*Generiert mit dem GPX Workflow Power-Analyse-System*\")\n    \n    # Write to file\n    try:\n        with open(output_path, 'w', encoding='utf-8') as f:\n            f.write('\\n'.join(md_content))\n        print(f\"[OK] Markdown report generated: {output_path}\")\n    except Exception as e:\n        print(f\"[ERROR] Could not write report: {e}\")\n\ndef main():\n    \"\"\"Main function with command line interface.\"\"\"\n    parser = argparse.ArgumentParser(\n        description=\"Enhanced Power Analysis with Markdown Output\",\n        formatter_class=argparse.RawTextHelpFormatter\n    )\n    \n    parser.add_argument(\"--power-csv\", required=True,\n                       help=\"Path to power data CSV from 10b_power_processing.py\")\n    parser.add_argument(\"--config\", default=\"config.yaml\",\n                       help=\"Path to configuration file\")\n    parser.add_argument(\"--output\", default=None,\n                       help=\"Output path for Markdown report\")\n    \n    args = parser.parse_args()\n    \n    generate_markdown_report(args.power_csv, args.config, args.output)\n\nif __name__ == \"__main__\":\n    main()\n