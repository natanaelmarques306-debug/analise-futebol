import json
import sqlite3
import threading
import time
from pathlib import Path


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.RLock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT, fetched REAL);
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS quota (day TEXT PRIMARY KEY, count INTEGER NOT NULL);
        """)
        self.db.commit()

    def cache_get(self, key: str, ttl: float):
        with self.lock:
            row = self.db.execute("SELECT payload, fetched FROM cache WHERE key=?", (key,)).fetchone()
            if row and time.time() - row[1] < ttl:
                return json.loads(row[0])
        return None

    def cache_set(self, key: str, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, json.dumps(value), time.time()))

    def get(self, key: str, default=None):
        with self.lock:
            row = self.db.execute("SELECT payload FROM state WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key: str, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value)))

    def reserve_request(self, day: str, limit: int) -> bool:
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO quota VALUES (?,0)", (day,))
            count = self.db.execute("SELECT count FROM quota WHERE day=?", (day,)).fetchone()[0]
            if count >= limit:
                return False
            self.db.execute("UPDATE quota SET count=count+1 WHERE day=?", (day,))
            return True

    def quota(self, day: str) -> int:
        with self.lock:
            row = self.db.execute("SELECT count FROM quota WHERE day=?", (day,)).fetchone()
            return row[0] if row else 0

    def close(self):
        with self.lock:
            self.db.close()
