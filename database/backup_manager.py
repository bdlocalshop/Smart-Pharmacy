import os
import shutil
import sqlite3
from datetime import datetime
from database.db import get_db_path

def get_backups_dir():
    """Returns absolute path to the local backups directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backups_dir = os.path.join(base_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir

def create_automated_backup(retention_days=14):
    """
    Creates a timestamped snapshot of the SQLite database.
    Cleans up automated backups older than retention_days.
    Uses SQLite's online backup API for safe zero-corruption live snapshots.
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None

    backups_dir = get_backups_dir()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"smart_pharmacy_auto_{timestamp_str}.db"
    dest_path = os.path.join(backups_dir, backup_filename)

    # Perform safe live backup using SQLite backup API
    src_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(dest_path)
    with dest_conn:
        src_conn.backup(dest_conn)
    dest_conn.close()
    src_conn.close()

    # Prune old automatic backups
    _cleanup_old_backups(backups_dir, retention_days)
    return dest_path

def create_manual_backup(target_directory):
    """
    Creates a manual backup snapshot into a user-selected folder (e.g. USB drive or cloud drive).
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError("Active database file not found.")

    os.makedirs(target_directory, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = os.path.join(target_directory, f"smart_pharmacy_backup_{timestamp_str}.db")

    src_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(dest_path)
    with dest_conn:
        src_conn.backup(dest_conn)
    dest_conn.close()
    src_conn.close()

    return dest_path

def restore_database(source_backup_path):
    """
    Restores the database from a backup file.
    Creates a safety backup of the current database before replacing it.
    """
    if not os.path.exists(source_backup_path):
        raise FileNotFoundError("Selected backup file does not exist.")

    db_path = get_db_path()

    # Take a safety snapshot first if current DB exists
    if os.path.exists(db_path):
        safety_path = db_path + f".before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        shutil.copy2(db_path, safety_path)

    # Restore by copying
    shutil.copy2(source_backup_path, db_path)

    # Also clean up WAL and SHM files if any to prevent state mismatch
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    if os.path.exists(wal_path):
        try: os.remove(wal_path)
        except: pass
    if os.path.exists(shm_path):
        try: os.remove(shm_path)
        except: pass

    return True

def list_existing_backups():
    """Lists all backup files in the local backups folder with metadata."""
    backups_dir = get_backups_dir()
    files = [f for f in os.listdir(backups_dir) if f.endswith(".db") or f.endswith(".bak")]
    backups = []
    for f in files:
        full_path = os.path.join(backups_dir, f)
        stat = os.stat(full_path)
        backups.append({
            "filename": f,
            "path": full_path,
            "size_kb": round(stat.st_size / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %I:%M %p")
        })
    backups.sort(key=lambda x: x["filename"], reverse=True)
    return backups

def _cleanup_old_backups(backups_dir, max_keep=20):
    """Retains the most recent max_keep auto backups."""
    files = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.startswith("smart_pharmacy_auto_")]
    files.sort(key=os.path.getmtime, reverse=True)
    if len(files) > max_keep:
        for old_file in files[max_keep:]:
            try:
                os.remove(old_file)
            except:
                pass
