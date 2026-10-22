
import sqlite3

DATABASE = "helpdesk.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_db_connection()

    # Tickets table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            email TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT DEFAULT 'Unassigned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate existing tickets table safely
    ticket_columns = connection.execute(
        "PRAGMA table_info(tickets)"
    ).fetchall()

    ticket_column_names = [column["name"] for column in ticket_columns]

    if "assigned_to" not in ticket_column_names:
        connection.execute("""
            ALTER TABLE tickets
            ADD COLUMN assigned_to TEXT DEFAULT 'Unassigned'
        """)

    # Users table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add role to existing users table if needed
    user_columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    user_column_names = [column["name"] for column in user_columns]

    if "role" not in user_column_names:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN role TEXT NOT NULL DEFAULT 'technician'
        """)

    connection.commit()
    connection.close()
