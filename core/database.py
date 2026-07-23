import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_NAME = os.path.join(DATA_DIR, "sparkleen_krystal.db")


def init_db():
    """Creates the dropoff_records table if it doesn't already exist."""
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dropoff_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        items TEXT NOT NULL,
        total_units INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        payment_status TEXT NOT NULL,
        amount_paid REAL NOT NULL,
        balance REAL NOT NULL,
        service_type TEXT,
        dropoff_date DATE NOT NULL,
        collection_date DATE,
        late_fee_applied BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    connection.commit()
    connection.close()


def get_connection():
    return sqlite3.connect(DATABASE_NAME)
