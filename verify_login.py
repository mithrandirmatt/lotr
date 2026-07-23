import sqlite3
import bcrypt

print("=" * 60)
print("ADMIN LOGIN VERIFICATION")
print("=" * 60)

conn = sqlite3.connect('lotr.db')
cursor = conn.cursor()

# Check if admin user exists with correct credentials
expected_email = "lotradmin@example.com"
password_hash = bcrypt.hashpw(b'yourmommalooksfunny', bcrypt.gensalt()).decode('utf-8')

print(f"\n🔍 Checking for admin account...")
cursor.execute("""
    SELECT email, is_admin
    FROM users
    WHERE email = ? AND password = ?
""", (expected_email, password_hash))

result = cursor.fetchone()
if result:
    print("✅ Admin account found with correct credentials!")
    print(f"   Email: {result[0]}")
    print(f"   Is admin: {bool(result[1])}")
else:
    print("❌ No matching admin record found.")

# Show all users for debugging
print("\n📋 All registered accounts:")
cursor.execute("SELECT id, email, unique_name, is_admin FROM users")
rows = cursor.fetchall()
for row in rows:
    status = "✅ ADMIN" if row[3] else ""
    print(f"  ID:{row[0]:2} | {row[1]:35} | {row[2]:15} | is_admin={bool(row[3])} {status}")

print("\n" + "=" * 60)
print("LOGIN INSTRUCTIONS")
print("=" * 60)
print("""
To login to the admin panel, use these exact values:

Email:    lotradmin@example.com
Password: yourmommalooksfunny

The backend expects email-based authentication for ALL users, including admins.
Any user with is_admin=True can log in using their registered email and password.
""")
