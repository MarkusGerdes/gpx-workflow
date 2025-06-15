#!/usr/bin/env python3
"""
Power Data Analyzer - Findet unrealistische Power-Werte
"""

import pandas as pd
import numpy as np

def analyze_power_data():
    """Analysiert die Power-Daten auf unrealistische Werte."""
    
    power_csv = "output/10b_Rampendruck_und_toskanische_Hoehenmeter_power_data.csv"
    
    try:
        print("=== POWER DATA ANALYSIS ===")
        
        # Lade Power-Daten
        df = pd.read_csv(power_csv, comment='#')
        
        print(f"Data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Power-Spalten analysieren
        power_cols = [col for col in df.columns if 'Power' in col or 'power' in col]
        print(f"\nPower columns: {power_cols}")
        
        for col in power_cols:
            if col in df.columns:
                values = df[col]
                print(f"\n--- {col} ---")
                print(f"Min: {values.min():.1f}")
                print(f"Max: {values.max():.1f}")
                print(f"Mean: {values.mean():.1f}")
                print(f"Median: {values.median():.1f}")
                print(f"95th percentile: {values.quantile(0.95):.1f}")
                print(f"99th percentile: {values.quantile(0.99):.1f}")
                
                # Unrealistische Werte finden
                unrealistic = values > 500  # >500W ist für Hobbysportler unrealistisch
                very_unrealistic = values > 1000  # >1000W ist nur für Profis kurzzeitig
                extreme = values > 2000  # >2000W ist völlig unrealistisch
                
                print(f"Values > 500W: {unrealistic.sum()} ({unrealistic.sum()/len(df)*100:.1f}%)")
                print(f"Values > 1000W: {very_unrealistic.sum()} ({very_unrealistic.sum()/len(df)*100:.1f}%)")
                print(f"Values > 2000W: {extreme.sum()} ({extreme.sum()/len(df)*100:.1f}%)")
                
                if extreme.sum() > 0:
                    print(f"EXTREME values (>2000W):")
                    extreme_data = df[extreme][['Distanz (km)', 'Geschwindigkeit (km/h)', 'Gradient', col, 'Elevation (m)']]
                    print(extreme_data.head(10))
        
        # Geschwindigkeit vs Power Korrelation
        if 'Power_W' in df.columns and 'Geschwindigkeit (km/h)' in df.columns:
            speed = df['Geschwindigkeit (km/h)']
            power = df['Power_W']
            
            print(f"\n--- SPEED vs POWER ANALYSIS ---")
            
            # Finde extrem hohe Power bei niedriger Geschwindigkeit
            low_speed_high_power = df[(speed < 10) & (power > 1000)]
            
            if len(low_speed_high_power) > 0:
                print(f"LOW SPEED (<10 km/h) + HIGH POWER (>1000W): {len(low_speed_high_power)} cases")
                print("This suggests calculation errors!")
                print(low_speed_high_power[['Distanz (km)', 'Geschwindigkeit (km/h)', 'Gradient', 'Power_W', 'Elevation (m)']].head())
        
        # Gradient-Analyse
        if 'Gradient' in df.columns:
            gradient = df['Gradient']
            print(f"\n--- GRADIENT ANALYSIS ---")
            print(f"Gradient range: {gradient.min():.1f}% to {gradient.max():.1f}%")
            
            # Extreme Gradienten finden
            extreme_gradients = abs(gradient) > 50
            if extreme_gradients.sum() > 0:
                print(f"EXTREME gradients (>50%): {extreme_gradients.sum()}")
                print("This could cause unrealistic power calculations!")
                extreme_grad_data = df[extreme_gradients][['Distanz (km)', 'Gradient', 'Power_W', 'Elevation (m)']]
                print(extreme_grad_data.head())
        
        print("\n" + "="*50)
        
    except Exception as e:
        print(f"Error analyzing power data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_power_data()
