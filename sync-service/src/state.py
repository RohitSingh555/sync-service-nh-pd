import sqlite3

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

def get_last_poll():
    cursor.execute("SELECT value FROM state WHERE key = 'last_nethunt_poll'")
    result = cursor.fetchone()
    return int(result[0]) if result else None

def set_last_poll(ts):
    cursor.execute("REPLACE INTO state (key, value) VALUES ('last_nethunt_poll', ?)", (ts,))
    conn.commit()

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
