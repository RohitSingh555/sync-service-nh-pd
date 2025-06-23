from datetime import datetime, timezone
import sqlite3
import logging

# Initialize SQLite database
DB_PATH = "sync_service.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS mappings (
    pd_id TEXT PRIMARY KEY,
    nh_id TEXT
)
""")
conn.commit()

def set_last_poll(updated_at_string: str):
    try:
        cursor.execute("REPLACE INTO state (key, value) VALUES (?, ?)", ('last_nethunt_poll', updated_at_string))
        conn.commit()
        logging.info(f"Successfully updated last_nethunt_poll to {updated_at_string}")
    except Exception as e:
        logging.error(f"Failed to update last_nethunt_poll: {e}")

def get_last_poll():
    try:
        cursor.execute("SELECT value FROM state WHERE key = 'last_nethunt_poll'")
        result = cursor.fetchone()
        if result:
            logging.info(f"Retrieved last_nethunt_poll: {result[0]}")
            return result[0]
        logging.info("No last_nethunt_poll found, returning None")
        return None
    except Exception as e:
        logging.error(f"Failed to retrieve last_nethunt_poll: {e}")
        return None

def map_pd_to_nh(pd_id, nh_id):
    cursor.execute("REPLACE INTO mappings (pd_id, nh_id) VALUES (?, ?)", (pd_id, nh_id))
    conn.commit()

def get_nh_by_pd(pd_id):
    cursor.execute("SELECT nh_id FROM mappings WHERE pd_id = ?", (pd_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def map_nh_to_pd(nh_id, pd_id):
    cursor.execute("REPLACE INTO mappings (pd_id, nh_id) VALUES (?, ?)", (pd_id, nh_id))
    conn.commit()

def get_pd_by_nh(nh_id):
    cursor.execute("SELECT pd_id FROM mappings WHERE nh_id = ?", (nh_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_last_task_created_at():
    cursor.execute("SELECT value FROM state WHERE key = 'last_task_created_at'")
    result = cursor.fetchone()
    if result:
        return result[0]
    return None

def set_last_task_created_at(created_at_string: str):
    cursor.execute("REPLACE INTO state (key, value) VALUES (?, ?)", ('last_task_created_at', created_at_string))
    conn.commit()
