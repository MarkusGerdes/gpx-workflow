#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_generate_map_screenshot.py
-----------------------------
Generates PNG screenshots from interactive HTML maps using Selenium.
Opens HTML map files in a headless Chrome browser and captures screenshots
with detailed performance tracking and browser automation metrics.
"""

# === SCRIPT METADATA ===
SCRIPT_NAME = "10_generate_map_screenshot.py"
SCRIPT_VERSION = "2.0.0"
SCRIPT_DESCRIPTION = "Automated screenshot generation from interactive HTML maps using Selenium WebDriver with performance tracking"
LAST_UPDATED = "2025-06-07"
AUTHOR = "Markus"
CONFIG_COMPATIBILITY = "2.1"

# === CHANGELOG ===
CHANGELOG = """
v1.0.0 (pre-2025): Initial version with basic screenshot functionality
v1.1.0 (2025-06-07): Standardized header, improved error handling and documentation
v2.0.0 (2025-06-07): Enhanced metadata system with browser automation performance tracking and screenshot quality metrics
"""

# === SCRIPT CONFIGURATION ===
DEFAULT_CONFIG_SECTION = "map_screenshot"
INPUT_FILE_PATTERN = "*_interactive_map.html"
OUTPUT_FILE_PATTERN = "*_map_screenshot.png"

# === DEPENDENCIES ===
PYTHON_VERSION_MIN = "3.8"
REQUIRED_PACKAGES = [
    "selenium>=4.0.0",
    "webdriver-manager>=3.8.0",
    "pandas>=1.3.0"
]

# === BROWSER CONFIGURATION ===
DEFAULT_BROWSER_WIDTH = 1200
DEFAULT_BROWSER_HEIGHT = 800
DEFAULT_MAP_LOAD_DELAY = 5
WEBDRIVER_TIMEOUT = 30
CHROME_HEADLESS_MODE = "new"
BROWSER_LOG_LEVEL = 3  # Suppress most browser logs

# === PERFORMANCE TRACKING ===
TRACK_SCREENSHOT_PERFORMANCE = True
TRACK_BROWSER_AUTOMATION = True
TRACK_FILE_OPERATIONS = True

import sys
import os
import argparse
import time
from pathlib import Path
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

# Use webdriver_manager to automatically handle chromedriver download/updates
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Fehler: webdriver-manager nicht gefunden. Bitte installieren: pip install webdriver-manager")
    sys.exit(1)

# === PERFORMANCE TRACKING GLOBALS ===
screenshot_stats = {
    'start_time': None,
    'webdriver_init_time': 0,
    'page_load_time': 0,
    'screenshot_capture_time': 0,
    'browser_automation_errors': 0,
    'file_validation_time': 0,
    'total_wait_time': 0,
    'processing_stages': {}
}

# === FUNCTIONS ===

def print_script_info():
    """Print script metadata for logging purposes."""
    print(f"=== {SCRIPT_NAME} v{SCRIPT_VERSION} ===")
    print(f"Description: {SCRIPT_DESCRIPTION}")
    print(f"Last Updated: {LAST_UPDATED}")
    print(f"Config Compatibility: {CONFIG_COMPATIBILITY}")
    print(f"Browser: Chrome (headless)")
    print(f"Default Resolution: {DEFAULT_BROWSER_WIDTH}x{DEFAULT_BROWSER_HEIGHT}")
    print(f"Performance Tracking: {TRACK_SCREENSHOT_PERFORMANCE}")
    print("=" * 50)

def log_stage(stage_name: str, duration: float = None, details: dict = None):
    """Log processing stage for performance tracking."""
    screenshot_stats['processing_stages'][stage_name] = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'details': details or {}
    }

def save_performance_metadata(png_output_path: str, metadata: dict):
    """Save screenshot generation performance metadata to CSV file."""
    if not TRACK_SCREENSHOT_PERFORMANCE:
        return
    
    # Create metadata CSV path
    base_path = png_output_path.replace('.png', '_metadata.csv')
    
    # Calculate total processing time
    total_time = time.time() - screenshot_stats['start_time'] if screenshot_stats['start_time'] else 0
    
    # Calculate performance metrics
    automation_success_rate = round((1 - screenshot_stats['browser_automation_errors'] / max(1, 1)) * 100, 1)
    efficiency_score = round((screenshot_stats['screenshot_capture_time'] / max(total_time, 0.001)) * 100, 1)
    
    # Prepare metadata row
    metadata_row = {
        'timestamp': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'input_file': metadata.get('input_file', ''),
        'output_file': os.path.basename(png_output_path),
        'processing_time_total_seconds': round(total_time, 2),
        'webdriver_initialization_seconds': round(screenshot_stats['webdriver_init_time'], 2),
        'page_load_time_seconds': round(screenshot_stats['page_load_time'], 2),
        'screenshot_capture_time_seconds': round(screenshot_stats['screenshot_capture_time'], 2),
        'total_wait_time_seconds': round(screenshot_stats['total_wait_time'], 2),
        'file_validation_time_seconds': round(screenshot_stats['file_validation_time'], 2),
        'browser_automation_success_rate': automation_success_rate,
        'efficiency_score_percent': efficiency_score,
        'browser_automation_errors': screenshot_stats['browser_automation_errors'],
        'browser_width': metadata.get('width', DEFAULT_BROWSER_WIDTH),
        'browser_height': metadata.get('height', DEFAULT_BROWSER_HEIGHT),
        'map_load_delay_seconds': metadata.get('delay', DEFAULT_MAP_LOAD_DELAY),
        'chrome_headless_mode': CHROME_HEADLESS_MODE,
        'webdriver_timeout_seconds': WEBDRIVER_TIMEOUT,
        'input_file_size_bytes': metadata.get('input_file_size', 0),
        'output_file_size_bytes': metadata.get('output_file_size', 0),
        'html_file_valid': metadata.get('html_file_valid', False),
        'screenshot_successful': metadata.get('screenshot_successful', False),
        'chrome_driver_version': metadata.get('chrome_driver_version', 'unknown'),
        'automation_platform': 'selenium_chrome',
        'performance_optimization_level': 'standard'
    }
    
    # Convert to DataFrame and save
    df = pd.DataFrame([metadata_row])
    df.to_csv(base_path, index=False, encoding='utf-8', float_format='%.3f')
    print(f"[Metadata] Screenshot performance data saved: {base_path}")

def get_file_size(file_path: str) -> int:
    """Get file size in bytes, return 0 if file doesn't exist."""
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError):
        return 0

