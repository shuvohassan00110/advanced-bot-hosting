# -*- coding: utf-8 -*-
"""
Database operations
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from config import DB_PATH, OWNER_ID, ADMIN_ID

def now_iso() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat(timespec="seconds")

def db_connect():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_database():
    """Initialize all database tables"""
    conn = db_connect()
    c = conn.cursor()
    
    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        join_date TEXT,
        last_active TEXT,
        active_project_id INTEGER
    )
    """)
    
    # Admins table
    c.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    )
    """)
    
    # Banned users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS banned_users(
        user_id INTEGER PRIMARY KEY,
        banned_date TEXT,
        reason TEXT,
        banned_by INTEGER
    )
    """)
    
    # Premium subscriptions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions(
        user_id INTEGER PRIMARY KEY,
        expiry TEXT,
        granted_by INTEGER,
        granted_at TEXT
    )
    """)
    
    # Projects table
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects(
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        entry_file TEXT,
        language TEXT,
        auto_restart INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        description TEXT,
        UNIQUE(user_id, name)
    )
    """)
    
    # Files table
    c.execute("""
    CREATE TABLE IF NOT EXISTS files(
        user_id INTEGER,
        project_id INTEGER,
        file_name TEXT,
        file_type TEXT,
        file_size INTEGER,
        upload_date TEXT,
        PRIMARY KEY(user_id, project_id, file_name)
    )
    """)
    
    # Favorites table
    c.execute("""
    CREATE TABLE IF NOT EXISTS favorites(
        user_id INTEGER,
        project_id INTEGER,
        file_name TEXT,
        PRIMARY KEY(user_id, project_id, file_name)
    )
    """)
    
    # Statistics table
    c.execute("""
    CREATE TABLE IF NOT EXISTS bot_stats(
        stat_name TEXT PRIMARY KEY,
        stat_value INTEGER DEFAULT 0
    )
    """)
    
    # Initialize stats
    stats = ["total_uploads", "total_downloads", "total_runs", "total_restarts", "total_template_installs"]
    for stat in stats:
        c.execute("INSERT OR IGNORE INTO bot_stats(stat_name, stat_value) VALUES(?, 0)", (stat,))
    
    # Environment variables table
    c.execute("""
    CREATE TABLE IF NOT EXISTS env_vars(
        user_id INTEGER,
        project_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY(user_id, project_id, key)
    )
    """)
    
    # Installed packages table
    c.execute("""
    CREATE TABLE IF NOT EXISTS installed_packages(
        user_id INTEGER,
        project_id INTEGER,
        package_name TEXT,
        version TEXT,
        installed_at TEXT,
        PRIMARY KEY(user_id, project_id, package_name)
    )
    """)
    
    # Add default admins
    c.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (OWNER_ID,))
    c.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (ADMIN_ID,))
    
    conn.commit()
    conn.close()

# =============================================================================
# USER OPERATIONS
# =============================================================================

def ensure_user(user_id: int, username: str = None, full_name: str = None):
    """Ensure user exists in database"""
    conn = db_connect()
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        now = now_iso()
        c.execute("""
            INSERT INTO users(user_id, username, full_name, join_date, last_active)
            VALUES(?, ?, ?, ?, ?)
        """, (user_id, username, full_name, now, now))
    else:
        c.execute("""
            UPDATE users SET last_active=?, username=?, full_name=?
            WHERE user_id=?
        """, (now_iso(), username, full_name, user_id))
    
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    result = c.fetchone() is not None
    conn.close()
    return result or user_id == OWNER_ID

def is_banned(user_id: int) -> bool:
    """Check if user is banned"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,))
    result = c.fetchone() is not None
    conn.close()
    return result

def is_premium(user_id: int) -> bool:
    """Check if user has active premium"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT expiry FROM subscriptions WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return False
    
    try:
        expiry = datetime.fromisoformat(row[0])
        return expiry > datetime.now()
    except:
        return False

def get_user_stats(user_id: int) -> dict:
    """Get user statistics"""
    conn = db_connect()
    c = conn.cursor()
    
    # Get user info
    c.execute("SELECT join_date, last_active, active_project_id FROM users WHERE user_id=?", (user_id,))
    user_row = c.fetchone()
    
    # Count projects
    c.execute("SELECT COUNT(*) FROM projects WHERE user_id=?", (user_id,))
    project_count = c.fetchone()[0]
    
    # Count files
    c.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (user_id,))
    file_count = c.fetchone()[0]
    
    conn.close()
    
    return {
        'join_date': user_row[0] if user_row else None,
        'last_active': user_row[1] if user_row else None,
        'active_project_id': user_row[2] if user_row else None,
        'project_count': project_count,
        'file_count': file_count,
        'is_premium': is_premium(user_id),
        'is_admin': is_admin(user_id),
        'is_banned': is_banned(user_id)
    }

