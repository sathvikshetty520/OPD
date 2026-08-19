"""
Seed a staff user. Run manually:
    python create_user.py <username> <password> "<Display Name>"
"""

import sys
import db
import auth

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_user.py <username> <password> \"<Display Name>\"")
        sys.exit(1)

    username, password, display_name = sys.argv[1], sys.argv[2], sys.argv[3]
    db.init_db()
    db.create_user(username, auth.hash_password(password), display_name)
    print(f"Created user: {username}")