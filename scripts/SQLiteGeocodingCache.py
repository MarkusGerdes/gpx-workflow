#!/usr/bin/env python3
"""
SQLite Geocoding Cache - Separate Module
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from geopy.distance import geodesic

# GeocodingResult wird vom Hauptscript importiert
# Wir definieren es hier nochmal für Standalone-Nutzung
try:
    from dataclasses import dataclass
    
    @dataclass
    class GeocodingResult:
        """Datenklasse für Geocoding-Ergebnisse"""
        latitude: float
        longitude: float
        street: str
        city: str
        postal_code: str
        country: Optional[str] = None
        raw_address: Optional[Dict] = None
        api_provider: str = "Nominatim"
        query_date: Optional[str] = None
        
except ImportError:
    # Fallback wenn dataclasses nicht verfügbar
    class GeocodingResult:
        def __init__(self, latitude, longitude, street, city, postal_code, 
                     country=None, raw_address=None, api_provider="Nominatim", query_date=None):
            self.latitude = latitude
            self.longitude = longitude
            self.street = street
            self.city = city
            self.postal_code = postal_code
            self.country = country
            self.raw_address = raw_address
            self.api_provider = api_provider
            self.query_date = query_date


class SQLiteGeocodingCache:
    """SQLite-basierter Cache für Geocoding-Ergebnisse"""
    
    def __init__(self, db_path: str = "geocoding_cache.db"):
        """
        Initialisiert den SQLite-Cache
        
        Args:
            db_path: Pfad zur SQLite-Datenbankdatei
        """
        self.db_path = Path(db_path)
        self.connection = None
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_queries': 0
        }
        self._setup_database()
        
    def _setup_database(self):
        """Erstellt die Datenbankstruktur"""
        # Verzeichnis erstellen falls es nicht existiert
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        # WICHTIG: Foreign Keys AUSSCHALTEN für bessere Kompatibilität
        self.connection.execute("PRAGMA foreign_keys = OFF")
        
        # Geocoding Cache Tabelle
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                street TEXT,
                city TEXT,
                postal_code TEXT,
                country TEXT,
                raw_address TEXT,  -- JSON string
                api_provider TEXT DEFAULT 'Nominatim',
                query_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(latitude, longitude, api_provider)
            )
        """)
        
        # GPX Tracks Tabelle
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS gpx_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                track_name TEXT,
                processing_date TEXT NOT NULL,
                total_points INTEGER,
                geocoded_points INTEGER,
                sampling_distance REAL,
                script_version TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Track Points Tabelle (ohne Foreign Key Constraints)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS track_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                original_index INTEGER,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                geocoding_cache_id INTEGER,
                timestamp TEXT,
                elevation REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indizes für Performance
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_geocoding_coords 
            ON geocoding_cache(latitude, longitude)
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_track_points_coords 
            ON track_points(latitude, longitude)
        """)
        
        self.connection.commit()

    def find_cached_geocoding(self, latitude: float, longitude: float, 
                            tolerance_km: float = 0.1, 
                            api_provider: str = "Nominatim") -> Optional[GeocodingResult]:
        """
        Find cached geocoding result for given coordinates within tolerance.
        
        Args:
            latitude: Target latitude
            longitude: Target longitude  
            tolerance_km: Search tolerance in kilometers
            api_provider: API provider (wird jetzt ignoriert für bessere Cache-Hits)
            
        Returns:
            GeocodingResult if found in cache, None otherwise
        """
        try:
            self.stats['total_queries'] += 1
            
            # Calculate search bounds based on tolerance
            lat_delta = tolerance_km / 111.0  # Approximately 111 km per degree latitude
            # Adjust longitude delta based on latitude (longitude lines converge at poles)
            lon_delta = tolerance_km / (111.0 * abs(latitude / 90.0) + 0.1)
            
            # Query cache for nearby results (OHNE api_provider Filter)
            cursor = self.connection.execute("""
                SELECT latitude, longitude, street, city, postal_code, country, 
                       raw_address, api_provider, query_date
                FROM geocoding_cache 
                WHERE latitude BETWEEN ? AND ? 
                AND longitude BETWEEN ? AND ?
                ORDER BY (latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)
                LIMIT 10
            """, (
                latitude - lat_delta, latitude + lat_delta,
                longitude - lon_delta, longitude + lon_delta,
                latitude, latitude, longitude, longitude
            ))
            
            results = cursor.fetchall()
            
            if not results:
                self.stats['cache_misses'] += 1
                return None
                
            # Find the closest result within tolerance
            for result in results:
                cached_lat, cached_lon = result[0], result[1]
                distance_km = geodesic((latitude, longitude), (cached_lat, cached_lon)).kilometers
                
                if distance_km <= tolerance_km:
                    self.stats['cache_hits'] += 1
                    return GeocodingResult(
                        latitude=cached_lat,
                        longitude=cached_lon,
                        street=result[2],
                        city=result[3],
                        postal_code=result[4],
                        country=result[5],
                        raw_address=result[6],
                        api_provider=result[7],
                        query_date=result[8]
                    )
            
            self.stats['cache_misses'] += 1
            return None
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error searching cache: {e}")
            self.stats['cache_misses'] += 1
            return None

    def cache_geocoding_result(self, result: GeocodingResult) -> int:
        """
        Cache-Geocoding-Ergebnis speichern
        
        Args:
            result: GeocodingResult zum Speichern
            
        Returns:
            ID des gespeicherten Eintrags
        """
        try:
            cursor = self.connection.execute("""
                INSERT OR REPLACE INTO geocoding_cache 
                (latitude, longitude, street, city, postal_code, country, 
                 raw_address, api_provider, query_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.latitude, result.longitude, result.street, result.city,
                result.postal_code, result.country, 
                json.dumps(result.raw_address) if result.raw_address else None,
                result.api_provider, result.query_date
            ))
            
            self.connection.commit()
            return cursor.lastrowid
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error caching geocoding result: {e}")
            return None

    def create_gpx_track(self, filename: str, track_name: str = None, 
                        total_points: int = None, sampling_distance: float = None,
                        script_version: str = None) -> int:
        """Erstellt einen neuen GPX-Track-Eintrag"""
        cursor = self.connection.execute("""
            INSERT INTO gpx_tracks 
            (filename, track_name, processing_date, total_points, 
             sampling_distance, script_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            filename, track_name, datetime.now().isoformat(),
            total_points, sampling_distance, script_version
        ))
        
        self.connection.commit()
        return cursor.lastrowid

    def add_track_point(self, track_id: int, latitude: float, longitude: float,
                       original_index: int = None, geocoding_cache_id: int = None,
                       timestamp: str = None, elevation: float = None) -> int:
        """Fügt einen Track-Point hinzu"""
        cursor = self.connection.execute("""
            INSERT INTO track_points 
            (track_id, original_index, latitude, longitude, 
             geocoding_cache_id, timestamp, elevation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            track_id, original_index, latitude, longitude,
            geocoding_cache_id, timestamp, elevation
        ))
        
        self.connection.commit()
        return cursor.lastrowid

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Gibt Cache-Statistiken zurück"""
        stats = {}
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM geocoding_cache")
        stats['total_cache_entries'] = cursor.fetchone()[0]
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM gpx_tracks")
        stats['total_tracks'] = cursor.fetchone()[0]
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM track_points")
        stats['total_track_points'] = cursor.fetchone()[0]
        
        # Ergänze Runtime-Statistiken
        stats.update(self.stats)
        
        return stats

    def close(self):
        """Schließt die Datenbankverbindung"""
        if self.connection:
            self.connection.close()