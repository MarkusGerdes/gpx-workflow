#!/usr/bin/env python3
"""
SQLiteSurfaceCache.py - Surface-Daten Cache für Overpass API
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from geopy.distance import geodesic

try:
    from dataclasses import dataclass
    
    @dataclass
    class SurfaceResult:
        """Datenklasse für Surface-Ergebnisse"""
        latitude: float
        longitude: float
        surface: str
        highway: str
        tracktype: Optional[str] = None
        smoothness: Optional[str] = None
        osm_way_id: Optional[int] = None
        query_radius_m: int = 80
        api_provider: str = "Overpass"
        query_date: Optional[str] = None
        
except ImportError:
    # Fallback wenn dataclasses nicht verfügbar
    class SurfaceResult:
        def __init__(self, latitude, longitude, surface, highway, 
                     tracktype=None, smoothness=None, osm_way_id=None,
                     query_radius_m=80, api_provider="Overpass", query_date=None):
            self.latitude = latitude
            self.longitude = longitude
            self.surface = surface
            self.highway = highway
            self.tracktype = tracktype
            self.smoothness = smoothness
            self.osm_way_id = osm_way_id
            self.query_radius_m = query_radius_m
            self.api_provider = api_provider
            self.query_date = query_date


class SQLiteSurfaceCache:
    """SQLite-basierter Cache für Surface-Daten von Overpass API"""
    
    def __init__(self, db_path: str = "surface_cache.db"):
        """
        Initialisiert den SQLite Surface-Cache
        
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
        
        # Surface Cache Tabelle
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS surface_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                surface TEXT NOT NULL,
                highway TEXT,
                tracktype TEXT,
                smoothness TEXT,
                osm_way_id INTEGER,
                query_radius_m INTEGER NOT NULL,
                api_provider TEXT DEFAULT 'Overpass',
                query_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(latitude, longitude, query_radius_m, api_provider)
            )
        """)
        
        # GPX Surface Tracks Tabelle
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS gpx_surface_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                track_name TEXT,
                processing_date TEXT NOT NULL,
                total_blocks INTEGER,
                cached_blocks INTEGER,
                api_calls INTEGER,
                query_radius_m INTEGER,
                script_version TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Surface Track Points Tabelle
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS surface_track_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                block_id INTEGER NOT NULL,
                original_index INTEGER,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                surface_cache_id INTEGER,
                street TEXT,
                city TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indizes für Performance
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_surface_coords 
            ON surface_cache(latitude, longitude, query_radius_m)
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_surface_track_points_coords 
            ON surface_track_points(latitude, longitude)
        """)
        
        self.connection.commit()

    def find_cached_surface(self, latitude: float, longitude: float, 
                           query_radius_m: int, tolerance_km: float = 0.1) -> Optional[SurfaceResult]:
        """
        Sucht nach gecachten Surface-Daten für gegebene Koordinaten
        
        Args:
            latitude: Ziel-Breitengrad
            longitude: Ziel-Längengrad  
            query_radius_m: Abfrageradius in Metern
            tolerance_km: Suchtoleranz in Kilometern
            
        Returns:
            SurfaceResult falls im Cache gefunden, None andernfalls
        """
        try:
            self.stats['total_queries'] += 1
            
            # Suchbereich basierend auf Toleranz berechnen
            lat_delta = tolerance_km / 111.0  # Ca. 111 km pro Breitengrad
            # Längengradabstand anpassen (konvergiert zu Polen hin)
            lon_delta = tolerance_km / (111.0 * abs(latitude / 90.0) + 0.1)
            
            # Cache für ähnliche Ergebnisse abfragen
            cursor = self.connection.execute("""
                SELECT latitude, longitude, surface, highway, tracktype, 
                       smoothness, osm_way_id, query_radius_m, api_provider, query_date
                FROM surface_cache 
                WHERE latitude BETWEEN ? AND ? 
                AND longitude BETWEEN ? AND ?
                AND query_radius_m = ?
                ORDER BY (latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)
                LIMIT 10
            """, (
                latitude - lat_delta, latitude + lat_delta,
                longitude - lon_delta, longitude + lon_delta,
                query_radius_m,
                latitude, latitude, longitude, longitude
            ))
            
            results = cursor.fetchall()
            
            if not results:
                self.stats['cache_misses'] += 1
                return None
                
            # Nächstes Ergebnis innerhalb Toleranz finden
            for result in results:
                cached_lat, cached_lon = result[0], result[1]
                distance_km = geodesic((latitude, longitude), (cached_lat, cached_lon)).kilometers
                
                if distance_km <= tolerance_km:
                    self.stats['cache_hits'] += 1
                    return SurfaceResult(
                        latitude=cached_lat,
                        longitude=cached_lon,
                        surface=result[2],
                        highway=result[3],
                        tracktype=result[4],
                        smoothness=result[5],
                        osm_way_id=result[6],
                        query_radius_m=result[7],
                        api_provider=result[8],
                        query_date=result[9]
                    )
            
            self.stats['cache_misses'] += 1
            return None
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error searching surface cache: {e}")
            self.stats['cache_misses'] += 1
            return None

    def cache_surface_result(self, result: SurfaceResult) -> int:
        """
        Speichert Surface-Ergebnis im Cache
        
        Args:
            result: SurfaceResult zum Speichern
            
        Returns:
            ID des gespeicherten Eintrags
        """
        try:
            cursor = self.connection.execute("""
                INSERT OR REPLACE INTO surface_cache 
                (latitude, longitude, surface, highway, tracktype, 
                 smoothness, osm_way_id, query_radius_m, api_provider, query_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.latitude, result.longitude, result.surface, result.highway,
                result.tracktype, result.smoothness, result.osm_way_id,
                result.query_radius_m, result.api_provider, result.query_date
            ))
            
            self.connection.commit()
            return cursor.lastrowid
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error caching surface result: {e}")
            return None

    def create_surface_track(self, filename: str, track_name: str = None, 
                           total_blocks: int = None, query_radius_m: int = 80,
                           script_version: str = None) -> int:
        """Erstellt einen neuen Surface-Track-Eintrag"""
        cursor = self.connection.execute("""
            INSERT INTO gpx_surface_tracks 
            (filename, track_name, processing_date, total_blocks, 
             query_radius_m, script_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            filename, track_name, datetime.now().isoformat(),
            total_blocks, query_radius_m, script_version
        ))
        
        self.connection.commit()
        return cursor.lastrowid

    def add_surface_track_point(self, track_id: int, block_id: int, 
                               latitude: float, longitude: float,
                               original_index: int = None, surface_cache_id: int = None,
                               street: str = None, city: str = None) -> int:
        """Fügt einen Surface-Track-Point hinzu"""
        cursor = self.connection.execute("""
            INSERT INTO surface_track_points 
            (track_id, block_id, original_index, latitude, longitude, 
             surface_cache_id, street, city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            track_id, block_id, original_index, latitude, longitude,
            surface_cache_id, street, city
        ))
        
        self.connection.commit()
        return cursor.lastrowid

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Gibt Cache-Statistiken zurück"""
        stats = {}
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM surface_cache")
        stats['total_cache_entries'] = cursor.fetchone()[0]
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM gpx_surface_tracks")
        stats['total_tracks'] = cursor.fetchone()[0]
        
        cursor = self.connection.execute("SELECT COUNT(*) FROM surface_track_points")
        stats['total_track_points'] = cursor.fetchone()[0]
        
        # Runtime-Statistiken hinzufügen
        stats.update(self.stats)
        
        return stats

    def close(self):
        """Schließt die Datenbankverbindung"""
        if self.connection:
            self.connection.close()