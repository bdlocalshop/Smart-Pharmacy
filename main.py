"""
Smart Pharmacy Desktop Application
Main Entry Point
"""

import sys
import os

# Ensure current directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
from database.backup_manager import create_automated_backup
from ui.app_window import AppWindow

def main():
    print("Initializing Smart Pharmacy Database...")
    init_db()

    print("Executing automated rolling snapshot...")
    try:
        backup_path = create_automated_backup(retention_days=14)
        if backup_path:
            print(f"Automated backup snapshot created: {backup_path}")
    except Exception as e:
        print(f"Warning: Automated backup error: {e}")

    print("Launching Desktop Application Window...")
    app = AppWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
