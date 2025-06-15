###############################################################################
#  Snakefile – KORRIGIERTE Version ohne Duplikate
###############################################################################
import os
import glob

# --------------------------------------------------------------------------- #
# 1) Konfiguration
# --------------------------------------------------------------------------- #
configfile: "config.yaml"

# --------------------------------------------------------------------------- #
# 2) Dynamische Eingabedateien
# --------------------------------------------------------------------------- #
gpx_files      = glob.glob("data/*.gpx")
gpx_basenames  = [os.path.splitext(os.path.basename(f))[0] for f in gpx_files]
print(f"DEBUG: gpx_basenames = {gpx_basenames}")

# --------------------------------------------------------------------------- #
# 3) Finale Targets
# --------------------------------------------------------------------------- #
rule all:
    input:
        # Basis-Pipeline zuerst (wichtige Visualisierungen)
        expand("output/3_{basename}_peak_analysis_profile.png", basename=gpx_basenames),
        expand("output/3b_{basename}_speed_profile.png", basename=gpx_basenames),
        expand("output/10c_{basename}_power_visualization.png", basename=gpx_basenames),
        expand("output/10d_{basename}_detailed_power_analysis.txt", basename=gpx_basenames),
        expand("output/10d_{basename}_detailed_power_analysis.md", basename=gpx_basenames),
        # Finale Outputs
        expand("output/11_{basename}_stage_summary_final.html", basename=gpx_basenames),
        expand("output/11_{basename}_stage_summary_final.pdf",  basename=gpx_basenames),
        expand("output/extra_{basename}_track_3d_plotly_full.html", basename=gpx_basenames),
        expand("output/12_{basename}_for_notebooklm.md", basename=gpx_basenames)

# --------------------------------------------------------------------------- #
# 4) Workflow‑Schritte - KORREKTE REIHENFOLGE OHNE DUPLIKATE
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Schritt 2 – GPX → CSV (volle Auflösung)
# --------------------------------------------------------------------------- #
rule parse_full_gpx:
    input:
        gpx="data/{basename}.gpx"
    output:
        csv="output/2_{basename}_track_data_full.csv"
    log:
        "logs/2_{basename}_parse_gpx_full.log"
    shell:
        """
        python scripts/2_parse_gpx_full.py "{input.gpx}" "{output.csv}" > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 2b – vereinfacht → API‑Track
# --------------------------------------------------------------------------- #
rule create_api_optimized_track:
    input:
        full_track_csv="output/2_{basename}_track_data_full.csv"
    output:
        csv="output/2b_{basename}_track_data_api_optimized.csv"
    params:
        epsilon=config.get("rdp_epsilon", 0.0001)
    log:
        "logs/2b_{basename}_simplify_track_api.log"
    shell:
        """
        python scripts/2b_simplify_gpx_api.py \
            --input-csv "{input.full_track_csv}" \
            --output "{output.csv}" \
            --epsilon {params.epsilon} \
            > "{log}" 2>&1
        """

# Festlegen, ob es sich um eine Simulation handelt
IS_SIMULATION = config.get("power_estimation", {}).get("target_power_watts") is not None

rule power_processing:
    input:
        # Wählt die richtige Input-Datei basierend auf dem Modus
        track_csv= "output/2c_{basename}_track_data_full_with_elevation.csv" if IS_SIMULATION 
                   else "output/2d_{basename}_track_data_full_with_speed.csv",
        surface_data="output/4b_{basename}_surface_data.csv"
    output:
        power_data="output/10b_{basename}_power_data.csv"
    params:
        mass_kg=config["power_estimation"]["total_mass_kg"],
        position_key=config["power_estimation"]["rider_position_cda_key"],
        # Fügt den Target-Power-Parameter nur hinzu, wenn er in der Config existiert
        target_power_param= f'--target-power {config["power_estimation"]["target_power_watts"]}' if IS_SIMULATION else ""
    log:
        "logs/10b_{basename}_power_processing.log"
    shell:
        """
        python scripts/10b_power_processing.py \
            --track-csv "{input.track_csv}" \
            --surface-csv "{input.surface_data}" \
            --output-csv "{output.power_data}" \
            --mass {params.mass_kg} \
            --position "{params.position_key}" \
            {params.target_power_param} \
            > "{log}" 2>&1
        """


# --------------------------------------------------------------------------- #
# Schritt 2c – Höhendaten ergänzen
# --------------------------------------------------------------------------- #
rule add_elevation_data:
    input:
        track_csv="output/2_{basename}_track_data_full.csv"
    output:
        track_with_elevation="output/2c_{basename}_track_data_full_with_elevation.csv"
    params:
        batch_size=config.get("elevation_batch_size", 100),
    log:
        "logs/2c_{basename}_add_elevation.log"
    shell:
        """
        python scripts/2c_add_elevation.py \
            --input-csv "{input.track_csv}" \
            --output-csv "{output.track_with_elevation}" \
            --batch-size {params.batch_size} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 2d – Geschwindigkeit berechnen
