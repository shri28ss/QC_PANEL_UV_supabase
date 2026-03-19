import psycopg2
import psycopg2.extras
import re
from config import SUPABASE_DB_URL


def get_connection():
    """Connect to Supabase PostgreSQL database."""
    if not SUPABASE_DB_URL:
        raise Exception("SUPABASE_DB_URL is not set in your .env file.")
    if "[YOUR-PASSWORD]" in SUPABASE_DB_URL:
        raise Exception("Please replace [YOUR-PASSWORD] in SUPABASE_DB_URL with your actual Supabase password.")
    return psycopg2.connect(SUPABASE_DB_URL)


def get_cursor(conn):
    """Returns a RealDictCursor for PostgreSQL (returns rows as dicts)."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def execute_insert(conn, cursor, query, params):
    """
    Executes an INSERT query and returns the last inserted ID.
    Automatically appends RETURNING <id_col> for PostgreSQL.
    """
    if "RETURNING" not in query.upper():
        match = re.search(r"INSERT INTO (\w+)", query, re.IGNORECASE)
        if match:
            table = match.group(1)
            id_col = table.rstrip('s') + "_id"
            query = query.rstrip().rstrip(';') + f" RETURNING {id_col}"

    cursor.execute(query, params)
    result = cursor.fetchone()

    if result:
        if isinstance(result, dict) or hasattr(result, 'keys'):
            return list(result.values())[0]
        return result[0]
    return None