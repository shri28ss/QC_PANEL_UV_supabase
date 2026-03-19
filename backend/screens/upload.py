import streamlit as st
import tempfile
from db.connection import get_connection, get_cursor, execute_insert
from services.processing_engine import process_document
 
def show_upload():
 
    st.title("Upload Financial Statement")
 
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    password = st.text_input("PDF Password (if any)", type="password")
 
    if uploaded_file and st.button("Start Processing"):
 
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            file_path = tmp.name
 
        conn = get_connection()
        cursor = get_cursor(conn)
 
        query = """
            INSERT INTO documents
            (user_id, file_name, file_path, is_password_protected, status)
            VALUES (%s, %s, %s, %s, 'UPLOADED')
        """
        document_id = execute_insert(conn, cursor, query, (
            st.session_state.user_id,
            uploaded_file.name,
            file_path,
            bool(password)
        ))
 
        if password:
            cursor.execute("""
                INSERT INTO document_password (document_id, encrypted_password)
                VALUES (%s, %s)
            """, (document_id, password))
 
        conn.commit()
        cursor.close()
        conn.close()
 
        # Start processing
        process_document(document_id)
 
        st.session_state.current_document = document_id
        st.session_state.screen = "processing"
        st.rerun()
 