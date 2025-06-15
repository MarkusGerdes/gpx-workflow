#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_project_docs.py
Simple script to help update project documentation.
"""

SCRIPT_VERSION = "1.0.0"
LAST_UPDATED = "2025-06-07"

import os
from datetime import datetime
from pathlib import Path

def update_progress_log(work_done_today, time_spent, next_steps):
    """
    Hilft beim Update des Progress Logs
    """
    project_mgmt = Path(__file__).parent / "project_management"
    progress_file = project_mgmt / "PROGRESS_LOG.md"
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    new_entry = f"""
## 📅 {today} - Arbeitsession

### 🕐 Zeitraum: {time_spent}

### ✅ Durchgeführt:
{work_done_today}

### 🎯 Nächste Schritte:
{next_steps}

---

"""
    
    print("=== NEUER PROGRESS LOG EINTRAG ===")
    print(new_entry)
    print("\n>>> Kopieren Sie diesen Text in PROGRESS_LOG.md <<<")
    
    return new_entry

def update_status_dashboard(current_focus, completed_tasks):
    """
    Hilft beim Update des Status Dashboards
    """
    print("=== STATUS UPDATE ===")
    print(f"Aktueller Fokus: {current_focus}")
    print(f"Erledigte Aufgaben: {completed_tasks}")
    print("\n>>> Aktualisieren Sie PROJECT_STATUS.md entsprechend <<<")

if __name__ == "__main__":
    print("=== PROJECT DOCUMENTATION UPDATER ===\n")
    
    # Sammle Informationen
    work_done = input("Was wurde heute gemacht? (Bulletpoints): ")
    time_spent = input("Wie lange gearbeitet? (z.B. '2h am Nachmittag'): ")
    next_steps = input("Nächste 3 Prioritäten? (Bulletpoints): ")
    
    # Generiere Updates
    update_progress_log(work_done, time_spent, next_steps)
    
    current_focus = input("\nNeuer Fokus für nächste Session? ")
    completed = input("Welche ToDos sind erledigt? ")
    
    update_status_dashboard(current_focus, completed)
    
    print("\n=== FERTIG ===")
    print("Kopieren Sie die generierten Texte in die entsprechenden MD-Dateien!")
