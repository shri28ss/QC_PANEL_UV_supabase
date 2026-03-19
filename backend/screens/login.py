import streamlit as st
from db.connection import get_connection, get_cursor
import hashlib
 
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
 
def show_login():
    st.title("LedgerAI Login")
 
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
 
    if st.button("Login"):
 
        conn = get_connection()
        cursor = get_cursor(conn)
 
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND status='ACTIVE'",
            (email,)
        )
 
        user = cursor.fetchone()
        cursor.close()
        conn.close()
 
        if not user:
            st.error("User not found")
            return
 
        if user["password_hash"] != hash_password(password):
            st.error("Invalid password")
            return
 
        st.session_state.user_id = user["user_id"]
        st.session_state.screen = "upload"
        st.rerun()
 
    if st.button("Register"):
        st.session_state.screen = "register"
        st.rerun()