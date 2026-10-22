
import getpass
import sqlite3

from werkzeug.security import generate_password_hash
from database import create_database, get_db_connection

create_database()

username = input("Choose admin username: ").strip()

if not username:
    raise SystemExit("Username cannot be empty.")

password = getpass.getpass("Choose admin password: ")
confirm = getpass.getpass("Confirm password: ")

if len(password) < 12:
    raise SystemExit("Use a password with at least 12 characters.")

if password != confirm:
    raise SystemExit("Passwords do not match.")

connection = get_db_connection()

try:
    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256"
    )

    connection.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, "admin")
    )

    connection.commit()
    print("Admin account created successfully.")

except sqlite3.IntegrityError:
    print("That username already exists.")

finally:
    connection.close()