# --------------------------------------------------------------------------- #
rule calculate_speed:
    input:
        track_with_elevation="output/2c_{basename}_track_data_full_with_elevation.csv"
    output:
        track_with_speed="output/2d_{basename}_track_data_full_with_speed.csv"
    params:
        rolling_window=config.get("speed_profile", {}).get("smooth_window", 0)
    log:
        "logs/2d_{basename}_calculate_speed.log"
    shell:
        """
        python scripts/2d_calculate_speed.py "{input.track_with_elevation}" "{output.track_with_speed}" \
            --rolling-window {params.rolling_window} > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 3b – Speed Profile Plot
# --------------------------------------------------------------------------- #
rule plot_speed_profile:
    input:
        track_with_speed="output/2d_{basename}_track_data_full_with_speed.csv"
    output:
        plot="output/3b_{basename}_speed_profile.png"
    params:
        smooth_col_name=(
        f'Geschwindigkeit geglättet (km/h, W{config.get("speed_profile", {}).get("smooth_window", 0)})'
        if config.get("speed_profile", {}).get("smooth_window", 0) > 1 
        else ""
)
    log:
        "logs/3b_{basename}_plot_speed_profile.log"
    shell:
        """
        python scripts/3b_plot_speed_profile.py "{input.track_with_speed}" "{output.plot}" \
            --smooth-col-name "{params.smooth_col_name}" > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 4 – Reverse Geocoding (MUSS VOR 4b KOMMEN!)
