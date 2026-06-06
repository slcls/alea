import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "spv_state.db"

def init_db():
    DATA_DIR.mkdir(exist_ok=True)

    # Local SPV state connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Write-ahead logging
    cursor.execute("PRAGMA journal_mode=WAL;")
    conn.commit()

if __name__ == "__main__":
    db_conn = init_db()
    print(f"[ LOG ] btc_spv.py: SPV state database initialized at {DB_PATH}")
    print("[ LOG ] btc_spv.py: WAL mode enabled.")