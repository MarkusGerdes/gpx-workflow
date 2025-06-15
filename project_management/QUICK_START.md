# 🚀 Quick Start Guide für neue Chat-Sessions

## Sofort-Anweisung für Claude

Wenn Sie dieses Dokument in einem neuen Chat öffnen, verwenden Sie diese Anweisung:

```
Ich arbeite am GPX Workflow Strukturierungsprojekt. 

Bitte lese folgende Dateien um den aktuellen Stand zu verstehen:
1. C:\Users\marku\gpx_workflow_GEMINI\project_management\PROJECT_STATUS.md
2. C:\Users\marku\gpx_workflow_GEMINI\project_management\PROJECT_TODO.md  
3. C:\Users\marku\gpx_workflow_GEMINI\project_management\PROGRESS_LOG.md

Danach können wir an der Strukturierung weiterarbeiten.
```

## Projekt-Kontext (Backup-Info)

**Was:** GPX Workflow für Fahrrad-Touren Analyse  
**Wo:** `C:\Users\marku\gpx_workflow_GEMINI\`  
**Problem:** Scripts unorganisiert, Output-Chaos, Versioning fehlt  
**Ziel:** Systematische Strukturierung & Modernisierung  

## Wichtige Dateien für Kontext

1. **PROJECT_STATUS.md** - Aktueller Stand & Fokus
2. **PROJECT_TODO.md** - Detaillierte Aufgabenliste  
3. **PROGRESS_LOG.md** - Was wurde bereits gemacht
4. **scripts/11_generate_stage_summary.py** - Versioning-Referenz
5. **config_editor.py** - Streamlit Tool (braucht Update)

## Schnell-Befehle

```bash
# Config Editor starten
streamlit run config_editor.py

# Projektstruktur anzeigen  
ls -la scripts/ | head -20

# Aktuellen Status checken
cat project_management/PROJECT_STATUS.md
```

## Aktuelle Priorität

**SOFORT:** Versioning-System etablieren basierend auf `11_generate_stage_summary.py`

---

*Diese Datei dient als schneller Einstieg in neue Chat-Sessions*