# --------------------------------------------------------------------------- #
rule reverse_geocode:
    input:
        track_csv="output/2b_{basename}_track_data_api_optimized.csv"
    output:
        csv="output/4_{basename}_track_data_with_location_optimized.csv"
    params:
        sampling_distance_km=config["geocoding"]["sampling_distance_km"],
        cache_db=config.get("geocoding", {}).get("cache_db_path", "output/SQLliteDB/geocoding_cache.db"),
        cache_tolerance_km=config.get("geocoding", {}).get("cache_tolerance_km", 0.1),
        force_api_flag="--force-api" if config.get("geocoding", {}).get("force_api", False) else ""
    log:
        "logs/4_{basename}_reverse_geocode_optimized.log"
    shell:
        """
        python scripts/GPX_Workflow_SQLiteCaching.py \
            --input-csv "{input.track_csv}" \
            --output-csv "{output.csv}" \
            --sampling-dist {params.sampling_distance_km} \
            --cache-db "{params.cache_db}" \
            --cache-tolerance {params.cache_tolerance_km} \
            {params.force_api_flag} \
            --verbose \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 4b – Oberflächendaten mit SQLite Cache (NACH Schritt 4!)
# --------------------------------------------------------------------------- #
rule fetch_surface_data:
    input:
        track_csv_with_location_and_index="output/4_{basename}_track_data_with_location_optimized.csv",
        full_track_with_elevation="output/2c_{basename}_track_data_full_with_elevation.csv"
    output:
        csv="output/4b_{basename}_surface_data.csv"
    params:
        query_radius_m=config.get("surface_query", {}).get("query_radius_m", 80),
        dist_col_ref_name=config.get("surface_query", {}).get("reference_distance_column_name", "Distanz (km)"),
        cache_db="output/SQLliteDB/surface_cache.db",
        cache_tolerance=config.get("surface_query", {}).get("cache_tolerance_km", 0.1),
        force_api_flag="--force-api" if config.get("surface_query", {}).get("force_api", False) else "",
        verbose_flag="--verbose" if config.get("surface_query", {}).get("verbose", True) else ""
    log:
        "logs/4b_{basename}_fetch_surface_data.log"
    run:
        import subprocess
        import os
        
        # SQLite-Verzeichnis erstellen
        os.makedirs(os.path.dirname(params.cache_db), exist_ok=True)
        
        # Command zusammenbauen
        cmd = [
            "python", "scripts/4b_fetch_surface_grouped_SQLiteCache.py",
            "--input-csv", str(input.track_csv_with_location_and_index),
            "--full-track-ref-csv", str(input.full_track_with_elevation),
            "--output-csv", str(output.csv),
            "--cache-db", str(params.cache_db),
            "--cache-tolerance", str(params.cache_tolerance),
            "--radius", str(params.query_radius_m),
            "--dist-col-ref", str(params.dist_col_ref_name)
        ]
        
        # Optionale Flags
        if params.force_api_flag:
            cmd.append(str(params.force_api_flag))
        if params.verbose_flag:
            cmd.append(str(params.verbose_flag))
        
        # Script ausführen mit Logging
        with open(str(log[0]), 'w') as log_file:
            try:
                log_file.write(f"Running command: {' '.join(cmd)}\n")
                log_file.flush()
                
                result = subprocess.run(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                    text=True
                )
                
                log_file.write(f"\nScript exit code: {result.returncode}\n")
                log_file.write(f"Output file exists: {os.path.exists(str(output.csv))}\n")
                
                # Fallback wenn Script fehlschlägt
                if result.returncode != 0 or not os.path.exists(str(output.csv)):
                    log_file.write(f"Script failed, creating placeholder...\n")
                    with open(str(output.csv), 'w') as f:
                        f.write("Distanz (km),surface_type,confidence,lat,lon\n")
                        f.write("0.0,unknown,0.0,0.0,0.0\n")
                    log_file.write("Placeholder created successfully\n")
                    
            except Exception as e:
                log_file.write(f"Exception occurred: {str(e)}\n")
                # Notfall-Platzhalter
                with open(str(output.csv), 'w') as f:
                    f.write("Distanz (km),surface_type,confidence,lat,lon\n")
                    f.write("0.0,unknown,0.0,0.0,0.0\n")
                log_file.write("Emergency placeholder created\n")
# --------------------------------------------------------------------------- #
# Schritt 5a – Service‑POIs
# --------------------------------------------------------------------------- #
rule fetch_pois_service:
    input:
        track_csv="output/4_{basename}_track_data_with_location_optimized.csv"
    output:
        csv="output/5a_{basename}_pois_service_raw.csv"
    params:
        radius_m=config.get("poi_radius_m", 500),
        sampling_distance_km=config.get("poi_sampling_distance_km", 0.5),
    log:
        "logs/5a_{basename}_fetch_pois_service.log"
    shell:
        """
        python scripts/5a_fetch_service_pois.py \
            --input "{input.track_csv}" \
            --output "{output.csv}" \
            --radius {params.radius_m} \
            --sampling {params.sampling_distance_km} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 5b – Peaks / Viewpoints via BBOX
