import sqlite3
conn=sqlite3.connect('data/app.db')
cur=conn.cursor()
cur.execute("PRAGMA table_info(api_keys)")
print('api_keys columns:', [c[1] for c in cur.fetchall()])
cur.execute("PRAGMA table_info(crawlers)")
print('crawlers columns:', [c[1] for c in cur.fetchall()])
