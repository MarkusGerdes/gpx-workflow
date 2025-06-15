#!/usr/bin/env python3
"""
Input Data Analyzer - Findet das Root Problem
"""

import pandas as pd
import sys
import os

def analyze_input_data():
    """Analysiert die Power- und Surface-Daten auf Probleme."""
    
    print("=== INPUT DATA ANALYSIS ===")
    
    power_csv = "output/10b_HaBe_Feierabendrunde_von_Finki_aus_power_data.csv"
    surface_csv = "output/4b_HaBe_Feierabendrunde_von_Finki_aus_surface_data.csv"
    
    # Power-Daten analysieren
    print(f"\n1. POWER DATA: {power_csv}")
    if not os.path.exists(power_csv):
        print("❌ Power-Datei nicht gefunden!")
        return False
        
    try:
        df_power = pd.read_csv(power_csv, comment='#', nrows=100)  # Nur erste 100 Zeilen
        print(f"✅ Power-Datei lesbar: {len(df_power)} rows (sample)")
        print(f"Columns: {list(df_power.columns)}")
        
        # Prüfe kritische Spalten
        distance_cols = [col for col in df_power.columns if 'distanz' in col.lower() or 'distance' in col.lower()]
        power_cols = [col for col in df_power.columns if 'power' in col.lower()]
        speed_cols = [col for col in df_power.columns if 'geschwindigkeit' in col.lower() or 'speed' in col.lower()]
        
        print(f"Distance columns: {distance_cols}")
        print(f"Power columns: {power_cols}")
        print(f"Speed columns: {speed_cols}")
        
        if distance_cols:
            dist_col = distance_cols[0]
            print(f"Distance range: {df_power[dist_col].min():.2f} - {df_power[dist_col].max():.2f}")
            
            # Prüfe auf Duplikate
            duplicates = df_power[dist_col].duplicated().sum()
            print(f"Duplicate distances: {duplicates}")
            
            # Prüfe auf NaN
            nan_count = df_power[dist_col].isna().sum()
            print(f"NaN distances: {nan_count}")
            
        if power_cols:
            power_col = power_cols[0]
            print(f"Power range: {df_power[power_col].min():.1f} - {df_power[power_col].max():.1f} W")
            power_nan = df_power[power_col].isna().sum()
            print(f"NaN power values: {power_nan}")
            
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Power-Datei: {e}")
        return False
    
    # Surface-Daten analysieren
    print(f"\n2. SURFACE DATA: {surface_csv}")
    if not os.path.exists(surface_csv):
        print("❌ Surface-Datei nicht gefunden!")
        return False
        
    try:
        df_surface = pd.read_csv(surface_csv, comment='#', nrows=100)
        print(f"✅ Surface-Datei lesbar: {len(df_surface)} rows (sample)")
        print(f"Columns: {list(df_surface.columns)}")
        
        surface_distance_cols = [col for col in df_surface.columns if 'distanz' in col.lower() or 'distance' in col.lower()]
        surface_type_cols = [col for col in df_surface.columns if 'surface' in col.lower()]
        
        print(f"Surface distance columns: {surface_distance_cols}")
        print(f"Surface type columns: {surface_type_cols}")
        
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Surface-Datei: {e}")
        return False
    
    # File-Size Check
    power_size = os.path.getsize(power_csv) / 1024 / 1024  # MB
    surface_size = os.path.getsize(surface_csv) / 1024 / 1024  # MB
    
    print(f"\n3. FILE SIZES:")
    print(f"Power data: {power_size:.2f} MB")
    print(f"Surface data: {surface_size:.2f} MB")
    
    if power_size > 50:
        print("⚠️ WARNING: Power-Datei sehr groß (>50MB)")
    if surface_size > 50:
        print("⚠️ WARNING: Surface-Datei sehr groß (>50MB)")
    
    return True

def create_minimal_test_data():
    """Erstellt minimale Test-Daten falls Input-Daten problematisch sind."""
    
    print("\n=== CREATING MINIMAL TEST DATA ===")
    
    # Minimale Power-Daten
    test_data = {
        'Distanz (km)': [0.0, 1.0, 2.0, 3.0, 4.0],
        'Power_W': [150, 180, 200, 170, 160],
        'Elevation (m)': [100, 120, 140, 130, 110]
    }
    
    df_test = pd.DataFrame(test_data)
    test_power_csv = "output/TEST_minimal_power.csv"
    df_test.to_csv(test_power_csv, index=False)
    
    # Minimale Surface-Daten
    surface_data = {
        'Distanz (km)': [0.0, 1.0, 2.0, 3.0, 4.0],
        'Surface': ['asphalt', 'asphalt', 'gravel', 'asphalt', 'asphalt']
    }
    
    df_surface = pd.DataFrame(surface_data)
    test_surface_csv = "output/TEST_minimal_surface.csv"
    df_surface.to_csv(test_surface_csv, index=False)
    
    print(f"✅ Minimale Test-Daten erstellt:")
    print(f"   Power: {test_power_csv}")
    print(f"   Surface: {test_surface_csv}")
    
    return test_power_csv, test_surface_csv

if __name__ == "__main__":
    success = analyze_input_data()
    
    if not success:
        print("\nInput-Daten haben Probleme. Erstelle minimale Test-Daten...")
        test_power, test_surface = create_minimal_test_data()
        print(f"\nTeste mit minimalen Daten:")
        print(f"python scripts/10c_power_visualization_EMERGENCY.py --power-csv {test_power} --surface-csv {test_surface} --output-html output/MINIMAL_test.html --max-points 5")
