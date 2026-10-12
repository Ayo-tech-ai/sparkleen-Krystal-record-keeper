import os
import psycopg
from psycopg.rows import dict_row

# Kept for receipt PDF storage location (receipts are ephemeral but
# always regenerated on demand from the DB, so that's fine).
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Supabase Postgres connection string, e.g.:
#   postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
# On hosts without IPv6 (like Render free tier), use the Supavisor
# transaction pooler URI instead (port 6543) from the Supabase dashboard.
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")


def get_connection():
    """Opens a fresh connection to Supabase Postgres.

    A new connection per call is intentional: Render containers restart
    and sleep, and the Supavisor pooler handles short-lived connections
    efficiently. Keepalives stop idle connections being dropped.
    """
    if not SUPABASE_DB_URL:
        raise RuntimeError(
            "SUPABASE_DB_URL environment variable is not set. "
            "Add it in Render's Environment settings (and Streamlit secrets)."
        )
    return psycopg.connect(
        SUPABASE_DB_URL,
        row_factory=dict_row,
        keepalives=1,
        keepalives_idle=60,
        keepalives_interval=30,
        keepalives_count=5,
    )


def init_db():
    """Creates the dropoff_records table if it doesn't already exist."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dropoff_records (
                    id BIGSERIAL PRIMARY KEY,
                    invoice_number TEXT UNIQUE NOT NULL,
                    customer_name TEXT NOT NULL,
                    items TEXT NOT NULL,
                    total_units INTEGER NOT NULL,
                    total_amount DOUBLE PRECISION NOT NULL,
                    payment_status TEXT NOT NULL,
                    amount_paid DOUBLE PRECISION NOT NULL,
                    balance DOUBLE PRECISION NOT NULL,
                    service_type TEXT,
                    dropoff_date DATE NOT NULL,
                    collection_date DATE,
                    late_fee_applied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
