import sqlite3

# Initialize SQLite database
DB_PATH = "sync_service.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# ---------------------
# Create necessary tables
# ---------------------

# Polling state (e.g., last_nethunt_poll timestamp)
cursor.execute("""
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# Pipedrive ↔ NetHunt record ID mappings
cursor.execute("""
CREATE TABLE IF NOT EXISTS mappings (
    pd_id TEXT PRIMARY KEY,
    nh_id TEXT
)
""")

# NetHunt folder ID ↔ record ID mappings
cursor.execute("""
CREATE TABLE IF NOT EXISTS folder_record_mappings (
    folder_id TEXT PRIMARY KEY,
    record_id TEXT
)
""")

conn.commit()

# ---------------------
# State management
# ---------------------
def get_last_poll():
    cursor.execute("SELECT value FROM state WHERE key = 'last_nethunt_poll'")
    result = cursor.fetchone()
    return int(result[0]) if result else None

def set_last_poll(ts):
    cursor.execute("REPLACE INTO state (key, value) VALUES ('last_nethunt_poll', ?)", (ts,))
    conn.commit()

# ---------------------
# Pipedrive ↔ NetHunt mappings
# ---------------------
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

# ---------------------
# NetHunt folder ↔ record mappings
# ---------------------
def map_folder_to_record(folder_id, record_id):
    cursor.execute("REPLACE INTO folder_record_mappings (folder_id, record_id) VALUES (?, ?)", (folder_id, record_id))
    conn.commit()

def get_record_by_folder(folder_id):
    cursor.execute("SELECT record_id FROM folder_record_mappings WHERE folder_id = ?", (folder_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_folder_by_record(record_id):
    cursor.execute("SELECT folder_id FROM folder_record_mappings WHERE record_id = ?", (record_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_all_nethunt_folder_records():
    cursor.execute("SELECT folder_id, record_id FROM folder_record_mappings")
    results = cursor.fetchall()
    return [{"folder_id": row[0], "record_id": row[1]} for row in results]

# ---------------------
# Sample folder→record mapping insert
# ---------------------
if __name__ == "__main__":
    folder_id = "55eb66f5d38ea77a03e23d3f0f3dd31b891739d1"
    record_id = "6cff18ff6ad02610ded066fab268f76d7d6431c9"

    map_folder_to_record(folder_id, record_id)
    print(f"✅ Saved mapping: folder_id={folder_id} → record_id={get_record_by_folder(folder_id)}")