# =============================================================================
# PROJECT OPERATIONS
# =============================================================================

def create_project(user_id: int, name: str, description: str = "") -> int:
    """Create new project"""
    conn = db_connect()
    c = conn.cursor()
    now = now_iso()
    
    c.execute("""
        INSERT INTO projects(user_id, name, entry_file, language, auto_restart, created_at, updated_at, description)
        VALUES(?, ?, '', '', 0, ?, ?, ?)
    """, (user_id, name.strip(), now, now, description))
    
    project_id = c.lastrowid
    
    # Set as active if user has no active project
    c.execute("SELECT active_project_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row and row[0] is None:
        c.execute("UPDATE users SET active_project_id=? WHERE user_id=?", (project_id, user_id))
    
    conn.commit()
    conn.close()
    return project_id

def get_project(user_id: int, project_id: int) -> Optional[Tuple]:
    """Get project details"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT project_id, name, entry_file, language, auto_restart, description, created_at
        FROM projects WHERE user_id=? AND project_id=?
    """, (user_id, project_id))
    row = c.fetchone()
    conn.close()
    return row

def list_projects(user_id: int) -> List[Tuple]:
    """List all user projects"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT project_id, name, entry_file, language, auto_restart, description
        FROM projects WHERE user_id=?
        ORDER BY project_id DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_project_settings(user_id: int, project_id: int, entry_file: str, language: str, auto_restart: int):
    """Update project settings"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        UPDATE projects SET entry_file=?, language=?, auto_restart=?, updated_at=?
        WHERE user_id=? AND project_id=?
    """, (entry_file, language, auto_restart, now_iso(), user_id, project_id))
    conn.commit()
    conn.close()

def delete_project(user_id: int, project_id: int):
    """Delete project and all related data"""
    conn = db_connect()
    c = conn.cursor()
    
    c.execute("DELETE FROM favorites WHERE user_id=? AND project_id=?", (user_id, project_id))
    c.execute("DELETE FROM files WHERE user_id=? AND project_id=?", (user_id, project_id))
    c.execute("DELETE FROM env_vars WHERE user_id=? AND project_id=?", (user_id, project_id))
    c.execute("DELETE FROM installed_packages WHERE user_id=? AND project_id=?", (user_id, project_id))
    c.execute("DELETE FROM projects WHERE user_id=? AND project_id=?", (user_id, project_id))
    
    # Clear active project if it was this one
    c.execute("SELECT active_project_id FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row and row[0] == project_id:
        c.execute("UPDATE users SET active_project_id=NULL WHERE user_id=?", (user_id,))
    
    conn.commit()
    conn.close()

# =============================================================================
# FILE OPERATIONS
# =============================================================================

def add_file(user_id: int, project_id: int, file_name: str, file_type: str, file_size: int):
    """Add file to database"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO files(user_id, project_id, file_name, file_type, file_size, upload_date)
        VALUES(?, ?, ?, ?, ?, ?)
    """, (user_id, project_id, file_name, file_type, file_size, now_iso()))
    conn.commit()
    conn.close()

def remove_file(user_id: int, project_id: int, file_name: str):
    """Remove file from database"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("DELETE FROM files WHERE user_id=? AND project_id=? AND file_name=?", 
              (user_id, project_id, file_name))
    c.execute("DELETE FROM favorites WHERE user_id=? AND project_id=? AND file_name=?",
              (user_id, project_id, file_name))
    conn.commit()
    conn.close()

def list_files(user_id: int, project_id: int) -> List[Tuple]:
    """List all files in project"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT file_name, file_type, file_size, upload_date
        FROM files WHERE user_id=? AND project_id=?
        ORDER BY upload_date DESC
    """, (user_id, project_id))
    rows = c.fetchall()
    conn.close()
    return rows

def count_user_files(user_id: int) -> int:
    """Count total files for user"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# =============================================================================
# STATISTICS
# =============================================================================

def stat_increment(stat_name: str, amount: int = 1):
    """Increment a statistic"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("UPDATE bot_stats SET stat_value = stat_value + ? WHERE stat_name=?", 
              (amount, stat_name))
    conn.commit()
    conn.close()

def stat_get(stat_name: str) -> int:
    """Get statistic value"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT stat_value FROM bot_stats WHERE stat_name=?", (stat_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_all_stats() -> dict:
    """Get all statistics"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT stat_name, stat_value FROM bot_stats")
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}