# --------------------------------------------------------------------------- #
rule fetch_peaks_viewpoints_bbox:
    input:
        gpx="data/{basename}.gpx"
    output:
        json="output/5b_{basename}_peaks_viewpoints_bbox.json"
    params:
        buffer_degrees=config.get("peak_buffer_degrees", 0.05),
    log:
        "logs/5b_{basename}_fetch_peaks_viewpoints.log"
    shell:
        """
        python scripts/5b_fetch_peaks_viewpoints_bbox.py \
            --input-gpx "{input.gpx}" \
            --output-json "{output.json}" \
            --buffer {params.buffer_degrees} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 5c – POIs zusammenführen & filtern
# --------------------------------------------------------------------------- #
rule merge_and_filter_pois:
    input:
        service_pois="output/5a_{basename}_pois_service_raw.csv",
        peak_pois="output/5b_{basename}_peaks_viewpoints_bbox.json",
        full_track_csv="output/2c_{basename}_track_data_full_with_elevation.csv"
    output:
        csv="output/5c_{basename}_pois_relevant.csv"
    params:
        max_dist_service_km=config["poi"]["max_dist_service_km"],
        max_dist_viewpoint_km=config["poi"]["max_dist_viewpoint_km"],
    log:
        "logs/5c_{basename}_merge_filter_pois.log"
    shell:
        """
        python scripts/5c_merge_filter_pois.py \
            --service-pois "{input.service_pois}" \
            --peak-pois "{input.peak_pois}" \
            --full-track "{input.full_track_csv}" \
            --output "{output.csv}" \
            --max-dist-service-km {params.max_dist_service_km} \
            --max-dist-viewpoint-km {params.max_dist_viewpoint_km} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 6 – Interaktive Karte
# --------------------------------------------------------------------------- #
rule generate_map:
    input:
        track_csv="output/2c_{basename}_track_data_full_with_elevation.csv",
        pois_csv="output/5c_{basename}_pois_relevant.csv",
        reduced_track_csv="output/2b_{basename}_track_data_api_optimized.csv",
        surface_data="output/4b_{basename}_surface_data.csv"
    output:
        map_html="output/6_{basename}_map_full.html"
    log:
        "logs/6_{basename}_generate_map_full.log"
    shell:
        """
        python scripts/6_generate_map.py \
            --track-csv "{input.track_csv}" \
            --pois-csv "{input.pois_csv}" \
            --reduced-track-csv "{input.reduced_track_csv}" \
            --surface-data-csv "{input.surface_data}" \
            --output-html "{output.map_html}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 7 – Signifikante Orte extrahieren
# --------------------------------------------------------------------------- #
rule extract_significant_places:
    input:
        track_csv="output/4_{basename}_track_data_with_location_optimized.csv"
    output:
        summary_csv="output/7_{basename}_places_summary_optimized.csv"
    log:
        "logs/7_{basename}_extract_places_optimized.log"
    shell:
        """
        python scripts/7_extract_significant_places.py \
            --input-csv "{input.track_csv}" \
            --output-csv "{output.summary_csv}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 8 – Orte entlang der Route sortieren
# --------------------------------------------------------------------------- #
rule sort_places_by_route:
    input:
        track_csv="output/4_{basename}_track_data_with_location_optimized.csv",
        places_csv="output/7_{basename}_places_summary_optimized.csv"
    output:
        sorted_csv="output/8_{basename}_places_sorted_optimized.csv"
    log:
        "logs/8_{basename}_sort_places_optimized.log"
    shell:
        """
        python scripts/8_sort_places_by_route.py \
            --track-csv "{input.track_csv}" \
            --places-csv "{input.places_csv}" \
            --output-csv "{output.sorted_csv}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 8b – Ortsnamen geokodieren
# --------------------------------------------------------------------------- #
rule geocode_places:
    input:
        sorted_places="output/8_{basename}_places_sorted_optimized.csv"
    output:
        places_with_coords="output/8b_{basename}_places_with_coords.csv"
    params:
        country_context=config.get("geocoding_country_context", ""),
    log:
        "logs/8b_{basename}_geocode_places.log"
    shell:
        """
        python scripts/8b_geocode_places.py \
            --input-csv "{input.sorted_places}" \
            --output-csv "{output.places_with_coords}" \
            --context "{params.country_context}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 8c - Orte anreichern und filtern
