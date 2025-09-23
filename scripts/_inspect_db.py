import sqlite3
conn=sqlite3.connect('data/app.db')
cur=conn.cursor()
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='crawlers'")
print(cur.fetchone())
cur.execute("PRAGMA table_info(crawlers)")
print([tuple(r) for r in cur.fetchall()])
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
print('alembic_version exists:', bool(cur.fetchone()))
