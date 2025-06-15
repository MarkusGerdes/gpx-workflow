#!/usr/bin/env python3
"""
Smart GPS Data Cleaner - Entfernt fehlerhafte GPS-Punkte statt künstlicher Limits
"""

import pandas as pd
import numpy as np

def clean_gps_data():
    """Intelligente GPS-Daten-Bereinigung basierend auf Plausibilitätsprüfungen."""
    
    power_csv = "output/10b_Rampendruck_und_toskanische_Hoehenmeter_power_data.csv"
    cleaned_csv = "output/10b_Rampendruck_und_toskanische_Hoehenmeter_power_data_CLEANED.csv"
    
    try:
        print("=== SMART GPS DATA CLEANING ===")
        
        # Lade Power-Daten
        df = pd.read_csv(power_csv, comment='#')
        print(f"Original data: {len(df)} rows")
        
        # PLAUSIBILITÄTS-CHECKS (keine harten Limits!)
        
        # 1. GESCHWINDIGKEITS-SPRÜNGE erkennen
        speed_col = 'Geschwindigkeit (km/h)'
        if speed_col in df.columns:
            df['speed_diff'] = df[speed_col].diff().abs()
            
            # Unrealistische Beschleunigung: >30 km/h in einem GPS-Punkt
            MAX_SPEED_JUMP = 30  # km/h Sprung zwischen aufeinanderfolgenden Punkten
            speed_jumps = df['speed_diff'] > MAX_SPEED_JUMP
            
            print(f"Unrealistic speed jumps (>{MAX_SPEED_JUMP} km/h): {speed_jumps.sum()}")
            
            # Zeige Beispiele
            if speed_jumps.sum() > 0:
                jump_examples = df[speed_jumps][['Distanz (km)', speed_col, 'speed_diff', 'Power_W']].head()
                print("Speed jump examples:")
                print(jump_examples)
        
        # 2. POWER-SPRÜNGE erkennen  
        df['power_diff'] = df['Power_W'].diff().abs()
        
        # Unrealistische Power-Sprünge: >500W zwischen GPS-Punkten
        MAX_POWER_JUMP = 500  # Watt-Sprung zwischen Punkten
        power_jumps = df['power_diff'] > MAX_POWER_JUMP
        
        print(f"Unrealistic power jumps (>{MAX_POWER_JUMP}W): {power_jumps.sum()}")
        
        # 3. ZEIT-KONSISTENZ prüfen
        if 'TimeDelta (s)' in df.columns:
            time_delta = df['TimeDelta (s)']
            
            # Unrealistische Zeitsprünge (GPS-Lücken)
            time_gaps = time_delta > 30  # >30s Lücke
            time_negative = time_delta <= 0  # Negative/Null Zeit
            
            print(f"Large time gaps (>30s): {time_gaps.sum()}")
            print(f"Negative/zero time deltas: {time_negative.sum()}")
        
        # 4. KOMBINIERTEN GPS-FEHLER-INDEX erstellen
        gps_error_flags = pd.Series(False, index=df.index)
        
        # Markiere problematische Punkte
        if speed_col in df.columns:
            gps_error_flags |= speed_jumps
            
        gps_error_flags |= power_jumps
        
        if 'TimeDelta (s)' in df.columns:
            gps_error_flags |= time_gaps
            gps_error_flags |= time_negative
        
        # 5. KONTEXT-BASIERTE FILTERUNG
        # Einzelne Ausreißer entfernen, aber nicht ganze Bergab-Passagen
        
        # Isolierte Ausreißer finden (umgeben von normalen Werten)
        isolated_errors = pd.Series(False, index=df.index)
        
        for i in range(1, len(df) - 1):
            if gps_error_flags.iloc[i]:
                # Prüfe ob vorheriger und nächster Punkt normal sind
                prev_normal = not gps_error_flags.iloc[i-1]
                next_normal = not gps_error_flags.iloc[i+1]
                
                if prev_normal and next_normal:
                    isolated_errors.iloc[i] = True
        
        print(f"Isolated GPS errors to remove: {isolated_errors.sum()}")
        
        # 6. DATEN BEREINIGEN
        # Entferne nur isolierte Fehler, nicht zusammenhängende Segmente
        df_cleaned = df[~isolated_errors].copy()
        
        # Entferne temporäre Hilfsspalten
        df_cleaned = df_cleaned.drop(columns=['speed_diff', 'power_diff'], errors='ignore')
        
        print(f"Removed {len(df) - len(df_cleaned)} GPS points ({(len(df) - len(df_cleaned))/len(df)*100:.1f}%)")
        print(f"Cleaned data: {len(df_cleaned)} rows")
        
        # 7. POWER NEU BERECHNEN für die bereinigten Daten
        # (Optional: könnte man auch machen, aber die Power-Formeln sind korrekt)
        
        # 8. NEUE STATISTIKEN
        if speed_col in df_cleaned.columns:
            print(f"\\nCleaned speed stats:")
            print(f"  Min: {df_cleaned[speed_col].min():.1f} km/h")
            print(f"  Max: {df_cleaned[speed_col].max():.1f} km/h") 
            print(f"  Mean: {df_cleaned[speed_col].mean():.1f} km/h")
            print(f"  95th percentile: {df_cleaned[speed_col].quantile(0.95):.1f} km/h")
        
        print(f"\\nCleaned power stats:")
        print(f"  Min: {df_cleaned['Power_W'].min():.1f}W")
        print(f"  Max: {df_cleaned['Power_W'].max():.1f}W")
        print(f"  Mean: {df_cleaned['Power_W'].mean():.1f}W") 
        print(f"  95th percentile: {df_cleaned['Power_W'].quantile(0.95):.1f}W")
        
        # 9. DETAILLIERTE ANALYSE der entfernten Punkte
        if isolated_errors.sum() > 0:
            removed_points = df[isolated_errors]
            print(f"\\nRemoved points analysis:")
            print(f"  Speed range: {removed_points[speed_col].min():.1f} - {removed_points[speed_col].max():.1f} km/h")
            print(f"  Power range: {removed_points['Power_W'].min():.1f} - {removed_points['Power_W'].max():.1f}W")
        
        # Speichere bereinigte Daten
        df_cleaned.to_csv(cleaned_csv, index=False)
        print(f"\\n[SUCCESS] Cleaned GPS data saved: {cleaned_csv}")
        
        return cleaned_csv
        
    except Exception as e:
        print(f"Error cleaning GPS data: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    cleaned_file = clean_gps_data()
    if cleaned_file:
        print(f"\\nNow use the cleaned file for visualization:")
        print(f"python scripts/10c_power_visualization.py \\\\")
        print(f"  --power-csv {cleaned_file} \\\\")
        print(f"  --surface-csv output/4b_Rampendruck_und_toskanische_Hoehenmeter_surface_data.csv \\\\")
        print(f"  --output-html output/CLEANED_power_viz.html \\\\")
        print(f"  --max-points 1000")