# --------------------------------------------------------------------------- #
rule enrich_and_filter_places:
    input:
        places_with_coords = "output/8b_{basename}_places_with_coords.csv",
        full_track_csv     = "output/2c_{basename}_track_data_full_with_elevation.csv"
    output:
        relevant_places    = "output/8c_{basename}_places_relevant_enriched.csv"
    params:
        max_dist_meters = config.get("place_filtering", {}).get("max_dist_center_to_route_m", -1.0),
        min_occurrences = config.get("place_filtering", {}).get("min_occurrences", -1),
    log:
        "logs/8c_{basename}_enrich_filter_places.log"
    shell:
        """
        python scripts/8c_enrich_filter_places.py \
            --places-coords-csv "{input.places_with_coords}" \
            --full-track-csv "{input.full_track_csv}" \
            --output-csv "{output.relevant_places}" \
            --max-dist {params.max_dist_meters} \
            --min-occ {params.min_occurrences} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 3 – Peak‑Analyse & Profilplot (NACH allen Voraussetzungen!)
# --------------------------------------------------------------------------- #
rule analyze_peaks_and_plot:
    input:
        track_csv="output/2c_{basename}_track_data_full_with_elevation.csv",
        places_coords="output/8c_{basename}_places_relevant_enriched.csv",
        relevant_pois="output/5c_{basename}_pois_relevant.csv",
        surface_data="output/4b_{basename}_surface_data.csv"
    output:
        plot="output/3_{basename}_peak_analysis_profile.png",
        peak_data="output/3_{basename}_peak_segment_data.csv",
        stats="output/3_{basename}_overall_stats.csv"
    params:
        smooth_window=config.get("profile_analysis", {}).get("smooth_window", 11),
        smooth_poly=config.get("profile_analysis", {}).get("smooth_poly", 2),
        gain_threshold=config.get("profile_analysis", {}).get("gain_threshold", 30.0),
        eps_height=config.get("profile_analysis", {}).get("eps_height", 0.3),
        prominence=config.get("profile_analysis", {}).get("min_peak_prominence_m", 40.0),
        peak_edge_km=config.get("profile_analysis", {}).get("peak_edge_km", 0.25),
        plot_dpi=config.get("profile_analysis", {}).get("plot_dpi", 150),
        plot_x_tick_major=config.get("profile_analysis", {}).get("plot_x_tick_major", 5.0),
        plot_x_tick_minor=config.get("profile_analysis", {}).get("plot_x_tick_minor", 1.0),
        pause_min_duration=config.get("profile_analysis", {}).get("pause_min_duration_s", 120.0),
        pause_max_distance=config.get("profile_analysis", {}).get("pause_max_distance_m", 5.0),
    log: "logs/3_{basename}_analyze_peaks_plot.log"
    shell:
        """
        python scripts/3_analyze_peaks_plot.py \
            --input-csv "{input.track_csv}" \
            --output-plot "{output.plot}" \
            --output-peak-csv "{output.peak_data}" \
            --output-stats-csv "{output.stats}" \
            --smooth-window {params.smooth_window} \
            --smooth-poly {params.smooth_poly} \
            --gain-threshold {params.gain_threshold} \
            --eps-height {params.eps_height} \
            --prominence {params.prominence} \
            --peak-edge-km {params.peak_edge_km} \
            --plot-dpi {params.plot_dpi} \
            --plot-x-tick-major {params.plot_x_tick_major} \
            --plot-x-tick-minor {params.plot_x_tick_minor} \
            --pause-min-duration {params.pause_min_duration} \
            --pause-max-distance {params.pause_max_distance} \
            --places-coords-csv "{input.places_coords}" \
            --relevant-pois-csv "{input.relevant_pois}" \
            --surface-data-csv "{input.surface_data}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 3D – 3D Visualisierung