def capture_screenshot(html_input_path: str, png_output_path: str, width: int = 1200, height: int = 800, delay: int = 5):
    """Captures a screenshot of the HTML map."""
    screenshot_stats['start_time'] = time.time()
    print(f"[Info] Generating screenshot for: {html_input_path}")

    metadata = {
        'input_file': os.path.basename(html_input_path),
        'width': width,
        'height': height,
        'delay': delay,
        'screenshot_successful': False,
        'html_file_valid': False
    }

    # --- Input Validation Stage ---
    validation_start = time.time()
    if not os.path.exists(html_input_path):
        print(f"[Fehler] HTML-Inputdatei nicht gefunden: {html_input_path}")
        screenshot_stats['browser_automation_errors'] += 1
        save_performance_metadata(png_output_path, metadata)
        sys.exit(1)
    
    if not html_input_path.lower().endswith(".html"):
        print(f"[Fehler] Inputdatei ist keine HTML-Datei: {html_input_path}")
        screenshot_stats['browser_automation_errors'] += 1
        save_performance_metadata(png_output_path, metadata)
        sys.exit(1)

    metadata['html_file_valid'] = True
    metadata['input_file_size'] = get_file_size(html_input_path)
    screenshot_stats['file_validation_time'] = time.time() - validation_start

    log_stage("input_validation", screenshot_stats['file_validation_time'], {
        'file_exists': True,
        'file_size_bytes': metadata['input_file_size'],
        'file_extension_valid': True
    })

    # --- Ensure Output Directory Exists ---
    output_dir = os.path.dirname(png_output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # --- Configure Chrome Options ---
    chrome_options = ChromeOptions()
    chrome_options.add_argument(f"--headless={CHROME_HEADLESS_MODE}")
    chrome_options.add_argument(f"--window-size={width},{height}")
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"--log-level={BROWSER_LOG_LEVEL}")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # --- Initialize WebDriver ---
    driver = None
    webdriver_init_start = time.time()
    try:
        print("[Info] Initialisiere WebDriver...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(WEBDRIVER_TIMEOUT)
        
        screenshot_stats['webdriver_init_time'] = time.time() - webdriver_init_start
        print(f"[Info] WebDriver initialisiert ({screenshot_stats['webdriver_init_time']:.2f}s).")
        
        # Try to get Chrome version for metadata
        try:
            capabilities = driver.capabilities
            chrome_version = capabilities.get('browserVersion', 'unknown')
            metadata['chrome_driver_version'] = chrome_version
        except:
            metadata['chrome_driver_version'] = 'unknown'

        log_stage("webdriver_initialization", screenshot_stats['webdriver_init_time'], {
            'chrome_version': metadata['chrome_driver_version'],
            'window_size': f"{width}x{height}",
            'headless_mode': CHROME_HEADLESS_MODE
        })

        # --- Load HTML File ---
        page_load_start = time.time()
        abs_html_path = os.path.abspath(html_input_path)
        file_url = f"file:///{abs_html_path.replace(os.sep, '/')}"
        print(f"[Info] Lade URL: {file_url}")
        
        driver.get(file_url)
        screenshot_stats['page_load_time'] = time.time() - page_load_start
        
        log_stage("page_loading", screenshot_stats['page_load_time'], {
            'url_loaded': file_url,
            'load_method': 'file_protocol'
        })

        # --- Wait for Map to Load ---
        wait_start = time.time()
        print(f"[Info] Warte {delay} Sekunden, damit die Karte laden kann...")
        time.sleep(delay)
        screenshot_stats['total_wait_time'] = time.time() - wait_start

        log_stage("map_loading_wait", screenshot_stats['total_wait_time'], {
            'wait_duration_seconds': delay,
            'wait_strategy': 'fixed_delay'
        })

        # --- Capture Screenshot ---
        capture_start = time.time()
        print("[Info] Erstelle Screenshot...")
        success = driver.save_screenshot(png_output_path)
        screenshot_stats['screenshot_capture_time'] = time.time() - capture_start
        
        if success:
            metadata['screenshot_successful'] = True
            metadata['output_file_size'] = get_file_size(png_output_path)
            print(f"[OK] Screenshot erfolgreich gespeichert: {png_output_path}")
            print(f"[Info] Screenshot-Größe: {metadata['output_file_size']} bytes")
        else:
            screenshot_stats['browser_automation_errors'] += 1
            print(f"[Fehler] Screenshot konnte nicht gespeichert werden (save_screenshot gab False zurück): {png_output_path}")

        log_stage("screenshot_capture", screenshot_stats['screenshot_capture_time'], {
            'capture_successful': success,
            'output_file_size_bytes': metadata['output_file_size'],
            'capture_method': 'selenium_save_screenshot'
        })

        # Save performance metadata
        save_performance_metadata(png_output_path, metadata)

    except Exception as e:
        screenshot_stats['browser_automation_errors'] += 1
        print(f"[Fehler] Fehler während der Screenshot-Erstellung: {e}")
        if "selenium.common.exceptions" in str(type(e)):
             print(f"   (Selenium/WebDriver Fehlerdetails: {getattr(e, 'msg', 'Keine Details')})")
        
        # Save error metadata
        save_performance_metadata(png_output_path, metadata)
        
        if driver:
            driver.quit()
        sys.exit(1)

    finally:
        # --- Clean Up ---
        if driver:
            cleanup_start = time.time()
            print("[Info] Schließe WebDriver...")
            driver.quit()
            cleanup_time = time.time() - cleanup_start
            print(f"[Info] WebDriver geschlossen ({cleanup_time:.2f}s).")
            
            log_stage("webdriver_cleanup", cleanup_time, {
                'cleanup_successful': True
            })

if __name__ == "__main__":
    print_script_info()
    
    parser = argparse.ArgumentParser(description="Generate a PNG screenshot from a Folium HTML map.")
    parser.add_argument("--input-html", required=True, help="Path to the input HTML map file.")
    parser.add_argument("--output-png", required=True, help="Path to save the output PNG screenshot file.")
    parser.add_argument("--width", type=int, default=1200, help="Width of the browser window for screenshot.")
    parser.add_argument("--height", type=int, default=800, help="Height of the browser window for screenshot.")
    parser.add_argument("--delay", type=int, default=5, help="Delay in seconds to wait for the map to load.")
    args = parser.parse_args()

    capture_screenshot(args.input_html, args.output_png, args.width, args.height, args.delay)
