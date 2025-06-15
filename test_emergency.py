#!/usr/bin/env python3
"""
Emergency Test für vereinfachte Power-Visualisierung
"""

import subprocess
import sys
import os
import time

def test_emergency_power_viz():
    """Test der Emergency-Version."""
    
    print("=== EMERGENCY POWER VISUALIZATION TEST ===")
    
    # Test mit Emergency-Script
    power_csv = "output/10b_HaBe_Feierabendrunde_von_Finki_aus_power_data.csv"
    surface_csv = "output/4b_HaBe_Feierabendrunde_von_Finki_aus_surface_data.csv"
    output_html = "output/EMERGENCY_power_visualization.html"
    
    cmd = [
        "python", "scripts/10c_power_visualization_EMERGENCY.py",
        "--power-csv", power_csv,
        "--surface-csv", surface_csv, 
        "--output-html", output_html,
        "--max-points", "500"  # Sehr klein für Test
    ]
    
    print(f"Teste Emergency-Script: {' '.join(cmd)}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30  # Nur 30 Sekunden!
        )
        
        elapsed = time.time() - start_time
        print(f"Emergency-Script beendet in {elapsed:.1f}s")
        
        if result.returncode == 0:
            print("[SUCCESS] EMERGENCY-SCRIPT ERFOLGREICH!")
            print("STDOUT:")
            print(result.stdout)
            
            if os.path.exists(output_html):
                file_size = os.path.getsize(output_html) / 1024  # KB
                print(f"[OK] Emergency HTML erstellt: {file_size:.1f} KB")
                return True
        else:
            print(f"[ERROR] Emergency-Script fehlgeschlagen: {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            
    except subprocess.TimeoutExpired:
        print("[ERROR] AUCH EMERGENCY-SCRIPT HÄNGT!")
        return False
    except Exception as e:
        print(f"[ERROR] Fehler: {e}")
        return False
    
    return False

if __name__ == "__main__":
    success = test_emergency_power_viz()
    if success:
        print("\n[SUCCESS] EMERGENCY-VERSION FUNKTIONIERT!")
        print("\nNächster Schritt: Original 10c durch Emergency-Version ersetzen")
    else:
        print("\n[FAILED] AUCH EMERGENCY-VERSION FEHLGESCHLAGEN!")
        print("Das Problem liegt tiefer - möglicherweise in den Input-Daten")
    sys.exit(0 if success else 1)
