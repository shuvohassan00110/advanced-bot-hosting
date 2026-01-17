# -*- coding: utf-8 -*-
"""
Powerful admin panel features
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple
from database import db_connect, now_iso

# =============================================================================
# ADMIN MANAGEMENT
# =============================================================================

def add_admin(user_id: int) -> bool:
    """Add user as admin"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (user_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def remove_admin(user_id: int) -> bool:
    """Remove admin privileges"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def list_admins() -> List[int]:
    """Get list of all admins"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in c.fetchall()]
    conn.close()
    return admins

# =============================================================================
# BAN MANAGEMENT
# =============================================================================

def ban_user(user_id: int, reason: str, banned_by: int) -> bool:
    """Ban a user"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO banned_users(user_id, banned_date, reason, banned_by)
            VALUES(?, ?, ?, ?)
        """, (user_id, now_iso(), reason, banned_by))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def unban_user(user_id: int) -> bool:
    """Unban a user"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def list_banned() -> List[Tuple]:
    """Get list of banned users"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id, banned_date, reason FROM banned_users")
    banned = c.fetchall()
    conn.close()
    return banned

# =============================================================================
# PREMIUM MANAGEMENT
# =============================================================================

def add_premium(user_id: int, days: int, granted_by: int) -> bool:
    """Grant premium subscription"""
    try:
        expiry = (datetime.now() + timedelta(days=days)).isoformat(timespec='seconds')
        conn = db_connect()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO subscriptions(user_id, expiry, granted_by, granted_at)
            VALUES(?, ?, ?, ?)
        """, (user_id, expiry, granted_by, now_iso()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def remove_premium(user_id: int) -> bool:
    """Remove premium subscription"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def list_premium() -> List[Tuple]:
    """Get list of premium users"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id, expiry FROM subscriptions")
    premium = c.fetchall()
    conn.close()
    return premium

# =============================================================================
# USER ANALYTICS
# =============================================================================

def get_user_list(limit: int = 50) -> List[Tuple]:
    """Get list of users"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, full_name, join_date, last_active
        FROM users
        ORDER BY last_active DESC
        LIMIT ?
    """, (limit,))
    users = c.fetchall()
    conn.close()
    return users

def get_user_count() -> int:
    """Get total user count"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_active_users(hours: int = 24) -> int:
    """Get count of users active in last N hours"""
    threshold = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (threshold,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_bot_analytics() -> dict:
    """Get comprehensive bot analytics"""
    conn = db_connect()
    c = conn.cursor()
    
    # Total users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    # Active users (24h)
    threshold_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    c.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (threshold_24h,))
    active_24h = c.fetchone()[0]
    
    # Total projects
    c.execute("SELECT COUNT(*) FROM projects")
    total_projects = c.fetchone()[0]
    
    # Total files
    c.execute("SELECT COUNT(*) FROM files")
    total_files = c.fetchone()[0]
    
    # Premium users
    now = datetime.now().isoformat()
    c.execute("SELECT COUNT(*) FROM subscriptions WHERE expiry > ?", (now,))
    premium_count = c.fetchone()[0]
    
    # Banned users
    c.execute("SELECT COUNT(*) FROM banned_users")
    banned_count = c.fetchone()[0]
    
    # Admins
    c.execute("SELECT COUNT(*) FROM admins")
    admin_count = c.fetchone()[0]
    
    # Statistics
    c.execute("SELECT stat_name, stat_value FROM bot_stats")
    stats = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    return {
        'total_users': total_users,
        'active_24h': active_24h,
        'total_projects': total_projects,
        'total_files': total_files,
        'premium_users': premium_count,
        'banned_users': banned_count,
        'admins': admin_count,
        'stats': stats
    }

def search_user(query: str) -> List[Tuple]:
    """Search users by ID, username or name"""
    conn = db_connect()
    c = conn.cursor()
    
    # Try as ID first
    try:
        user_id = int(query)
        c.execute("""
            SELECT user_id, username, full_name, join_date, last_active
            FROM users WHERE user_id=?
        """, (user_id,))
        result = c.fetchall()
        conn.close()
        return result
    except ValueError:
        pass
    
    # Search by username/name
    query_like = f"%{query}%"
    c.execute("""
        SELECT user_id, username, full_name, join_date, last_active
        FROM users
        WHERE username LIKE ? OR full_name LIKE ?
        LIMIT 20
    """, (query_like, query_like))
    users = c.fetchall()
    conn.close()
    return users

# =============================================================================
# BROADCAST
# =============================================================================

async def broadcast_message(bot, message_text: str, target: str = "all", parse_mode: str = "HTML"):
    """
    Broadcast message to users
    
    Args:
        bot: Bot instance
        message_text: Message to send
        target: "all", "premium", or "active_24h"
        parse_mode: Parse mode for message
    
    Returns:
        (success_count, fail_count)
    """
    conn = db_connect()
    c = conn.cursor()
    
    if target == "all":
        c.execute("SELECT user_id FROM users")
    elif target == "premium":
        now = datetime.now().isoformat()
        c.execute("""
            SELECT u.user_id FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            WHERE s.expiry > ?
        """, (now,))
    elif target == "active_24h":
        threshold = (datetime.now() - timedelta(hours=24)).isoformat()
        c.execute("SELECT user_id FROM users WHERE last_active > ?", (threshold,))
    else:
        conn.close()
        return 0, 0
    
    user_ids = [row[0] for row in c.fetchall()]
    conn.close()
    
    success = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(
                user_id,
                message_text,
                parse_mode=parse_mode
            )
            success += 1
        except Exception:
            failed += 1
    
    return success, failed

# =============================================================================
# PROJECT MANAGEMENT (ADMIN)
# =============================================================================

def get_all_projects(limit: int = 50) -> List[Tuple]:
    """Get all projects (admin view)"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT p.project_id, p.user_id, p.name, p.entry_file, p.language, p.created_at
        FROM projects p
        ORDER BY p.created_at DESC
        LIMIT ?
    """, (limit,))
    projects = c.fetchall()
    conn.close()
    return projects

def admin_delete_project(user_id: int, project_id: int) -> bool:
    """Delete any project (admin only)"""
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE user_id=? AND project_id=?", (user_id, project_id))
        c.execute("DELETE FROM favorites WHERE user_id=? AND project_id=?", (user_id, project_id))
        c.execute("DELETE FROM env_vars WHERE user_id=? AND project_id=?", (user_id, project_id))
        c.execute("DELETE FROM projects WHERE user_id=? AND project_id=?", (user_id, project_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False