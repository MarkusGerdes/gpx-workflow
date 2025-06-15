#!/usr/bin/env python3
"""
Power Analysis Summary - Erstellt schriftliche Zusammenfassung der Power-Auswertung
"""

import pandas as pd
import numpy as np
from datetime import timedelta

def analyze_power_data():
    """Erstellt eine detaillierte schriftliche Power-Auswertung."""
    
    power_csv = "output/10b_Rampendruck_und_toskanische_Hoehenmeter_power_data.csv"
    
    try:
        print("=== POWER ANALYSIS SUMMARY ===")
        
        # Lade Power-Daten
        df = pd.read_csv(power_csv, comment='#')
        
        if 'Power_W' not in df.columns:
            print("Error: No Power_W column found in data")
            return
        
        power = df['Power_W']
        
        # GRUNDSTATISTIKEN
        print(f"\\n--- GRUNDSTATISTIKEN ---")
        print(f"Durchschnittliche Leistung: {power.mean():.1f} W")
        print(f"Maximale Leistung: {power.max():.1f} W")
        print(f"Minimale Leistung: {power.min():.1f} W")
        print(f"Mediane Leistung: {power.median():.1f} W")
        print(f"Standardabweichung: {power.std():.1f} W")
        
        # PERCENTILE
        print(f"\\n--- LEISTUNGSVERTEILUNG ---")
        print(f"25. Percentile: {power.quantile(0.25):.1f} W")
        print(f"75. Percentile: {power.quantile(0.75):.1f} W")
        print(f"90. Percentile: {power.quantile(0.90):.1f} W")
        print(f"95. Percentile: {power.quantile(0.95):.1f} W")
        print(f"99. Percentile: {power.quantile(0.99):.1f} W")
        
        # POWER-ZONEN ANALYSE (basierend auf typischen Radsport-Zonen)
        print(f"\\n--- POWER ZONEN VERTEILUNG ---")
        
        # Definiere Zonen basierend auf den Daten (adaptiv)
        max_power = power.max()
        
        # Zonen-Definitionen (adaptiv basierend auf max Power)
        zones = {
            'Z1 - Aktive Regeneration': (0, max_power * 0.15),
            'Z2 - Ausdauer': (max_power * 0.15, max_power * 0.25),
            'Z3 - Tempo': (max_power * 0.25, max_power * 0.35),
            'Z4 - Schwelle': (max_power * 0.35, max_power * 0.45),
            'Z5 - VO2Max': (max_power * 0.45, max_power * 0.55),
            'Z6 - Anaerob': (max_power * 0.55, max_power * 0.70),
            'Z7 - Neuromuskulär': (max_power * 0.70, max_power)
        }
        
        total_points = len(power)
        
        for zone_name, (min_w, max_w) in zones.items():
            zone_mask = (power >= min_w) & (power < max_w)
            zone_count = zone_mask.sum()
            zone_percentage = (zone_count / total_points) * 100
            
            # Berechne Zeit in Zone (approximiert)
            if 'TimeDelta (s)' in df.columns:
                zone_time_s = df.loc[zone_mask, 'TimeDelta (s)'].sum()
                zone_time = str(timedelta(seconds=int(zone_time_s)))
            else:
                # Schätze 5s pro GPS-Punkt
                zone_time_s = zone_count * 5
                zone_time = str(timedelta(seconds=int(zone_time_s)))
            
            print(f"{zone_name:20} {min_w:3.0f}-{max_w:3.0f}W  {zone_time:>8}  {zone_percentage:5.1f}%")
        
        # POWER KOMPONENTEN ANALYSE
        if all(col in df.columns for col in ['Power_Air_W', 'Power_Roll_W', 'Power_Climb_W']):
            print(f"\\n--- POWER KOMPONENTEN ---")
            air_avg = df['Power_Air_W'].mean()
            roll_avg = df['Power_Roll_W'].mean()
            climb_avg = df['Power_Climb_W'].mean()
            
            total_avg = air_avg + roll_avg + climb_avg
            
            print(f"Luftwiderstand:   {air_avg:6.1f} W ({air_avg/total_avg*100:4.1f}%)")
            print(f"Rollwiderstand:   {roll_avg:6.1f} W ({roll_avg/total_avg*100:4.1f}%)")
            print(f"Bergauffahrt:     {climb_avg:6.1f} W ({climb_avg/total_avg*100:4.1f}%)")
            print(f"Gesamt:           {total_avg:6.1f} W")
        
        # STRECKEN-INFORMATION
        if 'Distanz (km)' in df.columns:
            total_distance = df['Distanz (km)'].max()
            print(f"\\n--- STRECKEN-DATEN ---")
            print(f"Gesamtdistanz: {total_distance:.1f} km")
            
            if 'TimeDelta (s)' in df.columns:
                total_time_s = df['TimeDelta (s)'].sum()
                total_time = str(timedelta(seconds=int(total_time_s)))
                avg_speed = total_distance / (total_time_s / 3600) if total_time_s > 0 else 0
                print(f"Gesamtzeit: {total_time}")
                print(f"Durchschnittsgeschwindigkeit: {avg_speed:.1f} km/h")
            
            # Power per km
            power_per_km = power.mean() * (total_time_s / 3600) / total_distance if 'TimeDelta (s)' in df.columns else 0
            if power_per_km > 0:
                print(f"Durchschnittliche Leistung pro km: {power_per_km:.0f} Wh/km")
        
        # HÖHENDATEN
        if 'Elevation (m)' in df.columns:
            elevation = df['Elevation (m)']
            print(f"\\n--- HÖHENPROFIL ---")
            print(f"Min. Höhe: {elevation.min():.0f} m")
            print(f"Max. Höhe: {elevation.max():.0f} m")
            print(f"Höhendifferenz: {elevation.max() - elevation.min():.0f} m")
            
            if 'Aufstieg (m)' in df.columns:
                total_climb = df['Aufstieg (m)'].sum()
                print(f"Gesamter Aufstieg: {total_climb:.0f} m")
        
        # PERFORMANCE BEWERTUNG
        print(f"\\n--- PERFORMANCE BEWERTUNG ---")
        
        # Klassifizierung basierend auf Durchschnittsleistung
        avg_power = power.mean()
        
        if avg_power < 100:
            performance_level = "Entspannte Fahrt"
        elif avg_power < 150:
            performance_level = "Lockere Ausdauerfahrt"
        elif avg_power < 200:
            performance_level = "Moderate Trainingsfahrt"
        elif avg_power < 250:
            performance_level = "Intensive Trainingsfahrt"
        elif avg_power < 300:
            performance_level = "Harte Trainingsfahrt"
        else:
            performance_level = "Sehr intensive Fahrt"
        
        print(f"Fahrt-Klassifizierung: {performance_level}")
        
        # Variabilitäts-Index (VI = Normalized Power / Average Power)
        # Vereinfachte Berechnung: Standard deviation als Indikator
        variability = power.std() / power.mean() if power.mean() > 0 else 0
        
        if variability < 0.3:
            effort_consistency = "Sehr gleichmäßig"
        elif variability < 0.5:
            effort_consistency = "Gleichmäßig"
        elif variability < 0.7:
            effort_consistency = "Moderat variabel"
        else:
            effort_consistency = "Stark variabel"
        
        print(f"Anstrengung-Konsistenz: {effort_consistency} (Variabilität: {variability:.2f})")
        
        print(f"\\n" + "="*50)
        
    except Exception as e:
        print(f"Error analyzing power data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_power_data()
