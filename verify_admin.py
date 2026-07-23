import sqlite3
import bcrypt
import json

print("=" * 60)
print("ADMIN ACCOUNT VERIFICATION TOOL")
print("=" * 60)

conn = sqlite3.connect('lotr.db')
cursor = conn.cursor()

# Check if users table exists and has data
try:
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
    admin_count = cursor.fetchone()[0]
    print(f"\n📊 Admin accounts in database: {admin_count}")
except Exception as e:
    print(f"❌ Error checking admins: {e}")

# Show all user records
try:
    cursor.execute("SELECT id, email, unique_name, is_admin FROM users")
    rows = cursor.fetchall()
    print("\n📋 All registered accounts:")
    for row in rows:
        status = "✅ ADMIN" if row[3] else ""
        print(f"  ID:{row[0]:2} | {row[1]:35} | {row[2]:15} | is_admin={bool(row[3])} {status}")
except Exception as e:
    print(f"❌ Error reading users: {e}")

# Verify password hash for expected admin email
expected_email = "lotradmin@example.com"
password_hash = bcrypt.hashpw(b'yourmommalooksfunny', bcrypt.gensalt()).decode('utf-8')
print(f"\n🔐 Expected password hash for 'yourmommalooksfunny':")
print(f"   {password_hash[:50]}... (length: {len(password_hash)})")

# Check if expected admin exists with correct hash
try:
    cursor.execute("""
        SELECT email, is_admin
        FROM users
        WHERE email = ? AND password = ?
    """, (expected_email, password_hash))

    result = cursor.fetchone()
    if result:
        print(f"\n✅ SUCCESS: Admin account found with correct credentials!")
        print(f"   Email: {result[0]}")
        print(f"   Is admin: {bool(result[1])}")
    else:
        print(f"\n❌ NOT FOUND: No matching admin record for '{expected_email}'")

except Exception as e:
    print(f"❌ Error verifying credentials: {e}")

print("\n" + "=" * 60)
print("REMINDER:")
print("=" * 60)
print("""
Login with these exact values in the admin panel:
- Email: lotradmin@example.com
- Password: yourmommalooksfunny

If login still fails, check that FastAPI server is running at
http://localhost:8000 and CORS is enabled.
""")
