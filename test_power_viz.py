#!/usr/bin/env python3
"""
Test-Script für korrigierte Power-Visualisierung
"""

import subprocess
import sys
import os
import time

def test_power_visualization():
    """Test das korrigierte 10c_power_visualization.py Script."""
    
    print("=== POWER VISUALIZATION TEST ===")
    
    # Test mit existierenden Dateien
    power_csv = "output/10b_HaBe_Feierabendrunde_von_Finki_aus_power_data.csv"
    surface_csv = "output/4b_HaBe_Feierabendrunde_von_Finki_aus_surface_data.csv"
    output_html = "output/TEST_power_visualization.html"
    output_png = "output/TEST_power_visualization.png"
    
    # Prüfe Input-Dateien
    if not os.path.exists(power_csv):
        print(f"❌ Power-Datei nicht gefunden: {power_csv}")
        return False
        
    if not os.path.exists(surface_csv):
        print(f"❌ Surface-Datei nicht gefunden: {surface_csv}")
        return False
    
    print(f"✅ Input-Dateien gefunden")
    print(f"   Power: {power_csv}")
    print(f"   Surface: {surface_csv}")
    
    # Teste das Script mit Timeout
    cmd = [
        "python", "scripts/10c_power_visualization.py",
        "--power-csv", power_csv,
        "--surface-csv", surface_csv, 
        "--output-html", output_html,
        "--output-png", output_png,
        "--config-file", "config.yaml",
        "--smooth-window", "20",
        "--max-points", "1000"  # Reduziert für Test
    ]
    
    print(f"\nAusführung: {' '.join(cmd)}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=120  # 2 Minuten Timeout
        )
        
        elapsed = time.time() - start_time
        print(f"Script beendet in {elapsed:.1f}s")
        
        if result.returncode == 0:
            print("✅ Script erfolgreich beendet")
            print("STDOUT:")
            print(result.stdout)
            
            # Prüfe Output-Dateien
            if os.path.exists(output_html):
                file_size = os.path.getsize(output_html) / 1024  # KB
                print(f"✅ HTML erstellt: {file_size:.1f} KB")
            else:
                print("❌ HTML nicht erstellt")
                
            if os.path.exists(output_png):
                file_size = os.path.getsize(output_png) / 1024  # KB
                print(f"✅ PNG erstellt: {file_size:.1f} KB") 
            else:
                print("⚠️ PNG nicht erstellt (erwartet, wenn Kaleido fehlt)")
                
            return True
        else:
            print(f"❌ Script fehlgeschlagen (Exit Code: {result.returncode})")
            print("STDOUT:")
            print(result.stdout)
            print("STDERR:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Script hängt sich noch immer auf!")
        return False
    except Exception as e:
        print(f"❌ Fehler beim Ausführen: {e}")
        return False

if __name__ == "__main__":
    success = test_power_visualization()
    if success:
        print("\n🎉 POWER VISUALIZATION TEST ERFOLGREICH!")
    else:
        print("\n💥 POWER VISUALIZATION TEST FEHLGESCHLAGEN!")
    sys.exit(0 if success else 1)
