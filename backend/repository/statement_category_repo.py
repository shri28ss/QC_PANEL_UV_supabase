import json
from db.connection import get_connection, get_cursor, execute_insert

# ================================= Fetch All Active Categories =================================
def get_active_statement_categories():
    conn = get_connection()
    cursor = get_cursor(conn)

    query = """
        SELECT *
        FROM statement_categories
        WHERE status = 'ACTIVE'
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    for row in rows:
        row["statement_identifier"] = json.loads(row["statement_identifier"])
        row["extraction_logic"] = json.loads(row["extraction_logic"])

    return rows


# ================================= Insert New Category ================================
def insert_statement_category(
    statement_type,
    format_name,
    institution_name,
    ifsc_code,
    identifier_json,
    extraction_logic,
    threshold=65.00
):
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT statement_id
        FROM statement_categories
        WHERE format_name = %s
        """, (format_name,))

    existing = cursor.fetchone()
    cursor.fetchall()   # ← ADD THIS LINE

    if existing:
        cursor.close()
        conn.close()
        return existing["statement_id"]
    query = """
        INSERT INTO statement_categories
        (
            statement_type,
            format_name,
            institution_name,
            ifsc_code,
            statement_identifier,
            extraction_logic,
            match_threshold,
            logic_version,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s,%s, 1, 'UNDER_REVIEW')
    """

    inserted_id = execute_insert(
        conn,
        cursor,
        query,
        (
            statement_type,
            format_name,
            institution_name,
            ifsc_code,
            json.dumps(identifier_json),
            extraction_logic,
            threshold
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

    return inserted_id

#============================== Fetch All Under Review Categories ==============================
def get_under_review_formats():
    conn = get_connection()
    cursor = get_cursor(conn)

    query = """
        SELECT *
        FROM statement_categories
        WHERE status = 'UNDER_REVIEW'
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    for row in rows:
        row["statement_identifier"] = json.loads(row["statement_identifier"])
        if row.get("extraction_logic") is None:
            row["extraction_logic"] = ""

    return rows

# ============================== Activate Category After Validation ==============================
def activate_statement_category(statement_id):
    conn = get_connection()
    cursor = get_cursor(conn)

    query = """
        UPDATE statement_categories
        SET status = 'ACTIVE'
        WHERE statement_id = %s
    """

    cursor.execute(query, (statement_id,))
    conn.commit()

    cursor.close()
    conn.close()

def get_statement_by_id(statement_id):
    conn = get_connection()
    cursor = get_cursor(conn)

    query = """
        SELECT * FROM statement_categories
        WHERE statement_id = %s
    """

    cursor.execute(query, (statement_id,))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result


def update_extraction_logic(statement_id, new_logic):
    conn = get_connection()
    cursor = get_cursor(conn)

    query = """
        UPDATE statement_categories
        SET extraction_logic = %s
        WHERE statement_id = %s
    """

    cursor.execute(query, (new_logic, statement_id))
    conn.commit()
    cursor.close()
    conn.close()