# --------------------------------------------------------------------------- #
rule generate_3d_plotly_map_with_pois_and_surfaces:
    input:
        track_csv_with_surface="output/4b_{basename}_surface_data.csv",
        relevant_pois="output/5c_{basename}_pois_relevant.csv",
        relevant_places="output/8c_{basename}_places_relevant_enriched.csv"
    output:
        html_3d_map="output/extra_{basename}_track_3d_plotly_full.html"
    log:
        "logs/extra_{basename}_generate_3d_plotly_full.log"
    params:
        exaggeration=config.get("plotly_3d_map", {}).get("vertical_exaggeration", 5.0),
        title_prefix=config.get("plotly_3d_map", {}).get("title_prefix_full", "3D Ansicht mit POIs & Oberfläche"),
        default_line_width=config.get("plotly_3d_map", {}).get("line_width", 4),
        optional_yaml_arg=lambda config: \
            f"--surface-colors-yaml {config.get('plotly_3d_map', {}).get('surface_colors_yaml')}" \
            if config.get('plotly_3d_map', {}).get('surface_colors_yaml') else ""
    shell:
        """
        python scripts/06b_generate_3d_plotly_map.py \
            --track-csv "{input.track_csv_with_surface}" \
            --pois-csv "{input.relevant_pois}" \
            --places-csv "{input.relevant_places}" \
            --output-html "{output.html_3d_map}" \
            --exaggeration {params.exaggeration} \
            --title-prefix "{params.title_prefix}" \
            --line-width {params.default_line_width} \
            {params.optional_yaml_arg} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 9 – Gemini‑Beschreibung
# --------------------------------------------------------------------------- #
rule query_gemini_places:
    input:
        sorted_places_csv="output/8c_{basename}_places_relevant_enriched.csv"
    output:
        markdown_file="output/9_{basename}_day_preview_places.md"
    log:
        "logs/9_{basename}_query_gemini_places.log"
    params:
        place_column_param=config.get("gemini_wiki", {}).get("place_column", ""),
        country_context_param=config.get("gemini_wiki", {}).get("country_context", ""),
        wiki_lang_param=config.get("gemini_wiki", {}).get("wiki_lang", "AUTO"),
        max_wiki_chars_param=config.get("gemini_wiki", {}).get("max_wiki_chars", 500),
    shell:
        """
        python scripts/9_query_gemini_with_wiki.py \
            --input-csv "{input.sorted_places_csv}" \
            --output-md "{output.markdown_file}" \
            --place-column "{params.place_column_param}" \
            --country-context "{params.country_context_param}" \
            --wiki-lang "{params.wiki_lang_param}" \
            --max-wiki-chars {params.max_wiki_chars_param} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 10 – Karten‑Screenshot
