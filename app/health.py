from __future__ import annotations

import os
import sqlite3

path = os.getenv("DATABASE_PATH", "/app/data/trends.db")
with sqlite3.connect(path) as conn:
    conn.execute("select 1")
print("ok")
