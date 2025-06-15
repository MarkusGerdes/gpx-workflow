#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_surface_cache.py - Testet das Surface Cache System isoliert
"""

import os
import sys
from datetime import datetime

def test_cache_import():
    """Testet den Import der Cache-Klasse"""
    print("1. TESTE CACHE-IMPORT...")
    
    try:
        # Versuche Import mit verschiedenen Methoden
        try:
            from SQLiteSurfaceCache import SQLiteSurfaceCache, SurfaceResult
            print("   ✅ Direkter Import erfolgreich")
        except ImportError:
            # Dynamischer Import als Fallback
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "SQLiteSurfaceCache", 
                "SQLiteSurfaceCache.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            SQLiteSurfaceCache = module.SQLiteSurfaceCache
            SurfaceResult = module.SurfaceResult
            print("   ✅ Dynamischer Import erfolgreich")
        
        return SQLiteSurfaceCache, SurfaceResult
        
    except Exception as e:
        print(f"   ❌ Import fehlgeschlagen: {e}")
        return None, None

def test_cache_creation(SQLiteSurfaceCache):
    """Testet die Cache-Erstellung"""
    print("\n2. TESTE CACHE-ERSTELLUNG...")
    
    try:
        cache = SQLiteSurfaceCache("test_surface_cache.db")
        print("   ✅ Cache-Objekt erstellt")
        
        # Statistiken abrufen
        stats = cache.get_cache_statistics()
        print(f"   📊 Initiale Statistiken: {stats}")
        
        cache.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Cache-Erstellung fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cache_operations(SQLiteSurfaceCache, SurfaceResult):
    """Testet Cache-Operationen"""
    print("\n3. TESTE CACHE-OPERATIONEN...")
    
    try:
        cache = SQLiteSurfaceCache("test_surface_cache.db")
        
        # Test-Daten erstellen
        test_result = SurfaceResult(
            latitude=52.5200,
            longitude=13.4050,
            surface="paved",
            highway="residential",
            tracktype=None,
            smoothness="good",
            osm_way_id=123456789,
            query_radius_m=80,
            api_provider="Test",
            query_date=datetime.now().isoformat()
        )
        
        # Cache schreiben
        cache_id = cache.cache_surface_result(test_result)
        print(f"   ✅ Test-Daten geschrieben (ID: {cache_id})")
        
        # Cache lesen
        found_result = cache.find_cached_surface(52.5200, 13.4050, 80, tolerance_km=0.1)
        if found_result:
            print(f"   ✅ Test-Daten gefunden: {found_result.surface}")
        else:
            print("   ❌ Test-Daten nicht gefunden")
        
        # Track erstellen
        track_id = cache.create_surface_track(
            filename="test_track.csv",
            track_name="Test Track",
            total_blocks=1,
            query_radius_m=80,
            script_version="test_1.0"
        )
        print(f"   ✅ Test-Track erstellt (ID: {track_id})")
        
        # Track-Point hinzufügen
        point_id = cache.add_surface_track_point(
            track_id=track_id,
            block_id=1,
            latitude=52.5200,
            longitude=13.4050,
            surface_cache_id=cache_id
        )
        print(f"   ✅ Test-Track-Point hinzugefügt (ID: {point_id})")
        
        # Finale Statistiken
        final_stats = cache.get_cache_statistics()
        print(f"   📊 Finale Statistiken: {final_stats}")
        
        cache.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Cache-Operationen fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_original_script_integration():
    """Testet die Integration mit dem Original-Script"""
    print("\n4. TESTE ORIGINAL-SCRIPT-INTEGRATION...")
    
    # Prüfe ob das Original-Script existiert
    original_script = "4b_fetch_surface_grouped_SQLiteCache.py"
    
    if not os.path.exists(original_script):
        print(f"   ❌ Original-Script nicht gefunden: {original_script}")
        print("   💡 Mögliche Ursachen:")
        print("      - Script ist in anderem Verzeichnis")
        print("      - Script hat anderen Namen")
        print("      - Script wurde nicht erstellt")
        return False
    
    print(f"   ✅ Original-Script gefunden: {original_script}")
    
    # Prüfe Import im Original-Script
    try:
        with open(original_script, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "from SQLiteSurfaceCache import" in content:
            print("   ✅ SQLiteSurfaceCache Import im Script gefunden")
        else:
            print("   ❌ SQLiteSurfaceCache Import im Script NICHT gefunden")
            print("   💡 Das Original-Script verwendet möglicherweise nicht den Cache!")
        
        if "fetch_surface_data_with_sqlite_cache" in content:
            print("   ✅ Cache-Funktion im Script gefunden")
        else:
            print("   ❌ Cache-Funktion im Script NICHT gefunden")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Fehler beim Prüfen des Original-Scripts: {e}")
        return False

def test_database_files():
    """Testet vorhandene Datenbank-Dateien"""
    print("\n5. TESTE DATENBANK-DATEIEN...")
    
    # Suche nach Surface-Cache-Dateien
    cache_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if "surface" in file.lower() and file.endswith(".db"):
                cache_files.append(os.path.join(root, file))
    
    if cache_files:
        print(f"   📁 Gefundene Surface-Cache-Dateien:")
        for cache_file in cache_files:
            file_size = os.path.getsize(cache_file)
            print(f"      - {cache_file} ({file_size:,} Bytes)")
    else:
        print("   ❌ Keine Surface-Cache-Dateien gefunden")
    
    return len(cache_files) > 0

def main():
    print("=" * 60)
    print("SURFACE CACHE SYSTEM TEST")
    print("=" * 60)
    print(f"Aktuelles Verzeichnis: {os.getcwd()}")
    print(f"Python Version: {sys.version}")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test 1: Import
    SQLiteSurfaceCache, SurfaceResult = test_cache_import()
    if not SQLiteSurfaceCache:
        all_tests_passed = False
        print("\n❌ KRITISCHER FEHLER: Cache-Import fehlgeschlagen!")
        print("   Prüfen Sie, ob SQLiteSurfaceCache.py existiert und korrekt ist.")
        return
    
    # Test 2: Cache-Erstellung
    if not test_cache_creation(SQLiteSurfaceCache):
        all_tests_passed = False
    
    # Test 3: Cache-Operationen
    if not test_cache_operations(SQLiteSurfaceCache, SurfaceResult):
        all_tests_passed = False
    
    # Test 4: Original-Script-Integration
    if not test_original_script_integration():
        all_tests_passed = False
    
    # Test 5: Datenbank-Dateien
    if not test_database_files():
        all_tests_passed = False
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("✅ ALLE TESTS BESTANDEN")
        print("Das Cache-System funktioniert grundsätzlich!")
        print("\n💡 Wenn Ihr Original-Script trotzdem keine Daten cached:")
        print("   1. Prüfen Sie den exakten Datenbankpfad")
        print("   2. Stellen Sie sicher, dass das Script die Cache-Funktion verwendet")
        print("   3. Prüfen Sie die Script-Logs auf Fehler")
    else:
        print("❌ EINIGE TESTS FEHLGESCHLAGEN")
        print("Das Cache-System hat Probleme!")
        print("\n🔧 Lösungsvorschläge:")
        print("   1. Prüfen Sie alle Dateien sind im gleichen Verzeichnis")
        print("   2. Installieren Sie fehlende Dependencies")
        print("   3. Prüfen Sie Dateiberechtigungen")
    print("=" * 60)

if __name__ == "__main__":
    main()