# --------------------------------------------------------------------------- #
rule screenshot_map:
    input:
        html_map="output/6_{basename}_map_full.html"
    output:
        png_map="output/6_{basename}_map_full.png"
    params:
        width = config.get("screenshot_width", 1200),
        height = config.get("screenshot_height", 800),
        delay = config.get("screenshot_delay", 5),
    log:
        "logs/10_{basename}_map_screenshot_full.log"
    shell:
        """
        python scripts/10_generate_map_screenshot.py \
            --input-html "{input.html_map}" \
            --output-png "{output.png_map}" \
            --width {params.width} \
            --height {params.height} \
            --delay {params.delay} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 10d – Detailed Power Analysis
# --------------------------------------------------------------------------- #
rule detailed_power_analysis:
    input:
        power_data="output/10b_{basename}_power_data.csv"
    output:
        analysis_report="output/10d_{basename}_detailed_power_analysis.txt",
        markdown_report="output/10d_{basename}_detailed_power_analysis.md"
    params:
        ftp_watts=config.get("power_analysis", {}).get("ftp_watts", ""),
        rider_weight_kg=config.get("power_estimation", {}).get("rider_weight_kg", "")
    log:
        "logs/10d_{basename}_detailed_power_analysis.log"
    run:
        import subprocess
        import os
        
        # Build command
        cmd = [
            "python", "scripts/10d_detailed_power_analysis.py",
            "--power-csv", str(input.power_data),
            "--markdown"  # Always generate markdown version
        ]
        
        # Add optional parameters
        if params.ftp_watts:
            cmd.extend(["--ftp", str(params.ftp_watts)])
        
        if params.rider_weight_kg:
            cmd.extend(["--rider-weight", str(params.rider_weight_kg)])
        
        # Execute with logging
        with open(str(log[0]), 'w', encoding='utf-8') as log_file:
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=True,
                    encoding='utf-8'
                )
                
                # Write output to report file with UTF-8 encoding
                with open(str(output.analysis_report), 'w', encoding='utf-8') as f:
                    f.write(result.stdout)
                
                log_file.write(f"Command: {' '.join(cmd)}\n")
                log_file.write("Analysis completed successfully\n")
                log_file.write(f"Text report: {output.analysis_report}\n")
                log_file.write(f"Markdown report: {output.markdown_report}\n")
                
            except subprocess.CalledProcessError as e:
                log_file.write(f"Command: {' '.join(cmd)}\n")
                log_file.write(f"Error: {e}\n")
                log_file.write(f"Output: {e.stdout}\n")
                raise

# --------------------------------------------------------------------------- #
# Schritt 10c – Power Visualization
# --------------------------------------------------------------------------- #
rule power_visualization:
    input:
        power_data="output/10b_{basename}_power_data.csv",
        surface_data="output/4b_{basename}_surface_data.csv"
    output:
        png_viz="output/10c_{basename}_power_visualization.png"
    params:
        smooth_window=config.get("power_visualization", {}).get("smooth_window", 20),
        target_points=config.get("power_visualization", {}).get("max_points", 4000),
        gradient_threshold=config.get("power_visualization", {}).get("gradient_threshold", 2.0)
    log:
        "logs/10c_{basename}_power_visualization.log"
    shell:
        """
        python scripts/10c_power_visualization.py \
            "{input.power_data}" \
            "{input.surface_data}" \
            "{output.png_viz}" \
            --target-points {params.target_points} \
            --gradient-threshold {params.gradient_threshold} \
            --smooth-window {params.smooth_window} \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 11 – Stage‑Summary (HTML + PDF)
