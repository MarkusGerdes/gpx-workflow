#!/usr/bin/env python3
"""
GPX_Workflow_SQLite_administration.py
Verwaltungs-Script für den SQLite Geocoding Cache
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

#from GPX_Workflow_SQLiteCaching import SQLiteGeocodingCache
from sqlite_geocoding_cache import SQLiteGeocodingCache


class CacheManager:
    """Verwaltungsklasse für den Geocoding Cache"""
    
    def __init__(self, db_path: str):
        self.cache = SQLiteGeocodingCache(db_path)
        self.db_path = db_path

    def show_statistics(self):
        """Zeigt detaillierte Cache-Statistiken"""
        stats = self.cache.get_cache_statistics()
        
        print(f"\n{'='*60}")
        print(f"GEOCODING CACHE STATISTIKEN")
        print(f"{'='*60}")
        print(f"Datenbankdatei: {self.db_path}")
        print(f"Gecachte Standorte: {stats['total_cached_locations']:,}")
        print(f"Gespeicherte Tracks: {stats['total_tracks']:,}")
        print(f"Track-Punkte gesamt: {stats['total_track_points']:,}")
        print(f"Geocoding-Abdeckung: {stats['geocoding_coverage']:.1%}")
        
        # Datenbankgröße
        if Path(self.db_path).exists():
            db_size = Path(self.db_path).stat().st_size / (1024 * 1024)  # MB
            print(f"Datenbankgröße: {db_size:.2f} MB")
        
        print(f"{'='*60}\n")

    def list_tracks(self):
        """Listet alle gespeicherten Tracks auf"""
        cursor = self.cache.connection.execute("""
            SELECT id, filename, track_name, processing_date, 
                   total_points, geocoded_points, sampling_distance, script_version
            FROM gpx_tracks
            ORDER BY processing_date DESC
        """)
        
        tracks = cursor.fetchall()
        
        if not tracks:
            print("Keine Tracks in der Datenbank gefunden.")
            return
        
        print(f"\n{'='*80}")
        print(f"GESPEICHERTE GPX TRACKS")
        print(f"{'='*80}")
        print(f"{'ID':<4} {'Dateiname':<25} {'Punkte':<8} {'Datum':<20}")
        print(f"{'-'*80}")
        
        for track in tracks:
            track_id, filename, track_name, proc_date, total_pts, geocoded_pts, sampling, version = track
            total_pts = total_pts or 0
            proc_date_short = proc_date[:19] if proc_date else "N/A"
            
            print(f"{track_id:<4} {filename[:24]:<25} {total_pts:<8} {proc_date_short:<20}")
        
        print(f"{'-'*80}\n")

    def search_locations(self, search_term: str):
        """Sucht nach Orten im Cache"""
        cursor = self.cache.connection.execute("""
            SELECT latitude, longitude, street, city, postal_code
            FROM geocoding_cache
            WHERE city LIKE ? OR street LIKE ? OR postal_code LIKE ?
            ORDER BY city, street
            LIMIT 20
        """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
        
        results = cursor.fetchall()
        
        if not results:
            print(f"Keine Orte gefunden für: '{search_term}'")
            return
        
        print(f"\nSuchergebnisse für '{search_term}':")
        print(f"{'Breite':<10} {'Länge':<11} {'Stadt':<20} {'Straße':<25}")
        print(f"{'-'*70}")
        
        for result in results:
            lat, lon, street, city, postal = result
            street = street[:24] if street else "N/A"
            city = city[:19] if city else "N/A"
            
            print(f"{lat:<10.5f} {lon:<11.5f} {city:<20} {street:<25}")


def main():
    parser = argparse.ArgumentParser(description="Geocoding Cache Verwaltung")
    parser.add_argument("--db", default="geocoding_cache.db", help="Pfad zur SQLite-Datenbank")
    
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Kommandos")
    
    # Statistiken
    subparsers.add_parser("stats", help="Zeige Cache-Statistiken")
    
    # Tracks auflisten
    subparsers.add_parser("list", help="Liste alle Tracks")
    
    # Suchen
    search_parser = subparsers.add_parser("search", help="Suche nach Orten")
    search_parser.add_argument("term", help="Suchbegriff")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    manager = CacheManager(args.db)
    
    try:
        if args.command == "stats":
            manager.show_statistics()
        elif args.command == "list":
            manager.list_tracks()
        elif args.command == "search":
            manager.search_locations(args.term)
    finally:
        manager.cache.close()


if __name__ == "__main__":
    main()