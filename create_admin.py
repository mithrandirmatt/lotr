import sqlite3
import bcrypt
conn = sqlite3.connect('lotr.db')
cursor = conn.cursor()

# Create users table if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        unique_name TEXT UNIQUE NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        is_moderator BOOLEAN DEFAULT 0
    )
''')

# Create admin user if not exists
admin_email = 'lotradmin@example.com'
admin_password_hash = bcrypt.hashpw(b'yourmommalooksfunny', bcrypt.gensalt()).decode('utf-8')

cursor.execute('''
    INSERT OR IGNORE INTO users (email, password, unique_name, is_admin)
    VALUES (?, ?, ?, 1)
''', (admin_email, admin_password_hash, 'lotradmin'))

conn.commit()
print("Admin account created/verified!")
print(f"Email: {admin_email}")
print(f"Password hash length: {len(admin_password_hash)}")