# --------------------------------------------------------------------------- #
rule generate_stage_summary:
    input:
        overall_stats = "output/3_{basename}_overall_stats.csv",
        profile_png   = "output/3_{basename}_peak_analysis_profile.png",
        speed_profile_png = "output/3b_{basename}_speed_profile.png",
        track_with_speed = "output/2d_{basename}_track_data_full_with_speed.csv",
        plotly_3d_html = "output/extra_{basename}_track_3d_plotly_full.html",
        peak_data     = "output/3_{basename}_peak_segment_data.csv",
        geocoded_opt_csv = "output/4_{basename}_track_data_with_location_optimized.csv",
        surface_data  = "output/4b_{basename}_surface_data.csv",
        map_html      = "output/6_{basename}_map_full.html",
        map_png       = "output/6_{basename}_map_full.png",
        markdown_text = "output/9_{basename}_day_preview_places.md",
        sorted_places = "output/8c_{basename}_places_relevant_enriched.csv", 
        pois_csv = "output/5c_{basename}_pois_relevant.csv",                 
        track_csv_with_elevation = "output/2c_{basename}_track_data_full_with_elevation.csv",
        input_csv_step2 = "output/2_{basename}_track_data_full.csv",
        service_pois_csv = "output/5a_{basename}_pois_service_raw.csv",
        peak_pois_json = "output/5b_{basename}_peaks_viewpoints_bbox.json",
        power_visualization_png = "output/10c_{basename}_power_visualization.png"
    output:
        html_summary="output/11_{basename}_stage_summary_final.html",
        pdf_summary="output/11_{basename}_stage_summary_final.pdf"
    log:
        "logs/11_{basename}_generate_stage_summary_final.log"
    params:
        basename="{basename}",
        dist_col_name_in_surface_report=config.get("surface_query", {}).get("reference_distance_column_name", "Distanz (km)")
    shell:
        """
        python scripts/11_generate_stage_summary.py \
            --basename "{params.basename}" \
            --stats-csv "{input.overall_stats}" \
            --profile-png "{input.profile_png}" \
            --speed-profile-png "{input.speed_profile_png}" \
            --track-csv-with-speed "{input.track_with_speed}" \
            --plotly-3d-html "{input.plotly_3d_html}" \
            --peak-csv "{input.peak_data}" \
            --geocoded-opt-csv "{input.geocoded_opt_csv}" \
            --surface-data "{input.surface_data}" \
            --map-html "{input.map_html}" \
            --dist-col-name-from-config "{params.dist_col_name_in_surface_report}" \
            --map-png "{input.map_png}" \
            --markdown-text "{input.markdown_text}" \
            --sorted-places "{input.sorted_places}" \
            --pois-csv "{input.pois_csv}" \
            --track-csv-with-elevation "{input.track_csv_with_elevation}" \
            --input-csv-step2 "{input.input_csv_step2}" \
            --service-pois-csv "{input.service_pois_csv}" \
            --peak-pois-json "{input.peak_pois_json}" \
            --power-visualization-png "{input.power_visualization_png}" \
            --output-html "{output.html_summary}" \
            --output-pdf "{output.pdf_summary}" \
            --config-file "config.yaml" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# Schritt 12 – NotebookLM Vorbereitung
# --------------------------------------------------------------------------- #
rule prepare_for_notebooklm:
    input:
        stats="output/3_{basename}_overall_stats.csv",
        peaks="output/3_{basename}_peak_segment_data.csv",
        surface="output/4b_{basename}_surface_data.csv",
        pois="output/5c_{basename}_pois_relevant.csv",
        places="output/8c_{basename}_places_relevant_enriched.csv",
        gemini_md="output/9_{basename}_day_preview_places.md"
    output:
        notebooklm_file="output/12_{basename}_for_notebooklm.md"
    params:
        basename="{basename}",
        dist_col=config.get("surface_query", {}).get("reference_distance_column_name", "Distanz (km)")
    log:
        "logs/12_{basename}_prepare_notebooklm.log"
    shell:
        """
        python scripts/12_prepare_for_notebooklm.py \
            --basename "{params.basename}" \
            --stats-csv "{input.stats}" \
            --peak-csv "{input.peaks}" \
            --surface-data "{input.surface}" \
            --dist-col-name-from-config "{params.dist_col}" \
            --pois-csv "{input.pois}" \
            --places-csv "{input.places}" \
            --gemini-md "{input.gemini_md}" \
            --output-md "{output.notebooklm_file}" \
            > "{log}" 2>&1
        """

# --------------------------------------------------------------------------- #
# ERGÄNZENDE REGELN: Cache-Verwaltung (Optional)
# --------------------------------------------------------------------------- #

# Cache-Statistiken nach Verarbeitung (Windows-kompatibel)
rule surface_cache_stats:
    input:
        surface_data="output/4b_{basename}_surface_data.csv"
    params:
        cache_db="output/SQLliteDB/surface_cache.db"
    shell:
        """
        echo "Surface Cache Statistiken nach Verarbeitung von {wildcards.basename}:"
        python scripts/Surface_SQLite_administration.py stats --cache-db "{params.cache_db}" 2>NUL || echo "Cache-Status konnte nicht abgerufen werden"
        """

# Import bestehender Surface-Daten (Windows-kompatibel)
rule import_existing_surface_data:
    output:
        done="output/SQLliteDB/surface_import.done"
    params:
        input_dir="output",
        cache_db="output/SQLliteDB/surface_cache.db"
    shell:
        """
        python -c "import os; os.makedirs('output/SQLliteDB', exist_ok=True)"
        
        python scripts/import_existing_surface_data.py \
            --input-dir "{params.input_dir}" \
            --cache-db "{params.cache_db}" \
            --check-duplicates \
            --verbose 2>NUL || echo "Import fehlgeschlagen oder keine Daten gefunden"
        
        echo "Import completed" > {output.done}
        """

###############################################################################
#  EOF – leere Zeile nach POSIX‑Konvention
###############################################################################