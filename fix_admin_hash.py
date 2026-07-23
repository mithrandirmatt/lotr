import sqlite3
import bcrypt

print("=" * 60)
print("FIXING ADMIN PASSWORD HASH")
print("=" * 60)

conn = sqlite3.connect('lotr.db')
cursor = conn.cursor()

# Get current password hash for admin
cursor.execute("""
    SELECT email, password
    FROM users
    WHERE email = 'lotradmin@example.com' AND is_admin = 1
""")

current_row = cursor.fetchone()
if current_row:
    print(f"Current stored hash (first 50 chars): {current_row[1][:50]}...")

# Generate new correct hash for "yourmommalooksfunny"
new_hash = bcrypt.hashpw(b'yourmommalooksfunny', bcrypt.gensalt()).decode('utf-8')
print(f"\nNew correct hash (first 50 chars): {new_hash[:50]}...")

# Update the password hash
cursor.execute("""
    UPDATE users
    SET password = ?
    WHERE email = 'lotradmin@example.com' AND is_admin = 1
""", (new_hash,))

conn.commit()
print("\n✅ Password hash updated successfully!")

# Verify it works now
import bcrypt as bc
test_password = b'yourmommalooksfunny'
stored_hash_bytes = new_hash.encode('utf-8')
is_valid = bc.checkpw(test_password, stored_hash_bytes)
print(f"Verification: 'yourmommalooksfunny' matches hash? {is_valid}")
