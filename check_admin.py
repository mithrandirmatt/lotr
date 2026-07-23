import sqlite3
conn = sqlite3.connect('lotr.db')
cursor = conn.execute("SELECT id, email, unique_name, is_admin FROM users WHERE username='lotradmin'")
print(cursor.fetchone())
